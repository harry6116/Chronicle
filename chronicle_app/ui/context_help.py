"""Context-sensitive help helpers for Chronicle controls."""

import re


_GENERIC_NAMES = {"button", "choice", "text", "textctrl", "checkbox", "check", "combobox", "panel", "window"}


def bind_dialog_tab_order(wx, dialog, controls):
    """Keep every dialog action reachable under macOS keyboard preferences."""
    def navigate(event):
        if event.GetKeyCode() != wx.WXK_TAB or event.ControlDown() or event.CmdDown() or event.AltDown():
            event.Skip()
            return
        available = [control for control in controls if control.IsEnabled() and control.IsShown()]
        focused = wx.Window.FindFocus()
        while focused and focused not in available:
            focused = focused.GetParent()
        if focused not in available:
            event.Skip()
            return
        step = -1 if event.ShiftDown() else 1
        available[(available.index(focused) + step) % len(available)].SetFocus()

    dialog.Bind(wx.EVT_CHAR_HOOK, navigate)


def _clean_text(value):
    text = str(value or "").strip()
    return " ".join(text.split())


def _call_text(window, method_name):
    if window is None or not hasattr(window, method_name):
        return ""
    try:
        return _clean_text(getattr(window, method_name)())
    except Exception:
        return ""


def _tooltip_text(window):
    if window is None:
        return ""
    text = _call_text(window, "GetToolTipText")
    if text:
        return text
    if not hasattr(window, "GetToolTip"):
        return ""
    try:
        tooltip = window.GetToolTip()
    except Exception:
        return ""
    if tooltip is None:
        return ""
    if hasattr(tooltip, "GetTip"):
        try:
            return _clean_text(tooltip.GetTip())
        except Exception:
            return ""
    return _clean_text(tooltip)


def _control_name(window):
    name = _call_text(window, "GetName")
    if name and name.lower() not in _GENERIC_NAMES:
        return name
    # Text-entry labels/selections can contain document text or credentials.
    if not hasattr(window, "IsEditable"):
        label = _call_text(window, "GetLabel")
        if label:
            return label.replace("&&", "\0").replace("&", "").replace("\0", "&")
    if name:
        return "Text field" if hasattr(window, "IsEditable") else name
    if window is None:
        return "Chronicle"
    return window.__class__.__name__


def _current_value_text(window):
    identity = _call_text(window, "GetName")
    if hasattr(window, "IsEditable") or re.search(r"api.?key|password|secret|token", identity, re.I):
        return ""
    text = _call_text(window, "GetStringSelection")
    if text:
        return text
    # Generic GetValue() can expose free text; only numeric controls need it here.
    try:
        value = window.GetValue()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
    except (AttributeError, RuntimeError, TypeError):
        pass
    return ""


def _state_text(window):
    states = []
    if window is None:
        return ""
    if hasattr(window, "IsEnabled"):
        try:
            states.append("enabled" if window.IsEnabled() else "disabled")
        except Exception:
            pass
    if hasattr(window, "IsChecked"):
        try:
            states.append("checked" if window.IsChecked() else "not checked")
        except Exception:
            pass
    if hasattr(window, "GetSelections"):
        try:
            count = len(window.GetSelections())
            states.append(f"{count} selected")
        except Exception:
            pass
    return ", ".join(states)


def build_context_help_text(window, *, app_name="Chronicle"):
    """Return a dialog title and screen-reader friendly help text for a control."""
    name = _control_name(window) if window is not None else app_name
    help_text = _call_text(window, "GetHelpText")
    tooltip = _tooltip_text(window)
    value = _current_value_text(window)
    state = _state_text(window)

    lines = [name]
    for candidate in (help_text, tooltip):
        if candidate and candidate not in lines:
            lines.append(candidate)
    if value and value not in lines:
        lines.append(f"Current value: {value}.")
    if state:
        lines.append(f"Current state: {state}.")
    if not help_text and not tooltip and not value:
        lines.append(
            f"No specific help has been written for this control yet. "
            f"Use the full {app_name} user guide for the complete workflow."
        )
    lines.append("Use Open Full User Guide for the complete manual.")
    return f"{name} Help", "\n\n".join(lines)


def show_context_help_dialog(wx, focused, *, owner, open_guide, app_name="Chronicle"):
    """Show readable help, then restore focus in the originating window."""
    title, text = build_context_help_text(focused, app_name=app_name)
    dialog = wx.Dialog(owner, title=title, size=(620, 420), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
    dialog.SetName(title)
    dialog._chronicle_context_help = True
    panel = wx.Panel(dialog)
    root = wx.BoxSizer(wx.VERTICAL)
    message = wx.TextCtrl(panel, value=text, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP)
    message.SetName(title)
    message.SetHelpText("Read the help text, then Tab to Open Full User Guide or Close. Escape closes help.")
    root.Add(message, 1, wx.EXPAND | wx.ALL, 12)
    buttons = wx.BoxSizer(wx.HORIZONTAL)
    manual_button = wx.Button(panel, label="Open Full User Guide")
    manual_button.SetName("Open Full User Guide")
    manual_button.SetToolTip("Open Chronicle's complete user guide in your browser.")
    close_button = wx.Button(panel, wx.ID_CLOSE, "Close")
    close_button.SetName("Close Context Help")
    manual_button.Bind(wx.EVT_BUTTON, lambda _event: open_guide())
    close_button.Bind(wx.EVT_BUTTON, lambda _event: dialog.EndModal(wx.ID_CLOSE))
    buttons.Add(manual_button, 0, wx.RIGHT, 8)
    buttons.Add(close_button, 0)
    root.Add(buttons, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
    panel.SetSizer(root)
    bind_dialog_tab_order(wx, dialog, [message, manual_button, close_button])
    outer = wx.BoxSizer(wx.VERTICAL)
    outer.Add(panel, 1, wx.EXPAND)
    dialog.SetSizer(outer)
    dialog.SetEscapeId(wx.ID_CLOSE)
    dialog.CentreOnParent()
    def focus_message(event):
        if event.IsShown():
            message.SetFocus()
        event.Skip()

    dialog.Bind(wx.EVT_SHOW, focus_message)
    try:
        dialog.ShowModal()
    finally:
        dialog.Destroy()
        try:
            if focused and focused.IsShownOnScreen() and focused.IsEnabled():
                focused.SetFocus()
        except RuntimeError:
            pass


def install_context_help_filter(wx, frame, show_help):
    """Handle bare F1 in Chronicle-owned windows, including modal dialogs."""
    class ContextHelpFilter(wx.EventFilter):
        def __init__(self):
            super().__init__()
            self.pending = False

        def FilterEvent(self, event):
            if event.GetEventType() != wx.EVT_CHAR_HOOK.typeId:
                return self.Event_Skip
            if event.GetKeyCode() != wx.WXK_F1 or event.HasAnyModifiers():
                return self.Event_Skip
            focused = wx.Window.FindFocus()
            window = focused
            while window is not None:
                if getattr(window, "_chronicle_context_help", False):
                    return self.Event_Processed
                if window is frame:
                    break
                window = window.GetParent()
            if window is None:
                return self.Event_Skip
            if not self.pending:
                self.pending = True

                def display():
                    try:
                        if focused and not focused.IsBeingDeleted():
                            show_help(focused)
                    finally:
                        self.pending = False

                wx.CallAfter(display)
            return self.Event_Processed

    help_filter = ContextHelpFilter()
    wx.EvtHandler.AddFilter(help_filter)

    def remove_filter(event):
        if event.GetEventObject() is frame:
            wx.EvtHandler.RemoveFilter(help_filter)
        event.Skip()

    frame.Bind(wx.EVT_WINDOW_DESTROY, remove_filter)
    return help_filter
