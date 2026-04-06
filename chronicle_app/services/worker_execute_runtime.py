import os


def build_confidence_callback(*, enabled, file_name, describe_quality_score_fn, log_cb):
    if not enabled:
        return None

    def confidence_cb(page_num, score, method, _fn=file_name):
        score10 = max(1.0, min(10.0, score * 10.0))
        desc = describe_quality_score_fn(score10, method)
        log_cb(f"[Confidence] {_fn} page {page_num}: {score10:.1f}/10 - {desc}")

    return confidence_cb


def log_image_quality_if_needed(*, enabled, ext, path, file_name, assess_image_file_quality_fn, log_cb):
    if not enabled or ext not in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp']:
        return False
    quality = assess_image_file_quality_fn(path)
    if not quality:
        return False
    q_score, q_desc = quality
    log_cb(f"[Quality] {file_name}: {q_score:.1f}/10 - {q_desc}")
    return True


def build_page_progress_callback(
    *,
    file_name,
    update_progress_state_fn,
    should_log_page_progress_fn,
    log_cb,
    refresh_progress_fn,
    memory=None,
    log_prefix="Page",
    unit_label="page",
    source_unit_label=None,
    persist_progress_state_fn=None,
    resume_recovered_units=0,
    original_total_units=None,
):
    def page_progress_cb(done_pages, total_pages, current_source_page=None, _fn=file_name):
        total_processed = update_progress_state_fn(done_pages, total_pages)
        if persist_progress_state_fn is not None:
            persist_progress_state_fn(done_pages, total_pages, current_source_page)
        if memory is not None and hasattr(memory, 'force_flush'):
            memory.force_flush()
        if memory is not None and hasattr(memory, 'mark_page_processed') and memory.mark_page_processed():
            clear_cadence = getattr(memory, 'clear_every_pages', None)
            if clear_cadence:
                log_cb(
                    f"[Memory] Cleared buffered {unit_label} text at run {unit_label} {done_pages} "
                    f"(buffer cadence: every {clear_cadence} {unit_label}s)."
                )
            else:
                log_cb(f"[Memory] Cleared buffered {unit_label} text at run {unit_label} {done_pages}.")
        if should_log_page_progress_fn(done_pages, total_pages):
            if resume_recovered_units > 0:
                total_complete = done_pages + resume_recovered_units
                total_units = int(original_total_units or (total_pages + resume_recovered_units))
                if current_source_page is not None:
                    log_cb(
                        f"[{log_prefix}] Resume pass: {done_pages}/{total_pages} remaining {unit_label}s complete "
                        f"(currently on {source_unit_label or ('source ' + unit_label)} {current_source_page}; "
                        f"total progress: {total_complete}/{total_units})."
                    )
                else:
                    log_cb(
                        f"[{log_prefix}] Resume pass: {done_pages}/{total_pages} remaining {unit_label}s complete "
                        f"(total progress: {total_complete}/{total_units})."
                    )
                refresh_progress_fn()
                return
            if current_source_page is not None:
                log_cb(
                    f"[{log_prefix}] {done_pages}/{total_pages} {unit_label}s processed "
                    f"({source_unit_label or ('source ' + unit_label)} {current_source_page}, run total: {total_processed})."
                )
            else:
                log_cb(f"[{log_prefix}] {done_pages}/{total_pages} {unit_label}s processed (run total: {total_processed}).")
        refresh_progress_fn()

    return page_progress_cb


def dispatch_processing_for_job(
    ext,
    *,
    job_cfg,
    client,
    path,
    temp_path,
    fmt,
    prompt,
    model,
    file_obj,
    memory,
    processing_log,
    pause_cb,
    confidence_cb,
    page_progress_cb,
    page_scope,
    auto_escalation_model,
    process_pdf_fn,
    process_pptx_fn,
    process_epub_fn,
    process_img_fn,
    process_text_fn,
    persist_progress_state_fn=None,
    resume_from_unit=0,
    original_total_units=None,
):
    if ext == '.pdf':
        return process_pdf_fn(
            client, path, temp_path, fmt, prompt, model, file_obj, memory,
            processing_log, confidence_cb=confidence_cb, pause_cb=pause_cb,
            page_progress_cb=page_progress_cb, page_scope=page_scope,
            doc_profile=job_cfg.get("doc_profile", "standard"),
            auto_escalation_model=auto_escalation_model,
        )
    if ext in ['.pptx', '.ppt']:
        return process_pptx_fn(
            client, path, temp_path, fmt, prompt, model, file_obj, memory, processing_log,
            pause_cb=pause_cb, page_progress_cb=page_progress_cb, resume_from_batch=resume_from_unit,
        )
    if ext == '.epub':
        return process_epub_fn(
            client, path, temp_path, fmt, prompt, model, file_obj, memory, processing_log,
            pause_cb=pause_cb, page_progress_cb=page_progress_cb, resume_from_batch=resume_from_unit,
        )
    if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp']:
        return process_img_fn(client, path, temp_path, fmt, prompt, model, file_obj, memory, processing_log, pause_cb=pause_cb)
    return process_text_fn(
        client, path, temp_path, ext, fmt, prompt, model, file_obj, memory, processing_log,
        pause_cb=pause_cb, page_progress_cb=page_progress_cb, resume_from_batch=resume_from_unit,
        doc_profile=job_cfg.get("doc_profile", "standard"),
    )


def process_job_content(
    ext,
    *,
    cfg,
    path,
    file_name,
    temp_path,
    fmt,
    prompt,
    model,
    client,
    file_obj,
    memory,
    processing_log,
    pause_cb,
    page_scope,
    describe_quality_score_fn,
    assess_image_file_quality_fn,
    update_progress_state_fn,
    should_log_page_progress_fn,
    refresh_progress_fn,
    needs_pdf_audit,
    append_pdf_audit_appendix_if_needed_fn,
    run_pdf_textlayer_audit_fn,
    render_audit_appendix_fn,
    append_generated_text_fn,
    coverage_warn_threshold,
    coverage_append_full_threshold,
    process_pdf_fn,
    process_pptx_fn,
    process_epub_fn,
    process_img_fn,
    process_text_fn,
    persist_progress_state_fn=None,
    resume_from_unit=0,
    original_total_units=None,
):
    start_mem_checkpoint = memory.checkpoint() if memory is not None and hasattr(memory, "checkpoint") else None
    start_mem_len = len(memory) if memory is not None else 0
    confidence_cb = build_confidence_callback(
        enabled=bool(cfg.get('page_confidence_scoring', False)),
        file_name=file_name,
        describe_quality_score_fn=describe_quality_score_fn,
        log_cb=processing_log,
    )
    log_image_quality_if_needed(
        enabled=bool(cfg.get('page_confidence_scoring', False)),
        ext=ext,
        path=path,
        file_name=file_name,
        assess_image_file_quality_fn=assess_image_file_quality_fn,
        log_cb=processing_log,
    )
    page_progress_cb = None
    if ext == '.pdf':
        page_progress_cb = build_page_progress_callback(
            file_name=file_name,
            update_progress_state_fn=update_progress_state_fn,
            should_log_page_progress_fn=should_log_page_progress_fn,
            log_cb=processing_log,
            refresh_progress_fn=refresh_progress_fn,
            memory=memory,
            log_prefix="Page",
            unit_label="page",
            source_unit_label="source page",
            persist_progress_state_fn=persist_progress_state_fn,
            resume_recovered_units=resume_from_unit,
            original_total_units=original_total_units,
        )
    elif ext in ['.pptx', '.ppt']:
        page_progress_cb = build_page_progress_callback(
            file_name=file_name,
            update_progress_state_fn=update_progress_state_fn,
            should_log_page_progress_fn=should_log_page_progress_fn,
            log_cb=processing_log,
            refresh_progress_fn=refresh_progress_fn,
            memory=memory,
            log_prefix="Chunk",
            unit_label="chunk",
            persist_progress_state_fn=persist_progress_state_fn,
            resume_recovered_units=resume_from_unit,
            original_total_units=original_total_units,
        )
    elif ext in ['.docx', '.txt', '.md', '.rtf', '.csv', '.js', '.xlsx', '.xls', '.epub']:
        page_progress_cb = build_page_progress_callback(
            file_name=file_name,
            update_progress_state_fn=update_progress_state_fn,
            should_log_page_progress_fn=should_log_page_progress_fn,
            log_cb=processing_log,
            refresh_progress_fn=refresh_progress_fn,
            memory=memory,
            log_prefix="Chunk",
            unit_label="chunk",
            persist_progress_state_fn=persist_progress_state_fn,
            resume_recovered_units=resume_from_unit,
            original_total_units=original_total_units,
        )
    dispatch_processing_for_job(
        ext,
        job_cfg=cfg,
        client=client,
        path=path,
        temp_path=temp_path,
        fmt=fmt,
        prompt=prompt,
        model=model,
        file_obj=file_obj,
        memory=memory,
        processing_log=processing_log,
        pause_cb=pause_cb,
        confidence_cb=confidence_cb,
        page_progress_cb=page_progress_cb,
        page_scope=page_scope,
        auto_escalation_model=cfg.get("auto_escalation_model"),
        process_pdf_fn=process_pdf_fn,
        process_pptx_fn=process_pptx_fn,
        process_epub_fn=process_epub_fn,
        process_img_fn=process_img_fn,
        process_text_fn=process_text_fn,
        resume_from_unit=resume_from_unit,
    )
    if memory is not None and hasattr(memory, "read_text_since") and start_mem_checkpoint is not None:
        extracted_for_file = memory.read_text_since(start_mem_checkpoint)
    else:
        extracted_for_file = ''.join(memory[start_mem_len:]) if memory is not None else ''
    if needs_pdf_audit and file_obj and temp_path and os.path.exists(temp_path):
        try:
            if hasattr(file_obj, "flush"):
                file_obj.flush()
            with open(temp_path, "r", encoding="utf-8", errors="ignore") as fh:
                extracted_for_file = fh.read()
        except Exception as audit_read_ex:
            processing_log(f"[Audit] Falling back to buffered text for audit ({audit_read_ex}).")
    if needs_pdf_audit and extracted_for_file:
        append_pdf_audit_appendix_if_needed_fn(
            pdf_path=path,
            extracted_text=extracted_for_file,
            page_scope=page_scope,
            fmt=fmt,
            file_obj=file_obj,
            memory=memory,
            run_pdf_textlayer_audit_fn=run_pdf_textlayer_audit_fn,
            render_audit_appendix_fn=render_audit_appendix_fn,
            append_generated_text_fn=append_generated_text_fn,
            coverage_warn_threshold=coverage_warn_threshold,
            coverage_append_full_threshold=coverage_append_full_threshold,
            log_cb=processing_log,
        )
    return extracted_for_file
