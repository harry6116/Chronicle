import csv
import html
import io
import os
import re
from urllib.parse import quote

from chronicle_app.services.book_cleanup import _apply_book_plain_text_cleanup
from chronicle_app.services.book_cleanup import _normalize_book_dialogue_quotes
from chronicle_app.services.book_cleanup import _normalize_book_page_markers
from chronicle_app.services.html_heading_cleanup import _promote_bare_instruction_heading
from chronicle_app.services.html_heading_cleanup import _promote_bare_military_instruction_heading
from chronicle_app.services.html_heading_cleanup import _promote_bold_followup_after_h1
from chronicle_app.services.html_heading_cleanup import _promote_context_paragraph_heading
from chronicle_app.services.html_heading_cleanup import _promote_definition_list_headings
from chronicle_app.services.html_heading_cleanup import _promote_index_heading
from chronicle_app.services.html_heading_cleanup import _promote_index_section_heading
from chronicle_app.services.html_heading_cleanup import _promote_list_section_headings
from chronicle_app.services.html_heading_cleanup import _promote_military_continuation_heading
from chronicle_app.services.html_heading_cleanup import _promote_military_order_page_heading
from chronicle_app.services.html_heading_cleanup import _promote_numbered_instruction_headings
from chronicle_app.services.html_heading_cleanup import _promote_ordered_list_instruction_headings
from chronicle_app.services.html_heading_cleanup import _promote_short_first_h2_to_h1
from chronicle_app.services.html_heading_cleanup import _promote_short_h2_with_bold_followup
from chronicle_app.services.html_heading_cleanup import _promote_strong_paragraph_headings
from chronicle_app.services.output_cleanup import _collapse_inline_image_sources
from chronicle_app.services.output_cleanup import _convert_markdown_headings_inside_html
from chronicle_app.services.output_cleanup import _dedupe_adjacent_html_paragraph_blocks
from chronicle_app.services.output_cleanup import _strip_broken_placeholder_images_html
from chronicle_app.services.output_cleanup import _strip_html_page_wrapper_noise
from chronicle_app.services.output_cleanup import _strip_repeated_periodical_running_head_h1s
from chronicle_app.services.output_cleanup import strip_internal_chronicle_output_labels
from chronicle_app.services.handwriting_forms import _normalize_form_semantics_html
from chronicle_app.services.handwriting_forms import apply_handwriting_audit_flag
from chronicle_app.services.handwriting_forms import should_flag_handwriting_audit
from chronicle_app.services.html_heading_cleanup import _extract_running_header_title
from chronicle_app.services.html_heading_cleanup import _looks_like_heading_text
from chronicle_app.services.html_heading_cleanup import _promote_leading_paragraph_headings
from chronicle_app.services.html_heading_cleanup import _promote_sparse_heading_blocks
from chronicle_app.services.html_page_navigation import inject_page_navigation
from chronicle_app.services.html_page_navigation import inject_single_page_boundary_from_metadata
from chronicle_app.services.newspaper_processing import apply_newspaper_html_safety_fallback
from chronicle_app.services.newspaper_processing import build_newspaper_safety_notice
from chronicle_app.services.newspaper_processing import recover_newspaper_header_citation
from chronicle_app.services.newspaper_processing import recover_source_attribution_footer

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:  # pragma: no cover - optional dependency in lightweight test envs
    BeautifulSoup = None
    NavigableString = str
    Tag = None


MAX_FULL_DOCUMENT_HTML_NORMALIZATION_CHARS = 200_000


def _should_skip_expensive_full_html_normalization(body):
    return len(str(body or "")) > MAX_FULL_DOCUMENT_HTML_NORMALIZATION_CHARS


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


def get_modern_newspaper_profile_rules(format_type):
    table_rule = (
        "Rebuild sports boxes, election results, market tables, listings, and data panels into valid HTML tables when the row/column relationships are clear."
        if format_type in ("html", "epub")
        else "Rebuild sports boxes, election results, market tables, listings, and data panels into plain-text rows and columns with stable cell alignment."
    )
    return (
        "MODERN NEWSPAPER / E-PAPER RULES:\n"
        "- Treat the source as a contemporary newspaper, e-paper, or print-edition PDF, not a historical OCR newspaper scan and not a magazine feature layout.\n"
        "- Segment pages into masthead, section label, article, brief, live-update block, editorial/opinion piece, photo/caption, advertisement, sponsored content, index/teaser, puzzle, weather, sport, and table regions before transcription.\n"
        "- Article Boundaries: Preserve headlines, decks/subheads, bylines, wire/source labels, datelines, timestamps, corrections, section tags, and article breaks. Do not merge adjacent briefs or teasers into the main story.\n"
        "- Reading Order: Follow modern news hierarchy first, then columns within each story. Do not read straight across unrelated article cards, sidebars, ad blocks, or teaser modules.\n"
        "- Continuations and Jumps: Preserve visible `continued from`, `continued on`, jump-line, page-reference, and web-link cues. Join continuations only when the source explicitly marks the relationship.\n"
        "- Digital Furniture: Preserve meaningful publication metadata, issue/date/section labels, captions, correction notes, and source URLs. Suppress repeated navigation chrome, subscription prompts, sharing widgets, and template boilerplate when they are not document content.\n"
        "- Advertisements and Sponsored Content: Keep advertisements, sponsored posts, advertorial labels, and public notices as distinct sections when readable. Never interleave them into nearby reporting.\n"
        f"- Data Panels: {table_rule}\n"
        "- Photo Packages: Keep captions, credits, and cutlines attached to the nearest image. Describe meaningful news photos when image descriptions are enabled.\n"
        "- Modern Typography: Preserve contemporary punctuation, capitalization, acronyms, names, URLs, and social handles exactly unless the global punctuation toggle explicitly allows spacing-only cleanup.\n"
        "- HTML Simplicity: Output clean semantic article/section blocks. Do not recreate the newspaper as a visual facsimile, CSS grid, absolute-positioned layout, or image map.\n"
        "- Magazine Boundary: If the page behaves like a long-form magazine feature with contents-page furniture, reviews, pull quotes, and feature packages, keep the content faithful but do not invent magazine-only issue structure."
    )


def sanitize_model_output(text_content, format_type, doc_profile=None, preserve_original_page_numbers=False):
    if not text_content:
        return ""
    cleaned = strip_internal_chronicle_output_labels(text_content, format_type)
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
        cleaned = re.sub(r"\[Image:\s*([^\]]+)\]", r"[Image Description: \1]", cleaned, flags=re.IGNORECASE)
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
    return strip_internal_chronicle_output_labels(cleaned, format_type)


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


def apply_expanded_abbreviations(html_text: str, doc_profile=None) -> str:
    from chronicle_app.services.abbreviations import expand_abbreviations

    return expand_abbreviations(html_text, doc_profile=doc_profile)


def _inject_html_toc(text_content, *, include_page_headings=True):
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
        if not include_page_headings and re.fullmatch(
            r"(?:Source\s+)?Page\s+[0-9]+[A-Za-z]?",
            heading_text or "",
            flags=re.IGNORECASE,
        ):
            return match.group(0)
        if not heading_text or _is_noise_heavy_heading(heading_text, level):
            return match.group(0)
        counter += 1
        id_match = re.search(r'\bid=(["\'])(.*?)\1', attrs, flags=re.IGNORECASE | re.DOTALL)
        heading_id = id_match.group(2) if id_match else f"heading-{counter}"
        headings.append((int(level), heading_id, heading_text))
        if id_match:
            return match.group(0)
        return f'<h{level}{attrs} id="{heading_id}">{inner}</h{level}>'

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
        if not include_page_headings:
            return cleaned
        document_title_match = re.search(
            r'<h1\b([^>]*)\bid=(["\'])document-title\2([^>]*)>(.*?)</h1>',
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not document_title_match:
            return cleaned
        title_text = _strip_html_tags(document_title_match.group(4)) or "Document"
        visible_headings = [(1, "document-title", title_text)]

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


def _strip_page_boundary_headings_html(body):
    if not body:
        return body
    cleaned = re.sub(
        r'<nav\b[^>]*aria-label=(["\'])Page navigation\1[^>]*>.*?</nav>\s*',
        "",
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    cleaned = re.sub(
        r'<h2\b[^>]*>\s*(?:Source\s+)?Page\s+[0-9]+[A-Za-z]?\s*</h2>\s*',
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def _strip_html_tags(text):
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return clean_text_artifacts(text)


def _normalize_heading_hierarchy_html(body):
    match = re.search(r'(<main\b[^>]*>)(.*?)(</main\s*>)', body, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return body
    inner = match.group(2)
    original_inner = inner
    if re.search(r'<h1\b[^>]*\bid=(["\'])document-title\1', inner, flags=re.IGNORECASE):
        h1_seen = False

        def _demote_extra_h1(match_obj):
            nonlocal h1_seen
            if not h1_seen:
                h1_seen = True
                return match_obj.group(0)
            attrs = match_obj.group(1) or ""
            content = match_obj.group(2) or ""
            return f"<h2{attrs}>{content}</h2>"

        inner = re.sub(
            r"<h1\b([^>]*)>(.*?)</h1>",
            _demote_extra_h1,
            inner,
            flags=re.IGNORECASE | re.DOTALL,
        )
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


def normalize_streamed_html_document(full_html, *, insert_page_navigation=True, preserve_page_headings=True):
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
    body = re.sub(r"\[Image:\s*([^\]]+)\]", r"[Image Description: \1]", body, flags=re.IGNORECASE)
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

    if _should_skip_expensive_full_html_normalization(body):
        body = inject_single_page_boundary_from_metadata(body)
        if not preserve_page_headings:
            body = _strip_page_boundary_headings_html(body)
        elif insert_page_navigation:
            body = inject_page_navigation(body)
        if insert_page_navigation:
            body = _inject_html_toc(body, include_page_headings=preserve_page_headings)
        return f"{prefix}\n{body.strip()}\n{suffix}"

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
    body = inject_single_page_boundary_from_metadata(body)
    if not preserve_page_headings:
        body = _strip_page_boundary_headings_html(body)
    elif insert_page_navigation:
        body = inject_page_navigation(body)
    body = _inject_html_toc(body, include_page_headings=preserve_page_headings if insert_page_navigation else False)
    body = _strip_broken_placeholder_images_html(body)
    body = _strip_leaked_document_wrappers_html(body)
    body = body.strip()
    return f"{prefix}\n{body}\n{suffix}"


def write_header(file_obj, title, format_type, lang_code="en", text_dir="ltr"):
    if format_type != "html":
        return
    safe_lang = html.escape(str(lang_code or "en"), quote=True)
    safe_dir = html.escape(str(text_dir or "ltr"), quote=True)
    safe_title = html.escape(title or "Chronicle Output")
    file_obj.write(
        f"""<!DOCTYPE html>
<html lang="{safe_lang}" dir="{safe_dir}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title}</title>
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
.audit-note {{
  margin: 0 0 1rem;
  padding: 0.85rem 1rem;
  border-left: 4px solid #94a3b8;
  background: #eef3f8;
  color: var(--text);
  border-radius: 8px;
}}
.audit-note p {{ margin: 0; }}
.audit-note strong {{ font-weight: 700; }}
.skip-link {{
  position: absolute;
  left: 1rem;
  top: 1rem;
  transform: translateY(-160%);
  background: #ffffff;
  color: #0f172a;
  border: 2px solid #0f172a;
  border-radius: 4px;
  padding: 0.5rem 0.75rem;
  z-index: 10;
}}
.skip-link:focus {{ transform: translateY(0); }}
.page-navigation {{
  margin: 0 0 1.25rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--rule);
  background: var(--surface);
  border-radius: 8px;
}}
.page-navigation-title {{ margin: 0 0 0.5rem; }}
.page-navigation ol {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 0.85rem;
  margin: 0;
  padding-left: 1.25rem;
}}
.page-navigation a {{ color: #1d4ed8; }}
:focus-visible {{ outline: 3px solid #1d4ed8; outline-offset: 3px; }}
</style>
</head>
<body>
<a class="skip-link" href="#content">Skip to content</a>
<main id="content" role="main" aria-labelledby="document-title">
<h1 id="document-title">{safe_title}</h1>
"""
    )
    file_obj.flush()


def write_footer(file_obj, format_type):
    if format_type != "html":
        return
    file_obj.write("\n</main>\n</body>\n</html>")
    file_obj.flush()
