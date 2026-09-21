import re


def _is_common_leading_elision(fragment: str) -> bool:
    return bool(re.match(r"(?:em|cause|cos|round|til|tis|twas|un|neath)\b", fragment.lower()))


def _normalize_book_dialogue_quotes(text: str) -> str:
    if not text or "'" not in text:
        return text

    chars = []
    open_quote = False
    for index, char in enumerate(text):
        if char != "'":
            chars.append(char)
            continue

        prev_char = text[index - 1] if index > 0 else ""
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if prev_char.isalnum() and next_char.isalnum():
            chars.append(char)
            continue
        if not prev_char.strip() and _is_common_leading_elision(text[index + 1 :]):
            chars.append(char)
            continue
        chars.append('"')
        open_quote = not open_quote
    return "".join(chars)


def _split_fused_book_front_matter(text: str) -> str:
    if not text:
        return ""
    cleaned = text
    cleaned = re.sub(r"(\.\.\.|\.\s\.\s\.)(?=(Books by\b))", r"\1\n\n", cleaned)
    cleaned = re.sub(r"(?<=[a-z0-9\)])(?=(Books by\b))", "\n\n", cleaned)
    cleaned = re.sub(
        r"(?<=[a-z0-9\"'])\s+(?=(PENGUIN BOOKS|NEVER BEFORE HAS A CRIMINAL MASTERMIND)\b)",
        "\n\n",
        cleaned,
    )
    cleaned = re.sub(
        r"(?m)^(ARTEMIS FOWL)\n(?=(NEVER BEFORE HAS A CRIMINAL MASTERMIND)\b)",
        r"\1\n\n",
        cleaned,
    )
    cleaned = re.sub(
        r"(?m)^(NEVER BEFORE HAS A CRIMINAL MASTERMIND)\n(?=(PENGUIN BOOKS)\b)",
        r"\1\n\n",
        cleaned,
    )
    return cleaned

def _normalize_book_page_markers(text: str) -> str:
    if not text:
        return ""

    cleaned = re.sub(
        r"(?m)^(\[Original Page Number:\s*(\d+)\])(?:\s*\n\s*\[Original Page Number:\s*\2\])+$",
        r"\1",
        text,
    )
    marker_pattern = re.compile(r"(?m)^\[Original Page Number:\s*(\d+)\]\s*$")
    matches = list(marker_pattern.finditer(cleaned))
    if len(matches) < 2:
        return cleaned

    parts = []
    last_index = 0
    previous_number = None
    for match in matches:
        current_number = int(match.group(1))
        insertion = ""
        if previous_number is not None and current_number - previous_number > 1:
            insertion = "\n".join(
                f"[Original Page Number: {number}]"
                for number in range(previous_number + 1, current_number)
            ) + "\n"
        parts.append(cleaned[last_index:match.start()])
        parts.append(insertion)
        parts.append(match.group(0))
        last_index = match.end()
        previous_number = current_number
    parts.append(cleaned[last_index:])
    return "".join(parts)


def _repair_obvious_book_scan_wraps(text: str) -> str:
    if not text:
        return ""
    # Only repair a very small set of common suffix splits to avoid harming real compounds.
    return re.sub(
        r"\b([A-Za-z]{4,})-(ing|ed|er|ers|est|ly|ion|ions|ment|ments|ance|ances|ence|ences)\b",
        r"\1\2",
        text,
    )


def _cleanup_numeric_quote_noise(text: str) -> str:
    if not text:
        return ""

    def _fix_line(match):
        line = match.group(0)
        if re.fullmatch(r'[\d"\-\s]+', line.strip()):
            return line.replace('"', "")
        return line

    return re.sub(r"(?m)^.*$", _fix_line, text)


def _apply_book_plain_text_cleanup(text: str, preserve_original_page_numbers: bool) -> str:
    cleaned = text
    cleaned = _cleanup_numeric_quote_noise(cleaned)
    cleaned = re.sub(r"([^\n])((?:#{1,6})\s+[A-Z])", r"\1\n\2", cleaned)
    cleaned = _split_fused_book_front_matter(cleaned)
    cleaned = _normalize_book_dialogue_quotes(cleaned)
    cleaned = _repair_obvious_book_scan_wraps(cleaned)
    if preserve_original_page_numbers:
        cleaned = re.sub(
            r"(?m)^(Chapter\s+\d+:[^\n]+)\n(\d{1,3})$",
            r"\1\n[Original Page Number: \2]",
            cleaned,
        )
        cleaned = re.sub(
            r"(?m)^(\[Original Page Number:\s*\d+\])\n(\[Original Page Number:\s*\d+\])$",
            r"\1\n\2",
            cleaned,
        )
        cleaned = _normalize_book_page_markers(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned
