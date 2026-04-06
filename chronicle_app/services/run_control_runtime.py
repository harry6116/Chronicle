def wait_while_paused(
    *,
    is_running,
    is_paused,
    stop_requested,
    heartbeat_ping,
    sleep_fn,
    stop_requested_error_cls,
):
    if stop_requested:
        raise stop_requested_error_cls("Stop requested by user.")
    while is_running and is_paused and not stop_requested:
        heartbeat_ping()
        sleep_fn(0.25)
    if stop_requested:
        raise stop_requested_error_cls("Stop requested by user.")


def build_running_state_update(running):
    updates = {"is_running": bool(running)}
    if not running:
        updates.update(
            {
                "is_paused": False,
                "stop_requested": False,
                "current_processing_index": -1,
                "current_file_page_total": 0,
                "current_file_page_done": 0,
                "current_file_ordinal": 0,
            }
        )
    return updates


def count_active_queue_items(queue, *, terminal_statuses):
    active_count = sum(1 for row in queue if str(row.get("status", "Queued")) not in set(terminal_statuses))
    return max(active_count, 1)


def count_saved_queue_items(queue, *, terminal_statuses):
    queued_count = sum(1 for row in queue if str(row.get("status", "Queued")) not in set(terminal_statuses))
    return max(queued_count, 1)


def pause_current_processing_row(queue, current_processing_index):
    if 0 <= current_processing_index < len(queue):
        queue[current_processing_index]["status"] = "Paused"
        return True
    return False


def prepare_running_close(choice, *, keep_open_value, save_exit_value, discard_exit_value, is_running=True):
    if choice == keep_open_value:
        return {
            "should_veto": True,
            "pause_run": False,
            "pause_current_row_directly": False,
            "save_session": False,
            "discard_session": False,
        }
    if choice == save_exit_value:
        return {
            "should_veto": False,
            "pause_run": bool(is_running),
            "pause_current_row_directly": bool(is_running),
            "save_session": True,
            "discard_session": False,
        }
    if choice == discard_exit_value:
        return {
            "should_veto": False,
            "pause_run": False,
            "pause_current_row_directly": False,
            "save_session": False,
            "discard_session": True,
        }
    return {
        "should_veto": True,
        "pause_run": False,
        "pause_current_row_directly": False,
        "save_session": False,
        "discard_session": False,
    }
