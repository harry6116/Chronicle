import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


def load_dialog():
    source = Path(__file__).resolve().parents[1] / "chronicle_app/ui/dialogs.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    dialog = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ApiKeyDialog")
    wx = SimpleNamespace(Dialog=object, MessageBox=Mock(), OK=1, ICON_WARNING=2, ICON_INFORMATION=4, ID_OK=5)
    namespace = {"wx": wx}
    exec(compile(ast.Module(body=[dialog], type_ignores=[]), str(source), "exec"), namespace)
    return namespace["ApiKeyDialog"], wx


class ApiKeyDialogTest(unittest.TestCase):
    def setUp(self):
        self.dialog_type, self.wx = load_dialog()
        self.dialog = object.__new__(self.dialog_type)
        self.dialog.tg = Mock()
        self.dialog.tc = Mock()
        self.dialog.to = Mock()
        for control in (self.dialog.tg, self.dialog.tc, self.dialog.to):
            control.GetValue.return_value = ""
        self.dialog.keys = {"gemini": "previous", "claude": "", "openai": ""}
        self.dialog._save_keys = Mock()
        self.dialog.EndModal = Mock()

    def test_save_accepts_google_auth_keys_without_fixed_length(self):
        for length in (40, 120, 300):
            with self.subTest(length=length):
                key = "AQ." + "x" * length + "._-~+/="
                self.dialog.tg.GetValue.return_value = "  " + key + "  "
                self.dialog.OnSave(None)
                self.assertEqual(self.dialog.keys["gemini"], key)
                self.dialog._save_keys.assert_called_with({"gemini": key, "claude": "", "openai": ""})
                self.dialog.EndModal.assert_called_with(self.wx.ID_OK)

    def test_save_preserves_legacy_and_other_provider_keys(self):
        keys = {"gemini": "AI" + "za" + "x" * 35, "claude": "sk-ant-api03-" + "y" * 90, "openai": "sk-proj-" + "z" * 150}
        for attr, provider in (("tg", "gemini"), ("tc", "claude"), ("to", "openai")):
            getattr(self.dialog, attr).GetValue.return_value = " " + keys[provider] + " "
        self.dialog.OnSave(None)
        self.dialog._save_keys.assert_called_once_with(keys)

    def test_blank_keys_still_allow_offline_use(self):
        self.dialog.OnSave(None)
        self.dialog._save_keys.assert_called_once_with({"gemini": "", "claude": "", "openai": ""})

    def test_show_keys_preserves_names_values_and_tab_positions(self):
        self.wx.TE_PASSWORD = 16
        self.wx.TextCtrl = Mock(side_effect=lambda *args, **kwargs: Mock())
        self.dialog.chk = Mock()
        self.dialog.grid = Mock()
        self.dialog.Layout = Mock()
        for show in (True, False):
            self.dialog.chk.GetValue.return_value = show
            originals = [self.dialog.tg, self.dialog.tc, self.dialog.to]
            for index, control in enumerate(originals):
                control.GetValue.return_value = "disposable-value-" + str(index)
                control.GetName.return_value = ("Google Gemini API Key", "Anthropic Claude API Key", "OpenAI GPT API Key")[index]
            self.dialog.OnToggle(None)
            for old, attr in zip(originals, ("tg", "tc", "to")):
                replacement = getattr(self.dialog, attr)
                replacement.MoveBeforeInTabOrder.assert_called_once_with(old)
                replacement.SetName.assert_called_once_with(old.GetName())
                replacement.SetValue.assert_called_once_with(old.GetValue())
                old.Destroy.assert_called_once()

    def test_opaque_future_key_format_does_not_require_known_prefix(self):
        self.dialog.tg.GetValue.return_value = "future-provider-token_123"
        self.dialog.OnSave(None)
        self.dialog._save_keys.assert_called_once()

    def test_invalid_input_preserves_saved_keys_and_focuses_affected_field(self):
        for attr, label in (("tg", "Google Gemini"), ("tc", "Anthropic Claude"), ("to", "OpenAI")):
            for invalid in ("Bearer copied-token", "copied\nkey", "copied\tkey", '"quoted-key"', "non-ascii-\u00e9", "bad\x00key"):
                with self.subTest(provider=label, invalid=repr(invalid)):
                    self.setUp()
                    control = getattr(self.dialog, attr)
                    control.GetValue.return_value = invalid
                    self.dialog.OnSave(None)
                    self.dialog._save_keys.assert_not_called()
                    self.dialog.EndModal.assert_not_called()
                    self.assertEqual(self.dialog.keys["gemini"], "previous")
                    control.SetFocus.assert_called_once()
                    control.SetSelection.assert_called_once_with(-1, -1)
                    message = self.wx.MessageBox.call_args.args[0]
                    self.assertIn(label, message)
                    self.assertNotIn(invalid, message)


if __name__ == "__main__":
    unittest.main()
