import os
import re


def get_target_queue_indices_for_setting_change(queue, selected_indices, *, assignable_statuses=("Queued", "Paused")):
    selected = [idx for idx in selected_indices if 0 <= idx < len(queue)]
    allowed = set(assignable_statuses)
    if selected:
        assignable_selected = [idx for idx in selected if str(queue[idx].get("status", "Queued")) in allowed]
        if assignable_selected:
            return assignable_selected
        return selected
    return [
        idx for idx, row in enumerate(queue)
        if str(row.get("status", "Queued")) in allowed
    ]


def apply_settings_to_rows(queue, indices, settings, *, row_setting_keys, label_from_model_fn):
    for idx in indices:
        queue[idx]["settings"] = {key: settings.get(key) for key in row_setting_keys}
        queue[idx]["engine"] = label_from_model_fn(settings.get("model_name", "gemini-2.5-flash"))


def estimate_path_work_units(
    path,
    *,
    settings,
    pdf_reader_factory,
    normalize_pdf_page_scope_text_fn,
    parse_pdf_page_scope_spec_fn,
):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".pdf":
            reader = pdf_reader_factory(path)
            total_pages = len(reader.pages)
            page_scope = normalize_pdf_page_scope_text_fn((settings or {}).get("pdf_page_scope", ""))
            return max(1, len(parse_pdf_page_scope_spec_fn(page_scope, total_pages)))
    except Exception:
        return 1
    return 1


def refresh_queue_work_unit_estimates(queue, *, normalize_row_settings_fn, estimate_path_work_units_fn):
    for row in queue:
        row_path = row.get("path")
        if not row_path:
            row["_work_units"] = 1
            continue
        settings = normalize_row_settings_fn(row)
        row["_work_units"] = estimate_path_work_units_fn(row_path, settings=settings)


def get_run_unit_totals(
    queue,
    *,
    current_processing_index,
    current_file_page_done,
    terminal_statuses,
    completed_statuses=("Done", "Skipped", "Unsupported"),
):
    total_units = 0
    completed_units = 0
    processing_index = current_processing_index if 0 <= current_processing_index < len(queue) else -1
    completed = set(completed_statuses or ())
    for idx, row in enumerate(queue):
        units = max(1, int(row.get("_work_units", 1) or 1))
        total_units += units
        status = str(row.get("status", "Queued"))
        if status in completed:
            completed_units += units
        elif idx == processing_index:
            completed_units += max(0, min(units, int(current_file_page_done or 0)))
    return total_units, completed_units


def should_log_page_progress(done_pages, total_pages):
    if total_pages <= 20:
        return True
    if done_pages == 1 or done_pages == total_pages:
        return True
    if done_pages <= 20:
        return True
    return done_pages % 2 == 0


def should_status_echo_log(msg, *, engine_event=False):
    if not engine_event:
        return True
    noisy_prefixes = ("[Page]", "[Confidence]", "[Memory]")
    return not str(msg).startswith(noisy_prefixes)


def format_scan_log_message(msg):
    text = str(msg or "")
    if not text:
        return text

    def model_label(model):
        compact = str(model or "").strip()
        known = {
            "gemini-2.5-pro": "Gemini 2.5 Pro",
            "gemini-2.5-flash": "Gemini 2.5 Flash",
        }
        return known.get(compact.lower(), compact)

    def page_from_slice_name(name):
        match = re.search(r"_(\d+)_(\d+)\.pdf$", str(name or ""))
        if not match:
            return None
        first, last = match.groups()
        return first if first == last else f"{first}-{last}"

    match = re.match(r"^\[Mac\]\s*Keeping Chronicle active during extraction.*$", text)
    if match:
        return "Mac: preventing sleep or background pauses during extraction."

    match = re.match(r"^\[Progress\]\s*In-progress recovery file:\s*(.+)$", text)
    if match:
        return f"Progress backup: saving recoverable work to {match.group(1)}"

    match = re.match(
        r"^\[Gemini PDF\]\s*Uploading slice (.+?) \((\d+) bytes\)\.$",
        text,
    )
    if match:
        pdf_name, byte_count = match.groups()
        page = page_from_slice_name(pdf_name)
        size_kb = max(1, int(round(int(byte_count) / 1024)))
        if page:
            return f"Preparing PDF page {page} for Gemini ({size_kb} KB)."
        return f"Preparing PDF section for Gemini ({size_kb} KB)."

    match = re.match(r"^\[Gemini PDF\]\s*Waiting for slice (.+?) to become ready\.$", text)
    if match:
        page = page_from_slice_name(match.group(1))
        return f"Waiting for Gemini to accept PDF page {page}." if page else "Waiting for Gemini to accept the PDF section."

    match = re.match(r"^\[Gemini PDF\]\s*Slice (.+?) is ready\.$", text)
    if match:
        page = page_from_slice_name(match.group(1))
        return f"PDF page {page} is ready for reading." if page else "PDF section is ready for reading."

    match = re.match(
        r"^\[Gemini PDF\]\s*Requesting model output for page (\d+) of (\d+) pages via (.+?)\.$",
        text,
    )
    if match:
        page, total, model = match.groups()
        return f"Reading page {page} of {total} with {model_label(model)}."

    match = re.match(
        r"^\[Page\]\s*(\d+)/(\d+) pages processed \(source page (\d+), run total: (\d+)\)\.$",
        text,
    )
    if match:
        done, total, source_page, _run_total = match.groups()
        if done == source_page:
            return f"Finished page {done} of {total}."
        return f"Finished page {done} of {total} (source page {source_page})."

    match = re.match(
        r"^\[Memory\]\s*Cleared buffered page text at run page (\d+)(?: \(buffer cadence: every \d+ pages\))?\.$",
        text,
    )
    if match:
        return f"Memory: released temporary page text after page {match.group(1)}."

    match = re.match(
        r"^\[Gemini Image\] Requesting dense newspaper strip (\d+)/(\d+) for source page (\d+) via (?:streaming )?inline REST on (.+?)\.$",
        text,
    )
    if match:
        part_num, part_total, source_page, model = match.groups()
        return f"Scanning page {source_page}, part {part_num} of {part_total} with {model}."

    match = re.match(
        r"^\[Gemini Image\] Requesting dense newspaper page output for source page (\d+) via (?:streaming )?inline REST on (.+?)\.$",
        text,
    )
    if match:
        source_page, model = match.groups()
        return f"Scanning page {source_page} as a dense newspaper page with {model}."

    match = re.match(
        r"^\[Gemini Image\] Requesting full-page scanned image output for source page (\d+) via (?:streaming )?inline REST on (.+?)\.$",
        text,
    )
    if match:
        source_page, model = match.groups()
        return f"Scanning image-only page {source_page} with {model}."

    match = re.match(r"^\[Gemini Pro\] Still waiting for bounded (.+?) output \((.+?)\)\.$", text)
    if match:
        request_kind, timing = match.groups()
        return f"Still waiting for Gemini Pro {request_kind.lower()} output ({timing})."

    prefix_replacements = (
        (r"^\[PDF Heuristic\]\s*", "Preflight: "),
        (r"^\[Auto Engine\]\s*", "Routing: "),
        (r"^\[Gemini PDF\]\s*", "Gemini PDF: "),
        (r"^\[Gemini Image\]\s*", "Gemini image: "),
        (r"^\[OpenAI PDF\]\s*", "OpenAI PDF: "),
        (r"^\[Claude PDF\]\s*", "Claude PDF: "),
        (r"^\[FAIL-SAFE\]\s*", "Recovery: "),
        (r"^\[Gearshift Triggered\]\s*", "Retrying with a smaller PDF batch: "),
        (r"^\[Gearshift\]\s*", "Retry: "),
        (r"^\[Throttle\]\s*", "Waiting: "),
        (r"^\[Backpressure\]\s*", "Waiting: "),
        (r"^\[Rate Limit\]\s*", "Provider rate limit: "),
        (r"^\[Cache\]\s*", "Cache: "),
        (r"^\[Progress\]\s*", "Progress: "),
        (r"^\[Resume\]\s*", "Resume: "),
        (r"^\[Recovery\]\s*", "Recovery: "),
        (r"^\[Upload Wait\]\s*", "Upload wait: "),
        (r"^\[Finalize\]\s*", "Saving: "),
        (r"^\[Output QA\]\s*", "Output check: "),
        (r"^\[Audit\]\s*", "Output check: "),
        (r"^\[Scope\]\s*", "Page range: "),
        (r"^\[Quality\]\s*", "Image quality: "),
        (r"^\[Low-Memory\]\s*", "Memory guard: "),
        (r"^\[Mac\]\s*", "Mac: "),
        (r"^\[Image\]\s*", "Image: "),
    )
    for pattern, replacement in prefix_replacements:
        updated = re.sub(pattern, replacement, text)
        if updated != text:
            updated = re.sub(r"^Routing:\s+Routing\s+", "Routing: ", updated)
            return updated
    return text


def build_progress_summary(
    queue,
    *,
    current_processing_index,
    current_file_ordinal,
    current_file_page_total,
    current_file_page_done,
    terminal_statuses,
):
    total = len(queue)
    done = sum(1 for row in queue if row.get("status") == "Done")
    review = sum(1 for row in queue if row.get("status") == "Done" and row.get("review_recommended"))
    errors = sum(1 for row in queue if row.get("status") == "Error")
    paused = sum(1 for row in queue if row.get("status") == "Paused")
    stopped = sum(1 for row in queue if row.get("status") == "Stopped")
    queued = sum(1 for row in queue if row.get("status") == "Queued")
    processing = sum(1 for row in queue if row.get("status") == "Processing")
    terminal = sum(1 for row in queue if row.get("status") in set(terminal_statuses))
    total_units, completed_units = get_run_unit_totals(
        queue,
        current_processing_index=current_processing_index,
        current_file_page_done=current_file_page_done,
        terminal_statuses=terminal_statuses,
    )
    pct = int((completed_units / total_units) * 100) if total_units > 0 else 0
    page_detail = ""
    if current_file_ordinal > 0 and current_file_page_total > 0:
        current_path = ""
        if 0 <= current_processing_index < len(queue):
            current_path = str(queue[current_processing_index].get("path", "")).lower()
        page_label = "slides" if current_path.endswith((".pptx", ".ppt")) else "pages"
        page_detail = (
            f" Current file {current_file_ordinal}: "
            f"{current_file_page_done} of {current_file_page_total} {page_label}. "
            f"Completed work units: {completed_units} of {total_units}."
        )
    return (
        f"Progress {completed_units} of {total_units} work units ({pct}%). "
        f"Files done: {done} of {total}. Resolved: {terminal} of {total}. Processing: {processing}. Queued: {queued}. Paused: {paused}. "
        f"Done: {done}. Review: {review}. Stopped: {stopped}. Errors: {errors}.{page_detail}"
    )


def stop_selected_tasks(queue, selected_indices):
    stopped = 0
    includes_processing = False
    for idx in selected_indices:
        if not (0 <= idx < len(queue)):
            continue
        status = str(queue[idx].get("status", "Queued"))
        if status in {"Queued", "Paused"}:
            queue[idx]["status"] = "Stopped"
            stopped += 1
        elif status == "Processing":
            includes_processing = True
    return {"stopped": stopped, "includes_processing": includes_processing}


def pause_selected_tasks(queue, selected_indices):
    paused = 0
    for idx in selected_indices:
        if not (0 <= idx < len(queue)):
            continue
        status = str(queue[idx].get("status", "Queued"))
        if status in {"Queued", "Processing"}:
            queue[idx]["status"] = "Paused"
            paused += 1
    return paused


def resume_selected_tasks(queue, selected_indices):
    resumed = 0
    for idx in selected_indices:
        if not (0 <= idx < len(queue)):
            continue
        if str(queue[idx].get("status", "")) == "Paused":
            queue[idx]["status"] = "Queued"
            resumed += 1
    return resumed
