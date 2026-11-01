import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from chronicle_app.ui.context_help import bind_dialog_tab_order, build_context_help_text, install_context_help_filter


class _FakeControl:
    def __init__(
        self,
        *,
        name="",
        label="",
        help_text="",
        tooltip="",
        value="",
        enabled=True,
        checked=None,
        selections=None,
    ):
        self._name = name
        self._label = label
        self._help_text = help_text
        self._tooltip = tooltip
        self._value = value
        self._enabled = enabled
        self._checked = checked
        self._selections = selections

    def GetName(self):
        return self._name

    def GetLabel(self):
        return self._label

    def GetHelpText(self):
        return self._help_text

    def GetToolTipText(self):
        return self._tooltip

    def GetStringSelection(self):
        return self._value

    def IsEnabled(self):
        return self._enabled

    def IsChecked(self):
        if self._checked is None:
            raise AttributeError("not checkable")
        return self._checked

    def GetSelections(self):
        if self._selections is None:
            raise AttributeError("not selectable")
        return self._selections


class ContextHelpTest(unittest.TestCase):
    def test_generic_toolkit_name_uses_visible_label_without_mnemonic(self):
        title, _text = build_context_help_text(_FakeControl(name="button", label="&Run Preflight"))
        self.assertEqual(title, "Run Preflight Help")

    def test_api_key_value_is_never_copied_even_when_visible(self):
        control = _FakeControl(name="Google Gemini API Key", value="disposable-private-value")
        _title, text = build_context_help_text(control)
        self.assertNotIn("disposable-private-value", text)

    def test_free_text_selection_is_not_repeated_in_help(self):
        control = _FakeControl(name="Custom Instructions", value="private selected text")
        control.IsEditable = lambda: True
        _title, text = build_context_help_text(control)
        self.assertNotIn("private selected text", text)

    def test_boolean_value_is_reported_as_state_only(self):
        control = _FakeControl(name="Page Links", checked=False)
        control.GetValue = lambda: False
        _title, text = build_context_help_text(control)
        self.assertIn("not checked", text)
        self.assertNotIn("Current value", text)

    def test_missing_control_uses_app_name(self):
        title, _text = build_context_help_text(None, app_name="Chronicle")
        self.assertEqual(title, "Chronicle Help")

    def test_broken_control_accessors_fall_back_safely(self):
        control = _FakeControl(label="Start Reading")
        control.GetName = Mock(side_effect=RuntimeError("destroyed control"))
        _title, text = build_context_help_text(control)
        self.assertIn("Start Reading", text)

    def test_build_context_help_uses_accessible_name_help_tooltip_and_state(self):
        title, text = build_context_help_text(
            _FakeControl(
                name="Files Queue",
                help_text="Queued files list. Use arrow keys to move through queued items.",
                tooltip="Select files before choosing task actions.",
                value="Report.pdf",
                enabled=False,
                selections=[0, 2],
            )
        )

        self.assertEqual(title, "Files Queue Help")
        self.assertIn("Files Queue", text)
        self.assertIn("Queued files list", text)
        self.assertIn("Select files before choosing task actions", text)
        self.assertIn("Current value: Report.pdf.", text)
        self.assertIn("Current state: disabled, 2 selected.", text)
        self.assertIn("Open Full User Guide", text)

    def test_build_context_help_has_general_fallback_for_unnamed_controls(self):
        title, text = build_context_help_text(_FakeControl(), app_name="Chronicle")

        self.assertEqual(title, "_FakeControl Help")
        self.assertIn("No specific help has been written", text)
        self.assertIn("full Chronicle user guide", text)


class ContextHelpFilterTest(unittest.TestCase):
    def setUp(self):
        class EventFilter:
            Event_Skip = -1
            Event_Processed = 1

        self.callbacks = []
        self.frame = SimpleNamespace(Bind=Mock())
        self.modal = SimpleNamespace(GetParent=lambda: self.frame)
        self.focused = SimpleNamespace(GetParent=lambda: self.modal, IsBeingDeleted=lambda: False)
        self.wx = SimpleNamespace(
            EventFilter=EventFilter,
            EvtHandler=SimpleNamespace(AddFilter=Mock(), RemoveFilter=Mock()),
            EVT_CHAR_HOOK=SimpleNamespace(typeId=10), EVT_WINDOW_DESTROY=object(), WXK_F1=340,
            Window=SimpleNamespace(FindFocus=lambda: self.focused),
            CallAfter=self.callbacks.append,
        )
        self.show_help = Mock()
        self.filter = install_context_help_filter(self.wx, self.frame, self.show_help)

    def event(self, key=340, modified=False, event_type=10):
        return SimpleNamespace(GetEventType=lambda: event_type, GetKeyCode=lambda: key,
                               HasAnyModifiers=lambda: modified)

    def test_modal_control_f1_opens_once_and_uses_original_focus(self):
        self.assertEqual(self.filter.FilterEvent(self.event()), 1)
        self.assertEqual(self.filter.FilterEvent(self.event()), 1)
        self.assertEqual(len(self.callbacks), 1)
        original = self.focused
        self.focused = None
        self.callbacks.pop()()
        self.show_help.assert_called_once_with(original)
        self.assertFalse(self.filter.pending)

    def test_modified_f1_and_other_keys_are_left_alone(self):
        for event in (self.event(modified=True), self.event(key=65), self.event(event_type=11)):
            self.assertEqual(self.filter.FilterEvent(event), -1)
        self.assertEqual(self.callbacks, [])

    def test_unrelated_window_is_left_alone(self):
        self.focused.GetParent = lambda: None
        self.assertEqual(self.filter.FilterEvent(self.event()), -1)

    def test_help_dialog_does_not_spawn_recursive_help(self):
        self.modal._chronicle_context_help = True
        self.assertEqual(self.filter.FilterEvent(self.event()), 1)
        self.assertEqual(self.callbacks, [])

    def test_destroyed_control_does_not_open_help(self):
        self.filter.FilterEvent(self.event())
        self.focused.IsBeingDeleted = lambda: True
        self.callbacks.pop()()
        self.show_help.assert_not_called()
        self.assertFalse(self.filter.pending)

    def test_filter_removed_only_when_owning_frame_is_destroyed(self):
        destroy_handler = self.frame.Bind.call_args.args[1]
        event = SimpleNamespace(GetEventObject=lambda: self.modal, Skip=Mock())
        destroy_handler(event)
        self.wx.EvtHandler.RemoveFilter.assert_not_called()
        event.GetEventObject = lambda: self.frame
        destroy_handler(event)
        self.wx.EvtHandler.RemoveFilter.assert_called_once_with(self.filter)
        self.assertEqual(event.Skip.call_count, 2)


class DialogTabOrderTest(unittest.TestCase):
    def test_tab_and_shift_tab_visit_every_action(self):
        selected = []
        controls = [SimpleNamespace(IsEnabled=lambda: True, IsShown=lambda: True) for _ in range(3)]
        for index, control in enumerate(controls):
            control.SetFocus = lambda item=index: selected.append(item)
        focused = controls[0]
        wx = SimpleNamespace(Window=SimpleNamespace(FindFocus=lambda: focused), WXK_TAB=9, EVT_CHAR_HOOK=object())
        dialog = SimpleNamespace(Bind=Mock())
        bind_dialog_tab_order(wx, dialog, controls)
        handler = dialog.Bind.call_args.args[1]
        event = SimpleNamespace(GetKeyCode=lambda: 9, ControlDown=lambda: False, CmdDown=lambda: False,
                                AltDown=lambda: False, ShiftDown=lambda: False, Skip=Mock())
        handler(event)
        self.assertEqual(selected[-1], 1)
        focused = controls[1]
        handler(event)
        self.assertEqual(selected[-1], 2)
        event.ShiftDown = lambda: True
        handler(event)
        self.assertEqual(selected[-1], 0)
        event.GetKeyCode = lambda: 27
        handler(event)
        event.Skip.assert_called_once()


if __name__ == "__main__":
    unittest.main()
