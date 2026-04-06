import os


def build_queue_accessibility_name(row_count, selected_count):
    if row_count <= 0:
        return "Files Table (empty queue)"
    row_label = "row" if row_count == 1 else "rows"
    selected_label = "selected" if selected_count != 1 else "selected"
    return f"Files Table ({row_count} {row_label}, {selected_count} {selected_label})"


def build_queue_accessibility_description(row_count, selected_count, current_row_summary=""):
    if row_count <= 0:
        return "Queue is empty. Use Add Files or Add Folder to load items."
    row_phrase = "row is" if row_count == 1 else "rows are"
    selected_phrase = "row is" if selected_count == 1 else "rows are"
    base = (
        f"{row_count} queued rows are available. "
        "This queue lists columns Name, Reading Settings, and Status. "
        f"{selected_count} {selected_phrase} currently selected. "
        "Task Actions for selected file commands are available from the toolbar or context menu."
    )
    if current_row_summary:
        base += f" Current row: {current_row_summary}"
    return base


def get_queue_display_status(row):
    status = str(row.get("status", "Queued"))
    if status == "Done" and row.get("review_recommended"):
        return "Done (Review)"
    return status


def build_queue_current_row_announcement(frame):
    if not getattr(frame, "queue", None):
        return "Queue empty. Use Add Files or Add Folder to load items."
    row_index = frame.GetQueueCurrentRowIndex()
    if row_index is None or row_index < 0 or row_index >= len(frame.queue):
        row_index = 0
    row = frame.queue[row_index]
    settings = frame.NormalizeRowSettings(row)
    file_name = os.path.basename(row.get("path", "")) or "Untitled item"
    status = frame.GetQueueDisplayStatus(row)
    return (
        f"Row {row_index + 1} of {len(frame.queue)}. "
        f"File: {file_name}. "
        f"Reading settings: {frame.FormatRowSettingsSummary(settings)}. "
        f"Status: {status}."
    )


def ensure_queue_table_landing(frame, focus=False, select_row=True):
    file_list = getattr(frame, "file_list", None)
    if file_list is None:
        return False
    queue = getattr(frame, "queue", [])
    if not queue:
        if hasattr(file_list, "UnselectAll"):
            file_list.UnselectAll()
        if hasattr(file_list, "GetItemCount") and file_list.GetItemCount() > 0 and hasattr(file_list, "RowToItem"):
            item = file_list.RowToItem(0)
            if hasattr(file_list, "SetCurrentItem"):
                file_list.SetCurrentItem(item)
            if hasattr(file_list, "EnsureVisible"):
                file_list.EnsureVisible(item)
        if focus and hasattr(file_list, "SetFocus"):
            file_list.SetFocus()
        return True

    selected = frame.GetSelectedIndices()
    target_row = selected[0] if selected else 0

    if hasattr(file_list, "RowToItem"):
        item = file_list.RowToItem(target_row)
        if select_row and hasattr(file_list, "SelectRow"):
            file_list.SelectRow(target_row)
        if hasattr(file_list, "SetCurrentItem"):
            file_list.SetCurrentItem(item)
        if hasattr(file_list, "EnsureVisible"):
            file_list.EnsureVisible(item)
    else:
        if select_row:
            try:
                file_list.SetSelection(target_row)
            except Exception:
                pass
        try:
            file_list.SetFirstItem(target_row)
        except Exception:
            pass
    if focus and hasattr(file_list, "SetFocus"):
        file_list.SetFocus()
    return True
