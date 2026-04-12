import json
import os
import re
import time
import zlib
import base64

from chronicle_app.services.adaptive_engine_routing import select_execution_model_for_job


PROGRESS_STATE_HEADER_PREFIX = "[[CHRONICLE_PROGRESS_STATE::"
PROGRESS_STATE_HEADER_SUFFIX = "]]\n"
PROGRESS_STATE_HEADER_SIZE = 8192


def build_worker_run_plan(cfg, jobs, *, normalize_row_settings_fn, streamable_formats):
    custom_dest = str(cfg.get("custom_dest", "")).strip()
    dest_mode = int(cfg.get("dest_mode", 0))
    merge_mode = bool(cfg.get("merge_files", False))
    low_memory_mode = bool(cfg.get("low_memory_mode", False))
    memory_telemetry = bool(cfg.get("memory_telemetry", False))
    queued_jobs = [job for job in jobs if str(job.get("status", "Queued")) == "Queued"]
    queued_formats = {
        str(normalize_row_settings_fn(job).get("format_type", cfg.get("format_type", "html")))
        for job in queued_jobs
    }
    messages = []
    if merge_mode and len(queued_formats) > 1:
        merge_mode = False
        messages.append("[Merge] Disabled for this run because queued files have mixed assigned output formats.")
    if low_memory_mode and merge_mode:
        merge_mode = False
        messages.append("[Low-Memory] Merge mode disabled for this run.")
    default_fmt = cfg.get("format_type", "html")
    merge_fmt = (next(iter(queued_formats)) if queued_formats else default_fmt) if merge_mode else default_fmt
    streamable_fmt = merge_fmt in set(streamable_formats)
    return {
        "custom_dest": custom_dest,
        "dest_mode": dest_mode,
        "merge_mode": merge_mode,
        "low_memory_mode": low_memory_mode,
        "memory_telemetry": memory_telemetry,
        "queued_jobs": queued_jobs,
        "queued_formats": queued_formats,
        "default_fmt": default_fmt,
        "merge_fmt": merge_fmt,
        "streamable_fmt": streamable_fmt,
        "master_memory": [] if (merge_mode and not streamable_fmt) else None,
        "messages": messages,
    }


def determine_needs_pdf_audit(ext, cfg, *, low_memory_mode, path, low_memory_pdf_audit_skip_mb, getsize=os.path.getsize):
    needs_pdf_audit = ext == ".pdf" and bool(cfg.get("pdf_textlayer_audit", True))
    file_size_mb = 0.0
    if needs_pdf_audit and low_memory_mode:
        try:
            file_size_mb = getsize(path) / (1024.0 * 1024.0)
        except Exception:
            file_size_mb = 0.0
        if file_size_mb >= low_memory_pdf_audit_skip_mb:
            needs_pdf_audit = False
    return needs_pdf_audit, file_size_mb


def compute_target_dir(job, *, custom_dest, dest_mode, preserve_source_structure, isdir=os.path.isdir):
    fp = job["path"]
    if dest_mode == 0:
        return os.path.dirname(fp)
    root = job.get("source_root")
    src_dir = os.path.dirname(fp)
    if preserve_source_structure and root and isdir(root):
        try:
            rel_dir = os.path.relpath(src_dir, root)
        except Exception:
            rel_dir = "."
        if rel_dir and rel_dir != "." and not rel_dir.startswith(".."):
            return os.path.join(custom_dest, rel_dir)
    return custom_dest


def resolve_output_path(base, fmt, target_dir, *, collision_mode, path_exists=os.path.exists, now=None):
    output_path = os.path.join(target_dir, f"{base}.{fmt}")
    if path_exists(output_path):
        if collision_mode == "skip":
            return {"output_path": output_path, "should_skip": True}
        if collision_mode == "auto":
            stamp = int(time.time() if now is None else now)
            output_path = os.path.join(target_dir, f"{base}_{stamp}.{fmt}")
    return {"output_path": output_path, "should_skip": False}


def build_output_base_name(base, ext, job_cfg, *, normalize_pdf_page_scope_text_fn=None):
    output_base = str(base or "")
    if ext != ".pdf" or normalize_pdf_page_scope_text_fn is None:
        return output_base
    page_scope = normalize_pdf_page_scope_text_fn(job_cfg.get("pdf_page_scope", ""))
    if not page_scope or page_scope.lower() in {"all", "*"}:
        return output_base
    safe_scope = re.sub(r"[^0-9A-Za-z_-]+", "_", page_scope).strip("_")
    if not safe_scope:
        return output_base
    return f"{output_base}_pages_{safe_scope}"


def build_progress_temp_path(output_path):
    if not output_path:
        return None
    directory = os.path.dirname(output_path)
    basename = os.path.basename(output_path)
    return os.path.join(directory, f".chronicle_progress_{basename}.txt.tmp")


def build_legacy_progress_temp_path(output_path):
    return f"{output_path}.progress.txt.tmp" if output_path else None


def resolve_progress_temp_path(output_path, *, path_exists_fn=os.path.exists):
    current_path = build_progress_temp_path(output_path)
    legacy_path = build_legacy_progress_temp_path(output_path)
    if current_path and path_exists_fn(current_path):
        return current_path
    if legacy_path and path_exists_fn(legacy_path):
        return legacy_path
    return current_path


def _build_progress_state_path(progress_temp_path):
    return progress_temp_path or None


def _build_legacy_progress_state_path(progress_temp_path):
    return f"{progress_temp_path}.state.json" if progress_temp_path else None


def _encode_progress_state_payload(payload):
    compact = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return base64.b64encode(zlib.compress(compact)).decode("ascii")


def _decode_progress_state_payload(encoded):
    raw = zlib.decompress(base64.b64decode(encoded.encode("ascii")))
    return json.loads(raw.decode("utf-8"))


def build_progress_state_header(payload):
    encoded = _encode_progress_state_payload(payload)
    max_payload_len = PROGRESS_STATE_HEADER_SIZE - len(PROGRESS_STATE_HEADER_PREFIX) - len(PROGRESS_STATE_HEADER_SUFFIX)
    if len(encoded) > max_payload_len:
        raise ValueError("Embedded progress state is too large for the single sidecar header.")
    return f"{PROGRESS_STATE_HEADER_PREFIX}{encoded.ljust(max_payload_len)}{PROGRESS_STATE_HEADER_SUFFIX}"


def parse_progress_state_header(line):
    if not line or not line.startswith(PROGRESS_STATE_HEADER_PREFIX) or not line.endswith(PROGRESS_STATE_HEADER_SUFFIX):
        return None
    encoded = line[len(PROGRESS_STATE_HEADER_PREFIX):-len(PROGRESS_STATE_HEADER_SUFFIX)].rstrip()
    if not encoded:
        return None
    try:
        return _decode_progress_state_payload(encoded)
    except Exception:
        return None


def split_progress_file_content(text):
    if not text:
        return None, ""
    first_line, sep, remainder = text.partition("\n")
    if not sep:
        parsed = parse_progress_state_header(first_line + "\n")
        if parsed is None:
            return None, text
        return parsed, ""
    parsed = parse_progress_state_header(first_line + sep)
    if parsed is None:
        return None, text
    return parsed, remainder


def read_progress_state(progress_temp_path, *, path_exists_fn=os.path.exists, open_fn=open):
    if not progress_temp_path:
        return None
    active_path = progress_temp_path if path_exists_fn(progress_temp_path) else None
    if active_path is None:
        legacy_path = _build_legacy_progress_state_path(progress_temp_path)
        if legacy_path and path_exists_fn(legacy_path):
            active_path = legacy_path
        else:
            return None
    try:
        with open_fn(active_path, "r", encoding="utf-8", errors="ignore") as fh:
            line = fh.readline(PROGRESS_STATE_HEADER_SIZE + 8)
    except Exception:
        line = ""
    parsed = parse_progress_state_header(line)
    if parsed is not None:
        return parsed
    legacy_path = _build_legacy_progress_state_path(active_path)
    if legacy_path and path_exists_fn(legacy_path):
        try:
            with open_fn(legacy_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return None
    return None


def ensure_progress_sidecar_header(progress_temp_path, *, open_fn=open, path_exists_fn=os.path.exists):
    if not progress_temp_path:
        return
    blank_header = build_progress_state_header({})
    if not path_exists_fn(progress_temp_path):
        with open_fn(progress_temp_path, "w", encoding="utf-8") as fh:
            fh.write(blank_header)
        return
    try:
        with open_fn(progress_temp_path, "r", encoding="utf-8", errors="ignore") as fh:
            existing = fh.read()
    except Exception:
        existing = ""
    parsed, remainder = split_progress_file_content(existing)
    if parsed is not None:
        return
    with open_fn(progress_temp_path, "w", encoding="utf-8") as fh:
        fh.write(blank_header)
        fh.write(existing)


def write_progress_state(progress_temp_path, payload, *, open_fn=open, path_exists_fn=os.path.exists):
    if not progress_temp_path:
        return
    ensure_progress_sidecar_header(progress_temp_path, open_fn=open_fn, path_exists_fn=path_exists_fn)
    header = build_progress_state_header(payload)
    with open_fn(progress_temp_path, "r+", encoding="utf-8", errors="ignore") as fh:
        fh.seek(0)
        fh.write(header)
        fh.flush()


def read_progress_text(progress_temp_path, *, path_exists_fn=os.path.exists, open_fn=open):
    if not progress_temp_path:
        return ""
    active_path = progress_temp_path if path_exists_fn(progress_temp_path) else None
    if active_path is None:
        legacy_path = _build_legacy_progress_state_path(progress_temp_path)
        if legacy_path and path_exists_fn(legacy_path):
            active_path = legacy_path
        else:
            return ""
    with open_fn(active_path, "r", encoding="utf-8", errors="ignore") as fh:
        _, content = split_progress_file_content(fh.read())
        return content


def recover_completed_output_artifacts(
    *,
    output_path,
    temp_path,
    progress_temp_path,
    path_exists_fn=os.path.exists,
    replace_fn=os.replace,
    remove_fn=os.remove,
    log_cb=None,
):
    output_exists = bool(output_path and path_exists_fn(output_path))
    temp_exists = bool(temp_path and path_exists_fn(temp_path))
    progress_exists = bool(progress_temp_path and path_exists_fn(progress_temp_path))
    if not output_exists and temp_exists:
        replace_fn(temp_path, output_path)
        output_exists = True
        temp_exists = False
        if log_cb:
            log_cb(f"[Recovery] Materialized completed output from stranded temp file: {output_path}")
    if output_exists and progress_exists:
        try:
            remove_fn(progress_temp_path)
            if log_cb:
                log_cb(f"[Recovery] Removed stale completed progress sidecar: {progress_temp_path}")
        except Exception as cleanup_ex:
            if log_cb:
                log_cb(f"[Recovery] Warning: could not remove stale completed progress sidecar ({cleanup_ex})")
    return output_exists


def _compress_page_indices_to_scope(page_indices):
    if not page_indices:
        return ""
    parts = []
    start = prev = page_indices[0] + 1
    for idx in page_indices[1:]:
        page_num = idx + 1
        if page_num == prev + 1:
            prev = page_num
            continue
        parts.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = page_num
    parts.append(f"{start}-{prev}" if start != prev else str(start))
    return ",".join(parts)


def _load_pdf_resume_state(
    *,
    fp,
    progress_temp_path,
    job_cfg,
    path_exists_fn,
    open_fn,
    pdf_reader_factory,
    normalize_pdf_page_scope_text_fn,
    parse_pdf_page_scope_spec_fn,
):
    state_path = _build_progress_state_path(progress_temp_path)
    if not state_path or not path_exists_fn(progress_temp_path):
        return {"recovered_units": 0, "original_total_units": None, "resume_state_path": state_path, "resume_scope": None}
    state = read_progress_state(progress_temp_path, path_exists_fn=path_exists_fn, open_fn=open_fn)
    if not state:
        return {"recovered_units": 0, "original_total_units": None, "resume_state_path": state_path, "resume_scope": None}
    completed_pages = max(0, int(state.get("completed_pages", 0) or 0))
    if completed_pages <= 0:
        return {"recovered_units": 0, "original_total_units": None, "resume_state_path": state_path, "resume_scope": None}
    try:
        total_pdf_pages = len(pdf_reader_factory(fp).pages)
        original_scope = normalize_pdf_page_scope_text_fn(job_cfg.get("pdf_page_scope", ""))
        selected_page_indices = parse_pdf_page_scope_spec_fn(original_scope, total_pdf_pages)
    except Exception:
        return {"recovered_units": 0, "original_total_units": None, "resume_state_path": state_path, "resume_scope": None}
    total_units = len(selected_page_indices)
    if total_units <= 0:
        return {"recovered_units": 0, "original_total_units": None, "resume_state_path": state_path, "resume_scope": None}
    completed_pages = min(completed_pages, total_units)
    if completed_pages >= total_units:
        return {
            "recovered_units": completed_pages,
            "original_total_units": total_units,
            "resume_state_path": state_path,
            "resume_scope": "",
            "resume_complete": True,
        }
    remaining_indices = selected_page_indices[completed_pages:]
    return {
        "recovered_units": completed_pages,
        "original_total_units": total_units,
        "resume_state_path": state_path,
        "resume_scope": _compress_page_indices_to_scope(remaining_indices),
        "resume_complete": False,
    }


def _load_unit_resume_state(*, progress_temp_path, path_exists_fn, open_fn):
    state_path = _build_progress_state_path(progress_temp_path)
    if not state_path or not path_exists_fn(progress_temp_path):
        return {"recovered_units": 0, "original_total_units": None, "resume_state_path": state_path, "resume_from_unit": 0}
    state = read_progress_state(progress_temp_path, path_exists_fn=path_exists_fn, open_fn=open_fn)
    if not state:
        return {"recovered_units": 0, "original_total_units": None, "resume_state_path": state_path, "resume_from_unit": 0}
    completed_units = max(0, int(state.get("completed_units", state.get("completed_pages", 0)) or 0))
    total_units = max(0, int(state.get("total_units", state.get("total_pages", 0)) or 0))
    if completed_units <= 0:
        return {"recovered_units": 0, "original_total_units": None, "resume_state_path": state_path, "resume_from_unit": 0}
    if total_units and completed_units > total_units:
        completed_units = total_units
    return {
        "recovered_units": completed_units,
        "original_total_units": total_units or None,
        "resume_state_path": state_path,
        "resume_from_unit": completed_units,
    }


def load_merge_resume_state(*, progress_temp_path, expected_total_units, path_exists_fn, open_fn):
    state_path = _build_progress_state_path(progress_temp_path)
    default_result = {
        "recovered_units": 0,
        "original_total_units": expected_total_units or None,
        "resume_state_path": state_path,
        "completed_job_paths": [],
    }
    if not state_path or not path_exists_fn(progress_temp_path):
        return default_result
    state = read_progress_state(progress_temp_path, path_exists_fn=path_exists_fn, open_fn=open_fn)
    if not state:
        return default_result
    raw_completed_paths = state.get("completed_job_paths") or []
    completed_job_paths = []
    seen = set()
    for value in raw_completed_paths:
        path = str(value or "").strip()
        if not path or path in seen:
            continue
        seen.add(path)
        completed_job_paths.append(path)
    if not completed_job_paths:
        return default_result
    total_units = max(
        int(state.get("total_units", state.get("total_pages", 0)) or 0),
        int(expected_total_units or 0),
    )
    recovered_units = len(completed_job_paths)
    if total_units:
        recovered_units = min(recovered_units, total_units)
    return {
        "recovered_units": recovered_units,
        "original_total_units": total_units or None,
        "resume_state_path": state_path,
        "completed_job_paths": completed_job_paths,
    }


class BufferedOutputMemory(list):
    """Track streamed chunks while keeping RAM bounded for non-merge runs."""

    def __init__(self, *, file_obj=None, clear_every_pages=None, progress_temp_path=None):
        super().__init__()
        self.file_obj = file_obj
        self.clear_every_pages = clear_every_pages
        self.progress_temp_path = progress_temp_path
        self._pages_since_clear = 0

    def mark_page_processed(self):
        if not self.clear_every_pages:
            return False
        self._pages_since_clear += 1
        if self._pages_since_clear >= self.clear_every_pages:
            super().clear()
            self._pages_since_clear = 0
            return True
        return False

    def force_flush(self):
        if self.file_obj and not getattr(self.file_obj, "closed", False) and hasattr(self.file_obj, "flush"):
            self.file_obj.flush()

    def read_all_text(self):
        self.force_flush()
        if self.progress_temp_path and os.path.exists(self.progress_temp_path):
            return read_progress_text(self.progress_temp_path)
        return "".join(self)


class MirroredTextWriter:
    def __init__(self, primary_file_obj, progress_file_obj=None):
        self.primary_file_obj = primary_file_obj
        self.progress_file_obj = progress_file_obj

    @property
    def closed(self):
        return bool(getattr(self.primary_file_obj, "closed", False))

    def write(self, text):
        self.primary_file_obj.write(text)
        if self.progress_file_obj:
            self.progress_file_obj.write(text)

    def flush(self):
        if hasattr(self.primary_file_obj, "flush"):
            self.primary_file_obj.flush()
        if self.progress_file_obj and hasattr(self.progress_file_obj, "flush"):
            self.progress_file_obj.flush()

    def close(self):
        try:
            self.primary_file_obj.close()
        finally:
            if self.progress_file_obj and not getattr(self.progress_file_obj, "closed", False):
                self.progress_file_obj.close()


class MirroredProgressMemory(list):
    def __init__(self, *, progress_file_obj=None, progress_temp_path=None, retain_chunks=False):
        super().__init__()
        self.progress_file_obj = progress_file_obj
        self.progress_temp_path = progress_temp_path
        self.retain_chunks = retain_chunks
        self._char_count = 0

    def append(self, text):
        if not text:
            return
        if self.progress_file_obj:
            self.progress_file_obj.write(text)
            if hasattr(self.progress_file_obj, "flush"):
                self.progress_file_obj.flush()
        self._char_count += len(text)
        if self.retain_chunks:
            super().append(text)

    def checkpoint(self):
        return {"index": len(self), "char_count": self._char_count}

    def read_all_text(self):
        if (
            self.progress_file_obj
            and not getattr(self.progress_file_obj, "closed", False)
            and hasattr(self.progress_file_obj, "flush")
        ):
            self.progress_file_obj.flush()
        if self.progress_temp_path and os.path.exists(self.progress_temp_path):
            return read_progress_text(self.progress_temp_path)
        return "".join(self)

    def read_text_since(self, checkpoint):
        if self.retain_chunks:
            return "".join(self[checkpoint["index"] :])
        return self.read_all_text()[checkpoint["char_count"] :]


def estimate_current_file_total_units(
    ext,
    path,
    job_cfg,
    *,
    pdf_reader_factory,
    normalize_pdf_page_scope_text_fn,
    parse_pdf_page_scope_spec_fn,
    pptx_slide_count_fn,
    estimate_text_work_units_fn=None,
):
    if ext == ".pdf":
        try:
            pdf_reader = pdf_reader_factory(path)
            total_pdf_pages = len(pdf_reader.pages)
            page_scope = normalize_pdf_page_scope_text_fn(job_cfg.get("pdf_page_scope", ""))
            selected_pdf_pages = parse_pdf_page_scope_spec_fn(page_scope, total_pdf_pages)
            return {
                "total_units": max(1, len(selected_pdf_pages)),
                "selected_scope": page_scope,
                "selected_count": len(selected_pdf_pages),
                "source_total": total_pdf_pages,
                "unit_label": "page(s)",
            }
        except Exception:
            return {"total_units": 1, "selected_scope": "", "selected_count": 0, "source_total": 0, "unit_label": "page(s)"}
    if ext in [".docx", ".txt", ".md", ".rtf", ".csv", ".js", ".xlsx", ".xls", ".epub"]:
        if estimate_text_work_units_fn is not None:
            try:
                total_units = max(1, int(estimate_text_work_units_fn(path, ext, job_cfg)))
                return {"total_units": total_units, "selected_scope": "", "selected_count": 0, "source_total": 0, "unit_label": "chunk(s)"}
            except Exception:
                pass
        return {"total_units": 1, "selected_scope": "", "selected_count": 0, "source_total": 0, "unit_label": "file unit(s)"}
    if ext in [".pptx", ".ppt"]:
        if estimate_text_work_units_fn is not None:
            try:
                total_units = max(1, int(estimate_text_work_units_fn(path, ext, job_cfg)))
                return {"total_units": total_units, "selected_scope": "", "selected_count": 0, "source_total": 0, "unit_label": "chunk(s)"}
            except Exception:
                pass
        try:
            if ext == ".ppt":
                return {"total_units": 1, "selected_scope": "", "selected_count": 0, "source_total": 1, "unit_label": "slide(s)"}
            return {"total_units": max(1, int(pptx_slide_count_fn(path))), "selected_scope": "", "selected_count": 0, "source_total": 0, "unit_label": "slide(s)"}
        except Exception:
            return {"total_units": 1, "selected_scope": "", "selected_count": 0, "source_total": 0, "unit_label": "slide(s)"}
    return {"total_units": 1, "selected_scope": "", "selected_count": 0, "source_total": 0, "unit_label": "page(s)"}


def prepare_job_execution_context(
    job,
    *,
    cfg,
    resume_mode,
    low_memory_mode,
    low_memory_pdf_audit_skip_mb,
    custom_dest,
    dest_mode,
    merge_mode,
    master_output_path,
    master_temp_path,
    master_file_obj,
    master_memory,
    streamable_formats,
    supported_extensions,
    normalize_row_settings_fn,
    build_prompt_fn,
    model_from_label_fn,
    get_client_fn,
    determine_needs_pdf_audit_fn,
    compute_target_dir_fn,
    resolve_output_path_fn,
    write_header_fn,
    get_output_lang_code_fn,
    get_output_text_direction_fn,
    pdf_reader_factory=None,
    normalize_pdf_page_scope_text_fn=None,
    parse_pdf_page_scope_spec_fn=None,
    set_queue_status_fn,
    log_cb,
    makedirs_fn=os.makedirs,
    path_exists_fn=os.path.exists,
    remove_fn=os.remove,
    replace_fn=os.replace,
    open_fn=open,
):
    qidx = job.get('_queue_index', 0)
    fp = job['path']
    fn = os.path.basename(fp)
    base, ext = os.path.splitext(fn)[0], os.path.splitext(fn)[1].lower()

    if not path_exists_fn(fp):
        set_queue_status_fn(qidx, 'Missing')
        log_cb(f'Missing file: {fp}')
        return {'skip': True, 'qidx': qidx, 'path': fp, 'file_name': fn, 'base': base, 'ext': ext}
    if ext not in supported_extensions:
        set_queue_status_fn(qidx, 'Unsupported')
        log_cb(f'Unsupported file type: {fn}')
        return {'skip': True, 'qidx': qidx, 'path': fp, 'file_name': fn, 'base': base, 'ext': ext}

    row_settings = normalize_row_settings_fn(job)
    job_cfg = dict(cfg)
    job_cfg.update(row_settings)
    fmt = str(job_cfg.get('format_type', cfg.get('format_type', 'html')))
    model = str(job_cfg.get('model_name') or model_from_label_fn(job['engine']))
    routing = select_execution_model_for_job(
        fp,
        ext,
        job_cfg,
        model,
        pdf_reader_factory=pdf_reader_factory,
        normalize_pdf_page_scope_text_fn=normalize_pdf_page_scope_text_fn,
        parse_pdf_page_scope_spec_fn=parse_pdf_page_scope_spec_fn,
    )
    model = str(routing.get("model_name") or model)
    job_cfg["selected_model_name"] = model
    job_cfg["routing_mode"] = routing.get("routing_mode", "automatic")
    job_cfg["routing_reason"] = routing.get("routing_reason", "")
    job_cfg["auto_escalation_model"] = routing.get("auto_escalation_model")
    client = get_client_fn(model)
    needs_pdf_audit, file_size_mb = determine_needs_pdf_audit_fn(
        ext,
        cfg,
        low_memory_mode=low_memory_mode,
        path=fp,
        low_memory_pdf_audit_skip_mb=low_memory_pdf_audit_skip_mb,
    )
    if ext == '.pdf' and not needs_pdf_audit and low_memory_mode and file_size_mb >= low_memory_pdf_audit_skip_mb:
        log_cb(f'[Low-Memory] Skipping PDF text-layer audit for large file ({file_size_mb:.1f} MB): {fn}')

    if merge_mode:
        output_path = master_output_path
        temp_path = master_temp_path or master_output_path
        file_obj = master_file_obj
        progress_temp_path = None
        progress_file_obj = None
        if fmt in streamable_formats:
            memory = [] if needs_pdf_audit else None
        else:
            memory = master_memory
    else:
        target_dir = compute_target_dir_fn(
            job,
            custom_dest=custom_dest,
            dest_mode=dest_mode,
            preserve_source_structure=bool(cfg.get('preserve_source_structure', True)),
        )
        makedirs_fn(target_dir, exist_ok=True)
        output_base = build_output_base_name(
            base,
            ext,
            job_cfg,
            normalize_pdf_page_scope_text_fn=normalize_pdf_page_scope_text_fn,
        )
        output_plan = resolve_output_path_fn(
            output_base,
            fmt,
            target_dir,
            collision_mode=cfg.get('collision_mode'),
        )
        output_path = output_plan['output_path']
        if output_plan['should_skip']:
            set_queue_status_fn(qidx, 'Skipped')
            log_cb(
                f"Skipped {fn}: output already exists at {output_path} and File Collisions is set to Skip."
            )
            return {
                'skip': True,
                'qidx': qidx,
                'path': fp,
                'file_name': fn,
                'base': base,
                'ext': ext,
                'output_path': output_path,
            }

        temp_path = output_path + '.tmp'
        progress_temp_path = resolve_progress_temp_path(output_path, path_exists_fn=path_exists_fn)
        resume_info = {"recovered_units": 0, "original_total_units": None, "resume_state_path": _build_progress_state_path(progress_temp_path), "resume_from_unit": 0}
        if (
            resume_mode
            and ext == '.pdf'
            and pdf_reader_factory is not None
            and normalize_pdf_page_scope_text_fn is not None
            and parse_pdf_page_scope_spec_fn is not None
        ):
            resume_info = _load_pdf_resume_state(
                fp=fp,
                progress_temp_path=progress_temp_path,
                job_cfg=job_cfg,
                path_exists_fn=path_exists_fn,
                open_fn=open_fn,
                pdf_reader_factory=pdf_reader_factory,
                normalize_pdf_page_scope_text_fn=normalize_pdf_page_scope_text_fn,
                parse_pdf_page_scope_spec_fn=parse_pdf_page_scope_spec_fn,
            )
            if resume_info.get("resume_complete"):
                recover_completed_output_artifacts(
                    output_path=output_path,
                    temp_path=temp_path,
                    progress_temp_path=progress_temp_path,
                    path_exists_fn=path_exists_fn,
                    replace_fn=replace_fn,
                    remove_fn=remove_fn,
                    log_cb=log_cb,
                )
                set_queue_status_fn(qidx, 'Done')
                log_cb(f"Recovered completed PDF task from progress sidecar: {fn}")
                return {
                    'skip': True,
                    'qidx': qidx,
                    'path': fp,
                    'file_name': fn,
                    'base': base,
                    'ext': ext,
                    'output_path': output_path,
                }
            if resume_info.get("resume_scope"):
                job_cfg["pdf_page_scope"] = resume_info["resume_scope"]
                log_cb(
                    f"[Resume] Found preserved PDF progress for {fn}. "
                    f"Recovered {resume_info['recovered_units']} of {resume_info['original_total_units']} pages; "
                    f"continuing with pages {resume_info['resume_scope']}."
                )

        if resume_mode and ext in ['.docx', '.txt', '.md', '.rtf', '.csv', '.js', '.xlsx', '.xls', '.epub', '.pptx', '.ppt']:
            resume_info = _load_unit_resume_state(
                progress_temp_path=progress_temp_path,
                path_exists_fn=path_exists_fn,
                open_fn=open_fn,
            )
            if resume_info.get("recovered_units", 0) > 0:
                log_cb(
                    f"[Resume] Found preserved progress for {fn}. "
                    f"Recovered {resume_info['recovered_units']} of {resume_info.get('original_total_units') or '?'} units; "
                    "continuing from the next remaining unit."
                )

        preserve_progress = bool(
            resume_mode
            and ext in ['.pdf', '.docx', '.txt', '.md', '.rtf', '.csv', '.js', '.xlsx', '.xls', '.epub', '.pptx', '.ppt']
            and resume_info.get('recovered_units', 0) > 0
            and path_exists_fn(progress_temp_path)
            and (fmt not in streamable_formats or path_exists_fn(temp_path))
        )
        if path_exists_fn(temp_path) and not preserve_progress:
            remove_fn(temp_path)
        if path_exists_fn(progress_temp_path) and not preserve_progress:
            remove_fn(progress_temp_path)
        if preserve_progress:
            ensure_progress_sidecar_header(progress_temp_path, open_fn=open_fn, path_exists_fn=path_exists_fn)
        progress_file_obj = open_fn(progress_temp_path, 'a' if preserve_progress else 'w', encoding='utf-8')
        if not preserve_progress and progress_file_obj is not None and hasattr(progress_file_obj, "write"):
            progress_file_obj.write(build_progress_state_header({}))
            if hasattr(progress_file_obj, "flush"):
                progress_file_obj.flush()
        raw_file_obj = open_fn(temp_path, 'a' if preserve_progress else 'w', encoding='utf-8') if fmt in streamable_formats else None
        file_obj = MirroredTextWriter(raw_file_obj, progress_file_obj) if raw_file_obj else None
        log_cb(f"[Progress] In-progress recovery sidecar: {progress_temp_path}")
        if file_obj and not preserve_progress:
            write_header_fn(file_obj, base, fmt, get_output_lang_code_fn(job_cfg), get_output_text_direction_fn(job_cfg))
        if fmt in streamable_formats:
            if needs_pdf_audit:
                memory = BufferedOutputMemory(
                    file_obj=file_obj,
                    clear_every_pages=2,
                    progress_temp_path=progress_temp_path,
                )
            else:
                memory = None
        else:
            memory = MirroredProgressMemory(
                progress_file_obj=progress_file_obj,
                progress_temp_path=progress_temp_path,
                retain_chunks=False,
            )
    prompt = build_prompt_fn(job_cfg)

    return {
        'skip': False,
        'qidx': qidx,
        'path': fp,
        'file_name': fn,
        'base': base,
        'ext': ext,
        'job_cfg': job_cfg,
        'fmt': fmt,
        'prompt': prompt,
        'model': model,
        'routing_mode': job_cfg.get('routing_mode', 'automatic'),
        'routing_reason': job_cfg.get('routing_reason', ''),
        'auto_escalation_model': job_cfg.get('auto_escalation_model'),
        'client': client,
        'needs_pdf_audit': needs_pdf_audit,
        'file_size_mb': file_size_mb,
        'output_path': output_path,
        'temp_path': temp_path,
        'progress_temp_path': progress_temp_path,
        'resume_state_path': _build_progress_state_path(progress_temp_path),
        'recovered_units': resume_info.get('recovered_units', 0) if not merge_mode else 0,
        'original_total_units': resume_info.get('original_total_units') if not merge_mode else None,
        'resume_from_unit': resume_info.get('resume_from_unit', 0) if not merge_mode else 0,
        'progress_file_obj': progress_file_obj,
        'file_obj': file_obj,
        'memory': memory,
    }
