import io

from chronicle_app.services.pdf_auth import authenticate_pdf_document


class PdfPageRenderer:
    def __init__(
        self,
        *,
        path,
        reader,
        selected_page_indices,
        pdf_writer_cls,
        fitz_module,
        dense_newspaper_default_tile_count=2,
        dense_newspaper_max_tile_count=4,
        dense_newspaper_tile_overlap_ratio=0.025,
    ):
        self.path = path
        self.reader = reader
        self.selected_page_indices = selected_page_indices
        self.pdf_writer_cls = pdf_writer_cls
        self.fitz = fitz_module
        self.dense_newspaper_default_tile_count = dense_newspaper_default_tile_count
        self.dense_newspaper_max_tile_count = dense_newspaper_max_tile_count
        self.dense_newspaper_tile_overlap_ratio = dense_newspaper_tile_overlap_ratio

    def build_pdf_slice_bytes(self, start, end):
        writer = self.pdf_writer_cls()
        for idx in range(start, end):
            writer.add_page(self.reader.pages[self.selected_page_indices[idx]])
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    def build_page_png_bytes(self, page_idx):
        if self.fitz is None:
            raise RuntimeError("PyMuPDF is unavailable for scanned PDF image rendering.")
        last_error = None
        for zoom in (1.8, 1.45, 1.2):
            doc = None
            try:
                doc = self.fitz.open(self.path)
                authenticate_pdf_document(
                    doc,
                    self.path,
                    password=getattr(self.reader, "pdf_password", None),
                )
                page = doc.load_page(self.selected_page_indices[page_idx])
                pix = page.get_pixmap(
                    matrix=self.fitz.Matrix(zoom, zoom),
                    alpha=False,
                    colorspace=self.fitz.csRGB,
                )
                image_bytes = pix.tobytes("png")
                if image_bytes:
                    return image_bytes
            except Exception as render_ex:
                last_error = render_ex
            finally:
                self._close_doc(doc)
        raise RuntimeError(f"Could not render scanned PDF page image: {last_error}")

    def get_dense_newspaper_tile_count(self, page_idx):
        if self.fitz is None:
            return self.dense_newspaper_default_tile_count
        doc = None
        try:
            doc = self.fitz.open(self.path)
            authenticate_pdf_document(
                doc,
                self.path,
                password=getattr(self.reader, "pdf_password", None),
            )
            page = doc.load_page(self.selected_page_indices[page_idx])
            width = float(getattr(page.rect, "width", 0) or 0)
            text_chars = len(page.get_text("text") or "")
            if text_chars >= 100000:
                return self.dense_newspaper_max_tile_count
            if text_chars >= 80000:
                return 3
            if width >= 1800:
                return self.dense_newspaper_max_tile_count
            if width >= 1450:
                return 3
            return self.dense_newspaper_default_tile_count
        except Exception:
            return self.dense_newspaper_default_tile_count
        finally:
            self._close_doc(doc)

    def build_page_tile_png_bytes(self, page_idx, tile_idx, tile_count):
        if self.fitz is None:
            raise RuntimeError("PyMuPDF is unavailable for dense newspaper image rendering.")
        last_error = None
        zooms = (1.7, 1.45, 1.2) if tile_count <= 2 else (2.0, 1.7, 1.45)
        for zoom in zooms:
            doc = None
            try:
                doc = self.fitz.open(self.path)
                authenticate_pdf_document(
                    doc,
                    self.path,
                    password=getattr(self.reader, "pdf_password", None),
                )
                page = doc.load_page(self.selected_page_indices[page_idx])
                rect = page.rect
                overlap = rect.width * self.dense_newspaper_tile_overlap_ratio
                tile_width = rect.width / tile_count
                x0 = max(rect.x0, rect.x0 + tile_idx * tile_width - (overlap if tile_idx else 0))
                x1 = min(
                    rect.x1,
                    rect.x0 + (tile_idx + 1) * tile_width + (overlap if tile_idx < tile_count - 1 else 0),
                )
                clip = self.fitz.Rect(x0, rect.y0, x1, rect.y1)
                pix = page.get_pixmap(
                    matrix=self.fitz.Matrix(zoom, zoom),
                    clip=clip,
                    alpha=False,
                    colorspace=self.fitz.csRGB,
                )
                image_bytes = pix.tobytes("png")
                if image_bytes:
                    return image_bytes
            except Exception as render_ex:
                last_error = render_ex
            finally:
                self._close_doc(doc)
        raise RuntimeError(f"Could not render dense newspaper page strip: {last_error}")

    @staticmethod
    def _close_doc(doc):
        if doc is None:
            return
        try:
            doc.close()
        except Exception:
            pass
