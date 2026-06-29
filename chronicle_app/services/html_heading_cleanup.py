import html
import re


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


def _strip_html_tags(text):
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return clean_text_artifacts(text)


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


