import html
import re


def render_newspaper_ocr_line_as_html(line):
    compact = re.sub(r"\s+", " ", line or "").strip()
    if not compact:
        return ""
    compact = compact.strip("*# ")
    escaped = html.escape(compact)
    words = compact.split()
    looks_heading = (
        len(words) <= 8
        and any(ch.isalpha() for ch in compact)
        and (
            compact.upper() == compact
            or compact.endswith(":")
            or compact in {"The", "Age"}
        )
    )
    if looks_heading:
        return f"<h3>{escaped.rstrip(':')}</h3>\n"
    return f"<p>{escaped}</p>\n"


def render_plain_newspaper_ocr_as_html(raw_text, source_page, tile_num):
    lines = [line.strip() for line in (raw_text or "").splitlines() if line.strip()]
    if not lines:
        return ""
    fragments = ["<section>"]
    if tile_num in (None, 1):
        fragments.append(f"<h2>Page {source_page}</h2>")
    for line in lines:
        rendered = render_newspaper_ocr_line_as_html(line).rstrip()
        if rendered:
            fragments.append(rendered)
    fragments.append("</section>")
    return "\n".join(fragments)


def stream_plain_newspaper_ocr_as_html(text_stream, source_page, tile_num):
    yield "<section>\n"
    if tile_num in (None, 1):
        yield f"<h2>Page {source_page}</h2>\n"
    pending = ""
    for chunk in text_stream:
        pending += chunk
        while "\n" in pending:
            line, pending = pending.split("\n", 1)
            rendered = render_newspaper_ocr_line_as_html(line)
            if rendered:
                yield rendered
    rendered = render_newspaper_ocr_line_as_html(pending)
    if rendered:
        yield rendered
    yield "</section>\n"


def dense_newspaper_visible_chars(rendered_text, source_page):
    visible = re.sub(r"<[^>]+>", " ", str(rendered_text or ""))
    visible = html.unescape(visible)
    visible = re.sub(r"\bPage\s+%s\b" % re.escape(str(source_page)), " ", visible, flags=re.IGNORECASE)
    visible = re.sub(r"\s+", " ", visible).strip()
    return len(visible)
