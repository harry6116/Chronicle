from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock
from chronicle_app.ui.sponsorship import show_about_dialog, SPONSOR_URL, ONE_TIME_URL


class SponsorshipDialogTest(unittest.TestCase):
    def test_about_actions_focus_and_cleanup(self):
        wx = SimpleNamespace()
        for index, name in enumerate(('DEFAULT_DIALOG_STYLE', 'RESIZE_BORDER', 'VERTICAL', 'HORIZONTAL', 'ALL', 'EXPAND', 'RIGHT', 'TE_MULTILINE', 'TE_READONLY', 'TE_WORDWRAP', 'EVT_BUTTON', 'EVT_SHOW', 'EVT_CHAR_HOOK', 'ID_CANCEL')):
            setattr(wx, name, 1 << index)
        dialog, details, previous = MagicMock(), MagicMock(), MagicMock()
        dialog.IsBeingDeleted.return_value = False
        wx.Dialog = Mock(return_value=dialog)
        wx.Panel = Mock()
        wx.BoxSizer = Mock(side_effect=lambda *_: MagicMock())
        wx.TextCtrl = Mock(return_value=details)
        wx.Window = SimpleNamespace(FindFocus=lambda: previous)
        wx.CallAfter = lambda callback: callback()
        buttons = {}
        def button(*args, **kwargs):
            label = kwargs.get('label', args[-1])
            buttons[label] = MagicMock()
            return buttons[label]
        wx.Button = button
        opened = Mock()
        def modal():
            for binding in dialog.Bind.call_args_list:
                if binding.args[0] == wx.EVT_SHOW:
                    binding.args[1](SimpleNamespace(IsShown=lambda: True, Skip=Mock()))
            buttons['GitHub Sponsors'].Bind.call_args.args[1](None)
            buttons['Give Once'].Bind.call_args.args[1](None)
        dialog.ShowModal.side_effect = modal
        show_about_dialog(wx, object(), title='About Chronicle', details='Chronicle test', open_link=opened)
        self.assertEqual([c.args[0] for c in opened.call_args_list], [SPONSOR_URL, ONE_TIME_URL])
        details.SetFocus.assert_called_once()
        previous.SetFocus.assert_called_once()
        dialog.SetEscapeId.assert_called_once_with(wx.ID_CANCEL)
        dialog.Destroy.assert_called_once()
        self.assertEqual(list(buttons), ['GitHub Sponsors', 'Give Once', 'Close'])
        self.assertEqual(wx.TextCtrl.call_args.kwargs['style'], wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP)
