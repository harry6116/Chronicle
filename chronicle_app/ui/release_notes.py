"""Readable release notes with native update actions and predictable focus."""

from chronicle_app.ui.context_help import bind_dialog_tab_order


def show_release_notes_dialog(wx, owner, *, title, header, notes, release_url, install_url, open_link, remind_later=None):
    previous_focus = wx.Window.FindFocus()
    dialog = wx.Dialog(owner, title=title, size=(780, 580), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
    panel = wx.Panel(dialog)
    root = wx.BoxSizer(wx.VERTICAL)
    header_text = wx.StaticText(panel, label=header)
    header_text.SetName(header)
    root.Add(header_text, 0, wx.ALL | wx.EXPAND, 12)
    notes_view = wx.TextCtrl(
        panel, value=notes or "No release notes were provided for this update.",
        style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP,
    )
    notes_view.SetName("Release Notes")
    notes_view.SetHelpText("Read release notes with the arrow keys. Select and copy text as needed. Tab moves to the update actions; Escape closes the window.")
    notes_view.SetToolTip("Release notes. Use arrow keys to read, or select and copy text.")
    root.Add(notes_view, 1, wx.ALL | wx.EXPAND, 12)
    actions = wx.BoxSizer(wx.HORIZONTAL)
    tab_order = [notes_view]
    dialog.chronicle_install_requested = False
    if install_url:
        install = wx.Button(panel, label="Install and Restart Now")
        install.SetName("Install Update and Restart Now")
        install.SetToolTip("Close Chronicle and install the selected update after confirmation.")

        def request_install(_event):
            dialog.chronicle_install_requested = True
            dialog.EndModal(wx.ID_OK)

        install.Bind(wx.EVT_BUTTON, request_install)
        actions.Add(install, 0, wx.RIGHT, 8)
        tab_order.append(install)
    if remind_later is not None:
        later = wx.Button(panel, label="Remind Me Later")
        later.SetName("Remind Me Later")
        later.SetToolTip("Keep Chronicle running and show a quiet update reminder next time it starts. No automatic restart.")

        def postpone(_event):
            remind_later()
            dialog.EndModal(wx.ID_CANCEL)

        later.Bind(wx.EVT_BUTTON, postpone)
        actions.Add(later, 0, wx.RIGHT, 8)
        tab_order.append(later)
    for label, url, description in (
        ("Go to Release", release_url, "Open this release in your browser."),
    ):
        if not url:
            continue
        button = wx.Button(panel, label=label)
        button.SetName(label)
        button.SetToolTip(description)
        button.Bind(wx.EVT_BUTTON, lambda _event, target=url, name=label: open_link(target, name))
        actions.Add(button, 0, wx.RIGHT, 8)
        tab_order.append(button)
    actions.AddStretchSpacer(1)
    close = wx.Button(panel, wx.ID_CANCEL, "Close")
    close.SetName("Close Release Notes")
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
            def focus_notes():
                if dialog and not dialog.IsBeingDeleted() and dialog.IsShownOnScreen():
                    notes_view.SetFocus()
            wx.CallAfter(focus_notes)
        event.Skip()

    dialog.Bind(wx.EVT_SHOW, focus_when_shown)
    try:
        result = dialog.ShowModal()
        return dialog.chronicle_install_requested and result == wx.ID_OK
    finally:
        dialog.Destroy()
        if previous_focus and previous_focus.IsShownOnScreen() and previous_focus.IsEnabled():
            previous_focus.SetFocus()
