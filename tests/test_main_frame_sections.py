import sys
import types
import unittest


class _Sizer:
    def __init__(self, *args):
        self.args = args
        self.items = []
    def Add(self, *args):
        self.items.append(args)
    def AddGrowableCol(self, *args):
        pass


class _Widget:
    def __init__(self, *args, **kwargs):
        self.name = None
        self.tooltip = None
        self.min_size = None
        self.bound = []
        self.value = None
        self.selection = None
    def SetName(self, value):
        self.name = value
    def SetToolTip(self, value):
        self.tooltip = value
    def SetMinSize(self, value):
        self.min_size = value
    def Bind(self, event, handler):
        self.bound.append((event, handler))
    def SetValue(self, value):
        self.value = value
    def SetSelection(self, value):
        self.selection = value
    def SetHelpText(self, value):
        self.help_text = value


wx = types.SimpleNamespace(
    VERTICAL=1,
    HORIZONTAL=2,
    GA_HORIZONTAL=4,
    GA_SMOOTH=8,
    TE_READONLY=16,
    TE_MULTILINE=32,
    TE_RICH2=64,
    EXPAND=128,
    LEFT=256,
    RIGHT=512,
    TOP=1024,
    ALL=2048,
    ALIGN_CENTER_VERTICAL=4096,
    EVT_BUTTON=object(),
    EVT_CHOICE=object(),
    EVT_CHECKBOX=object(),
    ART_FILE_OPEN='file',
    ART_FOLDER_OPEN='folder',
    ART_DELETE='delete',
    ART_LIST_VIEW='list',
    StaticBoxSizer=_Sizer,
    BoxSizer=_Sizer,
    FlexGridSizer=_Sizer,
    Gauge=_Widget,
    TextCtrl=_Widget,
    StaticText=_Widget,
    Button=_Widget,
    Choice=_Widget,
    CheckBox=_Widget,
)
sys.modules['wx'] = wx
sys.modules.pop('chronicle_app.ui.main_frame_sections', None)

from chronicle_app.ui.main_frame_sections import (
    build_log_section,
    build_progress_section,
    build_queue_action_section,
    build_settings_section,
)


class MainFrameSectionsTest(unittest.TestCase):
    def test_build_progress_section_returns_named_controls(self):
        box, gauge, summary = build_progress_section(object())
        self.assertEqual(gauge.name, 'Task Progress Gauge')
        self.assertEqual(summary.name, 'Task Progress Summary')
        self.assertEqual(len(box.items), 2)

    def test_build_log_section_binds_save_handler(self):
        handler = lambda event: None
        label, log_ctrl, actions, button = build_log_section(object(), save_log_handler=handler)
        self.assertEqual(label.name, 'Processing Log Label')
        self.assertEqual(log_ctrl.name, 'Processing Log Window')
        self.assertEqual(button.name, 'Save Processing Log')
        self.assertEqual(button.bound[0][1], handler)
        self.assertEqual(len(actions.items), 1)

    def test_build_queue_action_section_creates_expected_buttons(self):
        binds = []
        section = build_queue_action_section(
            object(),
            bind=lambda widget, name: binds.append(name),
            set_button_icon=lambda widget, art_id: None,
        )
        self.assertEqual(section['btn_add'].name, 'Add Files')
        self.assertEqual(section['btn_clear'].name, 'Clear File List')
        self.assertIn('task_actions', binds)

    def test_build_settings_section_creates_core_controls(self):
        binds = []
        section = build_settings_section(
            object(),
            cfg={'format_type': 'html', 'recursive_scan': True, 'dest_mode': 1, 'custom_dest': '/tmp', 'doc_profile': 'standard'},
            profile_choices=[('standard', 'Standard')],
            get_pdf_page_items_fn=lambda selected: ['All Pages', 'Custom...'],
            bind=lambda widget, name: binds.append(name),
        )
        self.assertEqual(section['format_choice'].name, 'Output Format Selector')
        self.assertEqual(section['choice_profile'].name, 'Document Preset Picker')
        self.assertIn('can be much slower', section['choice_profile'].tooltip)

    def test_build_settings_section_keeps_forms_selected(self):
        section = build_settings_section(
            object(),
            cfg={'format_type': 'html', 'recursive_scan': False, 'dest_mode': 0, 'custom_dest': '', 'doc_profile': 'forms'},
            profile_choices=[('manual', 'Manuals / Procedures'), ('forms', 'Forms / Checklists')],
            get_pdf_page_items_fn=lambda selected: ['All Pages', 'Custom...'],
            bind=lambda widget, name: None,
        )
        self.assertEqual(section['choice_profile'].selection, 1)

    def test_build_settings_section_returns_preflight_and_run_controls(self):
        binds = []
        section = build_settings_section(
            object(),
            cfg={'format_type': 'html', 'recursive_scan': False, 'dest_mode': 0, 'custom_dest': '', 'doc_profile': 'standard'},
            profile_choices=[('standard', 'Miscellaneous / Mixed Files')],
            get_pdf_page_items_fn=lambda selected: ['All Pages', 'Custom...'],
            bind=lambda widget, name: binds.append(name),
        )
        self.assertEqual(section['btn_run_preflight'].name, 'Run Document Preflight')
        self.assertEqual(section['preflight_summary'].name, 'Document Preflight Summary')
        self.assertEqual(section['btn_start'].name, 'Start Reading')
        self.assertIn('run_option', binds)
        self.assertIn('schedule', binds)
        self.assertIn('run_preflight', binds)


if __name__ == '__main__':
    unittest.main()
