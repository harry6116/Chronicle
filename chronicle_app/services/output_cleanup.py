import html
import re
from collections import Counter


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
    paragraph_re = re.compile(r"<p\b[^>]*>.*?</p>\s*", flags=re.IGNORECASE | re.DOTALL)
    tokens = []
    pos = 0
    for match in paragraph_re.finditer(text):
        if match.start() > pos:
            tokens.append(("text", text[pos:match.start()]))
        tokens.append(("p", match.group(0)))
        pos = match.end()
    if pos < len(text):
        tokens.append(("text", text[pos:]))
    if not any(kind == "p" for kind, _value in tokens):
        return text

    for window in range(6, 0, -1):
        changed = True
        while changed:
            changed = False
            result = []
            idx = 0
            while idx < len(tokens):
                block = tokens[idx:idx + window]
                next_block = tokens[idx + window:idx + (window * 2)]
                if (
                    len(block) == window
                    and len(next_block) == window
                    and all(kind == "p" for kind, _value in block)
                    and block == next_block
                ):
                    result.extend(block)
                    idx += window * 2
                    changed = True
                    continue
                result.append(tokens[idx])
                idx += 1
            tokens = result
    return "".join(value for _kind, value in tokens)


def strip_internal_chronicle_output_labels(text_content, format_type):
    if not text_content:
        return text_content
    fmt = str(format_type or "").lower()
    cleaned = str(text_content)
    internal_label_pattern = (
        r"(?:Auto\s+Engine|PDF\s+Heuristic|Gemini(?:\s+PDF|\s+Image|\s+Pro)?|"
        r"FAIL-SAFE|Gearshift|Rate\s+Limit|Throttle|Cache|Progress|Resume|NETWORK\s+STALL\s+ALERT)"
    )
    cleaned = re.sub(r"\[\[CHRONICLE_PROGRESS_STATE::[^\]]*\]\]\s*", "", cleaned)
    cleaned = re.sub(rf"(?im)^\s*\[\s*{internal_label_pattern}\s*\][^\n]*(?:\n|$)", "", cleaned)
    cleaned = re.sub(r"(?i)\bChronicle Note:\s*", "Note: ", cleaned)
    cleaned = re.sub(r"(?i)\[CHRONICLE NOTE:\s*", "[Note: ", cleaned)
    cleaned = re.sub(r"(?i)\[CHRONICLE AUDIT FLAG:\s*", "[Audit flag: ", cleaned)

    if fmt in ("html", "epub"):
        cleaned = re.sub(
            rf"<(?:p|li|div|section|article|aside|h[1-6])\b[^>]*>\s*\[\s*{internal_label_pattern}\s*\][^<]*(?:<br\s*/?>\s*)?</(?:p|li|div|section|article|aside|h[1-6])>\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\sdata-strip=(['\"]).*?\1", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"\sdata-source-page=(['\"]).*?\1", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"\sclass=(['\"])chronicle-[^'\"]*\1", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"<h([1-6])\b([^>]*)>\s*Source\s+page\s+(\d+)\s*,\s*(?:strip|stripe)\s+\d+\s*</h\1>\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"<h([1-6])\b([^>]*)>\s*Source\s+page\s+(\d+)(?:\s*,\s*text\s+layer\s+fallback)?\s*</h\1>",
            r"<h\1\2>Page \3</h\1>",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            r"\b(?:Source\s+page\s+\d+\s*,\s*)?(?:strip|stripe)\s+\d+\b",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\btext\s+layer\s+fallback\b", "", cleaned, flags=re.IGNORECASE)
    else:
        cleaned = re.sub(r"(?im)^\s*Source\s+page\s+\d+\s*,\s*(?:strip|stripe)\s+\d+\s*$", "", cleaned)
        cleaned = re.sub(r"(?im)^\s*Source\s+page\s+(\d+)(?:\s*,\s*text\s+layer\s+fallback)?\s*$", r"Page \1", cleaned)
        cleaned = re.sub(r"\btext\s+layer\s+fallback\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


