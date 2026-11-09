"""Apply reading transformations without rewriting markup or literal identifiers."""
import re
from html.parser import HTMLParser


_LITERAL_ELEMENTS = {"style", "script", "code", "pre", "kbd", "samp", "textarea", "title", "abbr"}
_IMPRINT = re.compile(r"\bWt\.?\s+[A-Z0-9]|/Forms?/|\b(?:ISBN|ISSN)\b", re.IGNORECASE)
_LITERAL_TOKEN = re.compile(r"https?://[^\s<>]+|\b(?=[\w./-]*[A-Za-z_])[\w.-]+(?:/[\w.-]+)+\b|#[0-9a-fA-F]{3,8}\b")


def transform_reading_text(content, transform):
    if not content:
        return ""

    def prose(text):
        if _IMPRINT.search(text):
            return text
        parts = []
        start = 0
        for match in _LITERAL_TOKEN.finditer(text):
            parts.extend((transform(text[start:match.start()]), match.group()))
            start = match.end()
        parts.append(transform(text[start:]))
        return "".join(parts)

    class Reader(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.offsets = [0]
            for match in re.finditer("\n", content):
                self.offsets.append(match.end())
            self.literal_stack = []
            self.edits = []

        def handle_starttag(self, tag, attrs):
            if tag in _LITERAL_ELEMENTS:
                self.literal_stack.append(tag)

        def handle_endtag(self, tag):
            if tag in self.literal_stack:
                self.literal_stack = self.literal_stack[:self.literal_stack.index(tag)]

        def handle_data(self, data):
            if self.literal_stack:
                return
            line, column = self.getpos()
            start = self.offsets[line - 1] + column
            end = start + len(data)
            if self.edits and self.edits[-1][1] == start:
                self.edits[-1] = (self.edits[-1][0], end)
            else:
                self.edits.append((start, end))

        def handle_entityref(self, name):
            line, column = self.getpos()
            start = self.offsets[line - 1] + column
            length = len(name) + 1
            if content[start + length:start + length + 1] == ";":
                length += 1
            self.handle_data(content[start:start + length])

        def handle_charref(self, name):
            self.handle_entityref("#" + name)

    reader = Reader()
    reader.feed(content)
    reader.close()
    for start, end in reversed(reader.edits):
        content = content[:start] + prose(content[start:end]) + content[end:]
    return content


def add_reading_aid(text, pattern, expansion, *, flags=0, protect_acronyms=False):
    """Keep the source token and add at most one unambiguous reading aid."""
    parts = re.split(r"(\[[^\]\n]*\])", text)
    for index in range(0, len(parts), 2):
        segment = parts[index]
        followed_by_aid = index + 1 < len(parts)

        def replace(match):
            original = match.group()
            if protect_acronyms and re.fullmatch(r"(?:[A-Z]\.?){2,}", original):
                return original
            # Model-provided bracketed aids and uncertainty tags take priority.
            if not segment[match.end():].strip() and followed_by_aid:
                return original
            spoken = expansion(match) if callable(expansion) else match.expand(expansion)
            if original.strip().casefold() == spoken.strip().casefold():
                return original
            return f"{original} [{spoken.strip()}]"

        parts[index] = re.sub(pattern, replace, segment, flags=flags)
    return "".join(parts)
