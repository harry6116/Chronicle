import wx

from chronicle_app.ui.queue_support import (
    build_queue_current_row_announcement,
    ensure_queue_table_landing,
    get_queue_display_status,
)


class QueuePanel(wx.Panel):
    def __init__(self, parent, frame, *, empty_placeholder):
        super().__init__(parent)
        self.frame = frame
        self.empty_placeholder = empty_placeholder

        root = wx.BoxSizer(wx.VERTICAL)

        instructions = wx.StaticText(
            self,
            label="Queue your files here, then press Start Reading when you are ready.",
        )
        instructions.SetName("Queue List Instructions")
        root.Add(instructions, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.empty_state = wx.StaticText(self, label=self.empty_placeholder)
        self.empty_state.SetName("Empty Queue Message")
        self.empty_state.Wrap(640)
        root.Add(self.empty_state, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.file_list = wx.ListBox(self, style=wx.LB_EXTENDED | wx.LB_HSCROLL)
        self.file_list.SetName("Files Queue")
        self.file_list.SetHelpText("Queued files list. Use arrow keys to move through queued items.")
        self.file_list.Bind(wx.EVT_KEY_DOWN, frame.OnQueueKeyDown)
        self.file_list.Bind(wx.EVT_LISTBOX, frame.OnQueueSelectionChanged)
        self.file_list.Bind(wx.EVT_LISTBOX_DCLICK, frame.OnFileActivated)
        self.file_list.Bind(wx.EVT_CONTEXT_MENU, frame.OnQueueItemContextMenu)
        root.Add(self.file_list, 1, wx.EXPAND | wx.ALL, 10)

        self.SetSizer(root)

    def GetSelectedIndices(self):
        if not self.frame.queue:
            return []
        if hasattr(self.file_list, "GetSelections"):
            return [
                idx for idx in self.file_list.GetSelections()
                if isinstance(idx, int) and 0 <= idx < len(self.frame.queue)
            ]
        row = self.file_list.GetSelection() if hasattr(self.file_list, "GetSelection") else wx.NOT_FOUND
        if 0 <= row < len(self.frame.queue):
            return [row]
        return []

    def GetQueueDisplayStatus(self, row):
        return get_queue_display_status(row)

    def GetQueueCurrentRowIndex(self):
        selected = self.GetSelectedIndices()
        return selected[0] if selected else -1

    def BuildQueueCurrentRowAnnouncement(self):
        return build_queue_current_row_announcement(self.frame)

    def EnsureQueueTableLanding(self, focus=False, select_row=True):
        return ensure_queue_table_landing(self.frame, focus=focus, select_row=select_row)

    def ClearQueueSelection(self):
        if hasattr(self.file_list, "GetSelections") and hasattr(self.file_list, "Deselect"):
            for idx in list(self.file_list.GetSelections()):
                self.file_list.Deselect(idx)
            return
        if hasattr(self.file_list, "UnselectAll"):
            self.file_list.UnselectAll()
            return
        if hasattr(self.file_list, "GetSelection") and hasattr(self.file_list, "Deselect"):
            idx = self.file_list.GetSelection()
            if idx != wx.NOT_FOUND:
                self.file_list.Deselect(idx)

    def SelectQueueRows(self, rows):
        self.ClearQueueSelection()
        for idx in sorted(set(rows)):
            if 0 <= idx < len(self.frame.queue):
                self.file_list.SetSelection(idx)

    def RefreshQueueRows(self, indices):
        if indices is None:
            indices = []
        self.RefreshQueue()

    def RefreshQueue(self):
        selected_indices = self.GetSelectedIndices()
        selected_paths = {
            self.frame.queue[idx].get("path")
            for idx in selected_indices
            if 0 <= idx < len(self.frame.queue)
        }
        lead_selection = selected_indices[0] if selected_indices else wx.NOT_FOUND
        current_path = self.frame.queue[lead_selection].get("path") if 0 <= lead_selection < len(self.frame.queue) else None
        focus_was_in_queue = False
        try:
            focused = wx.Window.FindFocus()
            focus_was_in_queue = focused == self.file_list
        except Exception:
            focus_was_in_queue = False

        if hasattr(self.file_list, "Clear"):
            self.file_list.Clear()
        elif hasattr(self.file_list, "DeleteAllItems"):
            self.file_list.DeleteAllItems()

        if not self.frame.queue:
            self.empty_state.Show()
            self.ClearQueueSelection()
        else:
            self.empty_state.Hide()
            restored_rows = []
            for idx, row in enumerate(self.frame.queue):
                row_text = self.frame.QueueDisplayString(row)
                if hasattr(self.file_list, "Append"):
                    self.file_list.Append(row_text)
                elif hasattr(self.file_list, "AppendItem"):
                    self.file_list.AppendItem([row_text])
                if row.get("path") in selected_paths:
                    restored_rows.append(idx)
                elif current_path and row.get("path") == current_path:
                    restored_rows.append(idx)
            if restored_rows:
                self.SelectQueueRows(restored_rows)
                try:
                    self.file_list.SetFirstItem(restored_rows[0])
                except Exception:
                    pass
            else:
                self.ClearQueueSelection()

        if focus_was_in_queue:
            self.file_list.SetFocus()

        self.Layout()
        self.frame.UpdateQueueButtons()
        self.frame.UpdateProgressIndicators()
