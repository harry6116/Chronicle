"""Extract a reading copy from a text-backed, single-article webpage PDF."""

from collections import Counter
from dataclasses import dataclass
from html import escape
from itertools import groupby
import re
from urllib.parse import urlsplit

from chronicle_app.services.document_preflight import inspect_pdf


LOCAL_ARTICLE_MODEL = "local-webpage-article"
_RELATED = re.compile(r"^(?:more (?:in|from)\b|related (?:articles|stories)|you (?:may|might) also like|recommended for you)", re.I)
_PROMOTION = re.compile(r"^(?:download (?:our|the) .*?app|subscribe(?: now)?|sign up|share this|advertisement|watch now|listen live)\b", re.I)


def article_only_enabled(ext, settings):
    return ext == ".pdf" and settings.get("webpage_reading_mode") == "article"


def write_article_document(stream, article):
    stream.write('<!doctype html>\n<html><head><meta charset="utf-8"><title>'
                 + escape(article["title"]) + '</title></head><body>\n'
                 '<a href="#content">Skip to article</a>\n<main id="content">\n'
                 + article["html"] + "\n")


@dataclass
class Line:
    page: int
    block: int
    x: float
    y: float
    right: float
    size: float
    bold: bool
    text: str
    markup: str


def _read_lines(document, indices, pause=None):
    import fitz
    for index in indices:
        if pause:
            pause()
        page = document[index]
        links = [(link["from"], link["uri"]) for link in page.get_links()
                 if link.get("uri") and urlsplit(link["uri"]).scheme in {"http", "https"}]
        blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES)["blocks"]
        for block_index, block in enumerate(blocks):
            for line in block.get("lines", ()):
                pieces = []
                spans = [span for span in line["spans"] if span["text"].strip()]
                if not spans:
                    continue
                for span in line["spans"]:
                    text = escape(span["text"])
                    bounds = fitz.Rect(span["bbox"])
                    uri = next((uri for rectangle, uri in links
                                if bounds.get_area() and (bounds & rectangle).get_area() >= bounds.get_area() * .72), "")
                    pieces.append(f'<a href="{escape(uri, quote=True)}">{text}</a>' if uri else text)
                x, y, right, _ = line["bbox"]
                yield Line(index + 1, block_index, x, y, right, max(span["size"] for span in spans),
                           any(span["flags"] & 16 for span in spans),
                           "".join(span["text"] for span in line["spans"]).strip(), "".join(pieces).strip())


def build_article(document, indices, *, preserve_page_references=False, pause=None):
    if not inspect_pdf(document, indices).webpage:
        raise ValueError("Article only could not confirm a text-backed webpage capture. Choose Full extraction or include the article’s first page.")
    lines = sorted(_read_lines(document, indices, pause), key=lambda line: (line.page, line.y, line.x))
    first_page = lines[0].page
    starts = Counter(round(line.x / 4) * 4 for line in lines if len(line.text) >= 42)
    if not starts:
        raise ValueError("Article only could not identify an article text column.")
    ranked = starts.most_common(2)
    if len(ranked) == 2 and ranked[1][1] >= ranked[0][1] * .75:
        raise ValueError("Several text columns could contain the article. Use Full extraction to review this capture.")
    left = ranked[0][0]
    primary = [line for line in lines if abs(line.x - left) <= 10]
    body_size = Counter(round(line.size) for line in primary if len(line.text) >= 42).most_common(1)[0][0]
    max_right = max(line.right for line in primary if abs(line.size - body_size) < 1.5)
    title = next((line for line in primary if line.page == first_page and line.size >= body_size * 1.65
                  and len(line.text) >= 8 and not _PROMOTION.match(line.text)), None)
    if title is None:
        raise ValueError("Article only could not identify a reliable headline. Use Full extraction.")
    later = [line for line in lines if (line.page, line.y) > (title.page, title.y)]
    boundary = next((line for line in later if abs(line.x - left) <= 45 and _RELATED.match(line.text)), None)
    boundary_at = (boundary.page, boundary.y) if boundary else (len(document) + 1, 0)
    content = [line for line in lines if (title.page, title.y) <= (line.page, line.y) < boundary_at
               and left - 10 <= line.x <= left + 27 and line.right <= max_right + 35
               and not _PROMOTION.match(line.text)]
    if len(content) < 6:
        raise ValueError("Article only could not verify enough article text. Use Full extraction.")
    if any(line.size >= title.size * .93 and line.page != first_page for line in content):
        raise ValueError("The capture may contain more than one article. Use Full extraction or narrow the page scope.")

    fragments = ["<article>"]
    current_page = None
    saw_title = False
    title_text = ""
    points = []
    for (page, _), group in groupby(content, key=lambda line: (line.page, line.block)):
        group = list(group)
        first = group[0]
        # Remove compact app or player taglines adjacent to trimmed furniture while retaining dates/bylines.
        if (first.size < body_size * .8 and not re.match(r"^(?:by\s|published\b|updated\b|\d)", first.text, re.I)):
            continue
        if page != current_page:
            fragments.append(f'<span id="source-page-{page}"></span>')
            if preserve_page_references:
                fragments.append(f"<h2>Source page {page}</h2>")
            current_page = page
            points.append(page)
        markup = " ".join(line.markup for line in group)
        if not saw_title:
            fragments.append(f"<h1>{markup}</h1>")
            title_text = " ".join(line.text for line in group)
            saw_title = True
        elif first.size >= body_size * 1.28 and len(group) <= 3 and first.bold:
            fragments.append(f"<h2>{markup}</h2>")
        elif len(group) > 1 and all(line.x > left + 10 and len(line.text) < 110 for line in group):
            fragments.append("<ul>" + "".join(f"<li>{line.markup}</li>" for line in group) + "</ul>")
        else:
            fragments.append(f"<p>{markup}</p>")
    fragments.append("</article>")
    return {
        "html": "\n".join(fragments),
        "title": title_text,
        "source_pages": points,
        "end_label": boundary.text if boundary else "",
    }
