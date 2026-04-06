import os
import tempfile
import unittest

from chronicle_app.services.queue_runtime import (
    add_path_entries,
    collect_supported_files_from_folder,
    find_queue_rows_by_paths,
)


class QueueRuntimeTest(unittest.TestCase):
    def test_collect_supported_files_from_folder_respects_recursive_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            top_pdf = os.path.join(tmpdir, "a.pdf")
            subdir = os.path.join(tmpdir, "sub")
            nested_docx = os.path.join(subdir, "b.docx")
            hidden = os.path.join(tmpdir, ".hidden.pdf")
            os.makedirs(subdir)
            for path in (top_pdf, nested_docx, hidden):
                with open(path, "wb") as fh:
                    fh.write(b"x")

            flat = collect_supported_files_from_folder(tmpdir, recursive=False, supported_extensions={".pdf", ".docx"})
            deep = collect_supported_files_from_folder(tmpdir, recursive=True, supported_extensions={".pdf", ".docx"})

            self.assertEqual(flat, [top_pdf])
            self.assertEqual(deep, [top_pdf, nested_docx])

    def test_add_path_entries_dedupes_and_builds_rows(self):
        queue = [{"path": "/tmp/existing.pdf"}]
        added = add_path_entries(
            queue,
            ["/tmp/existing.pdf", "/tmp/new.pdf"],
            settings={"format_type": "html", "doc_profile": "standard"},
            engine_label="Gemini",
            row_setting_keys=("format_type", "doc_profile"),
            source_root="/tmp/source",
        )

        self.assertEqual(added, ["/tmp/new.pdf"])
        self.assertEqual(queue[-1]["engine"], "Gemini")
        self.assertEqual(queue[-1]["settings"], {"format_type": "html", "doc_profile": "standard"})
        self.assertEqual(queue[-1]["source_root"], "/tmp/source")

    def test_find_queue_rows_by_paths_returns_matching_indices(self):
        queue = [{"path": "a.pdf"}, {"path": "b.pdf"}, {"path": "c.pdf"}]
        rows = find_queue_rows_by_paths(queue, ["c.pdf", "a.pdf"])

        self.assertEqual(rows, [0, 2])


if __name__ == "__main__":
    unittest.main()
