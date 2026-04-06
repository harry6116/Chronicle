import gc
import html
import io
import os
import tempfile
import hashlib
import re

from chronicle_app.services.processing_runtime import CLAUDE_FILES_API_BETA
from chronicle_app.services.runtime_policies import normalize_model_name
from chronicle_app.services.runtime_policies import wait_for_gemini_upload_ready


OPENAI_PDF_BASE64_FALLBACK_REASON = "OpenAI PDF direct upload is not available in Chronicle yet. Falling back to the PDF text layer."
CLAUDE_PDF_FILES_API_FALLBACK_REASON = "Claude Files API is unavailable for this PDF slice. Falling back to inline PDF mode."


def process_pdf(
    client,
    path,
    out,
    fmt,
    prompt,
    model,
    f_obj,
    mem,
    log_cb,
    *,
    confidence_cb=None,
    pause_cb=None,
    page_progress_cb=None,
    page_scope="",
    doc_profile="standard",
    auto_escalation_model=None,
    script_dir,
    pdf_reader_cls,
    pdf_writer_cls,
    parse_pdf_page_scope_spec_fn,
    normalize_pdf_page_scope_text_fn,
    get_pdf_chunk_pages_fn,
    sha256_file_fn,
    sha256_text_fn,
    build_payload_fn,
    build_request_cache_key_fn,
    stream_with_cache_fn,
    generate_retry_fn,
    split_text_for_fail_safe_fn,
    remove_fn=os.remove,
    exists_fn=os.path.exists,
    tempdir_fn=tempfile.gettempdir,
    mkstemp_fn=tempfile.mkstemp,
    wait_for_gemini_upload_ready_fn=wait_for_gemini_upload_ready,
):
    reader = pdf_reader_cls(path)
    total_document_pages = len(reader.pages)
    selected_page_indices = parse_pdf_page_scope_spec_fn(page_scope, total_document_pages)
    total = len(selected_page_indices)
    file_size_mb = None
    try:
        file_size_mb = os.path.getsize(path) / (1024 * 1024)
    except OSError:
        file_size_mb = None
    curr = 0
    pages_done = 0
    is_acad = "ACADEMIC" in prompt
    penalties = [0.0 for _ in range(total)]
    methods = ["vision" for _ in range(total)]
    reported = [False for _ in range(total)]
    escalated_pages = set()
    normalized_scope = normalize_pdf_page_scope_text_fn(page_scope)
    text_fast_path_logged = False
    if normalized_scope and total < total_document_pages:
        log_cb(f"[Scope] Reading PDF pages {normalized_scope} ({total} selected of {total_document_pages}).")
    if "HISTORICAL NEWSPAPER RULES" in prompt and file_size_mb is not None and total_document_pages > 0:
        avg_page_mb = file_size_mb / total_document_pages
        if avg_page_mb >= 0.9:
            log_cb(
                "[PDF Heuristic] Dense scanned newspaper detected "
                f"({file_size_mb:.1f} MB total, about {avg_page_mb:.2f} MB/page). "
                "Using smaller PDF slices to avoid long upload stalls."
            )

    def build_pdf_slice_bytes(start, end):
        writer = pdf_writer_cls()
        for idx in range(start, end):
            writer.add_page(reader.pages[selected_page_indices[idx]])
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    def get_page_text_metrics(page_idx):
        try:
            text = reader.pages[selected_page_indices[page_idx]].extract_text() or ""
        except Exception:
            text = ""
        compact = " ".join(text.split())
        alpha_chars = sum(1 for ch in compact if ch.isalpha())
        digit_chars = sum(1 for ch in compact if ch.isdigit())
        line_count = len([line for line in text.splitlines() if line.strip()])
        return {
            "text": text,
            "compact": compact,
            "chars": len(compact),
            "alpha_chars": alpha_chars,
            "digit_chars": digit_chars,
            "line_count": line_count,
        }

    def should_use_text_fast_path(page_idx):
        profile = str(doc_profile or "standard").lower()
        if profile not in {"standard", "office", "government", "legal", "manual", "academic", "book", "tabular"}:
            return False, None
        if file_size_mb is not None and total_document_pages > 0:
            avg_page_mb_local = file_size_mb / max(1, total_document_pages)
            if avg_page_mb_local > 0.45:
                return False, None
        metrics = get_page_text_metrics(page_idx)
        compact = metrics["compact"]
        if metrics["chars"] < 220:
            return False, None
        if metrics["alpha_chars"] < 180:
            return False, None
        if metrics["line_count"] < 8:
            return False, None
        digit_share = metrics["digit_chars"] / max(1, metrics["chars"])
        if digit_share > 0.45:
            return False, None
        return True, metrics["text"]

    def analyze_text_fast_page(page_idx, page_text):
        lines = [line.strip() for line in (page_text or "").splitlines() if line.strip()]
        lower_lines = [line.lower() for line in lines]
        is_legal_profile = str(doc_profile or "").lower() == "legal"
        short_lines = sum(1 for line in lines if len(line) <= 60)
        standalone_numbers = [line for line in lines if line.isdigit() and len(line) <= 4]
        numbered_line_tokens = []
        for line in lines:
            if line.isdigit() and len(line) <= 4:
                numbered_line_tokens.append(int(line))
                continue
            prefixed_match = None
            if is_legal_profile:
                prefixed_match = re.match(r"^(\d{1,3})\s{2,}\S", line)
            if prefixed_match:
                numbered_line_tokens.append(int(prefixed_match.group(1)))
        sequential_line_number_hits = sum(
            1
            for curr_num, next_num in zip(numbered_line_tokens, numbered_line_tokens[1:])
            if next_num == curr_num + 1
        )
        dot_leader_lines = [
            line for line in lines
            if (".." in line and any(ch.isdigit() for ch in line[-8:])) or (" ." in line and any(ch.isdigit() for ch in line[-8:]))
        ]
        major_headings = sum(
            1
            for line in lines
            if line.startswith(("Chapter ", "Part ", "Division ", "Schedule "))
        )
        legal_clause_headings = sum(
            1
            for line in lines
            if re.match(r"^\d{1,3}[A-Za-z]?(?:\([A-Za-z0-9]+\))?\s+[A-Z]", line)
        )
        legal_alpha_paragraphs = sum(
            1
            for line in lines
            if re.match(r"^\([a-z]{1,2}\)\s+\S", line)
        )
        toc_signals = sum(
            1
            for line in lines
            if (
                line.startswith(("Chapter ", "Part ", "Division ", "Schedule "))
                or (".." in line and any(ch.isdigit() for ch in line[-8:]))
            )
        )
        looks_like_contents = bool(
            any(line == "contents" or line.startswith("contents ") for line in lower_lines)
            or (toc_signals >= 5 and len(dot_leader_lines) >= 3)
        )
        direct_render_preferred = bool(
            is_legal_profile
            and looks_like_contents
            and len(dot_leader_lines) >= 3
        )
        legal_clause_layout_preferred = bool(
            is_legal_profile
            and not looks_like_contents
            and (legal_clause_headings >= 1 or legal_alpha_paragraphs >= 2)
            and (
                sequential_line_number_hits >= 3
                or len(standalone_numbers) >= 2
                or major_headings >= 2
            )
        )
        direct_render_preferred = direct_render_preferred or legal_clause_layout_preferred
        structurally_hard = False if direct_render_preferred else bool(
            looks_like_contents
            or len(dot_leader_lines) >= 4
            or (major_headings >= 4 and short_lines >= max(10, len(lines) // 2))
            or (len(standalone_numbers) >= 3 and short_lines >= max(10, len(lines) // 2))
            or (
                is_legal_profile
                and len(numbered_line_tokens) >= 6
                and sequential_line_number_hits >= 4
                and short_lines >= max(6, len(lines) // 2)
            )
        )
        reason = None
        if looks_like_contents:
            reason = "contents page with legal hierarchy entries"
        elif len(dot_leader_lines) >= 4:
            reason = "dense table-of-contents style leader lines"
        elif major_headings >= 4 and short_lines >= max(10, len(lines) // 2):
            reason = "multiple structural headings on one page"
        elif len(standalone_numbers) >= 3 and short_lines >= max(10, len(lines) // 2):
            reason = "page appears layout-fragmented despite strong text"
        elif (
            is_legal_profile
            and len(numbered_line_tokens) >= 6
            and sequential_line_number_hits >= 4
            and short_lines >= max(6, len(lines) // 2)
        ):
            reason = "legal page includes embedded source line numbering that needs structural repair"
        return {
            "lines": lines,
            "standalone_numbers": standalone_numbers,
            "structurally_hard": structurally_hard,
            "direct_render_preferred": direct_render_preferred,
            "legal_clause_layout_preferred": legal_clause_layout_preferred,
            "reason": reason,
        }

    def stream_single_pdf_page_with_model(page_idx, request_model, request_prompt, cache_kind):
        pdf_name = f"chronicle_pdf_{selected_page_indices[page_idx] + 1}_{selected_page_indices[page_idx] + 1}.pdf"
        pdf_bytes = build_pdf_slice_bytes(page_idx, page_idx + 1)
        pdf_fingerprint = hashlib.sha256(pdf_bytes).hexdigest()
        cache_key = build_request_cache_key_fn(
            request_model,
            request_prompt,
            cache_kind,
            f"{page_idx}:{pdf_fingerprint}",
        )
        if "claude" in request_model:
            def _claude_pdf_request():
                uploaded = None
                try:
                    uploaded = upload_claude_pdf_slice(pdf_name, pdf_bytes)
                    file_id = get_uploaded_file_id(uploaded)
                    if not file_id:
                        raise RuntimeError("Claude Files API did not return a file id.")
                    payload = {
                        "_chronicle_claude_request": "message",
                        "content": [
                            {"type": "document", "source": {"type": "file", "file_id": file_id}},
                            {"type": "text", "text": request_prompt},
                        ],
                        "betas": [CLAUDE_FILES_API_BETA],
                    }
                    response = generate_retry_fn(client, request_model, payload, log_cb=log_cb)

                    def _cleanup_upload():
                        try:
                            client.beta.files.delete(file_id, betas=[CLAUDE_FILES_API_BETA])
                        except Exception as cleanup_ex:
                            log_cb(f"Warning: could not delete temporary Claude upload {file_id}: {cleanup_ex}")

                    return response, _cleanup_upload
                except Exception as upload_ex:
                    if uploaded is not None:
                        file_id = get_uploaded_file_id(uploaded)
                        if file_id:
                            try:
                                client.beta.files.delete(file_id, betas=[CLAUDE_FILES_API_BETA])
                            except Exception:
                                pass
                    log_cb(f"[Claude PDF] {CLAUDE_PDF_FILES_API_FALLBACK_REASON} ({upload_ex})")
                    payload = build_payload_fn(request_model, request_prompt, mime="application/pdf", file_bytes=pdf_bytes)
                    return generate_retry_fn(client, request_model, payload, log_cb=log_cb)

            stream_with_cache_fn(cache_key, _claude_pdf_request, out, fmt, f_obj, mem, log_cb, pause_cb=pause_cb)
            return
        if "gpt" in request_model:
            payload = build_payload_fn(request_model, request_prompt, mime="application/pdf", file_bytes=pdf_bytes)
            stream_with_cache_fn(
                cache_key,
                lambda: generate_retry_fn(client, request_model, payload, log_cb=log_cb),
                out,
                fmt,
                f_obj,
                mem,
                log_cb,
                pause_cb=pause_cb,
            )
            return

        def _gemini_pdf_request():
            uploaded = upload_gemini_pdf_slice(pdf_name, pdf_bytes)
            response = generate_retry_fn(client, request_model, [uploaded, request_prompt], log_cb=log_cb)

            def _cleanup_upload():
                try:
                    client.files.delete(name=uploaded.name)
                except Exception as cleanup_ex:
                    log_cb(f"Warning: could not delete temporary Gemini upload {uploaded.name}: {cleanup_ex}")

            return response, _cleanup_upload

        stream_with_cache_fn(cache_key, _gemini_pdf_request, out, fmt, f_obj, mem, log_cb, pause_cb=pause_cb)

    def process_text_fast_path(page_idx):
        nonlocal text_fast_path_logged
        source_page_num = selected_page_indices[page_idx] + 1
        use_fast_path, page_text = should_use_text_fast_path(page_idx)
        if not use_fast_path:
            return False
        analysis = analyze_text_fast_page(page_idx, page_text)
        if not text_fast_path_logged:
            log_cb(
                f"[PDF Fast Path] Strong embedded text layer detected from source page {source_page_num}. "
                "Using direct text-layer rendering on compatible pages to avoid upload stalls, while escalating structurally hard pages."
            )
            text_fast_path_logged = True
        if analysis["direct_render_preferred"]:
            if analysis.get("legal_clause_layout_preferred"):
                log_cb(
                    f"[PDF Fast Path] Keeping source page {source_page_num} on direct rendering because the legal clause layout "
                    "is text-backed and Chronicle's legal cleanup can preserve the hierarchy without a separate model call."
                )
            else:
                log_cb(
                    f"[PDF Fast Path] Keeping source page {source_page_num} on direct rendering because the legal contents layout "
                    "is text-backed and should preserve cleanly without a separate model call."
                )
        if analysis["structurally_hard"]:
            if auto_escalation_model and normalize_model_name(auto_escalation_model) != normalize_model_name(model):
                log_cb(
                    f"[Auto Engine] Routing source page {source_page_num} straight to {normalize_model_name(auto_escalation_model)} "
                    f"because the strong text layer still looks structurally hard ({analysis['reason']})."
                )
                try:
                    structural_prompt = (
                        prompt
                        + "\n\nSTRUCTURAL LEGAL PAGE MODE:\n"
                        + "- This page is text-backed but structurally important.\n"
                        + "- Preserve the legal hierarchy exactly, including chapter, part, division, section, clause numbering, and contents entries.\n"
                        + "- Preserve printed page references cleanly without duplicating bare numbers.\n"
                        + "- Do not flatten headings or contents items into body paragraphs."
                    )
                    stream_single_pdf_page_with_model(
                        page_idx,
                        auto_escalation_model,
                        structural_prompt,
                        "pdf-auto-escalate-upload",
                    )
                    methods[page_idx] = "auto-escalated"
                    escalated_pages.add(page_idx)
                    report_page(page_idx)
                    report_progress(1, page_idx)
                    return True
                except Exception as escalation_ex:
                    log_cb(
                        f"[Auto Engine] Direct structural escalation failed on page {source_page_num}: {escalation_ex}. "
                        "Falling back to normal processing."
                    )
            return False

        def is_heading_line(line):
            compact = " ".join(line.split())
            if not compact or len(compact) > 120:
                return False
            if compact.startswith(("Chapter ", "Part ", "Division ", "Schedule ", "Contents")):
                return True
            if re.fullmatch(r"[A-Z][A-Za-z ,.&'()/:-]{0,120}\b(?:Bill|Act|Rules|Regulations)\s+\d{4}", compact):
                return True
            words = compact.split()
            if len(words) <= 10 and compact.upper() == compact and any(ch.isalpha() for ch in compact):
                return True
            return False

        def is_section_heading(line):
            compact = " ".join(line.split())
            if not compact or len(compact) > 140:
                return False
            if compact.startswith(("Chapter ", "Part ", "Division ", "Schedule ", "Contents")):
                return False
            if compact.startswith(("(", "[")):
                return False
            if compact[:1].isdigit() and " " in compact:
                number, _, remainder = compact.partition(" ")
                if number.rstrip(".").isdigit() and remainder and remainder[:1].isupper():
                    return True
            return False

        def should_join_paragraph_line(current, nxt):
            if not current or not nxt:
                return False
            if is_heading_line(nxt) or is_section_heading(nxt):
                return False
            if nxt.isdigit():
                return False
            if current.endswith((".", "?", "!", ":", ";")):
                return False
            if current.endswith(","):
                return True
            if len(current) <= 4:
                return True
            if nxt[:1].islower() or nxt.startswith(("(", "[", '"', "'")):
                return True
            return len(current) >= 45 and len(nxt) >= 20

        def split_page_marker(lines):
            marker = None
            remaining = list(lines)
            if str(doc_profile or "").lower() == "legal":
                digit_only_lines = [line for line in remaining if line.isdigit() and len(line) <= 4]
                candidate_positions = [len(remaining) - 1, len(remaining) - 2]
                if len(digit_only_lines) <= 1:
                    candidate_positions.append(0)
            else:
                edge_positions = [len(remaining) - 1, len(remaining) - 2, len(remaining) - 3, len(remaining) - 4]
                candidate_positions = [0, 1, 2, 3] + edge_positions
            seen_positions = set()
            for pos in candidate_positions:
                if pos < 0 or pos >= len(remaining) or pos in seen_positions:
                    continue
                seen_positions.add(pos)
                line = remaining[pos]
                if line.isdigit() and len(line) <= 4:
                    marker = line
                    remaining.pop(pos)
                    break
            return marker, remaining

        def normalize_direct_fast_lines(lines):
            normalized = []
            number_tokens = []
            for line in lines:
                compact = " ".join(line.split())
                if not compact:
                    continue
                if compact.isdigit() and len(compact) <= 4:
                    number_tokens.append(int(compact))
                    continue
                prefixed = re.match(r"^(\d{1,3})\s{2,}(.*\S)$", compact)
                if prefixed:
                    number_tokens.append(int(prefixed.group(1)))
            sequential_hits = sum(
                1
                for curr_num, next_num in zip(number_tokens, number_tokens[1:])
                if next_num == curr_num + 1
            )
            line_numbered_layout = (
                str(doc_profile or "").lower() == "legal"
                and len(number_tokens) >= 6
                and sequential_hits >= 3
            )
            for line in lines:
                compact = " ".join(line.split())
                if not compact:
                    continue
                if str(doc_profile or "").lower() == "legal":
                    if re.fullmatch(r"No\.\s*,?\s*\d{4}", compact, flags=re.IGNORECASE):
                        continue
                    if re.fullmatch(r"[ivxlcdm]{1,10}", compact, flags=re.IGNORECASE):
                        continue
                    if re.fullmatch(r"[A-Z][A-Za-z ]{1,160}\b(?:Bill|Act|Rules|Regulations)\s+\d{4}", compact):
                        continue
                    if line_numbered_layout:
                        prefixed = re.match(r"^\d{1,3}\s{2,}(.*\S)$", compact)
                        if prefixed:
                            compact = prefixed.group(1).strip()
                        elif compact.isdigit() and len(compact) <= 3:
                            continue
                normalized.append(compact)
            return normalized

        def render_direct_html(lines):
            fragments = []
            page_marker, working_lines = split_page_marker(lines)
            working_lines = normalize_direct_fast_lines(working_lines)
            suppress_page_marker = str(doc_profile or "").lower() == "legal"
            if page_marker and not suppress_page_marker:
                escaped_marker = html.escape(page_marker)
                fragments.append(f"<p>[Original Page Number: {escaped_marker}]</p>")
            idx = 0
            while idx < len(working_lines):
                line = working_lines[idx]
                escaped = html.escape(line)
                if line.startswith("Chapter ") or line.startswith("Contents") or (" bill " in f" {line.lower()} "):
                    fragments.append(f"<h1>{escaped}</h1>")
                elif line.startswith("Part ") or (line.upper() == line and len(line.split()) <= 8):
                    fragments.append(f"<h2>{escaped}</h2>")
                elif line.startswith("Division "):
                    fragments.append(f"<h3>{escaped}</h3>")
                elif is_section_heading(line):
                    fragments.append(f"<h3>{escaped}</h3>")
                elif is_heading_line(line):
                    fragments.append(f"<h3>{escaped}</h3>")
                else:
                    paragraph = line
                    while idx + 1 < len(working_lines) and should_join_paragraph_line(paragraph, working_lines[idx + 1]):
                        idx += 1
                        paragraph = f"{paragraph} {working_lines[idx]}"
                    fragments.append(f"<p>{html.escape(paragraph)}</p>")
                idx += 1
            return "\n".join(fragments) + "\n"

        direct_output = page_text
        if fmt == "html":
            direct_output = render_direct_html(analysis["lines"])
        elif fmt == "md":
            direct_output = page_text.rstrip() + "\n\n"
        else:
            direct_output = page_text.rstrip() + "\n\n"

        if f_obj is not None:
            f_obj.write(direct_output)
            if hasattr(f_obj, "flush"):
                f_obj.flush()
        if mem is not None:
            mem.append(direct_output)
        methods[page_idx] = "text-layer-fast"
        report_page(page_idx)
        report_progress(1, page_idx)
        return True

    def write_pdf_slice_bytes_to_path(pdf_bytes, tmp_path):
        with open(tmp_path, "wb") as fh:
            fh.write(pdf_bytes)

    def allocate_temp_pdf_path(prefix):
        fd, tmp_path = mkstemp_fn(prefix=prefix, suffix=".pdf", dir=tempdir_fn())
        os.close(fd)
        return tmp_path

    def cleanup_temp_pdf(path):
        if not path:
            return
        try:
            if exists_fn(path):
                remove_fn(path)
        except Exception as cleanup_ex:
            log_cb(f"Warning: could not delete temporary PDF slice {path}: {cleanup_ex}")

    def report_page(page_idx):
        if not confidence_cb or reported[page_idx]:
            return
        score = max(0.0, min(1.0, 1.0 - penalties[page_idx]))
        confidence_cb(selected_page_indices[page_idx] + 1, score, methods[page_idx])
        reported[page_idx] = True

    def report_progress(increment=1, current_index=None):
        nonlocal pages_done
        pages_done += increment
        if page_progress_cb:
            source_page_num = (selected_page_indices[current_index] + 1) if current_index is not None else None
            done_pages = max(0, min(total, pages_done))
            try:
                page_progress_cb(done_pages, total, source_page_num)
            except TypeError:
                page_progress_cb(done_pages, total)

    def is_openai_pdf_base64_fallback(ex):
        return "cannot read base64 pdf" in str(ex).lower()

    def get_uploaded_file_id(uploaded):
        if hasattr(uploaded, "id"):
            return getattr(uploaded, "id")
        if isinstance(uploaded, dict):
            return uploaded.get("id")
        return None

    def upload_claude_pdf_slice(pdf_name, pdf_bytes):
        beta_client = getattr(client, "beta", None)
        files_api = getattr(beta_client, "files", None)
        messages_api = getattr(beta_client, "messages", None)
        if files_api is None or messages_api is None or not hasattr(files_api, "upload"):
            raise RuntimeError("Claude Files API SDK support is unavailable in this environment.")
        return files_api.upload(
            file=(pdf_name, pdf_bytes, "application/pdf"),
            betas=[CLAUDE_FILES_API_BETA],
        )

    def upload_gemini_pdf_slice(pdf_name, pdf_bytes):
        log_cb(f"[Gemini PDF] Uploading slice {pdf_name} ({len(pdf_bytes)} bytes).")
        upload_stream = io.BytesIO(pdf_bytes)
        upload_stream.name = pdf_name
        try:
            uploaded = client.files.upload(
                file=upload_stream,
                config={"mime_type": "application/pdf", "display_name": pdf_name},
            )
        except Exception as upload_ex:
            log_cb(f"[Gemini PDF] In-memory upload unavailable for this PDF slice. Falling back to temp-file upload. ({upload_ex})")
            tmp_path = allocate_temp_pdf_path("chronicle_pdf_upload_")
            try:
                write_pdf_slice_bytes_to_path(pdf_bytes, tmp_path)
                uploaded = client.files.upload(
                    file=tmp_path,
                    config={"mime_type": "application/pdf", "display_name": pdf_name},
                )
            finally:
                cleanup_temp_pdf(tmp_path)
        log_cb(f"[Gemini PDF] Waiting for slice {pdf_name} to become ready.")
        uploaded = wait_for_gemini_upload_ready_fn(client, uploaded, log_cb=log_cb, poll_sec=0.5, max_wait_sec=30.0)
        log_cb(f"[Gemini PDF] Slice {pdf_name} is ready.")
        return uploaded

    while curr < total:
        if pause_cb:
            pause_cb()
        remaining = total - curr
        effective_profile = "newspaper" if "HISTORICAL NEWSPAPER RULES" in prompt else str(doc_profile or "standard")
        chunk = min(
            1 if is_acad else get_pdf_chunk_pages_fn(
                model,
                effective_profile,
                total,
                file_size_mb=file_size_mb,
            ),
            remaining,
        )
        if process_text_fast_path(curr):
            curr += 1
            if curr > 0 and curr % 2 == 0:
                gc.collect()
            continue
        success = False
        while not success and chunk > 0:
            if pause_cb:
                pause_cb()
            end = min(curr + chunk, total)
            tmp_pdf = None
            pdf_name = f"chronicle_pdf_{selected_page_indices[curr] + 1}_{selected_page_indices[end - 1] + 1}.pdf"
            pdf_bytes = build_pdf_slice_bytes(curr, end)
            pdf_fingerprint = hashlib.sha256(pdf_bytes).hexdigest()
            try:
                if "claude" in model:
                    cache_key = build_request_cache_key_fn(model, prompt, "pdf-vision", f"{curr}:{end}:{pdf_fingerprint}")

                    def _claude_pdf_request():
                        uploaded = None
                        try:
                            uploaded = upload_claude_pdf_slice(pdf_name, pdf_bytes)
                            file_id = get_uploaded_file_id(uploaded)
                            if not file_id:
                                raise RuntimeError("Claude Files API did not return a file id.")
                            payload = {
                                "_chronicle_claude_request": "message",
                                "content": [
                                    {"type": "document", "source": {"type": "file", "file_id": file_id}},
                                    {"type": "text", "text": prompt},
                                ],
                                "betas": [CLAUDE_FILES_API_BETA],
                            }
                            response = generate_retry_fn(client, model, payload, log_cb=log_cb)

                            def _cleanup_upload():
                                try:
                                    client.beta.files.delete(file_id, betas=[CLAUDE_FILES_API_BETA])
                                except Exception as cleanup_ex:
                                    log_cb(f"Warning: could not delete temporary Claude upload {file_id}: {cleanup_ex}")

                            return response, _cleanup_upload
                        except Exception as upload_ex:
                            if uploaded is not None:
                                file_id = get_uploaded_file_id(uploaded)
                                if file_id:
                                    try:
                                        client.beta.files.delete(file_id, betas=[CLAUDE_FILES_API_BETA])
                                    except Exception:
                                        pass
                            log_cb(f"[Claude PDF] {CLAUDE_PDF_FILES_API_FALLBACK_REASON} ({upload_ex})")
                            payload = build_payload_fn(model, prompt, mime="application/pdf", file_bytes=pdf_bytes)
                            return generate_retry_fn(client, model, payload, log_cb=log_cb)

                    stream_with_cache_fn(
                        cache_key,
                        _claude_pdf_request,
                        out,
                        fmt,
                        f_obj,
                        mem,
                        log_cb,
                        pause_cb=pause_cb,
                    )
                elif "gpt" in model:
                    payload = build_payload_fn(model, prompt, mime="application/pdf", file_bytes=pdf_bytes)
                    cache_key = build_request_cache_key_fn(model, prompt, "pdf-vision", f"{curr}:{end}:{pdf_fingerprint}")
                    stream_with_cache_fn(
                        cache_key,
                        lambda: generate_retry_fn(client, model, payload, log_cb=log_cb),
                        out,
                        fmt,
                        f_obj,
                        mem,
                        log_cb,
                        pause_cb=pause_cb,
                    )
                else:
                    cache_key = build_request_cache_key_fn(model, prompt, "pdf-upload", f"{curr}:{end}:{pdf_fingerprint}")

                    def _gemini_pdf_request():
                        uploaded = upload_gemini_pdf_slice(pdf_name, pdf_bytes)
                        log_cb(
                            f"[Gemini PDF] Requesting model output for pages "
                            f"{selected_page_indices[curr] + 1}-{selected_page_indices[end - 1] + 1} via {normalize_model_name(model)}."
                        )
                        response = generate_retry_fn(client, model, [uploaded, prompt], log_cb=log_cb)

                        def _cleanup_upload():
                            try:
                                client.files.delete(name=uploaded.name)
                            except Exception as cleanup_ex:
                                log_cb(f"Warning: could not delete temporary Gemini upload {uploaded.name}: {cleanup_ex}")

                        return response, _cleanup_upload

                    stream_with_cache_fn(cache_key, _gemini_pdf_request, out, fmt, f_obj, mem, log_cb, pause_cb=pause_cb)
                success = True
                for idx in range(curr, end):
                    report_page(idx)
                    report_progress(1, idx)
                curr = end
                # Encourage prompt release of temp slice references during long PDF runs.
                tmp_pdf = None
                if curr > 0 and curr % 2 == 0:
                    gc.collect()
            except Exception as ex:
                openai_pdf_fallback = is_openai_pdf_base64_fallback(ex)
                if total == 1:
                    if openai_pdf_fallback:
                        log_cb(f"[OpenAI PDF] {OPENAI_PDF_BASE64_FALLBACK_REASON}")
                    else:
                        log_cb(f"[Gearshift] PDF Error on single page: {ex}")
                else:
                    if openai_pdf_fallback:
                        log_cb(
                            "[OpenAI PDF] "
                            f"{OPENAI_PDF_BASE64_FALLBACK_REASON} "
                            f"(pages {selected_page_indices[curr] + 1}-{selected_page_indices[end - 1] + 1})."
                        )
                    else:
                        log_cb(f"[Gearshift] PDF Error pages {curr+1}-{end}: {ex}")
                for idx in range(curr, end):
                    penalties[idx] += 0.14
                cleanup_temp_pdf(tmp_pdf)
                if chunk > 1 and remaining > 1 and not openai_pdf_fallback:
                    log_cb("[Gearshift Triggered] Reducing PDF chunk size after a chunk failure.")
                    chunk = max(1, chunk // 2)
                    log_cb(f"Throttling down to {chunk} pages.")
                else:
                    if (
                        not openai_pdf_fallback
                        and auto_escalation_model
                        and chunk == 1
                        and curr not in escalated_pages
                        and normalize_model_name(auto_escalation_model) != normalize_model_name(model)
                        and "gemini" in normalize_model_name(auto_escalation_model)
                    ):
                        log_cb(
                            f"[Auto Engine] Escalating page {selected_page_indices[curr] + 1} to {normalize_model_name(auto_escalation_model)} "
                            f"after {normalize_model_name(model)} struggled."
                        )
                        try:
                            retry_pdf_name = f"chronicle_pdf_escalate_{selected_page_indices[curr] + 1}.pdf"
                            retry_pdf_bytes = build_pdf_slice_bytes(curr, curr + 1)
                            dense_key = build_request_cache_key_fn(
                                auto_escalation_model,
                                prompt,
                                "pdf-auto-escalate-upload",
                                f"{curr}:{hashlib.sha256(retry_pdf_bytes).hexdigest()}",
                            )

                            def _gemini_auto_escalation_request():
                                uploaded = upload_gemini_pdf_slice(retry_pdf_name, retry_pdf_bytes)
                                log_cb(
                                    f"[Gemini PDF] Requesting escalated model output for source page "
                                    f"{selected_page_indices[curr] + 1} via {normalize_model_name(auto_escalation_model)}."
                                )
                                response = generate_retry_fn(client, auto_escalation_model, [uploaded, prompt], log_cb=log_cb)

                                def _cleanup_upload():
                                    try:
                                        client.files.delete(name=uploaded.name)
                                    except Exception as cleanup_ex:
                                        log_cb(f"Warning: could not delete temporary Gemini upload {uploaded.name}: {cleanup_ex}")

                                return response, _cleanup_upload

                            stream_with_cache_fn(
                                dense_key,
                                _gemini_auto_escalation_request,
                                out,
                                fmt,
                                f_obj,
                                mem,
                                log_cb,
                                pause_cb=pause_cb,
                            )
                            penalties[curr] += 0.08
                            methods[curr] = "auto-escalated"
                            escalated_pages.add(curr)
                            success = True
                            report_page(curr)
                            report_progress(1, curr)
                            curr += 1
                            if curr > 0 and curr % 2 == 0:
                                gc.collect()
                            continue
                        except Exception as escalation_ex:
                            log_cb(
                                f"[Auto Engine] Escalation failed on page {selected_page_indices[curr] + 1}: {escalation_ex}"
                            )
                    retry_tmp_pdf = None
                    if not openai_pdf_fallback:
                        log_cb(f"[Recovery] Dense-page recheck on page {selected_page_indices[curr] + 1}...")
                        try:
                            retry_pdf_name = f"chronicle_pdf_retry_{selected_page_indices[curr] + 1}.pdf"
                            retry_pdf_bytes = build_pdf_slice_bytes(curr, curr + 1)
                            dense_prompt = (
                                prompt
                                + "\n\nDENSE PAGE RECOVERY MODE:\n"
                                + "- Re-read this page carefully and iteratively.\n"
                                + "- Extract every visible character, heading, footnote, table cell, marginal note, stamp, and annotation.\n"
                                + "- Do not summarize and do not omit text due to layout density.\n"
                                + "- Preserve exact reading order as far as possible."
                            )
                            if "claude" in model or "gpt" in model:
                                payload = build_payload_fn(model, dense_prompt, mime="application/pdf", file_bytes=retry_pdf_bytes)
                                dense_key = build_request_cache_key_fn(
                                    model,
                                    dense_prompt,
                                    "pdf-dense",
                                    f"{curr}:{hashlib.sha256(retry_pdf_bytes).hexdigest()}",
                                )
                                stream_with_cache_fn(
                                    dense_key,
                                    lambda: generate_retry_fn(client, model, payload, log_cb=log_cb),
                                    out,
                                    fmt,
                                    f_obj,
                                    mem,
                                    log_cb,
                                    pause_cb=pause_cb,
                                )
                            else:
                                dense_key = build_request_cache_key_fn(
                                    model,
                                    dense_prompt,
                                    "pdf-dense-upload",
                                    f"{curr}:{hashlib.sha256(retry_pdf_bytes).hexdigest()}",
                                )

                                def _gemini_dense_request():
                                    uploaded = upload_gemini_pdf_slice(retry_pdf_name, retry_pdf_bytes)
                                    log_cb(
                                        f"[Gemini PDF] Requesting dense-page recovery output for source page "
                                        f"{selected_page_indices[curr] + 1} via {normalize_model_name(model)}."
                                    )
                                    response = generate_retry_fn(client, model, [uploaded, dense_prompt], log_cb=log_cb)

                                    def _cleanup_upload():
                                        try:
                                            client.files.delete(name=uploaded.name)
                                        except Exception as cleanup_ex:
                                            log_cb(f"Warning: could not delete temporary Gemini upload {uploaded.name}: {cleanup_ex}")

                                    return response, _cleanup_upload

                                stream_with_cache_fn(
                                    dense_key,
                                    _gemini_dense_request,
                                    out,
                                    fmt,
                                    f_obj,
                                    mem,
                                    log_cb,
                                    pause_cb=pause_cb,
                                )
                            log_cb(f"[Recovery] Dense-page recheck succeeded on page {selected_page_indices[curr] + 1}.")
                            penalties[curr] += 0.10
                            methods[curr] = "dense-recheck"
                            success = True
                            report_page(curr)
                            report_progress(1, curr)
                            curr += 1
                            if curr > 0 and curr % 2 == 0:
                                gc.collect()
                            continue
                        except Exception as retry_ex:
                            log_cb(f"[FAIL-SAFE] Dense-page recheck failed on page {selected_page_indices[curr] + 1}: {retry_ex}")
                        finally:
                            cleanup_temp_pdf(retry_tmp_pdf)
                    source_page_num = selected_page_indices[curr] + 1
                    log_cb(f"[FAIL-SAFE] Page {source_page_num} vision failed. Extracting raw text layer.")
                    txt = reader.pages[selected_page_indices[curr]].extract_text() or "[Unreadable Image Layer]"
                    units = split_text_for_fail_safe_fn(txt, max_chars=900)
                    if units and txt != "[Unreadable Image Layer]":
                        if len(units) > 1:
                            log_cb(f"[FAIL-SAFE] Page {curr+1} text-layer recovery using {len(units)} sentence/segment passes.")
                        for unit in units:
                            strict_prompt = (
                                prompt
                                + "\n\nLETTER-FIDELITY FAIL-SAFE MODE:\n"
                                + "- Treat the provided text segment as authoritative source text.\n"
                                + "- Preserve every legible character from this segment.\n"
                                + "- Do not summarize or omit any part of the segment.\n"
                                + "- Keep order exactly as provided."
                            )
                            payload = unit + "\n\n" + strict_prompt if ("claude" in model or "gpt" in model) else [unit, strict_prompt]
                            unit_key = build_request_cache_key_fn(
                                model,
                                strict_prompt,
                                "pdf-text-failsafe-unit",
                                sha256_text_fn(unit),
                            )
                            stream_with_cache_fn(
                                unit_key,
                                lambda payload=payload: generate_retry_fn(client, model, payload, log_cb=log_cb),
                                out,
                                fmt,
                                f_obj,
                                mem,
                                log_cb,
                                pause_cb=pause_cb,
                            )
                    else:
                        payload = txt + "\n\n" + prompt if ("claude" in model or "gpt" in model) else [txt, prompt]
                        txt_key = build_request_cache_key_fn(
                            model,
                            prompt,
                            "pdf-text-failsafe",
                            sha256_text_fn(txt),
                        )
                        stream_with_cache_fn(
                            txt_key,
                            lambda payload=payload: generate_retry_fn(client, model, payload, log_cb=log_cb),
                            out,
                            fmt,
                            f_obj,
                            mem,
                            log_cb,
                            pause_cb=pause_cb,
                        )
                    penalties[curr] += 0.28
                    methods[curr] = "text-layer-fallback"
                    success = True
                    report_page(curr)
                    report_progress(1)
                    curr += 1
