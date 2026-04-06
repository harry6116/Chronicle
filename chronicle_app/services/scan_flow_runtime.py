import os
import time


def apply_scan_settings(cfg, *, scanner, dpi, output_dir, preset_label, driver_from_source_fn):
    updated = dict(cfg)
    updated["scan_output_dir"] = output_dir
    updated["scan_dpi"] = dpi
    updated["scan_last_device"] = scanner.get("name", "")
    updated["scan_last_driver"] = driver_from_source_fn(scanner.get("source", ""))
    updated["scan_last_preset"] = preset_label
    updated["scan_auto_start"] = False
    updated["scan_extract_mode"] = "manual"
    updated["scan_merge_before_queue"] = False
    updated["scan_merge_extract_output"] = False
    return updated


def build_scan_start_message(scanner, dpi, preset_label):
    return f"Starting NAPS2 scan import ({scanner.get('name', 'Unknown device')}, {dpi} DPI, {preset_label})..."


def begin_scan_session(output_dir, *, listdir=os.listdir, isfile=os.path.isfile, join=os.path.join, time_module=time):
    before_paths = set(
        join(output_dir, name)
        for name in listdir(output_dir)
        if isfile(join(output_dir, name))
    )
    started_ts = time_module.time()
    stamp = time_module.strftime("%Y%m%d_%H%M%S")
    output_pdf = join(output_dir, f"scan_{stamp}.pdf")
    return {
        "before_paths": before_paths,
        "started_ts": started_ts,
        "output_pdf": output_pdf,
    }


def resolve_scan_driver(scanner, cfg, *, driver_from_source_fn):
    return driver_from_source_fn(scanner.get("source", "")) or str(cfg.get("scan_last_driver", "")).strip().lower()


def choose_scan_commands(commands):
    return list(commands or [])


def execute_scan_commands(commands, *, attempt_scan_fn, scanner_name, driver, dpi, output_pdf, log_cb):
    if not commands:
        return {"success": False, "error_kind": "missing_executable", "details": "NAPS2 console was not found. Install NAPS2 and try again."}
    last_err = ""
    for base_cmd in commands:
        ok, used_cmd, out, err = attempt_scan_fn(base_cmd, scanner_name, driver, dpi, output_pdf)
        if ok:
            log_cb(f"NAPS2 command succeeded: {' '.join(used_cmd)}")
            return {"success": True, "used_cmd": used_cmd, "details": out or err or ""}
        last_err = err
    return {"success": False, "error_kind": "command_failed", "details": last_err}


def resolve_scan_output_files(output_dir, before_paths, started_ts, output_pdf, *, collect_scan_files_fn, path_exists=os.path.exists):
    new_files = collect_scan_files_fn(output_dir, before_paths, started_ts)
    if not new_files and path_exists(output_pdf):
        new_files = [output_pdf]
    return list(new_files)


def build_scan_completion_message(paths, added_paths):
    return (
        f"Scan complete.\n\nDetected {len(paths)} file(s).\nAdded {len(added_paths)} file(s) to queue.",
        f"Scan complete. Added {len(added_paths)} file(s) from NAPS2 output.",
    )
