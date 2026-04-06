import json
import os
import re
import tempfile
import time


CONTINUITY_FILENAME = "CONTINUITY.md"
RUNTIME_STATUS_BEGIN = "<!-- CHRONICLE_RUNTIME_STATUS:BEGIN -->"
RUNTIME_STATUS_END = "<!-- CHRONICLE_RUNTIME_STATUS:END -->"
RUNTIME_STATUS_LABELS = (
    "Last app launch",
    "Last extraction start",
    "Last extraction completion",
    "Last extraction summary",
)


def load_json_file(filepath, default_val):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return default_val


def save_json_file(filepath, data):
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=4)


def resolve_continuity_file_path(*, script_dir):
    env_file = os.environ.get("CHRONICLE_CONTINUITY_FILE", "").strip()
    if env_file:
        return env_file

    env_dir = os.environ.get("CHRONICLE_CONTINUITY_DIR", "").strip()
    if env_dir:
        return os.path.join(env_dir, CONTINUITY_FILENAME)

    direct_path = os.path.join(script_dir, CONTINUITY_FILENAME)
    if os.path.exists(direct_path):
        return direct_path

    normalized_script_dir = os.path.abspath(str(script_dir))
    if ".app" in normalized_script_dir or "/Contents/" in normalized_script_dir:
        for candidate_root in _iter_continuity_search_roots(script_dir):
            candidate_path = os.path.join(candidate_root, CONTINUITY_FILENAME)
            if os.path.exists(candidate_path):
                return candidate_path
    return direct_path


def _iter_continuity_search_roots(script_dir):
    seen = set()
    candidates = [script_dir, os.getcwd()]
    for root in candidates:
        current = os.path.abspath(root)
        for _ in range(6):
            if current in seen:
                break
            seen.add(current)
            yield current
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent


def read_continuity_file(*, script_dir):
    continuity_path = resolve_continuity_file_path(script_dir=script_dir)
    if not os.path.exists(continuity_path):
        return continuity_path, None

    with open(continuity_path, "r", encoding="utf-8") as fh:
        return continuity_path, fh.read()


def emit_launch_continuity(*, script_dir, print_fn=print):
    continuity_path, continuity_text = read_continuity_file(script_dir=script_dir)
    print_fn(f"Chronicle repo root: {script_dir}")
    print_fn("")
    if continuity_text is None:
        print_fn(f"{CONTINUITY_FILENAME} not found at {continuity_path}.")
        return continuity_path, None

    print_fn(f"Loading {CONTINUITY_FILENAME} before launch.")
    print_fn("")
    print_fn(continuity_text)
    try:
        update_continuity_runtime_status(script_dir=script_dir, event="launch")
    except Exception:
        pass
    return continuity_path, continuity_text


def _format_runtime_status_timestamp(*, time_module=time):
    return time_module.strftime("%Y-%m-%d %H:%M:%S", time_module.localtime())


def _parse_runtime_status_block(text):
    if not text:
        return {}
    pattern = re.compile(
        rf"{re.escape(RUNTIME_STATUS_BEGIN)}\n?(.*?){re.escape(RUNTIME_STATUS_END)}",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return {}
    status = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line.startswith("- "):
            continue
        label, sep, value = line[2:].partition(":")
        if not sep:
            continue
        status[label.strip()] = value.strip()
    return status


def _render_runtime_status_block(status):
    normalized = dict(status or {})
    lines = [
        RUNTIME_STATUS_BEGIN,
        "## Runtime Status (Auto-updated)",
    ]
    for label in RUNTIME_STATUS_LABELS:
        lines.append(f"- {label}: {normalized.get(label, 'Not recorded')}")
    lines.append(RUNTIME_STATUS_END)
    return "\n".join(lines)


def update_continuity_runtime_status(*, script_dir, event, detail=None, time_module=time):
    continuity_path, continuity_text = read_continuity_file(script_dir=script_dir)
    if continuity_text is None:
        continuity_text = "# Chronicle Continuity\n"
    continuity_text = continuity_text.rstrip()
    status = _parse_runtime_status_block(continuity_text)
    timestamp = _format_runtime_status_timestamp(time_module=time_module)

    if event == "launch":
        status["Last app launch"] = timestamp
    elif event == "run_start":
        status["Last extraction start"] = timestamp
    elif event == "run_complete":
        status["Last extraction completion"] = timestamp
    else:
        raise ValueError(f"Unsupported continuity event: {event}")

    detail_text = str(detail or "").strip()
    if detail_text:
        status["Last extraction summary"] = detail_text

    block = _render_runtime_status_block(status)
    pattern = re.compile(
        rf"\n*{re.escape(RUNTIME_STATUS_BEGIN)}\n?.*?{re.escape(RUNTIME_STATUS_END)}",
        re.DOTALL,
    )
    if pattern.search(continuity_text):
        updated_text = pattern.sub(f"\n\n{block}", continuity_text, count=1).strip()
    else:
        updated_text = f"{continuity_text}\n\n{block}".strip()

    with open(continuity_path, "w", encoding="utf-8") as fh:
        fh.write(updated_text + "\n")
    return continuity_path, status


def get_runtime_build_stamp(*, script_dir, module_file, sys_executable, is_frozen):
    candidates = []
    if is_frozen:
        exe_dir = os.path.dirname(os.path.abspath(sys_executable))
        candidates.extend(
            [
                os.path.join(exe_dir, "build_stamp.txt"),
                os.path.abspath(os.path.join(exe_dir, "..", "Resources", "build_stamp.txt")),
                os.path.join(script_dir, "build_stamp.txt"),
            ]
        )
    else:
        candidates.append(os.path.join(script_dir, "build_stamp.txt"))

    for stamp_path in candidates:
        try:
            if os.path.exists(stamp_path):
                with open(stamp_path, "r", encoding="utf-8") as fh:
                    value = fh.read().strip()
                if value:
                    return value
        except Exception:
            pass

    try:
        target = sys_executable if is_frozen else module_file
        ts = os.path.getmtime(target)
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    except Exception:
        return "unknown"


def resolve_runtime_crash_log_path(*, app_name="Chronicle", platform_system=None, env=None, expanduser=None, tempdir=None):
    platform_name = platform_system or os.name
    platform_name = platform_name() if callable(platform_name) else platform_name
    env_map = env if env is not None else os.environ
    expanduser_fn = expanduser or os.path.expanduser
    tempdir_fn = tempdir or tempfile.gettempdir

    if platform_name == "Windows":
        base = env_map.get("LOCALAPPDATA") or env_map.get("APPDATA") or tempdir_fn()
        log_dir = os.path.join(base, app_name, "logs")
    elif platform_name == "Darwin":
        log_dir = os.path.join(expanduser_fn("~/Library/Logs"), app_name)
    else:
        base = env_map.get("XDG_STATE_HOME") or expanduser_fn("~/.local/state")
        log_dir = os.path.join(base, app_name, "logs")

    try:
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, "chronicle_crash.log")
    except Exception:
        return os.path.join(tempdir_fn(), "chronicle_crash.log")


def build_log_header(build_stamp, *, time_module=time):
    now_txt = time_module.strftime("%Y-%m-%d %H:%M:%S", time_module.localtime())
    return [
        "Chronicle Processing Log",
        f"Build: {build_stamp}",
        f"Generated: {now_txt}",
        "",
    ]


def resolve_default_log_directory(queue, cfg, script_dir):
    for item in queue:
        source_root = item.get("source_root")
        if source_root and os.path.isdir(source_root):
            return source_root
        scan_dir = os.path.dirname(item.get("path", ""))
        if scan_dir and os.path.isdir(scan_dir):
            return scan_dir
    if cfg.get("dest_mode", 0) == 1:
        custom_dest = str(cfg.get("custom_dest", "")).strip()
        if custom_dest and os.path.isdir(custom_dest):
            return custom_dest
    return script_dir


def write_processing_log(log_dir, build_stamp, processing_log_lines, *, time_module=time):
    os.makedirs(log_dir, exist_ok=True)
    stamp = time_module.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(log_dir, f"chronicle_processing_log_{stamp}.txt")
    with open(path, "w", encoding="utf-8") as fh:
        lines = build_log_header(build_stamp, time_module=time_module) + list(processing_log_lines)
        fh.write("\n".join(lines).rstrip() + "\n")
    return path
