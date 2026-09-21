import html
import os
import re
import urllib.request


NLA_OCR_MARKERS = (
    "national library of australia",
    "nla.gov.au/nla.news-page",
    "nla.news-page",
)


def is_nla_newspaper_profile(cfg):
    return str((cfg or {}).get("doc_profile") or "").lower() == "newspaper"


def is_nla_newspaper_source_path(path):
    name = os.path.basename(str(path or "")).lower()
    return name.startswith("nla.news-") or name.startswith("nla.news_")


def contains_nla_ocr_marker(text, *, sample_chars=40_000, strip_html=False):
    sample = str(text or "")[:sample_chars]
    if strip_html:
        sample = re.sub(r"<[^>]+>", " ", sample)
    sample = sample.lower()
    return any(marker in sample for marker in NLA_OCR_MARKERS)


def extract_nla_page_id(text):
    match = re.search(r"nla\.news-page(\d+)", text or "")
    return match.group(1) if match else None


def fetch_trove_text(url, *, urlopen_fn=None, timeout=25):
    opener = urlopen_fn or urllib.request.urlopen
    request = urllib.request.Request(url, headers={"User-Agent": "Chronicle newspaper OCR rescue"})
    with opener(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def strip_trove_tags(markup):
    cleaned = re.sub(r"<br\s*/?>", "\n", markup or "", flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    return cleaned.strip(" |")


def parse_trove_page_article_ids(page_html):
    article_ids = []
    for article_id in re.findall(r'class="[^"]*articleFromDB[^"]*"[^>]*id="article(\d+)"', page_html or "", flags=re.IGNORECASE):
        if article_id not in article_ids:
            article_ids.append(article_id)
    if article_ids:
        return article_ids
    for article_id in re.findall(r"/newspaper/article/(\d+)", page_html or ""):
        if article_id not in article_ids:
            article_ids.append(article_id)
    return article_ids


def parse_trove_article_rendition(article_html):
    title = ""
    title_match = re.search(r"<title>\s*([^<]+?)\s*</title>", article_html or "", flags=re.IGNORECASE)
    if title_match:
        title = html.unescape(title_match.group(1))
        title = re.sub(r"^\d{2}\s+\w+\s+\d{4}\s+-\s*", "", title).strip().rstrip(".")
    body = (article_html or "").split("<hr/>", 1)[-1]
    paragraphs = []
    for zone in re.findall(r"<div class='zone'>(.*?)</div>", body, flags=re.IGNORECASE | re.DOTALL):
        for match in re.finditer(r"<p[^>]*>(.*?)</p>", zone, flags=re.IGNORECASE | re.DOTALL):
            text = strip_trove_tags(match.group(1))
            compact = re.sub(r"\s+", "", text)
            if len(compact) < 2 or re.fullmatch(r"[-–—_.·,:;\[\](){}]+", compact):
                continue
            paragraphs.append(text)
    while paragraphs and title and paragraphs[0].rstrip(".").casefold() == title.rstrip(".").casefold():
        paragraphs.pop(0)
    return title, paragraphs


def has_large_nla_ocr_text(text, *, min_chars=100_000, sample_chars=40_000, strip_html=False):
    if len(text or "") < min_chars:
        return False
    return contains_nla_ocr_marker(text, sample_chars=sample_chars, strip_html=strip_html)


def should_skip_pdf_textlayer_audit_for_nla_source(*, ext, cfg, path):
    return ext == ".pdf" and is_nla_newspaper_profile(cfg) and is_nla_newspaper_source_path(path)


def should_skip_pdf_textlayer_audit_for_nla_output(*, ext, cfg, extracted_text):
    return (
        ext == ".pdf"
        and is_nla_newspaper_profile(cfg)
        and has_large_nla_ocr_text(extracted_text, min_chars=100_000, sample_chars=20_000, strip_html=True)
    )


def should_skip_cleanup_for_nla_ocr_output(raw_content, *, fmt, job_cfg):
    return (
        fmt in ("html", "txt", "md")
        and is_nla_newspaper_profile(job_cfg)
        and has_large_nla_ocr_text(raw_content, min_chars=100_000, sample_chars=40_000, strip_html=False)
    )
