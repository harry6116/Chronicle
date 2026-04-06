import json
import os
import platform
import re
import shutil
import subprocess


def _run_command_capture(cmd, timeout=20):
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, (proc.stdout or ""), (proc.stderr or "")
    except Exception as ex:
        return 1, "", str(ex)


def run_command_capture(cmd, timeout=20):
    return _run_command_capture(cmd, timeout=timeout)


def _contains_scanner_keyword(text):
    t = (text or "").lower()
    keywords = (
        "scanner",
        "scanjet",
        "canoscan",
        "perfection",
        "imageclass",
        "mfp",
        "all-in-one",
        "flatbed",
    )
    return any(k in t for k in keywords)


def _append_unique_scanner(scanners, seen, name, manufacturer="", source="", details="", force=False):
    disp_name = (name or "").strip()
    if not disp_name:
        return
    if not force and not _contains_scanner_keyword(f"{disp_name} {manufacturer} {details}"):
        return
    dedupe_key = f"{disp_name.lower()}|{(manufacturer or '').strip().lower()}"
    if dedupe_key in seen:
        return
    seen.add(dedupe_key)
    scanners.append(
        {
            "name": disp_name,
            "manufacturer": (manufacturer or "").strip(),
            "source": source,
            "details": (details or "").strip(),
        }
    )


def _walk_macos_profiler_items(node, scanners, seen, source):
    if isinstance(node, list):
        for item in node:
            _walk_macos_profiler_items(item, scanners, seen, source)
        return
    if not isinstance(node, dict):
        return

    name = str(node.get("_name") or node.get("device_name") or node.get("spphysicalloc") or "").strip()
    manufacturer = str(node.get("manufacturer") or node.get("spmanufacturer") or "").strip()
    details_blob = " ".join(str(v) for v in node.values() if isinstance(v, (str, int, float)))
    _append_unique_scanner(scanners, seen, name, manufacturer, source, details_blob)

    for val in node.values():
        if isinstance(val, (list, dict)):
            _walk_macos_profiler_items(val, scanners, seen, source)


def candidate_naps2_commands():
    commands = []
    system_name = platform.system()
    if system_name == "Windows":
        candidates = [
            shutil.which("naps2.console"),
            shutil.which("naps2.console.exe"),
            shutil.which("NAPS2.Console.exe"),
            r"C:\Program Files\NAPS2\NAPS2.Console.exe",
            r"C:\Program Files (x86)\NAPS2\NAPS2.Console.exe",
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                commands.append([candidate])
    elif system_name == "Darwin":
        candidates = [
            shutil.which("naps2"),
            shutil.which("naps2.console"),
            "/Applications/NAPS2.app/Contents/MacOS/NAPS2",
            os.path.expanduser("~/Applications/NAPS2.app/Contents/MacOS/NAPS2"),
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                commands.append([candidate, "console"])
    else:
        candidates = [shutil.which("naps2"), shutil.which("naps2.console")]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                commands.append([candidate, "console"])

    deduped = []
    seen = set()
    for cmd in commands:
        key = tuple(cmd)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cmd)
    return deduped


def _parse_naps2_device_lines(output):
    devices = []
    for raw_line in (output or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith(("driver:", "available devices", "devices:")):
            continue
        if "no devices" in low:
            continue
        line = re.sub(r"^\d+\.\s*", "", line)
        line = line.lstrip("- ").strip()
        if line:
            devices.append(line)
    return devices


def discover_scanners_naps2():
    scanners = []
    seen = set()
    commands = candidate_naps2_commands()
    if not commands:
        return scanners, "NAPS2 console was not found in PATH or standard install locations."

    system_name = platform.system()
    if system_name == "Windows":
        drivers = ["wia", "twain", "escl"]
    elif system_name == "Darwin":
        drivers = ["apple", "escl", "sane", "twain"]
    else:
        drivers = ["escl", "sane", "twain", "wia", "apple"]

    errors = []
    for base_cmd in commands:
        for driver in drivers:
            cmd = [*base_cmd, "--listdevices", "--driver", driver]
            code, out, err = _run_command_capture(cmd, timeout=30)
            if code != 0 and not out.strip():
                if err.strip():
                    errors.append(f"{' '.join(base_cmd)} [{driver}]: {err.strip()}")
                continue
            for name in _parse_naps2_device_lines(out):
                _append_unique_scanner(
                    scanners,
                    seen,
                    name=name,
                    manufacturer="",
                    source=f"NAPS2 {driver.upper()}",
                    details="",
                    force=True,
                )
        if scanners:
            return scanners, None

    if errors:
        return scanners, errors[0]
    return scanners, "NAPS2 did not report any scanner devices."


def discover_scanners_windows():
    scanners = []
    seen = set()
    cmd = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "$ErrorActionPreference='SilentlyContinue';"
            "$d=Get-PnpDevice -PresentOnly | "
            "Where-Object { $_.Class -eq 'Image' -or $_.FriendlyName -match 'scan|scanner|scanjet|canoscan|perfection|flatbed|mfp' } | "
            "Select-Object FriendlyName,Manufacturer,Status,Class;"
            "if(-not $d){"
            "$d=Get-CimInstance Win32_PnPEntity | "
            "Where-Object { $_.PNPClass -eq 'Image' -or $_.Name -match 'scan|scanner|scanjet|canoscan|perfection|flatbed|mfp' } | "
            "Select-Object @{N='FriendlyName';E={$_.Name}},Manufacturer,Status,@{N='Class';E={$_.PNPClass}}"
            "};"
            "$d | ConvertTo-Json -Compress"
        ),
    ]
    code, out, err = _run_command_capture(cmd, timeout=25)
    if code != 0 and not out.strip():
        return scanners, f"Windows scanner query failed: {err.strip() or 'unknown error'}"
    payload = out.strip()
    if not payload:
        return scanners, None
    try:
        parsed = json.loads(payload)
    except Exception:
        return scanners, "Windows scanner query returned non-JSON output."
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return scanners, None

    for item in parsed:
        if not isinstance(item, dict):
            continue
        name = str(item.get("FriendlyName") or "").strip()
        manu = str(item.get("Manufacturer") or "").strip()
        status = str(item.get("Status") or "").strip()
        cls = str(item.get("Class") or "").strip()
        _append_unique_scanner(scanners, seen, name, manu, "Windows PnP", f"{status} {cls}")
    return scanners, None


def discover_scanners_macos():
    scanners = []
    seen = set()
    cmd = ["system_profiler", "SPUSBDataType", "SPPrintersDataType", "-json"]
    code, out, err = _run_command_capture(cmd, timeout=30)
    if code != 0 and not out.strip():
        return scanners, f"macOS scanner query failed: {err.strip() or 'unknown error'}"
    payload = out.strip()
    if not payload:
        return scanners, None
    try:
        parsed = json.loads(payload)
    except Exception:
        return scanners, "macOS scanner query returned non-JSON output."

    usb_items = parsed.get("SPUSBDataType", [])
    printer_items = parsed.get("SPPrintersDataType", [])
    _walk_macos_profiler_items(usb_items, scanners, seen, "macOS USB")
    _walk_macos_profiler_items(printer_items, scanners, seen, "macOS Printers")
    return scanners, None


def discover_connected_flatbed_scanners():
    naps2_scanners, naps2_err = discover_scanners_naps2()
    if naps2_scanners:
        return naps2_scanners, None

    system_name = platform.system()
    if system_name == "Windows":
        scanners, fallback_err = discover_scanners_windows()
    elif system_name == "Darwin":
        scanners, fallback_err = discover_scanners_macos()
    else:
        return [], f"Scanner discovery is currently supported on Windows and macOS only (detected: {system_name})."

    if scanners:
        if naps2_err:
            return scanners, f"NAPS2 discovery unavailable ({naps2_err}). Showing OS fallback results."
        return scanners, fallback_err

    if naps2_err and fallback_err:
        return scanners, f"NAPS2: {naps2_err} | Fallback: {fallback_err}"
    return scanners, naps2_err or fallback_err


def driver_from_scanner_source(source):
    text = (source or "").strip().lower()
    if text.startswith("naps2 "):
        return text.split(" ", 1)[1].strip()
    return ""
