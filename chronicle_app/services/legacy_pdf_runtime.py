import os
import random

try:
    import fitz
except ImportError:  # pragma: no cover - optional dependency in lightweight test envs
    fitz = None

from chronicle_core import clean_text_artifacts, sanitize_model_output


LEGACY_PDF_CHUNK_PAGES = 3


def _append_streamed_text(response, fmt, file_obj, memory):
    emitted = []
    for chunk in response:
        text = getattr(chunk, "text", None)
        if not text:
            continue
        cleaned = sanitize_model_output(clean_text_artifacts(text), fmt)
        emitted.append(cleaned)
        if fmt in ("html", "txt", "md") and file_obj:
            file_obj.write(cleaned)
            file_obj.flush()
        if memory is not None:
            memory.append(cleaned)
    return "".join(emitted)


def process_pdf_gemini(client, path, fmt, prompt, model, file_obj, memory, pause_cb=None, page_progress_cb=None):
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is required for legacy PDF extraction.")
    doc = fitz.open(path)
    try:
        total_pages = len(doc)
        done = 0
        for page_index in range(total_pages):
            if pause_cb:
                pause_cb()
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            temp_png = os.path.join(
                os.path.dirname(path),
                f".chronicle_legacy_{page_index}_{random.randint(1000, 9999)}.png",
            )
            with open(temp_png, "wb") as fh:
                fh.write(pix.tobytes("png"))
            try:
                uploaded = client.files.upload(file=temp_png)
                try:
                    response = client.models.generate_content_stream(model=model, contents=[uploaded, prompt])
                    _append_streamed_text(response, fmt, file_obj, memory)
                finally:
                    client.files.delete(name=uploaded.name)
            finally:
                if os.path.exists(temp_png):
                    os.remove(temp_png)
            done += 1
            if page_progress_cb:
                page_progress_cb(done, total_pages)
    finally:
        doc.close()
