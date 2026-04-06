import time


def normalize_future_timestamp(value, *, now=None):
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return None
    current = time.time() if now is None else now
    if ts <= current:
        return None
    return ts


def format_timestamp_local(ts, *, time_module=time):
    return time_module.strftime("%Y-%m-%d %H:%M:%S", time_module.localtime(ts))


def build_schedule_summary_label(scheduled_start_ts, *, time_module=time):
    if scheduled_start_ts is None:
        return "No extraction scheduled."
    return f"Scheduled extraction: {format_timestamp_local(scheduled_start_ts, time_module=time_module)}"


def should_trigger_scheduled_start(scheduled_start_ts, *, is_running, scheduled_start_triggered, now=None):
    if scheduled_start_ts is None or is_running or scheduled_start_triggered:
        return False
    current = time.time() if now is None else now
    return current >= scheduled_start_ts
