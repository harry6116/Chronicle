import os
import tempfile
import types
import unittest

from chronicle_app.services.scan_runtime import (
    collect_scan_files,
    driver_from_scanner_source,
    merge_scan_files_to_single_pdf,
)


class ScanRuntimeTest(unittest.TestCase):
    def test_driver_from_scanner_source_extracts_naps2_driver(self):
        self.assertEqual(driver_from_scanner_source("NAPS2 TWAIN"), "twain")
        self.assertEqual(driver_from_scanner_source("macOS USB"), "")

    def test_collect_scan_files_filters_by_extension_and_newness(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_pdf = os.path.join(tmpdir, "old.pdf")
            new_jpg = os.path.join(tmpdir, "new.jpg")
            new_heic = os.path.join(tmpdir, "new.heic")
            new_avif = os.path.join(tmpdir, "new.avif")
            ignored_txt = os.path.join(tmpdir, "notes.txt")
            for path in (old_pdf, new_jpg, new_heic, new_avif, ignored_txt):
                with open(path, "wb") as fh:
                    fh.write(b"x")

            now = 1_700_000_000
            os.utime(old_pdf, (now - 10, now - 10))
            os.utime(new_jpg, (now + 2, now + 2))
            os.utime(new_heic, (now + 3, now + 3))
            os.utime(new_avif, (now + 4, now + 4))
            os.utime(ignored_txt, (now + 2, now + 2))

            results = collect_scan_files(tmpdir, {old_pdf}, now)

            self.assertEqual(results, [new_jpg, new_heic, new_avif])

    def test_merge_scan_files_to_single_pdf_merges_pdf_and_image_inputs(self):
        class FakeWriter:
            def __init__(self):
                self.pages = []

            def add_page(self, page):
                self.pages.append(page)

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        class FakeReader:
            def __init__(self, path):
                self.pages = [f"page:{os.path.basename(path)}"]

        class FakeImage:
            def __init__(self, mode="L"):
                self.mode = mode

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def convert(self, mode):
                return FakeImage(mode=mode)

            def save(self, path, _fmt, resolution=300.0):
                with open(path, "wb") as fh:
                    fh.write(b"%PDF-1.4\n")

        fake_image_module = types.SimpleNamespace(open=lambda _path: FakeImage())
        fake_random = types.SimpleNamespace(randint=lambda _a, _b: 1111)
        fake_time = types.SimpleNamespace(time=lambda: 1_700_000_000.0, strftime=lambda _fmt: "20260318_090000")

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "scan1.pdf")
            img_path = os.path.join(tmpdir, "scan2.png")
            with open(pdf_path, "wb") as fh:
                fh.write(b"%PDF-1.4\n")
            with open(img_path, "wb") as fh:
                fh.write(b"png")

            merged_path, page_count = merge_scan_files_to_single_pdf(
                [pdf_path, img_path],
                tmpdir,
                pdf_writer_cls=FakeWriter,
                pdf_reader_cls=FakeReader,
                image_module=fake_image_module,
                random_module=fake_random,
                time_module=fake_time,
            )

            self.assertTrue(os.path.exists(merged_path))
            self.assertEqual(page_count, 2)
            self.assertTrue(os.path.basename(merged_path).startswith("scan_merged_20260318_090000"))

    def test_merge_scan_files_to_single_pdf_converts_heic_inputs(self):
        class FakeWriter:
            def __init__(self):
                self.pages = []

            def add_page(self, page):
                self.pages.append(page)

            def write(self, fh):
                fh.write(b"%PDF-1.4\n")

        class FakeReader:
            def __init__(self, path):
                self.pages = [f"page:{os.path.basename(path)}"]

        class FakeImage:
            mode = "RGB"

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def save(self, path, _fmt, resolution=300.0):
                with open(path, "wb") as fh:
                    fh.write(b"%PDF-1.4\n")

        opened = []
        fake_image_module = types.SimpleNamespace(open=lambda path: opened.append(path) or FakeImage())
        fake_random = types.SimpleNamespace(randint=lambda _a, _b: 1111)
        fake_time = types.SimpleNamespace(time=lambda: 1_700_000_000.0, strftime=lambda _fmt: "20260318_090000")

        with tempfile.TemporaryDirectory() as tmpdir:
            heic_path = os.path.join(tmpdir, "scan1.heic")
            converted_path = os.path.join(tmpdir, "scan1.png")
            with open(heic_path, "wb") as fh:
                fh.write(b"heic")
            with open(converted_path, "wb") as fh:
                fh.write(b"png")

            merged_path, page_count = merge_scan_files_to_single_pdf(
                [heic_path],
                tmpdir,
                pdf_writer_cls=FakeWriter,
                pdf_reader_cls=FakeReader,
                image_module=fake_image_module,
                random_module=fake_random,
                time_module=fake_time,
                image_prepare_fn=lambda path: converted_path,
            )

            self.assertTrue(os.path.exists(merged_path))
            self.assertEqual(page_count, 1)
            self.assertEqual(opened, [converted_path])
            self.assertFalse(os.path.exists(converted_path))


if __name__ == "__main__":
    unittest.main()
