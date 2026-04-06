import unittest

from chronicle_app.services.ordering_runtime import (
    get_ordered_jobs_for_processing,
    get_page_sequence_number,
    resolve_merge_output_path,
)


class OrderingRuntimeTest(unittest.TestCase):
    def test_get_page_sequence_number_extracts_page_numbers(self):
        self.assertEqual(get_page_sequence_number('/tmp/Page_004_scan.pdf'), 4)
        self.assertIsNone(get_page_sequence_number('/tmp/alpha.pdf'))

    def test_get_ordered_jobs_for_processing_sorts_when_merge_has_sequence(self):
        queue = [
            {'path': '/tmp/page_10.pdf'},
            {'path': '/tmp/alpha.pdf'},
            {'path': '/tmp/page_2.pdf'},
        ]
        jobs, locked = get_ordered_jobs_for_processing(
            queue,
            merge_files=True,
            page_sequence_fn=get_page_sequence_number,
        )
        self.assertTrue(locked)
        self.assertEqual([job['path'] for job in jobs], ['/tmp/page_2.pdf', '/tmp/page_10.pdf', '/tmp/alpha.pdf'])

    def test_resolve_merge_output_path_uses_custom_dest_and_collision_suffix(self):
        created = []
        path = resolve_merge_output_path(
            [{'path': '/src/a.pdf'}],
            'html',
            custom_dest='/custom',
            dest_mode=1,
            script_dir='/app',
            collision_mode='skip',
            path_exists=lambda path: True,
            makedirs=lambda path, exist_ok=False: created.append((path, exist_ok)),
            now=123,
        )
        self.assertEqual(created, [('/custom', True)])
        self.assertEqual(path, '/custom/Chronicle_Merged_123.html')


if __name__ == '__main__':
    unittest.main()
