import copy
import os


def begin_run_start(*, resume_incomplete_only, scheduled_start_ts):
    return {
        "resume_mode": bool(resume_incomplete_only),
        "next_resume_incomplete_only": False,
        "should_clear_schedule": scheduled_start_ts is not None,
    }


def apply_start_configuration(
    cfg,
    *,
    control_settings,
    force_merge_from_scan,
    recursive_scan,
    dest_mode,
    custom_dest,
    preserve_source_structure,
    delete_source_on_success,
    script_dir,
):
    updated = dict(cfg)
    updated.update(control_settings)
    if force_merge_from_scan:
        updated["merge_files"] = True
    updated["recursive_scan"] = bool(recursive_scan)
    updated["dest_mode"] = int(dest_mode)
    updated["custom_dest"] = str(custom_dest).strip()
    updated["preserve_source_structure"] = bool(preserve_source_structure)
    updated["delete_source_on_success"] = bool(delete_source_on_success)
    updated["output_dir"] = os.path.join(script_dir, f"output_{updated['format_type']}")
    return updated


def validate_output_destination(cfg, *, isdir=os.path.isdir):
    if int(cfg.get("dest_mode", 0)) != 1:
        return None
    custom_dest = str(cfg.get("custom_dest", "")).strip()
    if not custom_dest:
        return "Please choose a custom output folder or select 'Same folder as source file'."
    if not isdir(custom_dest):
        return "Custom output folder does not exist."
    return None


def prepare_queue_for_start(queue, *, resume_mode, normalize_row_settings_fn):
    if resume_mode:
        for row in queue:
            if row.get("status") in {"Processing", "Paused"}:
                row["status"] = "Queued"
        return {"is_paused": False}

    for row in queue:
        if row.get("status") == "Paused":
            continue
        normalize_row_settings_fn(row)
        row["status"] = "Queued"
    return {}


def collect_pending_rows(queue):
    return [row for row in queue if row.get("status", "Queued") == "Queued"]


def expand_multi_range_pdf_rows(
    queue,
    *,
    normalize_row_settings_fn,
    normalize_pdf_page_scope_text_fn,
):
    expanded = []
    changed = False
    for row in queue:
        fp = str(row.get("path", ""))
        if os.path.splitext(fp)[1].lower() != ".pdf":
            expanded.append(row)
            continue
        settings = normalize_row_settings_fn(row)
        if bool(settings.get("merge_files", False)):
            expanded.append(row)
            continue
        page_scope = normalize_pdf_page_scope_text_fn(settings.get("pdf_page_scope", ""))
        if not page_scope or "," not in page_scope:
            expanded.append(row)
            continue
        parts = [part.strip() for part in page_scope.split(",") if part.strip()]
        if len(parts) <= 1:
            expanded.append(row)
            continue
        changed = True
        for part in parts:
            cloned = copy.deepcopy(row)
            cloned_settings = dict(settings)
            cloned_settings["pdf_page_scope"] = part
            cloned["settings"] = cloned_settings
            expanded.append(cloned)
    if changed:
        queue[:] = expanded
    return {"changed": changed, "queue": queue}


def validate_pending_pdf_page_scopes(
    pending_rows,
    *,
    normalize_row_settings_fn,
    pdf_reader_factory,
    normalize_pdf_page_scope_text_fn,
    parse_pdf_page_scope_spec_fn,
):
    for row in pending_rows:
        fp = str(row.get("path", ""))
        if os.path.splitext(fp)[1].lower() != ".pdf":
            continue
        settings = normalize_row_settings_fn(row)
        page_scope = normalize_pdf_page_scope_text_fn(settings.get("pdf_page_scope", ""))
        if not page_scope:
            continue
        try:
            total_pdf_pages = len(pdf_reader_factory(fp).pages)
            parse_pdf_page_scope_spec_fn(page_scope, total_pdf_pages)
        except Exception as ex:
            return {
                "filename": os.path.basename(fp),
                "details": str(ex),
            }
    return None


def find_missing_api_key_requirement(
    pending_rows,
    *,
    normalize_row_settings_fn,
    model_from_label_fn,
    label_from_model_fn,
    has_vendor_key_fn,
):
    for row in pending_rows:
        settings = normalize_row_settings_fn(row)
        model = str(settings.get("model_name") or model_from_label_fn(row["engine"]))
        vendor = "claude" if "claude" in model else "openai" if "gpt" in model else "gemini"
        if has_vendor_key_fn(vendor):
            continue
        return {
            "vendor": vendor,
            "label": label_from_model_fn(model),
        }
    return None


def build_start_messages(*, resume_mode, pending_count):
    action_label = "Resuming previous incomplete session" if resume_mode else "Starting extraction"
    return {
        "log_message": f"{action_label} for queued files ({pending_count} queued).",
        "status_text": f"Extraction started: {pending_count} queued file(s).",
    }


def build_run_reset_state():
    return {
        "stop_requested": False,
        "total_pages_processed": 0,
        "current_file_page_total": 0,
        "current_file_page_done": 0,
        "current_file_ordinal": 0,
        "current_run_resume_mode": False,
        "current_file_resume_recovered_units": 0,
        "current_file_resume_remaining_units": 0,
        "processing_log_lines": [],
    }
