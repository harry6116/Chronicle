import os
import re


def _approx_visible_text(content, *, fmt):
    text = str(content or "")
    if fmt == "html":
        text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def should_reject_cleaned_output(raw_content, cleaned_content, *, fmt, min_visible_ratio=0.72, min_raw_visible_chars=12000):
    raw_visible = _approx_visible_text(raw_content, fmt=fmt)
    cleaned_visible = _approx_visible_text(cleaned_content, fmt=fmt)
    raw_len = len(raw_visible)
    cleaned_len = len(cleaned_visible)
    if raw_len < min_raw_visible_chars:
        return False, {
            "raw_visible_chars": raw_len,
            "cleaned_visible_chars": cleaned_len,
            "visible_ratio": 1.0 if raw_len == 0 else cleaned_len / raw_len,
        }
    ratio = 0.0 if raw_len == 0 else cleaned_len / raw_len
    return ratio < min_visible_ratio, {
        "raw_visible_chars": raw_len,
        "cleaned_visible_chars": cleaned_len,
        "visible_ratio": ratio,
    }


def append_pdf_audit_appendix_if_needed(
    *,
    pdf_path,
    extracted_text,
    page_scope,
    fmt,
    file_obj,
    memory,
    run_pdf_textlayer_audit_fn,
    render_audit_appendix_fn,
    append_generated_text_fn,
    coverage_warn_threshold,
    coverage_append_full_threshold,
    log_cb,
):
    if not extracted_text:
        return False
    try:
        audit = run_pdf_textlayer_audit_fn(pdf_path, extracted_text, page_scope=page_scope)
    except TypeError:
        audit = run_pdf_textlayer_audit_fn(pdf_path, extracted_text)
    if not audit:
        return False
    coverage = audit["coverage"]
    missing_count = len(audit["missing_lines"])
    if audit.get("source_truncated") or audit.get("output_truncated"):
        log_cb("[Audit] Memory guard applied: large audit inputs were truncated for stability.")
    log_cb(
        f"[Audit] PDF text-layer character coverage: {coverage*100:.1f}% (heuristic unmatched lines: {missing_count})."
    )
    if coverage < coverage_warn_threshold and missing_count > 0:
        if coverage < coverage_append_full_threshold:
            log_cb("[Audit] Low coverage detected; appending full text-layer safety appendix.")
            appendix = render_audit_appendix_fn(fmt, "Text-Layer Safety Appendix", audit["source_text"])
        else:
            log_cb("[Audit] Appending recovered lines from text-layer audit.")
            appendix = render_audit_appendix_fn(
                fmt,
                "Recovered Lines From Text-Layer Audit",
                "\n".join(audit["missing_lines"][:300]),
            )
        append_generated_text_fn(fmt, file_obj, memory, appendix)
        return True
    return False


def cleanup_output_text(content, *, fmt, job_cfg, normalize_html_fn, modernize_punctuation_fn, modernize_currency_fn, expand_abbreviations_fn, enforce_heading_structure_fn, apply_integrity_contract_fn=None):
    if fmt == "html":
        content = normalize_html_fn(content)
        if job_cfg.get("modernize_punctuation"):
            content = modernize_punctuation_fn(content)
        if job_cfg.get("unit_conversion"):
            content = modernize_currency_fn(content)
        if job_cfg.get("abbrev_expansion"):
            content = expand_abbreviations_fn(content)
        # Legal HTML already goes through the integrity contract inside the
        # normalization pipeline, so avoid re-running that heavier pass on the
        # fully wrapped document during finalize.
        if apply_integrity_contract_fn is not None and str(job_cfg.get("doc_profile") or "").lower() != "legal":
            content = apply_integrity_contract_fn(content, fmt, job_cfg.get("doc_profile"))
        return enforce_heading_structure_fn(content, fmt, job_cfg.get("doc_profile"))
    if fmt in ("txt", "md"):
        if job_cfg.get("modernize_punctuation"):
            content = modernize_punctuation_fn(content)
        if job_cfg.get("unit_conversion"):
            content = modernize_currency_fn(content)
        if job_cfg.get("abbrev_expansion"):
            content = expand_abbreviations_fn(content)
    return content


def finalize_single_output(
    *,
    job_cfg,
    temp_path,
    memory,
    base,
    file_obj,
    fmt,
    output_path,
    dispatch_save_fn,
    write_footer_fn,
    cleanup_output_text_fn,
    log_cb,
    progress_temp_path=None,
    progress_file_obj=None,
    resume_state_path=None,
    path_exists=os.path.exists,
    replace_fn=os.replace,
    remove_fn=os.remove,
):
    if memory is not None:
        dispatch_save_fn(job_cfg, temp_path, memory, base)
    if file_obj:
        write_footer_fn(file_obj, fmt)
        file_obj.close()
    elif progress_file_obj and not getattr(progress_file_obj, "closed", False):
        progress_file_obj.close()
    if path_exists(temp_path) and fmt in ("html", "txt", "md"):
        try:
            with open(temp_path, "r", encoding="utf-8", errors="ignore") as fh:
                raw_content = fh.read()
            cleaned = cleanup_output_text_fn(raw_content, fmt=fmt, job_cfg=job_cfg)
            reject_cleaned, stats = should_reject_cleaned_output(raw_content, cleaned, fmt=fmt)
            if reject_cleaned:
                log_cb(
                    "[Finalize Guard] Cleaned output shrank too far; preserving raw assembled output "
                    f"(visible chars {stats['raw_visible_chars']} -> {stats['cleaned_visible_chars']}, "
                    f"ratio {stats['visible_ratio']:.2f})."
                )
                cleaned = raw_content
            with open(temp_path, "w", encoding="utf-8") as fh:
                fh.write(cleaned)
        except Exception as cleanup_ex:
            label = "HTML" if fmt == "html" else "text"
            log_cb(f"Warning: {label} cleanup skipped ({cleanup_ex})")
    if path_exists(temp_path):
        replace_fn(temp_path, output_path)
    if progress_temp_path and path_exists(progress_temp_path):
        remove_fn(progress_temp_path)
    if resume_state_path and resume_state_path != progress_temp_path and path_exists(resume_state_path):
        remove_fn(resume_state_path)


def maybe_delete_source_file(path, *, delete_source_on_success, is_protected_path_fn, remove_fn=os.remove, log_cb):
    if not delete_source_on_success:
        return False
    if is_protected_path_fn(path):
        log_cb(f"Protected folder rule: not deleting source file in protected directory: {path}")
        return False
    try:
        remove_fn(path)
        log_cb(f"Deleted source file: {path}")
        return True
    except Exception as ex:
        log_cb(f"Warning: could not delete source file ({path}): {ex}")
        return False


def finalize_merged_output(
    *,
    cfg,
    merge_fmt,
    streamable_fmt,
    master_file_obj,
    master_temp_path,
    master_output_path,
    master_memory,
    write_footer_fn,
    cleanup_output_text_fn,
    strip_synthetic_headings_fn,
    dispatch_save_fn,
    log_cb,
    progress_temp_path=None,
    progress_file_obj=None,
    resume_state_path=None,
    path_exists=os.path.exists,
    replace_fn=os.replace,
    remove_fn=os.remove,
):
    if not master_output_path:
        return False
    if streamable_fmt and master_file_obj:
        write_footer_fn(master_file_obj, merge_fmt)
        master_file_obj.close()
        try:
            with open(master_temp_path, "r", encoding="utf-8", errors="ignore") as fh:
                raw_content = fh.read()
            merged_content = cleanup_output_text_fn(raw_content, fmt=merge_fmt, job_cfg=cfg)
            merged_content = strip_synthetic_headings_fn(merged_content, merge_fmt)
            reject_cleaned, stats = should_reject_cleaned_output(raw_content, merged_content, fmt=merge_fmt)
            if reject_cleaned:
                log_cb(
                    "[Finalize Guard] Merged cleanup shrank too far; preserving raw assembled output "
                    f"(visible chars {stats['raw_visible_chars']} -> {stats['cleaned_visible_chars']}, "
                    f"ratio {stats['visible_ratio']:.2f})."
                )
                merged_content = raw_content
            with open(master_temp_path, "w", encoding="utf-8") as fh:
                fh.write(merged_content)
        except Exception as cleanup_ex:
            log_cb(f"Warning: merge cleanup skipped ({cleanup_ex})")
        if path_exists(master_temp_path):
            replace_fn(master_temp_path, master_output_path)
    elif not streamable_fmt:
        merge_cfg = dict(cfg)
        merge_cfg["format_type"] = merge_fmt
        dispatch_save_fn(merge_cfg, master_output_path, master_memory, "Chronicle Merged")
    if progress_file_obj and not getattr(progress_file_obj, "closed", False):
        progress_file_obj.close()
    if progress_temp_path and path_exists(progress_temp_path):
        remove_fn(progress_temp_path)
    if resume_state_path and resume_state_path != progress_temp_path and path_exists(resume_state_path):
        remove_fn(resume_state_path)
    log_cb(f"Saved merged output: {master_output_path}")
    return True


def finalize_worker_completion(*, auto_save_processing_log_fn, log_cb, platform_system, subprocess_popen, winsound_module):
    try:
        auto_log_path = auto_save_processing_log_fn()
        if auto_log_path:
            log_cb(f"Auto-saved processing log: {auto_log_path}")
    except Exception as auto_log_ex:
        log_cb(f"Warning: could not auto-save processing log ({auto_log_ex})")
    log_cb("--- COMPLETE ---")
    if platform_system == "Darwin":
        subprocess_popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
    elif platform_system == "Windows" and winsound_module is not None:
        winsound_module.PlaySound("SystemAsterisk", winsound_module.SND_ALIAS | winsound_module.SND_ASYNC)


def finalize_worker_session(*, master_file_obj, has_incomplete_items, save_active_session_fn, delete_active_session_fn, set_running_state_fn):
    try:
        if master_file_obj and not master_file_obj.closed:
            master_file_obj.close()
    except Exception:
        pass
    if has_incomplete_items:
        save_active_session_fn()
    else:
        delete_active_session_fn()
    set_running_state_fn(False)


def finalize_job_success(
    *,
    merge_mode,
    job_cfg,
    temp_path,
    memory,
    base,
    file_obj,
    fmt,
    output_path,
    source_path,
    file_name,
    ext,
    current_file_page_total,
    memory_telemetry,
    delete_source_on_success,
    dispatch_save_fn,
    write_footer_fn,
    cleanup_output_text_fn,
    is_protected_path_fn,
    set_queue_status_fn,
    log_cb,
    get_peak_rss_mb_fn,
    progress_temp_path=None,
    progress_file_obj=None,
    resume_state_path=None,
):
    if not merge_mode:
        finalize_single_output(
            job_cfg=job_cfg,
            temp_path=temp_path,
            memory=memory,
            base=base,
            file_obj=file_obj,
            fmt=fmt,
            output_path=output_path,
            dispatch_save_fn=dispatch_save_fn,
            write_footer_fn=write_footer_fn,
            cleanup_output_text_fn=cleanup_output_text_fn,
            log_cb=log_cb,
            progress_temp_path=progress_temp_path,
            progress_file_obj=progress_file_obj,
            resume_state_path=resume_state_path,
        )
    maybe_delete_source_file(
        source_path,
        delete_source_on_success=bool(delete_source_on_success),
        is_protected_path_fn=is_protected_path_fn,
        log_cb=log_cb,
    )
    set_queue_status_fn('Done')
    result = {
        'set_page_done_to_total': ext != '.pdf',
        'page_total_increment': max(1, current_file_page_total) if ext != '.pdf' else 0,
        'completion_message': f'Merged: {file_name}' if merge_mode else f'Saved: {output_path}',
    }
    log_cb(result['completion_message'])
    if memory_telemetry:
        log_cb(f'[Memory] Peak RSS after task: {get_peak_rss_mb_fn():.1f} MB')
    return result


def handle_job_error(
    *,
    merge_mode,
    file_obj,
    temp_path,
    file_name,
    error,
    set_queue_status_fn,
    log_cb,
    progress_temp_path=None,
    progress_file_obj=None,
    resume_state_path=None,
    path_exists=os.path.exists,
    remove_fn=os.remove,
):
    set_queue_status_fn('Error')
    log_cb(f'Error on {file_name}: {error}')
    if file_obj and not merge_mode:
        file_obj.close()
    elif progress_file_obj and not getattr(progress_file_obj, "closed", False):
        progress_file_obj.close()
    if path_exists(temp_path) and not merge_mode:
        remove_fn(temp_path)
    if progress_temp_path and path_exists(progress_temp_path):
        log_cb(f'Preserved in-progress temp file: {progress_temp_path}')
    if resume_state_path and resume_state_path != progress_temp_path and path_exists(resume_state_path):
        log_cb(f'Preserved resume sidecar: {resume_state_path}')
    return True
