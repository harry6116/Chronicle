import html
import re


BOUNDARY_FORMATS = {"html", "epub", "md", "txt", "docx", "pdf"}


def output_format_keeps_page_boundaries(fmt):
    return str(fmt or "").lower() in BOUNDARY_FORMATS


def ensure_source_page_boundary(text, source_page, *, fmt):
    if not output_format_keeps_page_boundaries(fmt):
        return text

    content = "" if text is None else str(text)
    fmt_key = str(fmt or "").lower()
    page_label = f"Page {source_page}"

    if fmt_key in {"html", "epub"}:
        heading_re = (
            r"<h[1-6]\b[^>]*>\s*(?:Source\s+)?Page\s+"
            + re.escape(str(source_page))
            + r"\s*</h[1-6]>"
        )
        if re.search(heading_re, content, flags=re.IGNORECASE):
            return content

        stripped = content.lstrip()
        leading_ws = content[: len(content) - len(stripped)]
        if re.match(r"<section\b[^>]*>", stripped, flags=re.IGNORECASE):
            return leading_ws + re.sub(
                r"(<section\b[^>]*>\s*)",
                r"\1" + f"<h2>{html.escape(page_label)}</h2>\n",
                stripped,
                count=1,
                flags=re.IGNORECASE,
            )
        return f"<section>\n<h2>{html.escape(page_label)}</h2>\n{content.rstrip()}\n</section>\n"

    line_re = r"(?im)^\s*(?:Source\s+)?Page\s+" + re.escape(str(source_page)) + r"\s*$"
    if re.search(line_re, content):
        return content
    return f"{page_label}\n\n{content.lstrip()}"
