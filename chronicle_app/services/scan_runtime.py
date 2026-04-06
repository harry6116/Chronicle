import os
import random
import time


def driver_from_scanner_source(source):
    text = (source or "").strip().lower()
    if text.startswith("naps2 "):
        return text.split(" ", 1)[1].strip()
    return ""


def scan_output_extensions():
    return {".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}


def collect_scan_files(output_dir, before_paths, started_ts):
    results = []
    for name in os.listdir(output_dir):
        path = os.path.join(output_dir, name)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext not in scan_output_extensions():
            continue
        try:
            mtime = os.path.getmtime(path)
        except Exception:
            mtime = 0
        if path not in before_paths or mtime >= (started_ts - 1.0):
            results.append(path)

    def _mtime(path):
        try:
            return os.path.getmtime(path)
        except Exception:
            return 0

    return sorted(set(results), key=lambda p: (_mtime(p), p))


def merge_scan_files_to_single_pdf(
    paths,
    output_dir,
    *,
    pdf_writer_cls,
    pdf_reader_cls,
    image_module,
    random_module=random,
    time_module=time,
):
    pdf_writer = pdf_writer_cls()
    temp_pdfs = []
    page_count = 0
    stamp = int(time_module.time() * 1000)

    try:
        for idx, path in enumerate(paths):
            ext = os.path.splitext(path)[1].lower()
            if ext == ".pdf":
                reader = pdf_reader_cls(path)
                for page in reader.pages:
                    pdf_writer.add_page(page)
                    page_count += 1
            elif ext in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}:
                with image_module.open(path) as img:
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    temp_pdf = os.path.join(
                        output_dir,
                        f".chronicle_scan_merge_{stamp}_{idx}_{random_module.randint(1000, 9999)}.pdf",
                    )
                    img.save(temp_pdf, "PDF", resolution=300.0)
                    temp_pdfs.append(temp_pdf)
                    reader = pdf_reader_cls(temp_pdf)
                    for page in reader.pages:
                        pdf_writer.add_page(page)
                        page_count += 1

        if page_count == 0:
            raise ValueError("No mergeable scan pages were found.")

        merged_path = os.path.join(output_dir, f"scan_merged_{time_module.strftime('%Y%m%d_%H%M%S')}.pdf")
        if os.path.exists(merged_path):
            merged_path = os.path.join(
                output_dir,
                f"scan_merged_{time_module.strftime('%Y%m%d_%H%M%S')}_{random_module.randint(1000, 9999)}.pdf",
            )
        with open(merged_path, "wb") as fh:
            pdf_writer.write(fh)
        return merged_path, page_count
    finally:
        for temp_pdf in temp_pdfs:
            try:
                if os.path.exists(temp_pdf):
                    os.remove(temp_pdf)
            except Exception:
                pass
