import re


def _count(pattern, text, flags=re.IGNORECASE):
    return len(re.findall(pattern, text or "", flags))


def analyze_output_quality(content, *, fmt, doc_profile="standard"):
    text = str(content or "")
    fmt = str(fmt or "").lower()
    profile = str(doc_profile or "standard").lower()
    warnings = []

    if fmt in {"html", "epub"}:
        if _count(r"<h[1-6][^>]*>\s*</h[1-6]>", text):
            warnings.append("empty heading")
        if _count(r"<!doctype\s+html|<html\b|<body\b", text) > 1:
            warnings.append("nested document wrapper")
        if _count(r"\bIMAGE_(?:URL|PLACEHOLDER)\b", text):
            warnings.append("image placeholder token")
        if _count(r"<img\b[^>]*(?:src=[\"']\s*[\"']|src=[\"']about:blank)", text):
            warnings.append("empty image source")
        if _count(r"^\s{0,3}#{1,6}\s+\S", text, re.MULTILINE):
            warnings.append("markdown heading leaked into HTML")
        heading_texts = [
            re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", match)).strip().lower()
            for match in re.findall(r"<h[1-6][^>]*>(.*?)</h[1-6]>", text, re.IGNORECASE | re.DOTALL)
        ]
        adjacent_duplicates = sum(
            1 for prev, cur in zip(heading_texts, heading_texts[1:]) if prev and prev == cur
        )
        if adjacent_duplicates:
            warnings.append("adjacent duplicate heading")
        if profile == "legal":
            for heading in heading_texts:
                if re.fullmatch(r"\d{1,2}\s+[A-Za-z]+\s+\d{4}\.?", heading):
                    warnings.append("date-only legal heading")
                    break
                if re.fullmatch(r"(?:part|chapter|division|section)\s+\d+\s+of\s+.+", heading):
                    warnings.append("legal cross-reference promoted as heading")
                    break
    else:
        if _count(r"<(?:html|body|figure|table|tr|td|th|h[1-6])\b", text):
            warnings.append("HTML tag leaked into non-HTML output")
        if _count(r"data:image/[^;\s]+;base64,", text):
            warnings.append("base64 image payload")

    return {
        "ok": not warnings,
        "warnings": warnings,
        "summary": "Output QA passed." if not warnings else "Output QA flagged: " + "; ".join(warnings),
    }


def build_run_health_summary(*, file_name, output_path, fmt, doc_profile, engine_label, total_units=None, resumed_units=0, qa_report=None):
    units = int(total_units or 0)
    recovered = int(resumed_units or 0)
    lines = [
        f"File: {file_name}",
        f"Output: {output_path}",
        f"Format: {str(fmt or '').upper()}",
        f"Preset: {doc_profile}",
        f"Engine: {engine_label}",
    ]
    if units:
        lines.append(f"Work units: {units}")
    if recovered:
        lines.append(f"Recovered from previous session: {recovered}")
    if qa_report:
        lines.append(qa_report.get("summary", "Output QA unavailable."))
    return "\n".join(lines)
