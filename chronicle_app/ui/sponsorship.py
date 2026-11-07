"""Native About dialog and optional project support links."""

from chronicle_app.ui.context_help import bind_dialog_tab_order

SPONSOR_URL = "https://github.com/sponsors/harry6116"
ONE_TIME_URL = SPONSOR_URL + "?frequency=one-time"


def show_about_dialog(wx, owner, *, title, details, open_link):
    previous_focus = wx.Window.FindFocus()
    dialog = wx.Dialog(owner, title=title, size=(720, 440), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
    panel = wx.Panel(dialog)
    root = wx.BoxSizer(wx.VERTICAL)
    text = wx.TextCtrl(panel, value=details + "\n\nSupport Chronicle (optional)\nOne-time contributions and monthly sponsorships are available.\nGive Once opens a single-payment option with no monthly commitment. GitHub sign-in is required.\n" + SPONSOR_URL,
                       style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP)
    text.SetName("About Chronicle and Optional Support")
    text.SetHelpText("Read with arrow keys. Tab moves to sponsorship actions and Close. Escape closes this dialog.")
    root.Add(text, 1, wx.ALL | wx.EXPAND, 12)
    actions = wx.BoxSizer(wx.HORIZONTAL)
    tab_order = [text]
    for label, url in (("GitHub Sponsors", SPONSOR_URL), ("Give Once", ONE_TIME_URL)):
        button = wx.Button(panel, label=label)
        button.SetName(label)
        button.SetToolTip("Open optional support in your browser." if label == "GitHub Sponsors" else "Open a one-time contribution in your browser. No monthly commitment.")
        button.Bind(wx.EVT_BUTTON, lambda _event, target=url, name=label: open_link(target, name))
        actions.Add(button, 0, wx.RIGHT, 8)
        tab_order.append(button)
    actions.AddStretchSpacer(1)
    close = wx.Button(panel, wx.ID_CANCEL, "Close")
    close.SetName("Close About Chronicle")
    actions.Add(close, 0)
    tab_order.append(close)
    root.Add(actions, 0, wx.ALL | wx.EXPAND, 12)
    panel.SetSizer(root)
    outer = wx.BoxSizer(wx.VERTICAL)
    outer.Add(panel, 1, wx.EXPAND)
    dialog.SetSizer(outer)
    dialog.SetEscapeId(wx.ID_CANCEL)
    bind_dialog_tab_order(wx, dialog, tab_order)
    dialog.CentreOnParent()

    def focus_when_shown(event):
        if event.IsShown():
            def focus_text():
                if dialog and not dialog.IsBeingDeleted() and dialog.IsShownOnScreen():
                    text.SetFocus()
            wx.CallAfter(focus_text)
        event.Skip()

    dialog.Bind(wx.EVT_SHOW, focus_when_shown)
    try:
        dialog.ShowModal()
    finally:
        dialog.Destroy()
        if previous_focus and previous_focus.IsShownOnScreen() and previous_focus.IsEnabled():
            previous_focus.SetFocus()
