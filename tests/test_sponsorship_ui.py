from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock
from chronicle_app.ui.sponsorship import show_about_dialog, SPONSOR_URL, ONE_TIME_URL, KOFI_URL, WEBSITE_URL


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
            for label in ('Chronicle Website', 'Email Michael', 'GitHub Issues', 'GitHub Sponsors', 'Give Once', 'Ko-fi'):
                buttons[label].Bind.call_args.args[1](None)
        dialog.ShowModal.side_effect = modal
        show_about_dialog(wx, object(), title='About Chronicle', details='Chronicle test', open_link=opened)
        self.assertEqual([c.args[0] for c in opened.call_args_list], [
            WEBSITE_URL, 'mailto:chronicle.vir@gmail.com',
            'https://github.com/harry6116/Chronicle/issues', SPONSOR_URL, ONE_TIME_URL, KOFI_URL])
        details.SetFocus.assert_called_once()
        previous.SetFocus.assert_called_once()
        dialog.SetEscapeId.assert_called_once_with(wx.ID_CANCEL)
        dialog.Destroy.assert_called_once()
        self.assertEqual(list(buttons), ['Chronicle Website', 'Email Michael', 'GitHub Issues', 'GitHub Sponsors', 'Give Once', 'Ko-fi', 'Close'])
        for label, button in buttons.items():
            button.SetName.assert_called_once_with('Close About Chronicle' if label == 'Close' else label)
        about_text = wx.TextCtrl.call_args.kwargs['value']
        self.assertIn(WEBSITE_URL, about_text)
        self.assertIn(KOFI_URL, about_text)
        self.assertIn('chronicle.vir@gmail.com', about_text)
        self.assertIn('Messages on GitHub are public', about_text)
        self.assertEqual(wx.TextCtrl.call_args.kwargs['style'], wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP)
