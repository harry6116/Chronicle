import json
import os
import re
import time


def _approx_visible_text(content, *, fmt):
    text = str(content or "")
    if fmt == "html":
        text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def should_reject_transformed_content(raw_content, transformed_content, *, fmt, min_visible_ratio=0.72, min_raw_visible_chars=12000):
    raw_visible = _approx_visible_text(raw_content, fmt=fmt)
    transformed_visible = _approx_visible_text(transformed_content, fmt=fmt)
    raw_len = len(raw_visible)
    transformed_len = len(transformed_visible)
    if raw_len < min_raw_visible_chars:
        return False
    ratio = 0.0 if raw_len == 0 else transformed_len / raw_len
    return ratio < min_visible_ratio


def save_pdf(path, content, large_print=False, *, fpdf_cls, sanitize_latin1_fn):
    pdf = fpdf_cls()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", size=18 if large_print else 11)
    try:
        pdf.write_html(content)
        pdf.output(path)
    except Exception:
        pdf.multi_cell(0, 16 if large_print else 10, text=sanitize_latin1_fn(content))
        pdf.output(path)


def save_docx(path, content, *, docx_module):
    def is_pipe_table_line(line):
        stripped = line.strip()
        return stripped.count("|") >= 2 and stripped.startswith("|") and stripped.endswith("|")

    def parse_pipe_row(line):
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    def is_markdown_table_separator(line):
        cells = parse_pipe_row(line)
        if not cells:
            return False
        return all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)

    def add_pipe_table(doc, lines):
        rows = [parse_pipe_row(line) for line in lines if line.strip()]
        if not rows:
            return
        if len(rows) > 1 and is_markdown_table_separator(lines[1]):
            rows.pop(1)
        if not rows:
            return
        if hasattr(doc, "add_table"):
            table = doc.add_table(rows=len(rows), cols=max(len(row) for row in rows))
            for row_idx, row in enumerate(rows):
                for col_idx, cell in enumerate(row):
                    table.cell(row_idx, col_idx).text = cell
        else:
            for row in rows:
                doc.add_paragraph(" | ".join(row))

    doc = docx_module.Document(path) if os.path.exists(path) else docx_module.Document()
    lines = content.split("\n")
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        clean_line = line.strip()
        if clean_line == "[[PAGE BREAK]]":
            if hasattr(doc, "add_page_break"):
                doc.add_page_break()
            else:
                doc.add_paragraph("")
            idx += 1
            continue
        if is_pipe_table_line(line):
            table_lines = []
            while idx < len(lines) and is_pipe_table_line(lines[idx]):
                table_lines.append(lines[idx])
                idx += 1
            add_pipe_table(doc, table_lines)
            continue
        if clean_line.startswith("### "):
            doc.add_heading(clean_line[4:], level=3)
        elif clean_line.startswith("## "):
            doc.add_heading(clean_line[3:], level=2)
        elif clean_line.startswith("# "):
            doc.add_heading(clean_line[2:], level=1)
        elif re.match(r"^\d+\.\s+", clean_line):
            doc.add_paragraph(re.sub(r"^\d+\.\s+", "", clean_line), style="List Number")
        elif clean_line.startswith("- ") or clean_line.startswith("* "):
            doc.add_paragraph(clean_line[2:], style="List Bullet")
        elif clean_line != "":
            doc.add_paragraph(clean_line)
        idx += 1
    doc.save(path)


def save_epub(path, title, content, lang_code="en", text_dir="ltr", *, epub_module, time_module=time):
    book = epub_module.EpubBook()
    book.set_identifier(f"chron_{int(time_module.time())}")
    book.set_title(title)
    book.set_language(lang_code)
    chapters = re.split(r"(<h2.*?>.*?</h2>)", content, flags=re.IGNORECASE)
    epub_chapters, current_title, current_content, idx = [], title, "", 1
    for segment in chapters:
        if segment.lower().startswith("<h2"):
            if current_content.strip():
                chapter = epub_module.EpubHtml(title=current_title, file_name=f"chap_{idx}.xhtml", lang=lang_code)
                chapter.content = f'<h1>{current_title}</h1><div dir="{text_dir}">{current_content}</div>'
                epub_chapters.append(chapter)
                idx += 1
            current_title = re.sub(r"<[^>]+>", "", segment)
            current_content = segment
        else:
            current_content += segment
    if current_content.strip():
        chapter = epub_module.EpubHtml(title=current_title, file_name=f"chap_{idx}.xhtml", lang=lang_code)
        chapter.content = f'<h1>{current_title}</h1><div dir="{text_dir}">{current_content}</div>'
        epub_chapters.append(chapter)
    for chapter in epub_chapters:
        book.add_item(chapter)
    book.spine = ["nav"] + epub_chapters
    book.add_item(epub_module.EpubNcx())
    book.add_item(epub_module.EpubNav())
    epub_module.write_epub(path, book, {})


def dispatch_save(
    cfg,
    path,
    memory,
    title,
    *,
    sanitize_model_output_fn,
    apply_modern_punctuation_fn,
    apply_modern_currency_fn,
    apply_expanded_abbreviations_fn,
    strip_synthetic_page_filename_headings_fn,
    get_output_lang_code_fn,
    get_output_text_direction_fn,
    save_docx_fn,
    save_pdf_fn,
    save_epub_fn,
):
    if hasattr(memory, "read_all_text"):
        content = memory.read_all_text()
    else:
        content = "".join(memory)
    if not content:
        return
    fmt = cfg.get("format_type", "html")
    raw_content = content
    content = sanitize_model_output_fn(
        content,
        fmt,
        cfg.get("doc_profile"),
        cfg.get("preserve_original_page_numbers", False),
    )
    if cfg.get("modernize_punctuation"):
        content = apply_modern_punctuation_fn(content)
    if cfg.get("unit_conversion"):
        content = apply_modern_currency_fn(content)
    if cfg.get("abbrev_expansion"):
        content = apply_expanded_abbreviations_fn(content)
    if cfg.get("merge_files", False):
        content = strip_synthetic_page_filename_headings_fn(content, fmt)
    if should_reject_transformed_content(raw_content, content, fmt=fmt):
        content = raw_content
    if fmt == "docx":
        save_docx_fn(path, content)
    elif fmt == "pdf":
        save_pdf_fn(path, content, cfg.get("large_print", False))
    elif fmt == "json":
        cleaned = content.strip()[7:-3].strip() if content.strip().startswith("```json") else content.strip()
        try:
            payload = json.loads(cleaned)
        except Exception:
            payload = {"extracted_content": cleaned}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=4)
    elif fmt == "csv":
        cleaned = content.replace("```csv", "").replace("```", "").strip()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(cleaned)
    elif fmt == "epub":
        save_epub_fn(path, title, content, get_output_lang_code_fn(cfg), get_output_text_direction_fn(cfg))
