import os
import re


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
