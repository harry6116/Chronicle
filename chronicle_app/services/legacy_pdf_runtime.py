import os
import random
import tempfile

try:
    import fitz
except ImportError:  # pragma: no cover - optional dependency in lightweight test envs
    fitz = None

from chronicle_core import clean_text_artifacts, sanitize_model_output
from chronicle_app.services.processing_runtime import GEMINI_GENERATE_TIMEOUT_MS
from chronicle_app.services.runtime_policies import wait_for_gemini_upload_ready


LEGACY_PDF_CHUNK_PAGES = 3
GEMINI_FILE_UPLOAD_TIMEOUT_MS = 300_000
GEMINI_FILE_DELETE_TIMEOUT_MS = 30_000


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
            fd, temp_png = tempfile.mkstemp(
                prefix=f"chronicle_legacy_{page_index}_{random.randint(1000, 9999)}_",
                suffix=".png",
                dir=tempfile.gettempdir(),
            )
            os.close(fd)
            with open(temp_png, "wb") as fh:
                fh.write(pix.tobytes("png"))
            try:
                uploaded = client.files.upload(
                    file=temp_png,
                    config={
                        "mime_type": "image/png",
                        "display_name": os.path.basename(temp_png),
                        "http_options": {"timeout": GEMINI_FILE_UPLOAD_TIMEOUT_MS},
                    },
                )
                uploaded = wait_for_gemini_upload_ready(
                    client,
                    uploaded,
                    poll_sec=0.5,
                    max_wait_sec=30.0,
                    log_cb=print,
                )
                try:
                    response = client.models.generate_content_stream(
                        model=model,
                        contents=[uploaded, prompt],
                        config={"http_options": {"timeout": GEMINI_GENERATE_TIMEOUT_MS}},
                    )
                    _append_streamed_text(response, fmt, file_obj, memory)
                finally:
                    try:
                        client.files.delete(
                            name=uploaded.name,
                            config={"http_options": {"timeout": GEMINI_FILE_DELETE_TIMEOUT_MS}},
                        )
                    except TypeError:
                        client.files.delete(name=uploaded.name)
            finally:
                if os.path.exists(temp_png):
                    os.remove(temp_png)
            done += 1
            if page_progress_cb:
                page_progress_cb(done, total_pages)
    finally:
        doc.close()
