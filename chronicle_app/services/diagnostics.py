import difflib
import json
import os
import time
import zipfile

from chronicle_app.services.security import redact_sensitive, sanitize_log_text


def build_provider_capability_matrix(keys, *, has_provider_key_fn=None):
    provider_rows = [
        ("Google Gemini", "gemini", "Gemini 2.5 Flash / Gemini 2.5 Pro", "Best default path for PDFs; paid setup is safer for sustained hard batches."),
        ("Anthropic Claude", "claude", "Claude Sonnet 4", "Strong structured fallback; API billing is separate from Claude chat plans."),
        ("OpenAI", "openai", "GPT-4o", "General multimodal fallback; Chronicle still treats OpenAI PDF handling as a fallback path."),
    ]
    lines = ["Provider Capability Matrix", ""]
    for label, vendor, models, note in provider_rows:
        configured = has_provider_key_fn(vendor) if has_provider_key_fn else bool((keys or {}).get(vendor))
        lines.append(f"{label}: {'configured' if configured else 'not configured'}")
        lines.append(f"  Models: {models}")
        lines.append(f"  Notes: {note}")
    return "\n".join(lines)


def build_resume_center_summary(session, *, terminal_statuses):
    if not isinstance(session, dict):
        return "No readable saved session was found."
    queue = session.get("queue", [])
    if not isinstance(queue, list) or not queue:
        return "No queued files are saved in the current session."
    terminal = set(terminal_statuses)
    active = []
    complete = 0
    for row in queue:
        status = str(row.get("status", "Queued"))
        name = os.path.basename(str(row.get("path", ""))) or "Untitled item"
        if status in terminal:
            complete += 1
        else:
            active.append(f"{name} ({status})")
    lines = [
        "Resume Center",
        f"Saved rows: {len(queue)}",
        f"Terminal rows: {complete}",
        f"Recoverable rows: {len(active)}",
    ]
    if active:
        lines.append("")
        lines.extend(active[:20])
        if len(active) > 20:
            lines.append(f"...and {len(active) - 20} more.")
    return "\n".join(lines)


def create_support_bundle(
    *,
    destination_dir,
    build_stamp,
    cfg,
    queue,
    processing_log_lines,
    session_file=None,
    provider_matrix_text="",
    time_module=time,
):
    os.makedirs(destination_dir, exist_ok=True)
    stamp = time_module.strftime("%Y%m%d_%H%M%S")
    bundle_path = os.path.join(destination_dir, f"chronicle_support_bundle_{stamp}.zip")
    summary = [
        "Chronicle Support Bundle",
        f"Build: {build_stamp}",
        f"Queued rows: {len(queue or [])}",
        f"Processing log lines: {len(processing_log_lines or [])}",
    ]
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("diagnostic_summary.txt", "\n".join(summary) + "\n")
        zf.writestr("provider_matrix.txt", str(provider_matrix_text or "").rstrip() + "\n")
        safe_processing_log = [sanitize_log_text(line) for line in (processing_log_lines or [])]
        zf.writestr("processing_log.txt", "\n".join(safe_processing_log).rstrip() + "\n")
        zf.writestr("config_redacted.json", json.dumps(redact_sensitive(cfg or {}), indent=2, sort_keys=True))
        zf.writestr("queue_redacted.json", json.dumps(redact_sensitive(queue or []), indent=2, sort_keys=True))
        if session_file and os.path.exists(session_file):
            try:
                with open(session_file, "r", encoding="utf-8") as fh:
                    session = json.load(fh)
                zf.writestr("active_session_redacted.json", json.dumps(redact_sensitive(session), indent=2, sort_keys=True))
            except Exception as ex:
                zf.writestr("active_session_read_error.txt", sanitize_log_text(ex))
    return bundle_path


def compare_output_files(path_a, path_b, *, max_diff_lines=80):
    with open(path_a, "r", encoding="utf-8", errors="ignore") as fh:
        left = fh.read().splitlines()
    with open(path_b, "r", encoding="utf-8", errors="ignore") as fh:
        right = fh.read().splitlines()
    diff = list(
        difflib.unified_diff(
            left,
            right,
            fromfile=os.path.basename(path_a),
            tofile=os.path.basename(path_b),
            lineterm="",
        )
    )
    shown = diff[:max_diff_lines]
    hidden = max(0, len(diff) - len(shown))
    summary = [
        "Output Comparison",
        f"Left lines: {len(left)}",
        f"Right lines: {len(right)}",
        f"Diff lines: {len(diff)}",
    ]
    if hidden:
        summary.append(f"Diff truncated: {hidden} additional line(s) not shown.")
    if shown:
        summary.append("")
        summary.extend(shown)
    else:
        summary.append("No text differences found.")
    return "\n".join(summary)
