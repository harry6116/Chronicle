import os
import platform
import subprocess


def should_start_mac_activity_guard(*, is_running, platform_system=None):
    if is_running:
        return False
    system = platform.system() if platform_system is None else platform_system
    return system == "Darwin"


def start_mac_activity_guard(
    *,
    current_process=None,
    is_running=False,
    platform_system=None,
    subprocess_popen=subprocess.Popen,
    log_cb=None,
):
    if current_process is not None and getattr(current_process, "poll", lambda: None)() is None:
        return current_process
    if not should_start_mac_activity_guard(is_running=is_running, platform_system=platform_system):
        return current_process
    try:
        process = subprocess_popen(
            ["caffeinate", "-dimsu", "-w", str(os.getpid())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if log_cb:
            log_cb("[Mac] Keeping Chronicle active during extraction so backgrounding the window does not pause provider/network work.")
        return process
    except Exception as ex:
        if log_cb:
            log_cb(f"[Mac] Warning: could not start background activity guard ({ex}).")
        return current_process


def stop_mac_activity_guard(process, *, log_cb=None):
    if process is None:
        return None
    try:
        if getattr(process, "poll", lambda: None)() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except Exception:
                process.kill()
    except Exception as ex:
        if log_cb:
            log_cb(f"[Mac] Warning: could not stop background activity guard ({ex}).")
    return None
