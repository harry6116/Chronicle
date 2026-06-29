import html
import os
import re

try:
    import fitz
except ImportError:  # pragma: no cover - optional dependency in lightweight test envs
    fitz = None


def clean_text_artifacts(text):
    if not text:
        return ""
    replacements = {
        "â€™": "'",
        "â€œ": '"',
        "â€": '"',
        "â€“": "-",
        "â€”": "-",
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "Â\xa0": " ",
        "Â": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def build_newspaper_safety_notice(format_type):
    if format_type == "html":
        return (
            '<div class="audit-note" role="note" aria-label="Newspaper Safety Fallback">'
            "<p><strong>Note:</strong> Newspaper safety fallback was applied to keep this reading output stable. "
            "Layout has been simplified to plain semantic blocks.</p></div>"
        )
    if format_type == "epub":
        return (
            '<div class="audit-note" role="note" aria-label="Newspaper Safety Fallback">'
            "<p><strong>Note:</strong> Newspaper safety fallback simplified this page to plain semantic blocks.</p></div>"
        )
    if format_type in ("txt", "md"):
        return "[Note: Newspaper safety fallback simplified this page to keep the reading output stable.]\n\n"
    return ""


def apply_newspaper_html_safety_fallback(text_content, format_type, doc_profile, max_chars=14000):
    if doc_profile != "newspaper" or format_type not in ("html", "epub"):
        return text_content
    if not text_content:
        return text_content
    notice = build_newspaper_safety_notice(format_type)

    def _inject_notice_inside_document(document, note_markup):
        if not note_markup or note_markup in document:
            return document
        if re.search(r"<main\b[^>]*>", document, flags=re.IGNORECASE):
            return re.sub(
                r"(<main\b[^>]*>\s*)",
                r"\1" + note_markup + "\n",
                document,
                count=1,
                flags=re.IGNORECASE,
            )
        if re.search(r"<body\b[^>]*>", document, flags=re.IGNORECASE):
            return re.sub(
                r"(<body\b[^>]*>\s*)",
                r"\1" + note_markup + "\n",
                document,
                count=1,
                flags=re.IGNORECASE,
            )
        return note_markup + "\n" + document

    def _strip_leading_notice(document, note_markup):
        if not note_markup:
            return document, False
        stripped = document.lstrip()
        if not stripped.startswith(note_markup):
            return document, False
        remainder = stripped[len(note_markup):].lstrip()
        return remainder, True

    cleaned = text_content
    cleaned, had_leading_notice = _strip_leading_notice(cleaned, notice)
    cleaned = re.sub(r"<div\b[^>]*>", "<section>", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</div\s*>", "</section>", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<section>\s*</section>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    if had_leading_notice:
        cleaned = _inject_notice_inside_document(cleaned, notice)
    if len(cleaned) <= max_chars:
        return cleaned
    body = re.sub(r"<figure\b[^>]*>.*?</figure>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<table\b[^>]*>.*?</table>", "", body, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<section\b[^>]*>\s*</section>", "", body, flags=re.IGNORECASE | re.DOTALL)
    if format_type in ("html", "epub") and notice and notice not in body:
        body = _inject_notice_inside_document(body, notice)
    return body


class _FitzPageAdapter:
    def __init__(self, page):
        self._page = page

    def extract_text(self):
        return self._page.get_text("text") or ""


class _FitzPdfReaderAdapter:
    def __init__(self, path):
        if fitz is None:
            raise RuntimeError("PyMuPDF (fitz) is required for PDF metadata recovery.")
        self._doc = fitz.open(path)
        meta = self._doc.metadata or {}
        self.metadata = {
            "/Author": meta.get("author", "") or "",
            "/Subject": meta.get("subject", "") or "",
            "/Creator": meta.get("creator", "") or "",
            "/Title": meta.get("title", "") or "",
        }
        self.pages = [_FitzPageAdapter(self._doc.load_page(i)) for i in range(len(self._doc))]


def _default_pdf_reader(path):
    try:
        return _FitzPdfReaderAdapter(path)
    except Exception:
        return None


def _infer_source_attribution(metadata, text_sample, source_path=None):
    metadata = metadata or {}
    text_sample = text_sample or ""
    author = (metadata.get("/Author") or "").strip()
    subject = (metadata.get("/Subject") or "").strip()
    creator = (metadata.get("/Creator") or "").strip()
    combined = " ".join(part for part in (author, subject, creator, text_sample) if part)
    url_match = re.search(r"https?://[^\s<>()]+", text_sample, flags=re.IGNORECASE)
    source_url = url_match.group(0).rstrip(".,);]") if url_match else ""
    stem = os.path.splitext(os.path.basename(source_path or ""))[0]
    archive_match = re.match(r"^([a-z0-9]+_\d{6})(?:_subset_\d+pages)?$", stem, flags=re.IGNORECASE)

    if re.search(r"National Library of Australia|nla\.gov\.au", combined, flags=re.IGNORECASE):
        return {"label": "National Library of Australia", "url": source_url}
    if re.search(r"Internet Archive|archive\.org", combined, flags=re.IGNORECASE):
        return {"label": "Internet Archive", "url": source_url}
    if archive_match:
        identifier = archive_match.group(1)
        return {"label": "Internet Archive", "url": f"https://archive.org/details/{identifier}"}
    if author and source_url:
        return {"label": author, "url": source_url}
    if author:
        return {"label": author, "url": ""}
    return None


def _strip_html_tags(text):
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return clean_text_artifacts(text)


def _extract_first_heading_text(text_content):
    if not text_content:
        return ""
    match = re.search(r"<h1\b[^>]*>(.*?)</h1>", text_content, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    heading = _strip_html_tags(match.group(1))
    return heading.rstrip(" .,:;")


def _extract_publication_date_line(text_content, text_sample):
    candidates = [
        _strip_html_tags(text_content or ""),
        clean_text_artifacts(text_sample or ""),
    ]
    patterns = [
        (
            r"([A-Z][A-Z .'\-]+,\s+(?:MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY),\s+[A-Z]+\s+\d{1,2},\s+\d{4})",
            0,
        ),
        (
            r"((?:MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY),\s+[A-Z]+\s+\d{1,2},\s+\d{4})",
            re.IGNORECASE,
        ),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        for pattern, flags in patterns:
            match = re.search(pattern, candidate, flags=flags)
            if match:
                return re.sub(r"\s+", " ", match.group(1)).strip().rstrip(" .,:;")
    return ""


def _extract_page_number(source_path, metadata, text_sample):
    title = clean_text_artifacts((metadata or {}).get("/Title") or "")
    stem = os.path.splitext(os.path.basename(source_path or ""))[0]
    candidates = [title, stem, clean_text_artifacts(text_sample or "")]
    for candidate in candidates:
        if not candidate:
            continue
        match = re.search(r"\bpage[-_ ]?(\d{1,4})\b", candidate, flags=re.IGNORECASE)
        if match:
            return str(int(match.group(1)))
    return ""


def _infer_newspaper_header_citation(text_content, source_path, metadata, text_sample):
    title = clean_text_artifacts((metadata or {}).get("/Title") or "")
    if title and re.search(r"\bpage\s+\d+\b", title, flags=re.IGNORECASE):
        return title.rstrip(" .")

    page_number = _extract_page_number(source_path, metadata, text_sample)
    heading = _extract_first_heading_text(text_content)
    date_line = _extract_publication_date_line(text_content, text_sample)
    parts = []
    if heading:
        parts.append(heading)
    if date_line:
        parts.append(date_line)
    if page_number:
        parts.append(f"Page {page_number}")
    if parts:
        return ", ".join(parts)
    return ""


def recover_newspaper_header_citation(text_content, format_type, doc_profile, source_path=None, pdf_reader_cls=None):
    if not text_content or format_type not in ("html", "epub") or doc_profile != "newspaper":
        return text_content
    if re.search(r"<header\b[^>]*>\s*<cite\b", text_content, flags=re.IGNORECASE):
        return text_content
    if not source_path or not os.path.exists(source_path) or not source_path.lower().endswith(".pdf"):
        return text_content

    pdf_reader_cls = pdf_reader_cls or _default_pdf_reader
    if pdf_reader_cls is None:
        return text_content

    try:
        reader = pdf_reader_cls(source_path)
        if reader is None:
            return text_content
        metadata = dict(reader.metadata or {})
        text_sample = ""
        if reader.pages:
            text_sample = (reader.pages[0].extract_text() or "")[:4000]
    except Exception:
        return text_content

    citation = _infer_newspaper_header_citation(text_content, source_path, metadata, text_sample)
    if not citation:
        return text_content

    header = f"<header><cite>{html.escape(citation)}</cite></header>"
    if re.search(r"<main\b[^>]*>", text_content, flags=re.IGNORECASE):
        return re.sub(
            r"(<main\b[^>]*>\s*)",
            r"\1" + header + "\n",
            text_content,
            count=1,
            flags=re.IGNORECASE,
        )
    return header + "\n" + text_content


def recover_source_attribution_footer(text_content, format_type, doc_profile, source_path=None, pdf_reader_cls=None):
    if not text_content or format_type not in ("html", "epub") or doc_profile != "newspaper":
        return text_content
    if "<footer><cite>" in text_content.lower():
        return text_content
    if not source_path or not os.path.exists(source_path) or not source_path.lower().endswith(".pdf"):
        return text_content

    pdf_reader_cls = pdf_reader_cls or _default_pdf_reader
    if pdf_reader_cls is None:
        return text_content

    try:
        reader = pdf_reader_cls(source_path)
        if reader is None:
            return text_content
        metadata = dict(reader.metadata or {})
        text_sample = ""
        if reader.pages:
            text_sample = (reader.pages[0].extract_text() or "")[:2000]
    except Exception:
        return text_content

    attribution = _infer_source_attribution(metadata, text_sample, source_path)
    if not attribution:
        return text_content

    label = html.escape(attribution["label"])
    source_url = attribution["url"]
    if source_url:
        safe_url = html.escape(source_url, quote=True)
        footer = f'<footer><cite>{label}</cite> <a href="{safe_url}">{safe_url}</a></footer>'
    else:
        footer = f"<footer><cite>{label}</cite></footer>"

    if re.search(r"</main\s*>", text_content, flags=re.IGNORECASE):
        return re.sub(r"</main\s*>", footer + "\n</main>", text_content, count=1, flags=re.IGNORECASE)
    return text_content.rstrip() + "\n" + footer
