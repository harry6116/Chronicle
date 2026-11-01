from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock

from chronicle_app.ui.release_notes import show_release_notes_dialog


class ReleaseNotesDialogTest(unittest.TestCase):
    def make_wx(self):
        wx = SimpleNamespace()
        for index, name in enumerate(("DEFAULT_DIALOG_STYLE", "RESIZE_BORDER", "VERTICAL", "HORIZONTAL", "ALL", "EXPAND", "RIGHT", "TE_MULTILINE", "TE_READONLY", "TE_WORDWRAP", "EVT_BUTTON", "EVT_CHAR_HOOK", "EVT_SHOW", "ID_OK", "ID_CANCEL")):
            setattr(wx, name, 1 << index)
        self.previous = MagicMock()
        self.dialog = MagicMock()
        self.dialog.IsBeingDeleted.return_value = False
        self.notes = MagicMock()
        self.buttons = {}
        wx.Window = SimpleNamespace(FindFocus=lambda: self.previous)
        wx.Dialog = Mock(return_value=self.dialog)
        wx.Panel = Mock()
        wx.BoxSizer = Mock(side_effect=lambda *_args: MagicMock())
        wx.StaticText = Mock()
        wx.TextCtrl = Mock(return_value=self.notes)

        def button(*args, **kwargs):
            label = kwargs.get("label", args[-1] if isinstance(args[-1], str) else "")
            result = MagicMock()
            self.buttons[label] = result
            return result

        wx.Button = button
        wx.CallAfter = lambda callback: callback()
        def show_modal():
            self.notes.SetFocus.assert_not_called()
            for binding in self.dialog.Bind.call_args_list:
                if binding.args[0] == wx.EVT_SHOW:
                    binding.args[1](SimpleNamespace(IsShown=lambda: True, Skip=Mock()))
            return wx.ID_CANCEL

        self.dialog.ShowModal.side_effect = show_modal
        return wx

    def show(self, wx, install_url="https://example.invalid/app.zip"):
        self.remind = Mock()
        return show_release_notes_dialog(
            wx, object(), title="Chronicle Update", header="An update is available.",
            notes="First line.\nSecond line.\n<script>Readable literal text.</script>",
            release_url="https://example.invalid/release", install_url=install_url,
            open_link=Mock(), remind_later=self.remind,
        )

    def test_notes_are_read_only_multiline_text_with_initial_and_return_focus(self):
        wx = self.make_wx()
        self.assertFalse(self.show(wx))
        options = wx.TextCtrl.call_args.kwargs
        self.assertEqual(options["style"], wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP)
        self.assertIn("\nSecond line.\n<script>", options["value"])
        self.notes.SetFocus.assert_called_once()
        self.previous.SetFocus.assert_called_once()
        self.dialog.SetEscapeId.assert_called_once_with(wx.ID_CANCEL)
        self.dialog.Destroy.assert_called_once()

    def test_hidden_dialog_does_not_receive_delayed_focus(self):
        wx = self.make_wx()
        self.dialog.IsShownOnScreen.return_value = False
        self.assertFalse(self.show(wx))
        self.notes.SetFocus.assert_not_called()

    def test_accepting_dialog_without_install_action_does_not_install(self):
        wx = self.make_wx()
        self.dialog.ShowModal.side_effect = None
        self.dialog.ShowModal.return_value = wx.ID_OK
        self.assertFalse(self.show(wx))

    def test_only_explicit_install_action_requests_installation(self):
        wx = self.make_wx()

        def choose_install():
            callback = self.buttons["Install and Restart Now"].Bind.call_args.args[1]
            callback(None)
            return wx.ID_OK

        self.dialog.ShowModal.side_effect = choose_install
        self.assertTrue(self.show(wx))
        self.dialog.EndModal.assert_called_once_with(wx.ID_OK)

    def test_remind_me_later_saves_reminder_without_requesting_installation(self):
        wx = self.make_wx()

        def choose_later():
            callback = self.buttons["Remind Me Later"].Bind.call_args.args[1]
            callback(None)
            return wx.ID_CANCEL

        self.dialog.ShowModal.side_effect = choose_later
        self.assertFalse(self.show(wx))
        self.remind.assert_called_once()
        self.dialog.EndModal.assert_called_once_with(wx.ID_CANCEL)

    def test_actions_have_one_release_link_and_an_explicit_later_choice(self):
        wx = self.make_wx()
        self.show(wx)
        self.assertEqual(set(self.buttons), {"Install and Restart Now", "Remind Me Later", "Go to Release", "Close"})

    def test_history_can_offer_reminder_without_an_install_button(self):
        wx = self.make_wx()
        self.assertFalse(self.show(wx, install_url=None))
        self.assertEqual(set(self.buttons), {"Remind Me Later", "Go to Release", "Close"})


if __name__ == "__main__":
    unittest.main()
