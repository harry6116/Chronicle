import os
import re
import subprocess

from chronicle_core import build_tabular_html_fragment, parse_csv_rows


def _load_text_document_content(
    path,
    ext,
    *,
    csv_to_accessible_text_fn,
    docx_module,
    openpyxl_module,
    subprocess_module=subprocess,
):
    full = ""
    if ext == ".docx":
        full = "\n".join([p.text for p in docx_module.Document(path).paragraphs])
    elif ext == ".csv":
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            raw_csv = fh.read()
        full = csv_to_accessible_text_fn(raw_csv)
    elif ext in [".xlsx", ".xls"]:
        if ext == ".xls":
            try:
                import xlrd  # type: ignore

                wb_xls = xlrd.open_workbook(path)
                for sheet in wb_xls.sheets():
                    full += f"\n[--- Tab: {sheet.name} ---]\n"
                    for ridx in range(sheet.nrows):
                        row = sheet.row_values(ridx)
                        if any(str(c).strip() for c in row):
                            full += " | ".join([str(c) if c is not None else "" for c in row]) + "\n"
            except Exception:
                try:
                    conv = subprocess_module.run(
                        ["textutil", "-convert", "txt", "-stdout", path],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if conv.returncode == 0 and conv.stdout.strip():
                        full = conv.stdout
                    else:
                        raise RuntimeError("textutil conversion returned no content.")
                except Exception as ex:
                    raise Exception(
                        "Legacy .xls parsing failed. Install xlrd for robust .xls support or convert to .xlsx. "
                        f"Details: {ex}"
                    )
        else:
            workbook = openpyxl_module.load_workbook(path, data_only=True)
            for name in workbook.sheetnames:
                full += f"\n[--- Tab: {name} ---]\n"
                for row in workbook[name].iter_rows(values_only=True):
                    if any(c for c in row if str(c).strip()):
                        full += " | ".join([str(c) if c else "" for c in row]) + "\n"
    else:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            full = fh.read()
    return full


def _write_direct_output(text, *, f_obj, mem):
    if f_obj is not None:
        f_obj.write(text)
        f_obj.flush()
    if mem is not None:
        mem.append(text)


def _build_source_text_prompt(prompt, *, source_kind, doc_profile=None):
    profile = str(doc_profile or "standard").lower()
    mode = (
        "\n\nSOURCE-TEXT REPLICATION MODE:\n"
        f"- This input comes from Chronicle's direct {source_kind} text extraction path, not a visual scan.\n"
        "- Treat the supplied source text as authoritative unless it is clearly malformed or structurally broken.\n"
        "- Prioritize faithful replication of the original wording, numbering, hierarchy, and reading order.\n"
        "- Preserve clause numbering, headings, list nesting, table relationships, and explicit page or slide references when present.\n"
        "- Do not add visual-guess OCR repairs that are only appropriate for faded, skewed, or image-only scans.\n"
        "- Apply accessibility cleanup conservatively: fix only genuine structural/accessibility defects, not normal born-digital wording or punctuation.\n"
    )
    if profile in {"legal", "government"}:
        mode += (
            "- Be especially strict about legal/government hierarchy, cross-references, schedules, tables, and citation fidelity.\n"
        )
    return prompt + mode


def _build_tabular_datasets(path, ext, *, openpyxl_module):
    if ext == ".csv":
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            rows = parse_csv_rows(fh.read())
        if not rows:
            return []
        headers = [str(cell).strip() for cell in rows[0]]
        body = [[str(cell).strip() for cell in row] for row in rows[1:]]
        return [{"name": "Table Data", "headers": headers, "rows": body}]

    if ext in [".xlsx", ".xls"] and openpyxl_module is not None:
        workbook = openpyxl_module.load_workbook(path, data_only=True)
        datasets = []
        for name in workbook.sheetnames:
            rows = []
            for row in workbook[name].iter_rows(values_only=True):
                values = ["" if cell is None else str(cell).strip() for cell in row]
                if any(values):
                    rows.append(values)
            if not rows:
                continue
            datasets.append({
                "name": name,
                "headers": rows[0],
                "rows": rows[1:],
            })
        return datasets
    return []


def _stream_text_batches(
    full_text,
    *,
    out,
    fmt,
    prompt,
    model,
    f_obj,
    mem,
    log_cb,
    pause_cb,
    payload_kind,
    text_chunk_chars,
    clean_text_fn,
    batch_text_chunks_fn,
    build_request_cache_key_fn,
    sha256_text_fn,
    stream_with_cache_fn,
    generate_retry_fn,
    client,
    progress_cb=None,
    resume_from_batch=0,
    doc_profile=None,
):
    prompt = _build_source_text_prompt(prompt, source_kind=payload_kind, doc_profile=doc_profile)
    clean = clean_text_fn(full_text)
    chunks = [clean[i:i + text_chunk_chars] for i in range(0, len(clean), text_chunk_chars)]
    batches = batch_text_chunks_fn(chunks)
    total_batches = max(1, len(batches))
    start_batch = max(0, min(int(resume_from_batch or 0), total_batches))
    for index, chunk in enumerate(batches[start_batch:], start=start_batch + 1):
        if pause_cb:
            pause_cb()
        payload = chunk + "\n\n" + prompt if ("claude" in model or "gpt" in model) else [chunk, prompt]
        key = build_request_cache_key_fn(model, prompt, payload_kind, sha256_text_fn(chunk))
        stream_with_cache_fn(
            key,
            lambda payload=payload: generate_retry_fn(client, model, payload, log_cb=log_cb),
            out,
            fmt,
            f_obj,
            mem,
            log_cb,
            pause_cb=pause_cb,
        )
        if progress_cb:
            progress_cb(index, total_batches)


def estimate_text_work_units(
    path,
    ext,
    *,
    text_chunk_chars,
    csv_to_accessible_text_fn,
    clean_text_fn,
    batch_text_chunks_fn,
    docx_module,
    openpyxl_module,
    subprocess_module=subprocess,
):
    full = _load_text_document_content(
        path,
        ext,
        csv_to_accessible_text_fn=csv_to_accessible_text_fn,
        docx_module=docx_module,
        openpyxl_module=openpyxl_module,
        subprocess_module=subprocess_module,
    )
    clean = clean_text_fn(full)
    chunks = [clean[i:i + text_chunk_chars] for i in range(0, len(clean), text_chunk_chars)]
    batches = batch_text_chunks_fn(chunks)
    return max(1, len(batches))


def process_text(
    client,
    path,
    out,
    ext,
    fmt,
    prompt,
    model,
    f_obj,
    mem,
    log_cb,
    *,
    pause_cb=None,
    text_chunk_chars,
    csv_to_accessible_text_fn,
    clean_text_fn,
    batch_text_chunks_fn,
    build_request_cache_key_fn,
    sha256_text_fn,
    stream_with_cache_fn,
    generate_retry_fn,
    docx_module,
    openpyxl_module,
    subprocess_module=subprocess,
    page_progress_cb=None,
    resume_from_batch=0,
    doc_profile=None,
):
    if fmt == "html" and doc_profile == "tabular" and ext in [".csv", ".xlsx", ".xls"]:
        datasets = _build_tabular_datasets(path, ext, openpyxl_module=openpyxl_module)
        if datasets:
            title = os.path.splitext(os.path.basename(path))[0]
            fragment = build_tabular_html_fragment(title, datasets)
            _write_direct_output(fragment, f_obj=f_obj, mem=mem)
            if page_progress_cb:
                page_progress_cb(1, 1)
            return

    full = _load_text_document_content(
        path,
        ext,
        csv_to_accessible_text_fn=csv_to_accessible_text_fn,
        docx_module=docx_module,
        openpyxl_module=openpyxl_module,
        subprocess_module=subprocess_module,
    )

    return _stream_text_batches(
        full,
        out=out,
        fmt=fmt,
        prompt=prompt,
        model=model,
        f_obj=f_obj,
        mem=mem,
        log_cb=log_cb,
        pause_cb=pause_cb,
        payload_kind="text",
        text_chunk_chars=text_chunk_chars,
        clean_text_fn=clean_text_fn,
        batch_text_chunks_fn=batch_text_chunks_fn,
        build_request_cache_key_fn=build_request_cache_key_fn,
        sha256_text_fn=sha256_text_fn,
        stream_with_cache_fn=stream_with_cache_fn,
        generate_retry_fn=generate_retry_fn,
        client=client,
        progress_cb=page_progress_cb,
        resume_from_batch=resume_from_batch,
        doc_profile=doc_profile,
    )


def process_pptx(
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
    pause_cb=None,
    page_progress_cb=None,
    text_chunk_chars,
    clean_text_fn,
    batch_text_chunks_fn,
    build_request_cache_key_fn,
    sha256_text_fn,
    stream_with_cache_fn,
    generate_retry_fn,
    subprocess_module=subprocess,
    pptx_module=None,
    resume_from_batch=0,
):
    ext = os.path.splitext(path)[1].lower()
    full = ""
    if ext == ".ppt":
        try:
            conv = subprocess_module.run(
                ["textutil", "-convert", "txt", "-stdout", path],
                capture_output=True,
                text=True,
                check=False,
            )
            if conv.returncode == 0 and conv.stdout.strip():
                full = conv.stdout
            else:
                raise RuntimeError("textutil conversion returned no content.")
        except Exception as ex:
            raise Exception(
                "Legacy .ppt parsing failed. Convert to .pptx for full structural extraction. "
                f"Details: {ex}"
            )
    else:
        if pptx_module is None:
            import pptx as pptx_module  # type: ignore
        prs = pptx_module.Presentation(path)
        total_slides = max(1, len(prs.slides))
        num = 1
        for slide in prs.slides:
            full += f"\n[--- Slide: {num} ---]\n"
            try:
                shapes = sorted(slide.shapes, key=lambda s: (s.top, s.left))
            except Exception:
                shapes = slide.shapes
            for shape in shapes:
                if shape.has_text_frame:
                    full += shape.text + "\n"
            num += 1

    return _stream_text_batches(
        full,
        out=out,
        fmt=fmt,
        prompt=prompt,
        model=model,
        f_obj=f_obj,
        mem=mem,
        log_cb=log_cb,
        pause_cb=pause_cb,
        payload_kind="pptx",
        text_chunk_chars=text_chunk_chars,
        clean_text_fn=clean_text_fn,
        batch_text_chunks_fn=batch_text_chunks_fn,
        build_request_cache_key_fn=build_request_cache_key_fn,
        sha256_text_fn=sha256_text_fn,
        stream_with_cache_fn=stream_with_cache_fn,
        generate_retry_fn=generate_retry_fn,
        client=client,
        progress_cb=page_progress_cb,
        resume_from_batch=resume_from_batch,
        doc_profile="transcript",
    )


def process_epub(
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
    pause_cb=None,
    page_progress_cb=None,
    text_chunk_chars,
    clean_text_fn,
    batch_text_chunks_fn,
    build_request_cache_key_fn,
    sha256_text_fn,
    stream_with_cache_fn,
    generate_retry_fn,
    epub_module,
    resume_from_batch=0,
):
    book = epub_module.read_epub(path)
    full = ""
    for item in book.get_items():
        if item.get_type() == 9:
            full += re.sub(r"<[^>]+>", " ", item.get_body_content().decode("utf-8")) + "\n"
    return _stream_text_batches(
        full,
        out=out,
        fmt=fmt,
        prompt=prompt,
        model=model,
        f_obj=f_obj,
        mem=mem,
        log_cb=log_cb,
        pause_cb=pause_cb,
        payload_kind="epub",
        text_chunk_chars=text_chunk_chars,
        clean_text_fn=clean_text_fn,
        batch_text_chunks_fn=batch_text_chunks_fn,
        build_request_cache_key_fn=build_request_cache_key_fn,
        sha256_text_fn=sha256_text_fn,
        stream_with_cache_fn=stream_with_cache_fn,
        generate_retry_fn=generate_retry_fn,
        client=client,
        progress_cb=page_progress_cb,
        resume_from_batch=resume_from_batch,
        doc_profile="book",
    )


def process_img(
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
    pause_cb=None,
    enhance_image_fn,
    build_payload_fn,
    build_request_cache_key_fn,
    sha256_file_fn,
    stream_with_cache_fn,
    generate_retry_fn,
    remove_fn=os.remove,
):
    if pause_cb:
        pause_cb()
    enhanced = enhance_image_fn(path)
    try:
        if "claude" in model or "gpt" in model:
            payload = build_payload_fn(model, prompt, enhanced, "image/png")
            key = build_request_cache_key_fn(model, prompt, "image", sha256_file_fn(enhanced))
            stream_with_cache_fn(
                key,
                lambda: generate_retry_fn(client, model, payload, log_cb=log_cb),
                out,
                fmt,
                f_obj,
                mem,
                log_cb,
                pause_cb=pause_cb,
            )
        else:
            key = build_request_cache_key_fn(model, prompt, "image-upload", sha256_file_fn(enhanced))

            def _gemini_img_request():
                uploaded = client.files.upload(file=enhanced)
                response = generate_retry_fn(client, model, [uploaded, prompt], log_cb=log_cb)

                def _cleanup_upload():
                    try:
                        client.files.delete(name=uploaded.name)
                    except Exception as cleanup_ex:
                        log_cb(f"Warning: could not delete temporary Gemini upload {uploaded.name}: {cleanup_ex}")

                return response, _cleanup_upload

            stream_with_cache_fn(key, _gemini_img_request, out, fmt, f_obj, mem, log_cb, pause_cb=pause_cb)
    finally:
        if enhanced != path:
            remove_fn(enhanced)
