import re

from chronicle_app.services.text_transforms import transform_reading_text

from .civil_titles import CIVIL_TITLE_ENTRIES
from .medical import MEDICAL_ENTRIES
from .military import MILITARY_ENTRIES
from .newspapers import HISTORICAL_NEWSPAPER_ENTRIES, MODERN_NEWSPAPER_ENTRIES


GLOSSARIES = {
    "civil_titles": CIVIL_TITLE_ENTRIES,
    "historical_newspaper": HISTORICAL_NEWSPAPER_ENTRIES,
    "medical": MEDICAL_ENTRIES,
    "military": MILITARY_ENTRIES,
    "modern_newspaper": MODERN_NEWSPAPER_ENTRIES,
}

PROFILE_GLOSSARIES = {
    "archival": ("military", "historical_newspaper", "civil_titles"),
    "intelligence": ("military", "civil_titles"),
    "manual": ("military", "civil_titles"),
    "military": ("military", "civil_titles"),
    "newspaper": ("historical_newspaper", "modern_newspaper", "civil_titles"),
    "historical_newspaper": ("historical_newspaper", "modern_newspaper", "civil_titles"),
    "modern_newspaper": ("modern_newspaper", "civil_titles"),
    "magazine": ("modern_newspaper", "civil_titles"),
    "medical": ("medical",),
    "legal": ("civil_titles",),
    "government": ("civil_titles",),
}


def _glossary_names_for_profile(doc_profile):
    profile = str(doc_profile or "military").lower()
    return PROFILE_GLOSSARIES.get(profile, ("military", "civil_titles"))


def _iter_entries(doc_profile):
    seen = set()
    for glossary_name in _glossary_names_for_profile(doc_profile):
        for entry in GLOSSARIES.get(glossary_name, ()):
            key = (entry[0], entry[1])
            if key in seen:
                continue
            seen.add(key)
            yield entry


def _expand_text_segment(text, doc_profile):
    cleaned = text
    for entry in _iter_entries(doc_profile):
        pattern, replacement = entry[:2]
        flags = entry[2] if len(entry) > 2 else re.IGNORECASE
        cleaned = re.sub(pattern, replacement, cleaned, flags=flags)
    cleaned = re.sub(r"\bSt\.\s+(?=(?:John|George)\b)", "Saint ", cleaned, flags=re.IGNORECASE)
    return cleaned


def _expand_preserving_acronyms(text, doc_profile):
    parts = re.split(r"((?<!\w)(?:[A-Z]\.){2,}(?:[A-Z]\.?)?)", text)
    result = []
    for index, part in enumerate(parts):
        if index % 2:
            expanded = part
            for entry in _iter_entries(doc_profile):
                pattern, replacement = entry[:2]
                flags = entry[2] if len(entry) > 2 else re.IGNORECASE
                if re.fullmatch(pattern, part, flags=flags):
                    expanded = replacement
                    break
            result.append(expanded)
        else:
            result.append(_expand_text_segment(part, doc_profile))
    return "".join(result)


def expand_abbreviations(text, doc_profile=None):
    return transform_reading_text(text, lambda segment: _expand_preserving_acronyms(segment, doc_profile))
