import json
import os
import time


def build_session_payload(schema_version, cfg, queue, is_running, is_paused):
    return {
        "schema_version": schema_version,
        "updated_at": time.time(),
        "cfg": cfg,
        "queue": queue,
        "is_running": is_running,
        "is_paused": is_paused,
    }


def save_active_session_file(session_file, payload, *, session_lock):
    tmp_path = session_file + ".tmp"
    with session_lock:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp_path, session_file)


def delete_active_session_file(session_file):
    if os.path.exists(session_file):
        os.remove(session_file)


def has_incomplete_items(queue_rows, terminal_statuses):
    for row in queue_rows:
        status = str(row.get("status", "Queued"))
        if status not in terminal_statuses:
            return True
    return False


def restore_session_queue(queue_rows, cfg, *, row_setting_keys, label_from_model_fn):
    restored = []
    for row in queue_rows:
        if not isinstance(row, dict):
            continue
        path = row.get("path")
        if not path:
            continue
        row_settings = row.get("settings") if isinstance(row.get("settings"), dict) else {}
        restored.append(
            {
                "path": path,
                "engine": row.get("engine", label_from_model_fn(cfg.get("model_name", "gemini-2.5-flash"))),
                "settings": {key: row_settings.get(key) for key in row_setting_keys if key in row_settings},
                "status": row.get("status", "Queued"),
                "source_root": row.get("source_root"),
            }
        )
    for row in restored:
        if row.get("status") in {"Processing", "Paused"}:
            row["status"] = "Queued"
    return restored
