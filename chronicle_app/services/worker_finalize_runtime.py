import os
import re
import shutil
import threading
import time

from chronicle_app.services.nla_newspaper import should_skip_cleanup_for_nla_ocr_output
from chronicle_app.services.output_quality import analyze_output_quality, build_run_health_summary


FINALIZE_FILESYSTEM_OPERATION_TIMEOUT_SECONDS = 2.0
FINALIZE_TEXT_CLEANUP_TIMEOUT_SECONDS = 20.0
FINALIZE_REDUNDANT_CLEANUP_SKIP_CHARS = 400_000
FINALIZE_REDUNDANT_CLEANUP_SKIP_PROFILES = {"archival", "military"}
FINALIZE_POST_SAVE_CLEANUP_DEFAULT = False


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


def should_skip_cleanup_for_ocr_backed_nla_newspaper(raw_content, *, fmt, job_cfg):
    return should_skip_cleanup_for_nla_ocr_output(raw_content, fmt=fmt, job_cfg=job_cfg)


def should_skip_redundant_large_profile_cleanup(raw_content, *, fmt, job_cfg):
    if fmt != "html" or not raw_content:
        return False
    profile = str((job_cfg or {}).get("doc_profile") or "").lower()
    if profile not in FINALIZE_REDUNDANT_CLEANUP_SKIP_PROFILES:
        return False
    if len(raw_content) < FINALIZE_REDUNDANT_CLEANUP_SKIP_CHARS:
        return False
    lower_sample = raw_content[:4000].lower() + raw_content[-4000:].lower()
    return "<html" in lower_sample and "<main" in lower_sample


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


def _expand_abbreviations_for_profile(expand_abbreviations_fn, content, doc_profile):
    try:
        return expand_abbreviations_fn(content, doc_profile)
    except TypeError:
        return expand_abbreviations_fn(content)


def cleanup_output_text(content, *, fmt, job_cfg, normalize_html_fn, modernize_punctuation_fn, modernize_currency_fn, expand_abbreviations_fn, enforce_heading_structure_fn, apply_integrity_contract_fn=None):
    if fmt == "html":
        content = normalize_html_fn(content)
        if job_cfg.get("modernize_punctuation"):
            content = modernize_punctuation_fn(content)
        if job_cfg.get("unit_conversion"):
            content = modernize_currency_fn(content)
        if job_cfg.get("abbrev_expansion"):
            content = _expand_abbreviations_for_profile(expand_abbreviations_fn, content, job_cfg.get("doc_profile"))
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
            content = _expand_abbreviations_for_profile(expand_abbreviations_fn, content, job_cfg.get("doc_profile"))
    return content


def _build_fallback_output_path(output_path, *, path_exists):
    root, ext = os.path.splitext(output_path)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    candidate = f"{root}_finalized_{stamp}{ext}"
    if not path_exists(candidate):
        return candidate
    for idx in range(2, 1000):
        candidate = f"{root}_finalized_{stamp}_{idx}{ext}"
        if not path_exists(candidate):
            return candidate
    return f"{root}_finalized_{stamp}_{int(time.time())}{ext}"


def _run_filesystem_call_with_timeout(fn, *args, timeout_s=FINALIZE_FILESYSTEM_OPERATION_TIMEOUT_SECONDS):
    if timeout_s is None or timeout_s <= 0:
        return fn(*args)
    result = {}

    def _target():
        try:
            result["value"] = fn(*args)
        except Exception as ex:
            result["error"] = ex

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout_s)
    if thread.is_alive():
        name = getattr(fn, "__name__", "filesystem operation")
        raise TimeoutError(f"{name} did not finish within {timeout_s:.1f}s")
    if "error" in result:
        raise result["error"]
    return result.get("value")


def _close_finalize_stream(file_obj, *, label, description, log_cb, operation_timeout_s=FINALIZE_FILESYSTEM_OPERATION_TIMEOUT_SECONDS):
    if not file_obj or getattr(file_obj, "closed", False):
        return True
    try:
        _run_filesystem_call_with_timeout(file_obj.close, timeout_s=operation_timeout_s)
        return True
    except Exception as ex:
        log_cb(f"[Finalize] {label}: warning: could not close {description} within finalization guard ({ex}).")
        return False


def _read_text_file(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def _write_text_file(path, content):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def _read_buffered_memory_text(memory):
    if memory is None:
        return ""
    if hasattr(memory, "read_all_text"):
        try:
            return memory.read_all_text() or ""
        except Exception:
            pass
    try:
        return "".join(memory)
    except Exception:
        return str(memory or "")


def _build_emergency_text_output_path(output_path, *, path_exists):
    root, _ext = os.path.splitext(output_path)
    candidate = f"{root}.recovered.txt"
    if not path_exists(candidate):
        return candidate
    stamp = time.strftime("%Y%m%d_%H%M%S")
    candidate = f"{root}.recovered_{stamp}.txt"
    if not path_exists(candidate):
        return candidate
    for idx in range(2, 1000):
        candidate = f"{root}.recovered_{stamp}_{idx}.txt"
        if not path_exists(candidate):
            return candidate
    return f"{root}.recovered_{stamp}_{int(time.time())}.txt"


def _write_emergency_text_output(
    output_path,
    memory,
    *,
    label,
    log_cb,
    path_exists,
    operation_timeout_s=FINALIZE_FILESYSTEM_OPERATION_TIMEOUT_SECONDS,
):
    emergency_path = _build_emergency_text_output_path(output_path, path_exists=path_exists)
    content = _read_buffered_memory_text(memory)
    if not content:
        content = "[Chronicle emergency save]\nNo buffered text was available, but final format dispatch failed."
    _run_filesystem_call_with_timeout(
        _write_text_file,
        emergency_path,
        content,
        timeout_s=operation_timeout_s,
    )
    log_cb(f"[Finalize] {label}: emergency text fallback saved as {emergency_path}.")
    return emergency_path


def should_run_post_save_cleanup(job_cfg):
    return bool((job_cfg or {}).get("post_save_cleanup", FINALIZE_POST_SAVE_CLEANUP_DEFAULT))


def _cleanup_saved_output(
    output_path,
    *,
    fmt,
    job_cfg,
    label,
    cleanup_output_text_fn,
    log_cb,
    path_exists,
    replace_fn,
    remove_fn,
    operation_timeout_s=FINALIZE_FILESYSTEM_OPERATION_TIMEOUT_SECONDS,
    cleanup_timeout_s=FINALIZE_TEXT_CLEANUP_TIMEOUT_SECONDS,
):
    if not path_exists(output_path) or fmt not in ("html", "txt", "md"):
        return
    if not should_run_post_save_cleanup(job_cfg):
        log_cb(f"[Finalize] {label}: saved output; final cleanup is bypassed for save reliability.")
        return
    cleanup_label = "HTML" if fmt == "html" else "text"
    cleanup_temp_path = f"{output_path}.cleanup.tmp"
    try:
        log_cb(f"[Finalize] {label}: running optional post-save {fmt.upper()} cleanup.")
        raw_content = _run_filesystem_call_with_timeout(
            _read_text_file,
            output_path,
            timeout_s=cleanup_timeout_s,
        )
        if should_skip_cleanup_for_ocr_backed_nla_newspaper(raw_content, fmt=fmt, job_cfg=job_cfg):
            log_cb(
                f"[Finalize] {label}: skipping redundant {fmt.upper()} cleanup for OCR-backed NLA newspaper output."
            )
            return
        if should_skip_redundant_large_profile_cleanup(raw_content, fmt=fmt, job_cfg=job_cfg):
            log_cb(
                f"[Finalize] {label}: skipping redundant {fmt.upper()} cleanup for large "
                f"{str(job_cfg.get('doc_profile') or '').lower()} output."
            )
            return
        cleaned = _run_filesystem_call_with_timeout(
            cleanup_output_text_fn,
            raw_content,
            timeout_s=cleanup_timeout_s,
        )
    except Exception as cleanup_ex:
        log_cb(f"Warning: {cleanup_label} cleanup skipped ({cleanup_ex})")
        return
    try:
        reject_cleaned, stats = should_reject_cleaned_output(raw_content, cleaned, fmt=fmt)
        if reject_cleaned:
            log_cb(
                "[Finalize Guard] Cleaned output shrank too far; preserving raw assembled output "
                f"(visible chars {stats['raw_visible_chars']} -> {stats['cleaned_visible_chars']}, "
                f"ratio {stats['visible_ratio']:.2f})."
            )
            cleaned = raw_content
        qa_report = analyze_output_quality(cleaned, fmt=fmt, doc_profile=job_cfg.get("doc_profile"))
        if not qa_report["ok"]:
            log_cb(f"[Output QA] {qa_report['summary']}")
        _run_filesystem_call_with_timeout(
            _write_text_file,
            cleanup_temp_path,
            cleaned,
            timeout_s=operation_timeout_s,
        )
        _run_filesystem_call_with_timeout(
            replace_fn,
            cleanup_temp_path,
            output_path,
            timeout_s=operation_timeout_s,
        )
    except Exception as cleanup_ex:
        log_cb(f"Warning: {cleanup_label} cleanup skipped ({cleanup_ex})")
        try:
            if path_exists(cleanup_temp_path):
                _run_filesystem_call_with_timeout(remove_fn, cleanup_temp_path, timeout_s=operation_timeout_s)
        except Exception:
            pass


def _promote_temp_output(
    temp_path,
    output_path,
    *,
    label,
    log_cb,
    path_exists,
    replace_fn,
    remove_fn,
    copy_file_fn=shutil.copyfile,
    sleep_fn=time.sleep,
    operation_timeout_s=FINALIZE_FILESYSTEM_OPERATION_TIMEOUT_SECONDS,
):
    if not path_exists(temp_path):
        return output_path
    last_error = None
    for attempt in range(1, 4):
        try:
            _run_filesystem_call_with_timeout(
                replace_fn,
                temp_path,
                output_path,
                timeout_s=operation_timeout_s,
            )
            return output_path
        except Exception as ex:
            last_error = ex
            if attempt < 3:
                log_cb(f"[Finalize] {label}: temp promotion retry {attempt}/3 after filesystem error ({ex}).")
                try:
                    sleep_fn(0.25 * attempt)
                except Exception:
                    pass
    fallback_path = _build_fallback_output_path(output_path, path_exists=path_exists)
    try:
        _run_filesystem_call_with_timeout(
            copy_file_fn,
            temp_path,
            fallback_path,
            timeout_s=operation_timeout_s,
        )
        try:
            _run_filesystem_call_with_timeout(remove_fn, temp_path, timeout_s=operation_timeout_s)
        except Exception as cleanup_ex:
            log_cb(f"[Finalize] {label}: warning: saved fallback output but could not remove temp file ({cleanup_ex}).")
        log_cb(
            f"[Finalize] {label}: warning: could not replace final output ({last_error}); "
            f"saved completed output as {fallback_path}."
        )
        return fallback_path
    except Exception as fallback_ex:
        log_cb(
            f"[Finalize] {label}: warning: could not promote temp output ({last_error}) "
            f"or save fallback copy ({fallback_ex}); completed temp file preserved at {temp_path}."
        )
        return temp_path


def _remove_finalize_sidecar(
    path,
    *,
    label,
    description,
    log_cb,
    path_exists,
    remove_fn,
    operation_timeout_s=FINALIZE_FILESYSTEM_OPERATION_TIMEOUT_SECONDS,
):
    if not path or not path_exists(path):
        return
    log_cb(f"[Finalize] {label}: removing {description}.")
    try:
        _run_filesystem_call_with_timeout(remove_fn, path, timeout_s=operation_timeout_s)
    except Exception as ex:
        log_cb(f"[Finalize] {label}: warning: could not remove {description} ({ex}).")


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
    operation_timeout_s=FINALIZE_FILESYSTEM_OPERATION_TIMEOUT_SECONDS,
    cleanup_timeout_s=FINALIZE_TEXT_CLEANUP_TIMEOUT_SECONDS,
):
    original_label = os.path.basename(output_path) or str(output_path or "output")
    log_cb(f"[Finalize] {original_label}: begin finalization.")
    if memory is not None:
        log_cb(f"[Finalize] {original_label}: flushing buffered output to temp file.")
        try:
            dispatch_save_fn(job_cfg, temp_path, memory, base)
        except Exception as dispatch_ex:
            log_cb(
                f"[Finalize] {original_label}: warning: final {fmt.upper()} save failed ({dispatch_ex}); "
                "writing emergency text fallback."
            )
            output_path = _write_emergency_text_output(
                output_path,
                memory,
                label=original_label,
                log_cb=log_cb,
                path_exists=path_exists,
                operation_timeout_s=operation_timeout_s,
            )
            temp_path = ""
    if file_obj:
        log_cb(f"[Finalize] {original_label}: writing footer and closing stream.")
        try:
            _run_filesystem_call_with_timeout(write_footer_fn, file_obj, fmt, timeout_s=operation_timeout_s)
        except Exception as footer_ex:
            log_cb(f"[Finalize] {original_label}: warning: footer write skipped by finalization guard ({footer_ex}).")
        _close_finalize_stream(
            file_obj,
            label=original_label,
            description="output stream",
            log_cb=log_cb,
            operation_timeout_s=operation_timeout_s,
        )
    elif progress_file_obj and not getattr(progress_file_obj, "closed", False):
        log_cb(f"[Finalize] {original_label}: closing progress file stream.")
        _close_finalize_stream(
            progress_file_obj,
            label=original_label,
            description="progress file stream",
            log_cb=log_cb,
            operation_timeout_s=operation_timeout_s,
        )
    if path_exists(temp_path):
        log_cb(f"[Finalize] {original_label}: promoting temp output into place.")
        output_path = _promote_temp_output(
            temp_path,
            output_path,
            label=original_label,
            log_cb=log_cb,
            path_exists=path_exists,
            replace_fn=replace_fn,
            remove_fn=remove_fn,
            operation_timeout_s=operation_timeout_s,
        )
    _cleanup_saved_output(
        output_path,
        fmt=fmt,
        job_cfg=job_cfg,
        label=original_label,
        cleanup_output_text_fn=lambda content: cleanup_output_text_fn(content, fmt=fmt, job_cfg=job_cfg),
        log_cb=log_cb,
        path_exists=path_exists,
        replace_fn=replace_fn,
        remove_fn=remove_fn,
        operation_timeout_s=operation_timeout_s,
        cleanup_timeout_s=cleanup_timeout_s,
    )
    _remove_finalize_sidecar(
        progress_temp_path,
        label=original_label,
        description="progress file",
        log_cb=log_cb,
        path_exists=path_exists,
        remove_fn=remove_fn,
        operation_timeout_s=operation_timeout_s,
    )
    if resume_state_path != progress_temp_path:
        _remove_finalize_sidecar(
            resume_state_path,
            label=original_label,
            description="resume file",
            log_cb=log_cb,
            path_exists=path_exists,
            remove_fn=remove_fn,
            operation_timeout_s=operation_timeout_s,
        )
    log_cb(f"[Finalize] {original_label}: finalization complete.")
    return output_path


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
    operation_timeout_s=FINALIZE_FILESYSTEM_OPERATION_TIMEOUT_SECONDS,
    cleanup_timeout_s=FINALIZE_TEXT_CLEANUP_TIMEOUT_SECONDS,
):
    if not master_output_path:
        return False
    label = os.path.basename(master_output_path) or str(master_output_path or "merged output")
    log_cb(f"[Finalize] {label}: begin merged finalization.")
    if streamable_fmt and master_file_obj:
        log_cb(f"[Finalize] {label}: writing merged footer and closing stream.")
        try:
            _run_filesystem_call_with_timeout(write_footer_fn, master_file_obj, merge_fmt, timeout_s=operation_timeout_s)
        except Exception as footer_ex:
            log_cb(f"[Finalize] {label}: warning: merged footer write skipped by finalization guard ({footer_ex}).")
        _close_finalize_stream(
            master_file_obj,
            label=label,
            description="merged output stream",
            log_cb=log_cb,
            operation_timeout_s=operation_timeout_s,
        )
        if path_exists(master_temp_path):
            log_cb(f"[Finalize] {label}: promoting merged temp output into place.")
            master_output_path = _promote_temp_output(
                master_temp_path,
                master_output_path,
                label=label,
                log_cb=log_cb,
                path_exists=path_exists,
                replace_fn=replace_fn,
                remove_fn=remove_fn,
                operation_timeout_s=operation_timeout_s,
            )
        _cleanup_saved_output(
            master_output_path,
            fmt=merge_fmt,
            job_cfg=cfg,
            label=label,
            cleanup_output_text_fn=lambda content: strip_synthetic_headings_fn(
                cleanup_output_text_fn(content, fmt=merge_fmt, job_cfg=cfg),
                merge_fmt,
            ),
            log_cb=log_cb,
            path_exists=path_exists,
            replace_fn=replace_fn,
            remove_fn=remove_fn,
            operation_timeout_s=operation_timeout_s,
            cleanup_timeout_s=cleanup_timeout_s,
        )
    elif not streamable_fmt:
        log_cb(f"[Finalize] {label}: dispatching buffered merged save.")
        merge_cfg = dict(cfg)
        merge_cfg["format_type"] = merge_fmt
        dispatch_save_fn(merge_cfg, master_output_path, master_memory, "Chronicle Merged")
    if progress_file_obj and not getattr(progress_file_obj, "closed", False):
        log_cb(f"[Finalize] {label}: closing merged progress file stream.")
        _close_finalize_stream(
            progress_file_obj,
            label=label,
            description="merged progress file stream",
            log_cb=log_cb,
            operation_timeout_s=operation_timeout_s,
        )
    _remove_finalize_sidecar(
        progress_temp_path,
        label=label,
        description="merged progress file",
        log_cb=log_cb,
        path_exists=path_exists,
        remove_fn=remove_fn,
        operation_timeout_s=operation_timeout_s,
    )
    if resume_state_path != progress_temp_path:
        _remove_finalize_sidecar(
            resume_state_path,
            label=label,
            description="merged resume file",
            log_cb=log_cb,
            path_exists=path_exists,
            remove_fn=remove_fn,
            operation_timeout_s=operation_timeout_s,
        )
    log_cb(f"[Finalize] {label}: merged finalization complete.")
    log_cb(f"Saved merged output: {master_output_path}")
    return True


def finalize_worker_completion(
    *,
    auto_save_processing_log_fn,
    log_cb,
    platform_system,
    subprocess_popen,
    winsound_module,
    all_items_completed=True,
):
    try:
        log_cb("[Finalize] Run completion: auto-save processing log step.")
        auto_log_path = auto_save_processing_log_fn()
        if auto_log_path:
            log_cb(f"Auto-saved processing log: {auto_log_path}")
    except Exception as auto_log_ex:
        log_cb(f"Warning: could not auto-save processing log ({auto_log_ex})")
    if not all_items_completed:
        log_cb("--- RUN ENDED WITH ATTENTION NEEDED ---")
        log_cb("[Finalize] Run completion: completion sound skipped because one or more queued items did not finish.")
        return
    log_cb("--- COMPLETE ---")
    if platform_system == "Darwin":
        log_cb("[Finalize] Run completion: triggering macOS completion sound.")
        subprocess_popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
    elif platform_system == "Windows" and winsound_module is not None:
        log_cb("[Finalize] Run completion: triggering Windows completion sound.")
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
        output_path = finalize_single_output(
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
    log_cb(
        "[Health] "
        + build_run_health_summary(
            file_name=file_name,
            output_path=output_path,
            fmt=fmt,
            doc_profile=job_cfg.get("doc_profile", "standard"),
            engine_label=job_cfg.get("model_name", "automatic"),
            total_units=current_file_page_total,
        ).replace("\n", " | ")
    )
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
        log_cb(f'Preserved resume file: {resume_state_path}')
    return True
