import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from chronicle_app.ui.bindings import bind_named, bind_menu_action, defer_menu_action


class _Widget:
    def __init__(self):
        self.bound = []

    def Bind(self, event, handler, **kwargs):
        self.bound.append((event, handler))
        self.binding_options = kwargs


class BindNamedTest(unittest.TestCase):
    def test_menu_action_waits_until_menu_dispatch_returns(self):
        queued = []
        actions = []
        widget = _Widget()
        widget.IsBeingDeleted = lambda: False
        bind_menu_action(widget, 'menu', lambda event: actions.append(event),
                         item_id=7, call_after=queued.append)
        event, handler = widget.bound[0]
        self.assertEqual(event, 'menu')
        self.assertEqual(widget.binding_options, {'id': 7})
        handler(object())
        self.assertEqual(actions, [])
        queued.pop()()
        self.assertEqual(actions, [None])

    def test_pending_menu_action_does_not_run_after_window_destruction(self):
        queued = []
        actions = []
        widget = _Widget()
        widget.IsBeingDeleted = lambda: True
        defer_menu_action(widget, lambda event: actions.append(event), call_after=queued.append)
        queued.pop()()
        self.assertEqual(actions, [])

    def test_every_menu_bar_command_uses_deferred_dispatch_on_mac_and_windows(self):
        from chronicle_app.ui import menus

        for system, count in (("Darwin", 18), ("Windows", 17)):
            with self.subTest(system=system):
                queued = []
                ids = iter(range(100, 200))
                menu = MagicMock()
                wx = SimpleNamespace(MenuBar=MagicMock(), Menu=MagicMock(return_value=menu),
                                     NewIdRef=lambda: next(ids), ID_PREFERENCES=1, ID_EXIT=2,
                                     EVT_MENU=object(), CallAfter=queued.append)
                frame = MagicMock()
                frame.IsBeingDeleted.return_value = False
                with patch.object(menus, 'wx', wx), patch.object(menus.platform, 'system', return_value=system):
                    menus.ChronicleMenuBar(frame).install()
                self.assertEqual(frame.Bind.call_count, count)
                for binding in frame.Bind.call_args_list:
                    binding.args[1](object())
                frame.OnCheckForUpdates.assert_not_called()
                frame.OnPrefs.assert_not_called()
                frame.OnContextHelp.assert_not_called()
                self.assertEqual(len(queued), count)
                for callback in queued:
                    callback()
                frame.OnCheckForUpdates.assert_called_once_with(None)
                frame.OnPrefs.assert_called_once_with(None)
                frame.OnContextHelp.assert_called_once_with(None)
                labels = [call.args[1] for call in menu.Append.call_args_list]
                self.assertIn("Check for &Updates...\tShift+F1", labels)
                self.assertIn("Context &Help\tF1", labels)
                self.assertIn("&Preferences...\tAlt+P", labels)
                self.assertEqual(any("Mac Folder" in label for label in labels), system == "Darwin")

    def test_binds_only_requested_handler(self):
        widget = _Widget()
        event_a = object()
        event_b = object()
        handler_a = object()
        handler_b = object()

        bindings = {
            'add_files': (event_a, handler_a),
            'add_folder': (event_b, handler_b),
        }

        bind_named(widget, 'add_files', bindings)

        self.assertEqual(widget.bound, [(event_a, handler_a)])

    def test_raises_for_unknown_binding_name(self):
        widget = _Widget()
        with self.assertRaises(KeyError):
            bind_named(widget, 'missing', {})
        self.assertEqual(widget.bound, [])


if __name__ == '__main__':
    unittest.main()
