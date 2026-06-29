import html
import re


def should_flag_handwriting_audit(text_content, format_type, doc_profile, min_chars=200):
    if doc_profile not in ("archival", "handwritten"):
        return False
    if not text_content:
        return False
    normalized = text_content
    if format_type in ("html", "epub"):
        normalized = re.sub(r"<br\s*/?>", "\n", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = html.unescape(normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if len(normalized) < min_chars:
        return False
    return "[unclear" not in normalized.lower()


def apply_handwriting_audit_flag(text_content, format_type, doc_profile, whole_document=False):
    if not should_flag_handwriting_audit(text_content, format_type, doc_profile):
        return text_content

    if format_type == "html":
        style_block = (
            ".audit-note {"
            " margin: 0 0 1rem;"
            " padding: 0.85rem 1rem;"
            " border-left: 4px solid #94a3b8;"
            " background: #eef3f8;"
            " color: var(--text);"
            " border-radius: 8px;"
            "}"
            ".audit-note p { margin: 0; }"
            ".audit-note strong { font-weight: 700; }"
        )
        warning = (
            '<div class="audit-note" role="note" aria-label="Transcription Audit Flag">'
            "<p><strong>Note:</strong> This handwritten document was transcribed with high fluency "
            "and no uncertainty markers. Please be aware that automated systems may silently guess degraded cursive.</p>"
            "</div>"
        )
        if whole_document:
            if re.search(r'aria-label="Transcription Audit Flag"', text_content, flags=re.IGNORECASE):
                return text_content
            flagged = re.sub(
                r"(<main\b[^>]*>\s*)",
                r"\1" + warning,
                text_content,
                flags=re.IGNORECASE,
                count=1,
            )
            if ".audit-note" not in flagged:
                if "</style>" in flagged:
                    flagged = flagged.replace("</style>", style_block + "\n</style>", 1)
                elif "</head>" in flagged:
                    flagged = flagged.replace("</head>", f"<style>{style_block}</style>\n</head>", 1)
                elif "<body" in flagged:
                    flagged = re.sub(
                        r"(<body\b[^>]*>\s*)",
                        r"\1<style>" + style_block + "</style>\n",
                        flagged,
                        flags=re.IGNORECASE,
                        count=1,
                    )
                else:
                    flagged = f"<style>{style_block}</style>\n" + flagged
            return flagged
        return warning + "\n" + text_content

    if format_type == "epub":
        warning = (
            '<div class="audit-note" role="note" aria-label="Transcription Audit Flag">'
            "<p><strong>Note:</strong> This handwritten document was transcribed with high fluency "
            "and no uncertainty markers. Please review for potential automated guesses in degraded cursive.</p>"
            "</div>"
        )
        if 'aria-label="Transcription Audit Flag"' in text_content:
            return text_content
        return warning + "\n" + text_content

    if format_type in ("txt", "md"):
        warning = "[Audit flag: Suspiciously fluent handwriting transcription. Review for potential automated guesses.]\n\n"
        if text_content.startswith("[Audit flag:"):
            return text_content
        return warning + text_content

    return text_content


def normalize_form_semantics_html(body):
    body = re.sub(
        r'\[(?:Text\s*input\s*area|Text\s*input|Input\s*area)\]',
        '[Text Field: Empty]',
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r'<input\b[^>]*\btype\s*=\s*(?:["\']?)(?:text|search|email|tel|url|number|date|datetime-local|month|week|time)(?:["\']?)[^>]*\/?>',
        '[Text Field: Empty]',
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r'<textarea\b[^>]*>.*?</textarea\s*>',
        '[Text Field: Empty]',
        body,
        flags=re.IGNORECASE | re.DOTALL,
    )
    body = re.sub(
        r'<input\b(?=[^>]*\btype\s*=\s*(?:["\']?)checkbox(?:["\']?))[^>]*\/?>',
        lambda m: '[Checkbox: Selected]' if re.search(r'\bchecked\b', m.group(0), flags=re.IGNORECASE) else '[Checkbox: Empty]',
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r'<input\b(?=[^>]*\btype\s*=\s*(?:["\']?)radio(?:["\']?))[^>]*\/?>',
        lambda m: '[Radio Button: Selected]' if re.search(r'\bchecked\b', m.group(0), flags=re.IGNORECASE) else '[Radio Button: Empty]',
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r'\[Checkbox:\s*(Selected|Empty)\]\s*(Yes|No)\b',
        r'[Radio Button: \1] \2',
        body,
        flags=re.IGNORECASE,
    )
    return body


_normalize_form_semantics_html = normalize_form_semantics_html
