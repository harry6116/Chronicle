import html
import re
from urllib.parse import quote


def _page_heading_id(page_number, used_ids):
    base = f"page-{page_number}"
    candidate = base
    suffix = 2
    while candidate in used_ids:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used_ids.add(candidate)
    return candidate


def inject_page_navigation(cleaned):
    if not cleaned or re.search(r'<nav\b[^>]*aria-label=(["\'])Page navigation\1', cleaned, flags=re.IGNORECASE):
        return cleaned

    used_ids = {item[1] for item in re.findall(r'\bid=(["\'])(.*?)\1', cleaned, flags=re.IGNORECASE | re.DOTALL)}
    page_links = []

    def _rewrite_page_heading(match):
        attrs = match.group(1) or ""
        inner = match.group(2) or ""
        text = re.sub(r"<[^>]+>", " ", inner)
        text = html.unescape(re.sub(r"\s+", " ", text)).strip()
        page_match = re.fullmatch(r"(?:Source\s+)?Page\s+([0-9]+[A-Za-z]?)", text, flags=re.IGNORECASE)
        if not page_match:
            return match.group(0)
        if re.search(r'\bid\s*=', attrs, flags=re.IGNORECASE):
            id_match = re.search(r'\bid\s*=\s*(["\'])(.*?)\1', attrs, flags=re.IGNORECASE | re.DOTALL)
            heading_id = id_match.group(2) if id_match else _page_heading_id(page_match.group(1).lower(), used_ids)
        else:
            heading_id = _page_heading_id(page_match.group(1).lower(), used_ids)
            attrs = f'{attrs} id="{heading_id}"'
        page_links.append((heading_id, text))
        return f"<h2{attrs}>{inner}</h2>"

    updated = re.sub(
        r"<h2\b([^>]*)>(.*?)</h2>",
        _rewrite_page_heading,
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if len(page_links) < 2:
        return cleaned

    nav_lines = [
        '<nav id="page-navigation" class="page-navigation" role="navigation" aria-label="Page navigation">',
        '<p class="page-navigation-title"><strong>Pages</strong></p>',
        "<ol>",
    ]
    for heading_id, label in page_links:
        nav_lines.append(f'  <li><a href="#{quote(heading_id, safe="-_")}">{html.escape(label)}</a></li>')
    nav_lines.extend(["</ol>", "</nav>"])
    nav_markup = "\n".join(nav_lines)

    title_pattern = r'(<h1\b[^>]*\bid=(["\'])document-title\2[^>]*>.*?</h1>\s*)'
    if re.search(title_pattern, updated, flags=re.IGNORECASE | re.DOTALL):
        return re.sub(title_pattern, r"\1" + nav_markup + "\n", updated, count=1, flags=re.IGNORECASE | re.DOTALL)
    if re.search(r"<main\b[^>]*>", updated, flags=re.IGNORECASE):
        return re.sub(r"(<main\b[^>]*>\s*)", r"\1" + nav_markup + "\n", updated, count=1, flags=re.IGNORECASE)
    return nav_markup + "\n" + updated


def inject_single_page_boundary_from_metadata(cleaned):
    if not cleaned:
        return cleaned
    if re.search(r"<h2\b[^>]*>\s*(?:Source\s+)?Page\s+[0-9]+[A-Za-z]?\s*</h2>", cleaned, flags=re.IGNORECASE):
        return cleaned
    page_match = re.search(
        r"<(?:header|footer)\b[^>]*>.*?\bpage\s+([0-9]+[A-Za-z]?)\b.*?</(?:header|footer)>",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not page_match:
        page_match = re.search(r"https?://nla\.gov\.au/nla\.news-page([0-9]+)", cleaned, flags=re.IGNORECASE)
        if not page_match:
            return cleaned
        page_label = "1"
    else:
        page_label = page_match.group(1)
    heading = f"<h2>Page {html.escape(page_label)}</h2>\n"
    title_pattern = r'(<h1\b[^>]*\bid=(["\'])document-title\2[^>]*>.*?</h1>\s*)'
    if re.search(title_pattern, cleaned, flags=re.IGNORECASE | re.DOTALL):
        return re.sub(title_pattern, r"\1" + heading, cleaned, count=1, flags=re.IGNORECASE | re.DOTALL)
    if re.search(r"<h1\b[^>]*>.*?</h1>", cleaned, flags=re.IGNORECASE | re.DOTALL):
        return re.sub(
            r"(<h1\b[^>]*>.*?</h1>\s*)",
            r"\1" + heading,
            cleaned,
            count=1,
            flags=re.IGNORECASE | re.DOTALL,
        )
    if re.search(r"<main\b[^>]*>", cleaned, flags=re.IGNORECASE):
        return re.sub(r"(<main\b[^>]*>\s*)", r"\1" + heading, cleaned, count=1, flags=re.IGNORECASE)
    return heading + cleaned
