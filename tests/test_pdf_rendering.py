import unittest

from chronicle_app.services.pdf_rendering import PdfPageRenderer


class PdfRenderingTest(unittest.TestCase):
    def test_build_pdf_slice_uses_selected_source_pages(self):
        class Writer:
            def __init__(self):
                self.pages = []

            def add_page(self, page):
                self.pages.append(page)

            def write(self, buffer):
                buffer.write(",".join(self.pages).encode("utf-8"))

        reader = type("Reader", (), {"pages": ["p1", "p2", "p3"]})()
        renderer = PdfPageRenderer(
            path="dummy.pdf",
            reader=reader,
            selected_page_indices=[2, 0],
            pdf_writer_cls=Writer,
            fitz_module=None,
        )

        self.assertEqual(renderer.build_pdf_slice_bytes(0, 2), b"p3,p1")

    def test_tile_count_uses_text_density_and_width(self):
        class Rect:
            width = 1900

        class Page:
            rect = Rect()

            def get_text(self, _kind):
                return "x" * 100

        class Doc:
            def load_page(self, page_idx):
                self.page_idx = page_idx
                return Page()

            def close(self):
                self.closed = True

        class Fitz:
            @staticmethod
            def open(_path):
                return Doc()

        renderer = PdfPageRenderer(
            path="dummy.pdf",
            reader=type("Reader", (), {"pages": []})(),
            selected_page_indices=[7],
            pdf_writer_cls=object,
            fitz_module=Fitz,
            dense_newspaper_max_tile_count=4,
        )

        self.assertEqual(renderer.get_dense_newspaper_tile_count(0), 4)

    def test_missing_fitz_raises_for_page_image_rendering(self):
        renderer = PdfPageRenderer(
            path="dummy.pdf",
            reader=type("Reader", (), {"pages": []})(),
            selected_page_indices=[0],
            pdf_writer_cls=object,
            fitz_module=None,
        )

        with self.assertRaisesRegex(RuntimeError, "PyMuPDF is unavailable"):
            renderer.build_page_png_bytes(0)


if __name__ == "__main__":
    unittest.main()
