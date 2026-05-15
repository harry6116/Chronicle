import gc
import html
import io
import json
import os
import queue
import subprocess
import sys
import tempfile
import hashlib
import base64
import re
import threading
import time
import urllib.request

from chronicle_app.services.processing_runtime import CLAUDE_FILES_API_BETA
from chronicle_app.services.processing_runtime import GEMINI_GENERATE_TIMEOUT_MS
from chronicle_app.services.processing_runtime import PrecleanStream
from chronicle_app.services.nla_newspaper import contains_nla_ocr_marker
from chronicle_app.services.runtime_policies import normalize_model_name
from chronicle_app.services.runtime_policies import wait_for_gemini_upload_ready


OPENAI_PDF_BASE64_FALLBACK_REASON = "OpenAI PDF direct upload is not available in Chronicle yet. Falling back to the PDF text layer."
CLAUDE_PDF_FILES_API_FALLBACK_REASON = "Claude Files API is unavailable for this PDF slice. Falling back to inline PDF mode."
GEMINI_FILE_UPLOAD_TIMEOUT_MS = 300_000
GEMINI_FILE_DELETE_TIMEOUT_MS = 30_000
GEMINI_NONSTREAM_WALL_TIMEOUT_SEC = 180.0
GEMINI_NONSTREAM_PROGRESS_LOG_SEC = 30.0
DENSE_NEWSPAPER_DEFAULT_TILE_COUNT = 2
DENSE_NEWSPAPER_MAX_TILE_COUNT = 4
DENSE_NEWSPAPER_TILE_OVERLAP_RATIO = 0.025
DENSE_NEWSPAPER_LOCAL_OCR_MIN_CHARS = 8000
NLA_LOCAL_OCR_FAST_PATH_ENV = "CHRONICLE_NLA_LOCAL_OCR_FAST_PATH"
NLA_TROVE_ARTICLE_OCR_ENV = "CHRONICLE_NLA_TROVE_ARTICLE_OCR"
PDF_TEXT_FAST_PATH_ENV = "CHRONICLE_PDF_TEXT_FAST_PATH"
PDF_TEXT_LAYER_FALLBACK_ENV = "CHRONICLE_ALLOW_PDF_TEXT_LAYER_FALLBACK"
DEEP_SCAN_TEXT_FAST_PATH_BLOCKED_PROFILES = {
    "academic",
    "archival",
    "comic",
    "handwritten",
    "intelligence",
    "legal",
    "magazine",
    "medical",
    "military",
    "modern_newspaper",
    "newspaper",
}
SCANNED_IMAGE_ONLY_PROFILES = {
    "archival",
    "forms",
    "government",
    "handwritten",
    "manual",
    "military",
    "standard",
}

try:
    import fitz
except ImportError:  # pragma: no cover - optional in lightweight test environments
    fitz = None


def _gemini_http_options(timeout_ms):
    return {"http_options": {"timeout": timeout_ms}}


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
    allow_text_layer_fallback=False,
    urlopen_fn=None,
):
    reader = pdf_reader_cls(path)
    allow_text_layer_fallback = bool(
        allow_text_layer_fallback or os.environ.get(PDF_TEXT_LAYER_FALLBACK_ENV) == "1"
    )
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
    used_dense_newspaper_local_ocr = False
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

    def is_dense_newspaper_pdf():
        if "HISTORICAL NEWSPAPER RULES" not in prompt:
            return False
        if file_size_mb is None or total_document_pages <= 0:
            return False
        return (file_size_mb / max(1, total_document_pages)) >= 0.9

    def is_gemini_pro_model(request_model):
        return "gemini-2.5-pro" in normalize_model_name(request_model).lower()

    def is_gemini_model(request_model):
        return "gemini" in normalize_model_name(request_model).lower()

    def resolve_dense_newspaper_strip_model():
        if is_gemini_pro_model(model):
            return normalize_model_name(model)
        if auto_escalation_model and is_gemini_pro_model(auto_escalation_model) and is_gemini_model(model):
            return normalize_model_name(auto_escalation_model)
        return None

    def build_pdf_slice_bytes(start, end):
        writer = pdf_writer_cls()
        for idx in range(start, end):
            writer.add_page(reader.pages[selected_page_indices[idx]])
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    def build_page_png_bytes(page_idx):
        if fitz is None:
            raise RuntimeError("PyMuPDF is unavailable for scanned PDF image rendering.")
        last_error = None
        for zoom in (1.8, 1.45, 1.2):
            doc = None
            try:
                doc = fitz.open(path)
                page = doc.load_page(selected_page_indices[page_idx])
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False, colorspace=fitz.csRGB)
                image_bytes = pix.tobytes("png")
                if image_bytes:
                    return image_bytes
            except Exception as render_ex:
                last_error = render_ex
            finally:
                if doc is not None:
                    try:
                        doc.close()
                    except Exception:
                        pass
        raise RuntimeError(f"Could not render scanned PDF page image: {last_error}")

    def get_dense_newspaper_tile_count(page_idx):
        if fitz is None:
            return DENSE_NEWSPAPER_DEFAULT_TILE_COUNT
        doc = None
        try:
            doc = fitz.open(path)
            page = doc.load_page(selected_page_indices[page_idx])
            width = float(getattr(page.rect, "width", 0) or 0)
            if width >= 1800:
                return DENSE_NEWSPAPER_MAX_TILE_COUNT
            if width >= 1450:
                return 3
            return DENSE_NEWSPAPER_DEFAULT_TILE_COUNT
        except Exception:
            return DENSE_NEWSPAPER_DEFAULT_TILE_COUNT
        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception:
                    pass

    def build_page_tile_png_bytes(page_idx, tile_idx, tile_count):
        if fitz is None:
            raise RuntimeError("PyMuPDF is unavailable for dense newspaper image rendering.")
        last_error = None
        zooms = (1.7, 1.45, 1.2) if tile_count <= 2 else (2.0, 1.7, 1.45)
        for zoom in zooms:
            doc = None
            try:
                doc = fitz.open(path)
                page = doc.load_page(selected_page_indices[page_idx])
                rect = page.rect
                overlap = rect.width * DENSE_NEWSPAPER_TILE_OVERLAP_RATIO
                tile_width = rect.width / tile_count
                x0 = max(rect.x0, rect.x0 + tile_idx * tile_width - (overlap if tile_idx else 0))
                x1 = min(rect.x1, rect.x0 + (tile_idx + 1) * tile_width + (overlap if tile_idx < tile_count - 1 else 0))
                clip = fitz.Rect(x0, rect.y0, x1, rect.y1)
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False, colorspace=fitz.csRGB)
                image_bytes = pix.tobytes("png")
                if image_bytes:
                    return image_bytes
            except Exception as render_ex:
                last_error = render_ex
            finally:
                if doc is not None:
                    try:
                        doc.close()
                    except Exception:
                        pass
        raise RuntimeError(f"Could not render dense newspaper page strip: {last_error}")

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

    def is_nla_newspaper_ocr_text(text):
        return contains_nla_ocr_marker(text, sample_chars=2000)

    def extract_nla_page_id(text):
        match = re.search(r"nla\.news-page(\d+)", text or "")
        return match.group(1) if match else None

    def fetch_trove_text(url):
        opener = urlopen_fn or urllib.request.urlopen
        request = urllib.request.Request(url, headers={"User-Agent": "Chronicle newspaper OCR rescue"})
        with opener(request, timeout=25) as response:
            return response.read().decode("utf-8", errors="replace")

    def strip_trove_tags(markup):
        cleaned = re.sub(r"<br\s*/?>", "\n", markup or "", flags=re.IGNORECASE)
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        cleaned = html.unescape(cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
        return cleaned.strip(" |")

    def parse_trove_page_article_ids(page_html):
        article_ids = []
        for article_id in re.findall(r'class="[^"]*articleFromDB[^"]*"[^>]*id="article(\d+)"', page_html or "", flags=re.IGNORECASE):
            if article_id not in article_ids:
                article_ids.append(article_id)
        if article_ids:
            return article_ids
        for article_id in re.findall(r"/newspaper/article/(\d+)", page_html or ""):
            if article_id not in article_ids:
                article_ids.append(article_id)
        return article_ids

    def parse_trove_article_rendition(article_html):
        title = ""
        title_match = re.search(r"<title>\s*([^<]+?)\s*</title>", article_html or "", flags=re.IGNORECASE)
        if title_match:
            title = html.unescape(title_match.group(1))
            title = re.sub(r"^\d{2}\s+\w+\s+\d{4}\s+-\s*", "", title).strip().rstrip(".")
        body = (article_html or "").split("<hr/>", 1)[-1]
        paragraphs = []
        for zone in re.findall(r"<div class='zone'>(.*?)</div>", body, flags=re.IGNORECASE | re.DOTALL):
            for match in re.finditer(r"<p[^>]*>(.*?)</p>", zone, flags=re.IGNORECASE | re.DOTALL):
                text = strip_trove_tags(match.group(1))
                compact = re.sub(r"\s+", "", text)
                if len(compact) < 2 or re.fullmatch(r"[-–—_.·,:;\[\](){}]+", compact):
                    continue
                paragraphs.append(text)
        while paragraphs and title and paragraphs[0].rstrip(".").casefold() == title.rstrip(".").casefold():
            paragraphs.pop(0)
        return title, paragraphs

    def should_use_dense_newspaper_local_ocr(page_idx):
        if os.environ.get(NLA_LOCAL_OCR_FAST_PATH_ENV) != "1":
            return False, None
        if not is_dense_newspaper_pdf():
            return False, None
        metrics = get_page_text_metrics(page_idx)
        if metrics["chars"] < DENSE_NEWSPAPER_LOCAL_OCR_MIN_CHARS:
            return False, metrics
        if not is_nla_newspaper_ocr_text(metrics["text"]):
            return False, metrics
        return True, metrics

    def should_use_scanned_image_only_page(page_idx, chunk_size):
        if chunk_size != 1:
            return False, None
        if not is_gemini_pro_model(model):
            return False, None
        if is_dense_newspaper_pdf():
            return False, None
        profile = str(doc_profile or "standard").lower()
        if profile not in SCANNED_IMAGE_ONLY_PROFILES:
            return False, None
        if file_size_mb is None or total_document_pages <= 0:
            return False, None
        avg_page_mb = file_size_mb / max(1, total_document_pages)
        if avg_page_mb < 0.75:
            return False, None
        metrics = get_page_text_metrics(page_idx)
        if metrics["chars"] > 220:
            return False, metrics
        return True, metrics

    def should_use_text_fast_path(page_idx):
        if os.environ.get(PDF_TEXT_FAST_PATH_ENV) != "1":
            return False, None
        profile = str(doc_profile or "standard").lower()
        if profile in DEEP_SCAN_TEXT_FAST_PATH_BLOCKED_PROFILES:
            return False, None
        if profile not in {"standard", "office", "government", "legal", "manual", "academic", "book", "tabular", "transcript"}:
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
                cleanup_gemini_upload(uploaded)

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

        def is_transcript_stage_direction(line):
            compact = line.strip()
            if len(compact) < 3:
                return False
            if compact.startswith("*") and compact.endswith("*"):
                return True
            if compact.startswith("(") and compact.endswith(")"):
                return True
            if compact.startswith("[") and compact.endswith("]"):
                return True
            return False

        def split_transcript_speaker_line(line):
            if ":" not in line:
                return None
            speaker, dialogue = line.split(":", 1)
            speaker = " ".join(speaker.split())
            dialogue = " ".join(dialogue.split())
            if not speaker or not dialogue:
                return None
            if len(speaker) > 80:
                return None
            if speaker.startswith(("*", "(", "[")):
                return None
            if not any(ch.isalpha() for ch in speaker):
                return None
            return speaker, dialogue

        def split_transcript_stage_dialogue_line(line):
            compact = " ".join(line.split())
            match = re.match(r"^(\*[^*]{2,}\*)\s*:\s*(\S.*)$", compact)
            if not match:
                return None
            return match.group(1), match.group(2)

        def transcript_running_page_marker(line):
            compact = " ".join(line.split())
            match = re.match(r"^.+?\s+([IVXLCDM]+-\d+)$", compact)
            if match and len(compact) <= 90:
                return match.group(1)
            return None

        def is_transcript_structural_heading(line):
            compact = " ".join(line.split())
            if not compact:
                return False
            upper = compact.upper()
            if upper in {"FIRST ACT", "SECOND ACT", "THIRD ACT", "FOURTH ACT", "FIFTH ACT"}:
                return True
            if re.fullmatch(r"ACT\s+[IVXLCDM0-9]+", upper):
                return True
            if upper.startswith(("SCENE:", "SCENE ", "THE PERSONS IN THE PLAY", "THE SCENES OF THE PLAY", "TIME:")):
                return True
            return False

        def is_transcript_speaker_cue(line):
            compact = " ".join(line.split())
            if not compact or len(compact) > 50:
                return False
            if any(ch.isdigit() for ch in compact):
                return False
            if transcript_running_page_marker(compact):
                return False
            if is_transcript_structural_heading(compact):
                return False
            if compact.upper() != compact:
                contd_pattern = r"^[A-Z][A-Z .'\-]+(?:\s+\(cont'd\)|\s+\(CONT'D\))$"
                if not re.fullmatch(contd_pattern, compact):
                    return False
            if not any(ch.isalpha() for ch in compact):
                return False
            if any(ch in compact for ch in ":;?!"):
                return False
            words = compact.replace("(cont'd)", "").replace("(CONT'D)", "").split()
            return 1 <= len(words) <= 5

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
                if (
                    str(doc_profile or "").lower() == "transcript"
                    and idx == 0
                    and idx + 1 < len(working_lines)
                    and working_lines[idx + 1].strip().startswith("-")
                    and line.upper() == line
                ):
                    fragments.append(f"<h1>{escaped}</h1>")
                elif str(doc_profile or "").lower() == "transcript" and is_transcript_structural_heading(line):
                    fragments.append(f"<h2>{escaped}</h2>")
                elif str(doc_profile or "").lower() == "transcript" and transcript_running_page_marker(line):
                    marker = transcript_running_page_marker(line)
                    fragments.append(f"<p>[Original Page Number: {html.escape(marker)}]</p>")
                elif str(doc_profile or "").lower() == "transcript" and split_transcript_stage_dialogue_line(line):
                    stage, dialogue = split_transcript_stage_dialogue_line(line)
                    while idx + 1 < len(working_lines) and should_join_paragraph_line(dialogue, working_lines[idx + 1]):
                        idx += 1
                        dialogue = f"{dialogue} {working_lines[idx]}"
                    fragments.append(f"<p><strong><em>{html.escape(stage)}</em></strong>: {html.escape(dialogue)}</p>")
                elif str(doc_profile or "").lower() == "transcript" and is_transcript_stage_direction(line):
                    fragments.append(f"<p><strong><em>{escaped}</em></strong></p>")
                elif str(doc_profile or "").lower() == "transcript" and split_transcript_speaker_line(line):
                    speaker, dialogue = split_transcript_speaker_line(line)
                    fragments.append(f"<p><strong>{html.escape(speaker)}</strong>: {html.escape(dialogue)}</p>")
                elif str(doc_profile or "").lower() == "transcript" and is_transcript_speaker_cue(line):
                    fragments.append(f"<p><strong>{escaped}</strong></p>")
                elif line.startswith("Chapter ") or line.startswith("Contents") or (" bill " in f" {line.lower()} "):
                    fragments.append(f"<h1>{escaped}</h1>")
                elif line.startswith("Part ") or (
                    str(doc_profile or "").lower() != "transcript"
                    and line.upper() == line
                    and len(line.split()) <= 8
                ):
                    fragments.append(f"<h2>{escaped}</h2>")
                elif line.startswith("Division "):
                    fragments.append(f"<h3>{escaped}</h3>")
                elif str(doc_profile or "").lower() != "transcript" and is_section_heading(line):
                    fragments.append(f"<h3>{escaped}</h3>")
                elif str(doc_profile or "").lower() != "transcript" and is_heading_line(line):
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
        upload_config = {
            "mime_type": "application/pdf",
            "display_name": pdf_name,
            **_gemini_http_options(GEMINI_FILE_UPLOAD_TIMEOUT_MS),
        }
        try:
            uploaded = client.files.upload(
                file=upload_stream,
                config=upload_config,
            )
        except Exception as upload_ex:
            log_cb(f"[Gemini PDF] In-memory upload unavailable for this PDF slice. Falling back to temp-file upload. ({upload_ex})")
            tmp_path = allocate_temp_pdf_path("chronicle_pdf_upload_")
            try:
                write_pdf_slice_bytes_to_path(pdf_bytes, tmp_path)
                uploaded = client.files.upload(
                    file=tmp_path,
                    config=upload_config,
                )
            finally:
                cleanup_temp_pdf(tmp_path)
        log_cb(f"[Gemini PDF] Waiting for slice {pdf_name} to become ready.")
        uploaded = wait_for_gemini_upload_ready_fn(client, uploaded, log_cb=log_cb, poll_sec=0.5, max_wait_sec=30.0)
        log_cb(f"[Gemini PDF] Slice {pdf_name} is ready.")
        return uploaded

    def upload_gemini_image_slice(image_name, image_bytes):
        log_cb(f"[Gemini Image] Uploading rendered page {image_name} ({len(image_bytes)} bytes).")
        upload_stream = io.BytesIO(image_bytes)
        upload_stream.name = image_name
        upload_config = {
            "mime_type": "image/png",
            "display_name": image_name,
            **_gemini_http_options(GEMINI_FILE_UPLOAD_TIMEOUT_MS),
        }
        try:
            uploaded = client.files.upload(
                file=upload_stream,
                config=upload_config,
            )
        except Exception as upload_ex:
            log_cb(f"[Gemini Image] In-memory upload unavailable for this rendered page. Falling back to temp-file upload. ({upload_ex})")
            fd, tmp_path = mkstemp_fn(prefix="chronicle_page_upload_", suffix=".png", dir=tempdir_fn())
            os.close(fd)
            try:
                with open(tmp_path, "wb") as fh:
                    fh.write(image_bytes)
                uploaded = client.files.upload(
                    file=tmp_path,
                    config=upload_config,
                )
            finally:
                cleanup_temp_pdf(tmp_path)
        log_cb(f"[Gemini Image] Waiting for rendered page {image_name} to become ready.")
        uploaded = wait_for_gemini_upload_ready_fn(client, uploaded, log_cb=log_cb, poll_sec=0.5, max_wait_sec=30.0)
        log_cb(f"[Gemini Image] Rendered page {image_name} is ready.")
        return uploaded

    def cleanup_gemini_upload(uploaded):
        try:
            client.files.delete(
                name=uploaded.name,
                config=_gemini_http_options(GEMINI_FILE_DELETE_TIMEOUT_MS),
            )
        except TypeError:
            try:
                client.files.delete(name=uploaded.name)
            except Exception as cleanup_ex:
                log_cb(f"Warning: could not delete temporary Gemini upload {uploaded.name}: {cleanup_ex}")
        except Exception as cleanup_ex:
            log_cb(f"Warning: could not delete temporary Gemini upload {uploaded.name}: {cleanup_ex}")

    def generate_gemini_nonstream(request_model, contents):
        result_q = queue.Queue(maxsize=1)

        def _request():
            try:
                try:
                    result = client.models.generate_content(
                        model=normalize_model_name(request_model),
                        contents=contents,
                        config=_gemini_http_options(GEMINI_GENERATE_TIMEOUT_MS),
                    )
                except TypeError:
                    result = client.models.generate_content(
                        model=normalize_model_name(request_model),
                        contents=contents,
                    )
                result_q.put((True, result))
            except BaseException as exc:
                result_q.put((False, exc))

        worker = threading.Thread(target=_request, name="chronicle-gemini-nonstream", daemon=True)
        worker.start()
        start = time.time()
        next_progress_log = GEMINI_NONSTREAM_PROGRESS_LOG_SEC
        while worker.is_alive():
            elapsed = time.time() - start
            remaining = GEMINI_NONSTREAM_WALL_TIMEOUT_SEC - elapsed
            if remaining <= 0:
                break
            worker.join(min(5.0, remaining))
            elapsed = time.time() - start
            if worker.is_alive() and elapsed >= next_progress_log:
                log_cb(
                    "[Gemini Pro] Still waiting for bounded non-stream output "
                    f"({elapsed:.0f}s elapsed, timeout {GEMINI_NONSTREAM_WALL_TIMEOUT_SEC:.0f}s)."
                )
                next_progress_log += GEMINI_NONSTREAM_PROGRESS_LOG_SEC
        if worker.is_alive():
            raise TimeoutError(
                "Timed out waiting for Gemini Pro non-stream output "
                f"after {GEMINI_NONSTREAM_WALL_TIMEOUT_SEC:.0f}s."
            )
        ok, value = result_q.get()
        if ok:
            return value
        raise value

    def resolve_gemini_rest_api_key():
        api_client = getattr(client, "_api_client", None)
        api_key = getattr(api_client, "api_key", None)
        if api_key:
            return str(api_key).strip()
        for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
            api_key = os.environ.get(env_name)
            if api_key:
                return api_key.strip()
        if getattr(sys, "frozen", False):
            support_dir = os.path.expanduser("~/Library/Application Support/Chronicle")
            json_path = os.path.join(support_dir, "api_keys.json")
            try:
                with open(json_path, "r", encoding="utf-8") as fh:
                    saved = json.load(fh)
                api_key = saved.get("gemini") if isinstance(saved, dict) else None
                if api_key:
                    return str(api_key).strip()
            except Exception:
                pass
            text_path = os.path.join(support_dir, "api_key_gemini.txt")
            try:
                with open(text_path, "r", encoding="utf-8") as fh:
                    api_key = fh.read().strip()
                if api_key:
                    return api_key
            except Exception:
                pass
        return ""

    def post_gemini_rest_generate(model_key, payload, api_key, error_prefix):
        body = json.dumps(payload).encode("utf-8")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_key}:generateContent"
        try:
            completed = subprocess.run(
                [
                    "/usr/bin/curl",
                    "--silent",
                    "--show-error",
                    "--fail-with-body",
                    "--http1.1",
                    "--noproxy",
                    "*",
                    "--connect-timeout",
                    "30",
                    "--max-time",
                    str(int(GEMINI_NONSTREAM_WALL_TIMEOUT_SEC)),
                    "-H",
                    "Content-Type: application/json",
                    "-H",
                    f"x-goog-api-key: {api_key}",
                    "--data-binary",
                    "@-",
                    url,
                ],
                input=body,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=GEMINI_NONSTREAM_WALL_TIMEOUT_SEC + 10.0,
            )
        except subprocess.TimeoutExpired as timeout_ex:
            raise TimeoutError(f"{error_prefix}: curl timed out after {timeout_ex.timeout:.0f}s.") from timeout_ex
        if completed.returncode != 0:
            stdout_text = completed.stdout.decode("utf-8", errors="replace").strip()
            stderr_text = completed.stderr.decode("utf-8", errors="replace").strip()
            detail = stdout_text or stderr_text or f"curl exited {completed.returncode}"
            raise RuntimeError(f"{error_prefix}: {detail}")
        return completed.stdout

    def iter_gemini_rest_stream_text(model_key, payload, api_key, error_prefix):
        body = json.dumps(payload).encode("utf-8")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_key}:streamGenerateContent?alt=sse"
        proc = subprocess.Popen(
            [
                "/usr/bin/curl",
                "--silent",
                "--show-error",
                "--fail-with-body",
                "--no-buffer",
                "--http1.1",
                "--noproxy",
                "*",
                "--connect-timeout",
                "30",
                "--max-time",
                str(int(GEMINI_NONSTREAM_WALL_TIMEOUT_SEC)),
                "-H",
                "Content-Type: application/json",
                "-H",
                f"x-goog-api-key: {api_key}",
                "--data-binary",
                "@-",
                url,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            proc.stdin.write(body)
            proc.stdin.close()
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            raise
        try:
            for raw_line in iter(proc.stdout.readline, b""):
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload_text = line[5:].strip()
                if not payload_text or payload_text == "[DONE]":
                    continue
                data = json.loads(payload_text)
                if "error" in data:
                    message = data.get("error", {}).get("message") or data["error"]
                    raise RuntimeError(f"{error_prefix}: {message}")
                parts = (
                    data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [])
                )
                text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
                if text:
                    yield text
            stderr_text = proc.stderr.read().decode("utf-8", errors="replace").strip()
            return_code = proc.wait(timeout=5)
            if return_code != 0:
                detail = stderr_text or f"curl exited {return_code}"
                raise RuntimeError(f"{error_prefix}: {detail}")
        finally:
            if proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass

    def generate_gemini_file_rest(request_model, uploaded, text_prompt, mime_type):
        api_key = resolve_gemini_rest_api_key()
        file_uri = getattr(uploaded, "uri", None)
        if not api_key or not file_uri:
            return generate_gemini_nonstream(request_model, [uploaded, text_prompt])
        model_key = normalize_model_name(request_model)
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"fileData": {"mimeType": mime_type, "fileUri": file_uri}},
                        {"text": text_prompt},
                    ],
                }
            ]
        }
        result_q = queue.Queue(maxsize=1)

        def _rest_request():
            try:
                result_q.put((True, post_gemini_rest_generate(model_key, payload, api_key, "Gemini REST request failed")))
            except BaseException as exc:
                result_q.put((None, exc))

        worker = threading.Thread(target=_rest_request, name="chronicle-gemini-rest", daemon=True)
        worker.start()
        start = time.time()
        next_progress_log = GEMINI_NONSTREAM_PROGRESS_LOG_SEC
        while worker.is_alive():
            elapsed = time.time() - start
            remaining = GEMINI_NONSTREAM_WALL_TIMEOUT_SEC - elapsed
            if remaining <= 0:
                break
            worker.join(min(5.0, remaining))
            elapsed = time.time() - start
            if worker.is_alive() and elapsed >= next_progress_log:
                log_cb(
                    "[Gemini Pro] Still waiting for bounded REST output "
                    f"({elapsed:.0f}s elapsed, timeout {GEMINI_NONSTREAM_WALL_TIMEOUT_SEC:.0f}s)."
                )
                next_progress_log += GEMINI_NONSTREAM_PROGRESS_LOG_SEC
        if worker.is_alive():
            raise TimeoutError(
                "Timed out waiting for Gemini Pro REST output "
                f"after {GEMINI_NONSTREAM_WALL_TIMEOUT_SEC:.0f}s."
            )
        ok, value = result_q.get()
        if ok is None:
            return generate_gemini_nonstream(request_model, [uploaded, text_prompt])
        if ok is False:
            raise value
        response_bytes = value
        data = json.loads(response_bytes.decode("utf-8", errors="replace") or "{}")
        if "error" in data:
            message = data.get("error", {}).get("message") or data["error"]
            raise RuntimeError(f"Gemini REST request failed: {message}")
        parts = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        return text

    def stream_gemini_file_rest_text(request_model, uploaded, text_prompt, mime_type):
        api_key = resolve_gemini_rest_api_key()
        file_uri = getattr(uploaded, "uri", None)
        if not api_key or not file_uri:
            return None
        model_key = normalize_model_name(request_model)
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"fileData": {"mimeType": mime_type, "fileUri": file_uri}},
                        {"text": text_prompt},
                    ],
                }
            ]
        }
        return iter_gemini_rest_stream_text(
            model_key,
            payload,
            api_key,
            "Gemini REST stream failed",
        )

    def generate_gemini_inline_image_rest(request_model, image_bytes, text_prompt, mime_type="image/png"):
        api_key = resolve_gemini_rest_api_key()
        if not api_key:
            if not getattr(sys, "frozen", False):
                inline_payload = [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": mime_type,
                                    "data": base64.b64encode(image_bytes).decode("ascii"),
                                }
                            },
                            {"text": text_prompt},
                        ],
                    }
                ]
                result = generate_gemini_nonstream(request_model, inline_payload)
                return getattr(result, "text", "") or ""
            raise RuntimeError("Gemini API key is unavailable for inline image REST generation.")
        model_key = normalize_model_name(request_model)
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            }
                        },
                        {"text": text_prompt},
                    ],
                }
            ]
        }
        result_q = queue.Queue(maxsize=1)

        def _rest_request():
            try:
                result_q.put((True, post_gemini_rest_generate(model_key, payload, api_key, "Gemini inline image REST request failed")))
            except BaseException as exc:
                result_q.put((False, exc))

        worker = threading.Thread(target=_rest_request, name="chronicle-gemini-inline-image-rest", daemon=True)
        worker.start()
        start = time.time()
        next_progress_log = GEMINI_NONSTREAM_PROGRESS_LOG_SEC
        while worker.is_alive():
            elapsed = time.time() - start
            remaining = GEMINI_NONSTREAM_WALL_TIMEOUT_SEC - elapsed
            if remaining <= 0:
                break
            worker.join(min(5.0, remaining))
            elapsed = time.time() - start
            if worker.is_alive() and elapsed >= next_progress_log:
                log_cb(
                    "[Gemini Pro] Still waiting for inline image REST output "
                    f"({elapsed:.0f}s elapsed, timeout {GEMINI_NONSTREAM_WALL_TIMEOUT_SEC:.0f}s)."
                )
                next_progress_log += GEMINI_NONSTREAM_PROGRESS_LOG_SEC
        if worker.is_alive():
            raise TimeoutError(
                "Timed out waiting for Gemini inline image REST output "
                f"after {GEMINI_NONSTREAM_WALL_TIMEOUT_SEC:.0f}s."
            )
        ok, value = result_q.get()
        if ok is False:
            raise value
        data = json.loads(value.decode("utf-8", errors="replace") or "{}")
        if "error" in data:
            message = data.get("error", {}).get("message") or data["error"]
            raise RuntimeError(f"Gemini inline image REST request failed: {message}")
        parts = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )
        return "".join(part.get("text", "") for part in parts if isinstance(part, dict))

    def stream_gemini_inline_image_rest_text(request_model, image_bytes, text_prompt, mime_type="image/png"):
        api_key = resolve_gemini_rest_api_key()
        if not api_key:
            raise RuntimeError("Gemini API key is unavailable for streaming inline image REST generation.")
        model_key = normalize_model_name(request_model)
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            }
                        },
                        {"text": text_prompt},
                    ],
                }
            ]
        }
        return iter_gemini_rest_stream_text(
            model_key,
            payload,
            api_key,
            "Gemini inline image REST stream failed",
        )

    def render_plain_newspaper_ocr_as_html(raw_text, source_page, tile_num):
        lines = [line.strip() for line in (raw_text or "").splitlines() if line.strip()]
        if not lines:
            return ""
        fragments = [
            "<section>",
        ]
        if tile_num in (None, 1):
            fragments.append(f"<h2>Page {source_page}</h2>")
        for line in lines:
            compact = re.sub(r"\s+", " ", line).strip()
            if not compact:
                continue
            compact = compact.strip("*# ")
            escaped = html.escape(compact)
            words = compact.split()
            looks_heading = (
                len(words) <= 8
                and any(ch.isalpha() for ch in compact)
                and (
                    compact.upper() == compact
                    or compact.endswith(":")
                    or compact in {"The", "Age"}
                )
            )
            if looks_heading:
                fragments.append(f"<h3>{escaped.rstrip(':')}</h3>")
            else:
                fragments.append(f"<p>{escaped}</p>")
        fragments.append("</section>")
        return "\n".join(fragments)

    def render_newspaper_ocr_line_as_html(line):
        compact = re.sub(r"\s+", " ", line or "").strip()
        if not compact:
            return ""
        compact = compact.strip("*# ")
        escaped = html.escape(compact)
        words = compact.split()
        looks_heading = (
            len(words) <= 8
            and any(ch.isalpha() for ch in compact)
            and (
                compact.upper() == compact
                or compact.endswith(":")
                or compact in {"The", "Age"}
            )
        )
        if looks_heading:
            return f"<h3>{escaped.rstrip(':')}</h3>\n"
        return f"<p>{escaped}</p>\n"

    def stream_plain_newspaper_ocr_as_html(text_stream, source_page, tile_num):
        yield "<section>\n"
        if tile_num in (None, 1):
            yield f"<h2>Page {source_page}</h2>\n"
        pending = ""
        for chunk in text_stream:
            pending += chunk
            while "\n" in pending:
                line, pending = pending.split("\n", 1)
                rendered = render_newspaper_ocr_line_as_html(line)
                if rendered:
                    yield rendered
        rendered = render_newspaper_ocr_line_as_html(pending)
        if rendered:
            yield rendered
        yield "</section>\n"

    def emit_dense_newspaper_text_layer_fallback(page_idx, reason):
        if not allow_text_layer_fallback:
            raise RuntimeError(
                "Dense newspaper image processing failed, and PDF text-layer emergency fallback is disabled. "
                "Enable the user-controlled emergency text-layer fallback to recover raw embedded OCR."
            )
        source_page = selected_page_indices[page_idx] + 1
        if reason:
            log_cb(f"[FAIL-SAFE] Dense newspaper page {source_page} using local OCR text layer after image-strip failure: {reason}")
        else:
            log_cb(f"[FAIL-SAFE] Dense newspaper page {source_page} using local OCR text layer after image-strip failure.")
        txt = reader.pages[selected_page_indices[page_idx]].extract_text() or ""
        if not txt.strip():
            txt = "[Unreadable Image Layer]"
        if fmt in ("html", "epub"):
            rendered = render_plain_newspaper_ocr_as_html(txt, source_page, None)
        else:
            rendered = txt.rstrip() + "\n\n"
        if f_obj is not None and hasattr(f_obj, "write"):
            f_obj.write(rendered)
            if hasattr(f_obj, "flush"):
                f_obj.flush()
        if mem is not None:
            mem.append(rendered)
        penalties[page_idx] += 0.24
        methods[page_idx] = "newspaper-text-layer-fallback"
        report_page(page_idx)
        report_progress(1, page_idx)

    def process_dense_newspaper_local_ocr_page(page_idx, metrics):
        nonlocal used_dense_newspaper_local_ocr
        source_page = selected_page_indices[page_idx] + 1
        log_cb(
            f"[PDF Fast Path] Dense NLA newspaper OCR detected on source page {source_page} "
            f"({metrics['chars']} text-layer characters). Using local OCR output to avoid image-strip stalls."
        )
        txt = metrics.get("text") or ""
        if not txt.strip():
            txt = "[Unreadable Image Layer]"
        if fmt in ("html", "epub"):
            rendered = render_plain_newspaper_ocr_as_html(txt, source_page, None)
        else:
            rendered = txt.rstrip() + "\n\n"
        if f_obj is not None and hasattr(f_obj, "write"):
            f_obj.write(rendered)
            if hasattr(f_obj, "flush"):
                f_obj.flush()
        if mem is not None:
            mem.append(rendered)
        methods[page_idx] = "newspaper-local-ocr"
        used_dense_newspaper_local_ocr = True
        report_page(page_idx)
        report_progress(1, page_idx)

    def process_nla_trove_article_ocr_page(page_idx):
        if os.environ.get(NLA_TROVE_ARTICLE_OCR_ENV) != "1":
            return False
        if fmt not in ("html", "epub") or str(doc_profile or "").lower() != "newspaper":
            return False
        metrics = get_page_text_metrics(page_idx)
        page_id = extract_nla_page_id(metrics.get("text", ""))
        if not page_id:
            return False
        source_page = selected_page_indices[page_idx] + 1
        try:
            page_html = fetch_trove_text(f"https://trove.nla.gov.au/newspaper/page/{page_id}")
            article_ids = parse_trove_page_article_ids(page_html)
            if not article_ids:
                return False
            fragments = [f"<section>", f"<h2>Page {source_page}</h2>"]
            article_count = 0
            for article_id in article_ids:
                article_html = fetch_trove_text(
                    f"https://trove.nla.gov.au/newspaper/rendition/nla.news-article{article_id}.txt"
                )
                title, paragraphs = parse_trove_article_rendition(article_html)
                if not paragraphs:
                    continue
                fragments.append("<article>")
                if title:
                    fragments.append(f"<h3>{html.escape(title, quote=False)}</h3>")
                for paragraph in paragraphs:
                    fragments.append(f"<p>{html.escape(paragraph, quote=False)}</p>")
                fragments.append("</article>")
                article_count += 1
            fragments.append("</section>")
            if article_count <= 0:
                return False
            rendered = "\n".join(fragments) + "\n"
            if f_obj:
                f_obj.write(rendered)
            if mem is not None:
                mem.append(rendered)
            methods[page_idx] = "nla-trove-article-ocr"
            reported[page_idx] = True
            report_page(page_idx)
            report_progress(1, page_idx)
            log_cb(f"Trove OCR: used article-level OCR for source page {source_page} ({article_count} article sections).")
            return True
        except Exception as trove_ex:
            log_cb(f"Trove OCR: article-level OCR was unavailable for source page {source_page}; using visual scan fallback. ({trove_ex})")
            return False

    def make_visible_rendered_page_path(source_page):
        source_dir = os.path.dirname(path) or "."
        base_name = os.path.splitext(os.path.basename(path))[0]
        safe_base = re.sub(r"[^A-Za-z0-9._-]+", "_", base_name).strip("._-") or "document"
        prefix = f"chronicle_temp_{safe_base}_page_{source_page}_"
        fd, rendered_path = mkstemp_fn(prefix=prefix, suffix=".png", dir=source_dir)
        os.close(fd)
        return rendered_path

    def process_scanned_image_only_page_with_pro(page_idx, request_model):
        source_page = selected_page_indices[page_idx] + 1
        log_cb(
            f"[Gemini Image] Source page {source_page} is an image-only scanned PDF page. "
            f"Rendering it as a visible PNG beside the PDF before requesting {normalize_model_name(request_model)}."
        )
        image_bytes = build_page_png_bytes(page_idx)
        rendered_path = make_visible_rendered_page_path(source_page)
        with open(rendered_path, "wb") as rendered_fh:
            rendered_fh.write(image_bytes)
        log_cb(f"[Gemini Image] Visible rendered page: {rendered_path}")
        image_prompt = (
            f"{prompt}\n\n"
            "SCANNED IMAGE-ONLY PDF PAGE MODE:\n"
            f"- This is source page {source_page} rendered from a scanned image-only PDF.\n"
            "- Read the entire visible page image, not just the title block or decorative heading.\n"
            "- Transcribe all visible tables, dates, columns, stamps, marginalia, signatures, annotations, and body text.\n"
            "- Preserve the document's reading order. Do not summarize. Do not stop after the cover/title area.\n"
            "- If the page contains multiple logical forms or diary entries on one physical image, include them all.\n"
        )
        cache_key = build_request_cache_key_fn(
            request_model,
            image_prompt,
            "pdf-scanned-image-page",
            f"{page_idx}:{hashlib.sha256(image_bytes).hexdigest()}",
        )
        stream_rest_available = bool(resolve_gemini_rest_api_key())

        def _gemini_scanned_image_request():
            transport_label = "streaming inline REST" if stream_rest_available else "inline REST"
            log_cb(
                f"[Gemini Image] Requesting full-page scanned image output for source page {source_page} "
                f"via {transport_label} on {normalize_model_name(request_model)}."
            )
            if stream_rest_available:
                response = stream_gemini_inline_image_rest_text(request_model, image_bytes, image_prompt, "image/png")
            else:
                response = generate_gemini_inline_image_rest(request_model, image_bytes, image_prompt, "image/png")

            def _cleanup_rendered_page():
                try:
                    remove_fn(rendered_path)
                except Exception as cleanup_ex:
                    log_cb(f"Warning: could not remove visible rendered page temp file {rendered_path}: {cleanup_ex}")

            return response, _cleanup_rendered_page

        try:
            generated = stream_with_cache_fn(cache_key, _gemini_scanned_image_request, out, fmt, f_obj, mem, log_cb, pause_cb=pause_cb)
            generated_len = len(generated or "")
            log_cb(f"[Gemini Image] Full-page scanned image returned {generated_len} character(s).")
        except Exception:
            try:
                remove_fn(rendered_path)
            except Exception:
                pass
            raise
        finally:
            try:
                if exists_fn(rendered_path):
                    remove_fn(rendered_path)
            except Exception:
                pass
        methods[page_idx] = "pro-scanned-page-image"

    def process_dense_newspaper_page_with_pro_tiles(page_idx, request_model):
        source_page = selected_page_indices[page_idx] + 1
        tile_count = get_dense_newspaper_tile_count(page_idx)
        log_cb(
            f"[Gemini Image] Rendering source page {source_page} as "
            f"{tile_count} newspaper strips before upload via {normalize_model_name(request_model)}."
        )
        for tile_idx in range(tile_count):
            tile_num = tile_idx + 1
            image_name = f"chronicle_page_{source_page}_strip_{tile_num}.png"
            image_bytes = build_page_tile_png_bytes(page_idx, tile_idx, tile_count)
            tile_prompt = (
                "OCR this historical newspaper image strip. "
                f"It is source page {source_page}, strip {tile_num} of {tile_count} in left-to-right order. "
                "Transcribe as much visible text as possible. Preserve headings and item boundaries. "
                "Read each column from top to bottom before moving to the next column. "
                "Do not summarize. This is a dense newspaper strip, not a cover page. "
                "Return plain text only."
            )
            tile_key = build_request_cache_key_fn(
                request_model,
                tile_prompt,
                "pdf-newspaper-pro-image-strip",
                f"{page_idx}:{tile_idx}:{hashlib.sha256(image_bytes).hexdigest()}",
            )
            stream_rest_available = bool(resolve_gemini_rest_api_key()) and fmt in ("html", "epub")

            def _gemini_tile_request(image_name=image_name, image_bytes=image_bytes, tile_prompt=tile_prompt, tile_num=tile_num):
                transport_label = "streaming inline REST" if stream_rest_available else "inline REST"
                log_cb(
                    f"[Gemini Image] Requesting dense newspaper strip {tile_num}/{tile_count} "
                    f"for source page {source_page} via {transport_label} on {normalize_model_name(request_model)}."
                )
                if stream_rest_available:
                    response = PrecleanStream(
                        stream_plain_newspaper_ocr_as_html(
                            stream_gemini_inline_image_rest_text(request_model, image_bytes, tile_prompt, "image/png"),
                            source_page,
                            tile_num,
                        )
                    )
                else:
                    raw_text = generate_gemini_inline_image_rest(request_model, image_bytes, tile_prompt, "image/png")
                    response = raw_text
                return response, lambda: None

            last_tile_ex = None
            max_attempts = 1 if stream_rest_available else 2
            for attempt in range(max_attempts):
                try:
                    generated = stream_with_cache_fn(tile_key, _gemini_tile_request, out, fmt, f_obj, mem, log_cb, pause_cb=pause_cb)
                    break
                except Exception as tile_ex:
                    last_tile_ex = tile_ex
                    if attempt + 1 < max_attempts:
                        log_cb(
                            f"[Gemini Image] Dense newspaper strip {tile_num}/{tile_count} failed: {tile_ex}. "
                            "Retrying once with Gemini Pro."
                        )
                    else:
                        raise last_tile_ex
            generated_len = len(generated or "")
            log_cb(
                f"[Gemini Image] Dense newspaper strip {tile_num}/{tile_count} "
                f"returned {generated_len} character(s)."
            )
        methods[page_idx] = "pro-image-strips"

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
        if is_dense_newspaper_pdf() and resolve_dense_newspaper_strip_model():
            chunk = 1
        use_local_ocr, local_ocr_metrics = should_use_dense_newspaper_local_ocr(curr)
        if use_local_ocr:
            process_dense_newspaper_local_ocr_page(curr, local_ocr_metrics)
            curr += 1
            if curr > 0 and curr % 2 == 0:
                gc.collect()
            continue
        if not (is_dense_newspaper_pdf() and resolve_dense_newspaper_strip_model()) and process_nla_trove_article_ocr_page(curr):
            curr += 1
            if curr > 0 and curr % 2 == 0:
                gc.collect()
            continue
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
            dense_newspaper_strip_model = resolve_dense_newspaper_strip_model() if is_dense_newspaper_pdf() and chunk == 1 else None
            scanned_image_model = None
            if not dense_newspaper_strip_model:
                use_scanned_image, scanned_image_metrics = should_use_scanned_image_only_page(curr, chunk)
                if use_scanned_image:
                    scanned_image_model = normalize_model_name(model)
                    log_cb(
                        f"[PDF Heuristic] Image-only scanned page detected on source page {selected_page_indices[curr] + 1} "
                        f"({scanned_image_metrics['chars']} text-layer characters, "
                        f"{(file_size_mb / max(1, total_document_pages)):.2f} MB/page). "
                        "Using rendered image transport instead of Gemini PDF upload."
                    )
            pdf_bytes = None
            pdf_fingerprint = None
            try:
                if "claude" in model:
                    pdf_bytes = build_pdf_slice_bytes(curr, end)
                    pdf_fingerprint = hashlib.sha256(pdf_bytes).hexdigest()
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
                    pdf_bytes = build_pdf_slice_bytes(curr, end)
                    pdf_fingerprint = hashlib.sha256(pdf_bytes).hexdigest()
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
                    if dense_newspaper_strip_model:
                        if normalize_model_name(dense_newspaper_strip_model) != normalize_model_name(model):
                            log_cb(
                                f"[Auto Engine] Routing dense newspaper page {selected_page_indices[curr] + 1} "
                                f"directly to {normalize_model_name(dense_newspaper_strip_model)} image strips "
                                f"to avoid fragile PDF slice rebuilding."
                            )
                        process_dense_newspaper_page_with_pro_tiles(curr, dense_newspaper_strip_model)
                        success = True
                        report_page(curr)
                        report_progress(1, curr)
                        curr += 1
                        if curr > 0 and curr % 2 == 0:
                            gc.collect()
                        continue
                    if scanned_image_model:
                        process_scanned_image_only_page_with_pro(curr, scanned_image_model)
                        success = True
                        report_page(curr)
                        report_progress(1, curr)
                        curr += 1
                        if curr > 0 and curr % 2 == 0:
                            gc.collect()
                        continue
                    pdf_bytes = build_pdf_slice_bytes(curr, end)
                    pdf_fingerprint = hashlib.sha256(pdf_bytes).hexdigest()
                    cache_key = build_request_cache_key_fn(model, prompt, "pdf-upload", f"{curr}:{end}:{pdf_fingerprint}")

                    def _gemini_pdf_request():
                        if dense_newspaper_strip_model:
                            image_name = f"chronicle_page_{selected_page_indices[curr] + 1}.png"
                            image_bytes = build_page_png_bytes(curr)
                            uploaded = upload_gemini_image_slice(image_name, image_bytes)
                            log_cb(
                                f"[Gemini Image] Requesting dense newspaper page output for source page "
                                f"{selected_page_indices[curr] + 1} via {normalize_model_name(dense_newspaper_strip_model)}."
                            )
                            response = stream_gemini_file_rest_text(
                                dense_newspaper_strip_model,
                                uploaded,
                                prompt,
                                "image/png",
                            )
                            if response is None:
                                response = generate_gemini_nonstream(dense_newspaper_strip_model, [uploaded, prompt])

                            def _cleanup_upload():
                                cleanup_gemini_upload(uploaded)

                            return response, _cleanup_upload
                        uploaded = upload_gemini_pdf_slice(pdf_name, pdf_bytes)
                        log_cb(
                            f"[Gemini PDF] Requesting model output for pages "
                            f"{selected_page_indices[curr] + 1}-{selected_page_indices[end - 1] + 1} via {normalize_model_name(model)}."
                        )
                        if is_dense_newspaper_pdf() and "gemini-2.5-pro" in normalize_model_name(model).lower():
                            log_cb(
                                "[Gemini PDF] Dense newspaper Pro request is using bounded REST streaming when available "
                                "so a silent stream cannot stall the run."
                            )
                            response = stream_gemini_file_rest_text(
                                model,
                                uploaded,
                                prompt,
                                "application/pdf",
                            )
                            if response is None:
                                response = generate_gemini_nonstream(model, [uploaded, prompt])
                        else:
                            response = generate_retry_fn(client, model, [uploaded, prompt], log_cb=log_cb)

                        def _cleanup_upload():
                            cleanup_gemini_upload(uploaded)

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
                if (
                    allow_text_layer_fallback
                    and (dense_newspaper_strip_model or (is_dense_newspaper_pdf() and chunk == 1 and not openai_pdf_fallback))
                ):
                    emit_dense_newspaper_text_layer_fallback(curr, ex)
                    success = True
                    curr += 1
                    if curr > 0 and curr % 2 == 0:
                        gc.collect()
                    continue
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
                                if "gemini-2.5-pro" in normalize_model_name(auto_escalation_model).lower():
                                    response = stream_gemini_file_rest_text(
                                        auto_escalation_model,
                                        uploaded,
                                        prompt,
                                        "application/pdf",
                                    )
                                    if response is None:
                                        response = generate_gemini_nonstream(auto_escalation_model, [uploaded, prompt])
                                else:
                                    response = generate_retry_fn(client, auto_escalation_model, [uploaded, prompt], log_cb=log_cb)

                                def _cleanup_upload():
                                    cleanup_gemini_upload(uploaded)

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
                                    if "gemini-2.5-pro" in normalize_model_name(model).lower():
                                        response = stream_gemini_file_rest_text(
                                            model,
                                            uploaded,
                                            dense_prompt,
                                            "application/pdf",
                                        )
                                        if response is None:
                                            response = generate_gemini_nonstream(model, [uploaded, dense_prompt])
                                    else:
                                        response = generate_retry_fn(client, model, [uploaded, dense_prompt], log_cb=log_cb)

                                    def _cleanup_upload():
                                        cleanup_gemini_upload(uploaded)

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
                    if not allow_text_layer_fallback:
                        raise RuntimeError(
                            "PDF vision/model processing failed and PDF text-layer emergency fallback is disabled. "
                            "Enable the user-controlled emergency text-layer fallback to recover raw embedded text."
                        ) from ex
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
                    report_progress(1, curr)
                    curr += 1
    return {
        "used_dense_newspaper_local_ocr": used_dense_newspaper_local_ocr,
    }
