import types
import unittest

from chronicle_app.services.scan_flow_runtime import (
    apply_scan_settings,
    begin_scan_session,
    build_scan_completion_message,
    build_scan_start_message,
    choose_scan_commands,
    execute_scan_commands,
    resolve_scan_driver,
    resolve_scan_output_files,
)


class ScanFlowRuntimeTest(unittest.TestCase):
    def test_apply_scan_settings_persists_last_scan_metadata(self):
        updated = apply_scan_settings(
            {},
            scanner={'name': 'Flatbed', 'source': 'wia'},
            dpi=300,
            output_dir='/tmp/scans',
            preset_label='Colour',
            driver_from_source_fn=lambda source: f'drv:{source}',
        )
        self.assertEqual(updated['scan_last_device'], 'Flatbed')
        self.assertEqual(updated['scan_last_driver'], 'drv:wia')
        self.assertFalse(updated['scan_auto_start'])

    def test_begin_scan_session_tracks_existing_files_and_output_name(self):
        fake_time = types.SimpleNamespace(time=lambda: 5.0, strftime=lambda fmt: '20260101_010203')
        session = begin_scan_session(
            '/tmp/out',
            listdir=lambda path: ['a.pdf', 'subdir'],
            isfile=lambda path: path.endswith('a.pdf'),
            join=lambda a, b: f'{a}/{b}',
            time_module=fake_time,
        )
        self.assertEqual(session['before_paths'], {'/tmp/out/a.pdf'})
        self.assertEqual(session['output_pdf'], '/tmp/out/scan_20260101_010203.pdf')

    def test_execute_scan_commands_reports_missing_or_success(self):
        missing = execute_scan_commands(
            [],
            attempt_scan_fn=lambda *args: None,
            scanner_name='A',
            driver='d',
            dpi=300,
            output_pdf='/tmp/x.pdf',
            log_cb=lambda msg: None,
        )
        logs = []
        success = execute_scan_commands(
            [['naps2']],
            attempt_scan_fn=lambda *args: (True, ['naps2', 'scan'], '', ''),
            scanner_name='A',
            driver='d',
            dpi=300,
            output_pdf='/tmp/x.pdf',
            log_cb=logs.append,
        )
        self.assertEqual(missing['error_kind'], 'missing_executable')
        self.assertTrue(success['success'])
        self.assertIn('succeeded', logs[0])

    def test_resolve_scan_driver_output_files_and_messages(self):
        self.assertEqual(
            resolve_scan_driver({'source': 'twain'}, {'scan_last_driver': 'old'}, driver_from_source_fn=lambda src: ''),
            'old',
        )
        files = resolve_scan_output_files(
            '/tmp/out', set(), 0.0, '/tmp/out/scan.pdf',
            collect_scan_files_fn=lambda *args: [],
            path_exists=lambda path: True,
        )
        dialog_message, log_message = build_scan_completion_message(['a.pdf', 'b.pdf'], ['a.pdf'])
        self.assertEqual(files, ['/tmp/out/scan.pdf'])
        self.assertIn('Detected 2 file(s)', dialog_message)
        self.assertIn('Added 1 file(s)', log_message)
        self.assertIn('Flatbed', build_scan_start_message({'name': 'Flatbed'}, 300, 'Colour'))
        self.assertEqual(choose_scan_commands([['a']]), [['a']])


if __name__ == '__main__':
    unittest.main()
