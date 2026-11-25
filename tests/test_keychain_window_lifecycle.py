import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from chronicle_app.services.provider_credentials import RESET_NOTICE


class KeychainWindowLifecycleTests(unittest.TestCase):
    def test_main_frame_construction_does_not_request_credentials(self):
        root = Path(__file__).resolve().parents[1]
        gui = ast.parse((root / "chronicle_gui.py").read_text(encoding="utf-8"))
        frame = next(node for node in gui.body if isinstance(node, ast.ClassDef) and node.name == "MainFrame")
        constructor = next(node for node in frame.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
        calls = {node.func.attr for node in ast.walk(constructor)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertNotIn("RefreshProviderCredentials", calls)

    def test_upgrade_warns_before_access_and_default_choice_defers_reset(self):
        root = Path(__file__).resolve().parents[1]
        gui = ast.parse((root / "chronicle_gui.py").read_text(encoding="utf-8"))
        frame = next(node for node in gui.body if isinstance(node, ast.ClassDef) and node.name == "MainFrame")
        methods = [node for node in frame.body if isinstance(node, ast.FunctionDef)
                   and node.name in ("EnsureCredentialReset", "RefreshProviderCredentials")]
        for response in (0, 1):
            with self.subTest(response=response):
                dialog = Mock()
                dialog.ShowModal.return_value = response
                wx = SimpleNamespace(MessageDialog=Mock(return_value=dialog), MessageBox=Mock(),
                                     ID_YES=1, YES_NO=2, NO_DEFAULT=4, ICON_WARNING=8,
                                     ICON_INFORMATION=16, OK=32)
                settings = SimpleNamespace(path=SimpleNamespace(isfile=lambda _: False, islink=lambda _: False))
                operation = Mock(side_effect=lambda owner, title, callback, **kwargs: callback())
                namespace = {"wx": wx, "os": settings, "run_credential_operation": operation,
                             "CREDENTIAL_RESET_FILE": "marker", "APP_DATA_DIR": "settings",
                             "SCRIPT_DIR": "application", "RESET_NOTICE": RESET_NOTICE}
                exec(compile(ast.Module(body=methods, type_ignores=[]), "<key-reset>", "exec"), namespace)
                owner = SimpleNamespace(_existing_credential_profile=True, keys={}, credential_issue="",
                                        CredentialResetPending=lambda: True, credential_store=Mock(), file_list=Mock())
                result = namespace["EnsureCredentialReset"](owner)
                self.assertEqual(result, response == wx.ID_YES)
                self.assertTrue(wx.MessageDialog.call_args.args[-1] & wx.NO_DEFAULT)
                self.assertIn("enter the API keys you want to use", wx.MessageDialog.call_args.args[1])
                dialog.SetYesNoLabels.assert_called_once_with("Remove Saved Keys", "Later")
                if response == wx.ID_YES:
                    owner.credential_store.reset_for_upgrade.assert_called_once_with("marker", "settings", "application")
                else:
                    namespace["RefreshProviderCredentials"](owner)
                    self.assertEqual(owner.keys, {})
                    operation.assert_not_called()
                    self.assertEqual(owner.credential_store.mock_calls, [])

    def test_keychain_window_is_visible_before_access_and_restores_focus(self):
        root = Path(__file__).resolve().parents[1]
        source = ast.parse((root / "chronicle_app/ui/keychain_window.py").read_text(encoding="utf-8"))
        function = next(node for node in source.body if isinstance(node, ast.FunctionDef))
        for denied in (False, True):
            with self.subTest(denied=denied):
                self.check_keychain_window(function, denied)

    def check_keychain_window(self, function, denied):
        events = []
        deferred = []
        dialog, field, prior = Mock(), Mock(), Mock()
        shown = SimpleNamespace(IsShown=lambda: True, Skip=Mock())
        dialog.Destroy.side_effect = lambda: events.append("destroyed")
        field.SetFocus.side_effect = lambda: events.append("instructions focused")
        prior.SetFocus.side_effect = lambda: events.append("focus restored")
        dialog.EndModal.side_effect = lambda _: events.append("closed")
        prior.IsShownOnScreen.return_value = True

        def show_modal():
            events.append("visible")
            show_handler = next(call.args[1] for call in dialog.Bind.call_args_list if call.args[0] == "show")
            show_handler(shown)
            while deferred:
                callback, args = deferred.pop(0)
                callback(*args)

        dialog.ShowModal.side_effect = show_modal
        wx = SimpleNamespace(
            Platform="__WXMAC__", Window=SimpleNamespace(FindFocus=lambda: prior),
            Dialog=lambda *args, **kw: dialog, TextCtrl=lambda *args, **kw: field, BoxSizer=Mock(),
            TE_READONLY=1, TE_MULTILINE=2, VERTICAL=3, ALL=4, EXPAND=8, ID_NONE=-3,
            EVT_CLOSE="close", EVT_SHOW="show", ID_OK=5,
            CallAfter=lambda callback, *args: deferred.append((callback, args)),
        )
        threading = SimpleNamespace(Thread=lambda *, target, **kwargs: SimpleNamespace(start=target))
        scope = {"wx": wx, "threading": threading}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "<keychain-window>", "exec"), scope)

        def access():
            events.append("access requested")
            if denied:
                raise RuntimeError("Denied")
            return "result"

        if denied:
            with self.assertRaisesRegex(RuntimeError, "Denied"):
                scope[function.name](Mock(), "Keychain", access)
        else:
            self.assertEqual(scope[function.name](Mock(), "Keychain", access), "result")
        self.assertEqual(events, ["visible", "instructions focused", "access requested",
                                  "closed", "destroyed", "focus restored"])
