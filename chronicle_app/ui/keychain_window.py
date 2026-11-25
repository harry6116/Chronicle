"""Keep Chronicle accessible while macOS asks for Keychain permission."""

import threading

import wx


def run_credential_operation(parent, title, operation, *, fallback_focus=None):
    if wx.Platform != "__WXMAC__":
        return operation()

    previous_focus = wx.Window.FindFocus()
    dialog = wx.Dialog(parent, title=title, size=(520, 170))
    message = "If macOS asks for permission to access Keychain, respond to the system prompt. Chronicle will continue when it closes."
    status = wx.TextCtrl(dialog, value=message, style=wx.TE_READONLY | wx.TE_MULTILINE)
    status.SetName("Keychain access instructions")
    layout = wx.BoxSizer(wx.VERTICAL)
    layout.Add(status, 1, wx.ALL | wx.EXPAND, 12)
    dialog.SetSizer(layout)
    dialog.SetEscapeId(wx.ID_NONE)
    dialog.Bind(wx.EVT_CLOSE, lambda event: event.Veto())
    result = []

    def finish(value, error):
        result.append((value, error))
        dialog.EndModal(wx.ID_OK)

    def worker():
        try:
            value = operation()
        except Exception as error:
            wx.CallAfter(finish, None, error)
        else:
            wx.CallAfter(finish, value, None)

    def start():
        status.SetFocus()
        status.SetInsertionPoint(0)
        threading.Thread(target=worker, name="Chronicle Keychain", daemon=True).start()

    def on_show(event):
        if event.IsShown():
            dialog.Unbind(wx.EVT_SHOW, handler=on_show)
            wx.CallAfter(start)
        event.Skip()

    dialog.Bind(wx.EVT_SHOW, on_show)
    try:
        dialog.ShowModal()
    finally:
        dialog.Destroy()
        target = previous_focus if previous_focus and previous_focus.IsShownOnScreen() else fallback_focus
        if target and target.IsShownOnScreen():
            target.SetFocus()
    if not result:
        raise RuntimeError("Keychain access was interrupted.")
    value, error = result[0]
    if error is not None:
        raise error
    return value
