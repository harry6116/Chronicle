"""Local PDF evidence for extraction and preset decisions."""

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

from chronicle_app.services.adaptive_engine_routing import _sample_page_indices
from chronicle_app.services.nla_newspaper import extract_nla_page_id


_WEB_MARKERS = re.compile(
    r"\b(?:related (?:articles|stories)|more (?:in|from) \w+|read more|share this|"
    r"subscribe|advertisement|featured|listen live|watch now|cookie policy|all rights reserved)\b", re.I
)
_NEWSPAPER_SECTIONS = (
    r"births\s*[,;&–-]\s*(?:deaths|marriages)|family notices|in memoriam",
    r"classified (?:ads|advertisements)|sales by auction|public notices",
    r"letters to the editor|leading articles|editorial",
    r"shipping intelligence|shipping news|telegraphic news|police court",
    r"daily circulation|price one penny|morning edition|evening edition",
)
_WO95_REFERENCE = r"WO[\s/-]+95[\s/-]+\d{1,5}(?:[\s/-]+\d{1,4})?(?:_\d+\.jpe?g)?"
_WO95_PAGE_HEADER = re.compile(
    rf"^\s*The National Archives['’]?\s+reference\s+{_WO95_REFERENCE}\s*$", re.I | re.M,
)
_CROWN_COPYRIGHT = re.compile(r"^\s*(?:©\s*)?Crown Copyright\s*$", re.I | re.M)
_EVENT_CUES = (
    re.compile(r"\b(?:hamfest|swapfest|open (?:day|house)|swap meet|festival|fair|expo)\b", re.I),
    re.compile(r"\b(?:hours|time|when)\s*:|\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", re.I),
    re.compile(r"\b(?:admission|tickets|registration|venue|parking)\b", re.I),
)


@dataclass
class PdfEvidence:
    selected_pages: int
    inspected_pages: tuple
    text_pages: int
    tall_pages: tuple
    regions: int
    webpage: bool
    recommended_profile: str
    reason: str
    trials: tuple
    narrow_columns: int = 0
    image_pages: int = 0
    unit_war_diary: bool = False
    archive_reference_pages: int = 0


def _narrow_columns(page, blocks):
    """Count distinct text starts repeated down the page, including OCR lines."""
    rect = page.rect
    bands = {}
    for x0, y0, x1, _y1, text, *_ in blocks:
        width = (x1 - x0) / rect.width
        if len(text.strip()) < 28 or not .045 <= width <= .24:
            continue
        x = round((x0 - rect.x0) / rect.width / .018)
        y = int((y0 - rect.y0) / rect.height * 8)
        bands.setdefault(x, Counter())[y] += 1
    accepted = []
    for x, counts in sorted(bands.items(), key=lambda pair: -sum(pair[1].values())):
        if len(counts) >= 3 and all(abs(x - other) >= 3 for other in accepted):
            accepted.append(x)
    return len(accepted)


def inspect_pdf(document, indices):
    sizes = [(index, document[index].rect) for index in indices]
    tall = [index for index, rect in sizes if rect.height >= rect.width * 2.5]
    sampled = _sample_page_indices(len(document), indices, max_pages=12)
    # Include unusual page geometry, keeping the expensive text pass bounded.
    unusual = [index for index, _ in sorted(
        sizes, key=lambda item: item[1].height / max(1, item[1].width), reverse=True
    )[:4]]
    inspected = sorted(set(sampled + unusual))
    snippets, text_pages, checked_regions = [], [], 0
    column_counts, image_pages, archive_pages = [], 0, 0
    archive_reference_pages = 0
    metadata = document.metadata or {}
    description = " ".join(str(metadata.get(key) or "") for key in ("title", "subject", "keywords"))
    archive_author = str(metadata.get("author") or "").strip().casefold()
    archive_title = str(metadata.get("title") or "").strip()
    war_diary_metadata = (
        archive_author in {"the national archives", "national archives"}
        and bool(re.fullmatch(_WO95_REFERENCE, archive_title, re.I))
    )
    newspaper_metadata = bool(re.search(r"\bnewspaper\b", description, re.I))
    scan_metadata = bool(re.search(r"\b(?:digitisation|digitization|digitised|digitized|microfilm|archive|archival)\b", description, re.I))
    for index in inspected:
        page = document[index]
        columns = _narrow_columns(page, page.get_text("blocks"))
        column_counts.append(columns)
        full_scan = any(
            (page.rect & page.rect.__class__(image["bbox"])).get_area() >= page.rect.get_area() * .70
            for image in page.get_image_info()
        )
        image_pages += full_scan
        if index in tall:
            height = page.rect.height / 4
            regions = [page.rect.__class__(page.rect.x0, page.rect.y0 + height * part,
                                           page.rect.x1, page.rect.y0 + height * (part + 1))
                       for part in range(4)]
            text = "\n".join(page.get_text("text", clip=region) for region in regions)
            checked_regions += len(regions)
        else:
            text = page.get_text("text")
        # These are page identifiers inside the PDF, not clues from its filename.
        archive_pages += bool(extract_nla_page_id(text))
        if _WO95_PAGE_HEADER.search(text):
            archive_reference_pages += 1
            text = _CROWN_COPYRIGHT.sub("", _WO95_PAGE_HEADER.sub("", text))
        snippets.append(text[:36000])
        if len(" ".join(text.split())) >= 120:
            text_pages.append(index)

    sample = "\n".join(snippets)
    markers = {match.group(0).lower() for match in _WEB_MARKERS.finditer(sample)}
    magazine_metadata = bool(re.search(r"\b(?:magazines?|periodicals?)\b", description, re.I))
    abstract = re.search(r"(?im)^\s*(?:abstract\s*(?:[:—–-]|$)|methodology\s*$)", sample)
    publication = re.search(
        r"(?im)^\s*(?:references|bibliography|results)\s*$|\bdoi\s*:|\bIEEE TRANSACTIONS\b",
        sample,
    )
    narrow = max(column_counts, default=0)
    news_sections = sum(bool(re.search(pattern, sample, re.I)) for pattern in _NEWSPAPER_SECTIONS)
    print_layout = sum(count >= 3 for count in column_counts) >= max(1, (len(inspected) + 2) // 3)
    is_newspaper = (
        (newspaper_metadata and (scan_metadata or print_layout or archive_pages))
        or (archive_pages and (print_layout or image_pages or archive_pages >= 2))
        or (print_layout and news_sections >= 2)
    )
    unit_war_diary = bool(war_diary_metadata or archive_reference_pages)
    event_pages = sum(all(cue.search(page_text) for cue in _EVENT_CUES) for page_text in snippets)
    event_flyers = event_pages >= max(2 if len(indices) > 4 else 1, (len(text_pages) + 1) // 2)
    webpage = not (unit_war_diary or is_newspaper or magazine_metadata or event_flyers or (abstract and publication)) and bool(
        text_pages and ((tall and markers) or len(markers) >= 3)
    )
    if unit_war_diary:
        profile, reason = "military", "The National Archives catalogue reference belongs to the WO 95 unit war diary series."
    elif is_newspaper:
        historical = bool(scan_metadata or archive_pages or image_pages)
        profile = "newspaper" if historical else "modern_newspaper"
        clues = []
        if archive_pages:
            clues.append("Trove digitised newspaper page identifiers")
        elif newspaper_metadata:
            clues.append("newspaper information in the PDF metadata")
        if print_layout:
            clues.append(f"a print layout with up to {narrow} narrow text columns")
        if news_sections >= 2:
            clues.append("newspaper sections such as notices, classifieds or editorials")
        reason = "Detected " + " and ".join(clues) + "."
    elif abstract and publication:
        profile, reason = "academic", "The sample contains an abstract or methodology together with research publication evidence."
    elif magazine_metadata:
        profile, reason = "magazine", "The PDF metadata identifies a magazine or periodical."
    elif webpage:
        profile, reason = "standard", "Webpage furniture and usable source text suggest a webpage capture."
    elif re.search(r"(?im)^\s*(?:annual report|executive summary|management report)\s*$", sample):
        profile, reason = "reports", "A report title or executive summary heading matches a business or government report."
    elif event_flyers:
        profile, reason = "promotional", "Event names, hours and admission or venue details occur together on inspected pages."
    else:
        profile, reason = "standard", "The inspected text does not provide a reliable match for a specialist preset."
    candidates = []
    if tall:
        candidates.append(tall[0] + 1)
    weak = [index + 1 for index in inspected if index not in text_pages]
    if weak:
        midpoint = (indices[0] + indices[-1]) / 2 + 1
        candidates.extend((weak[0], min(weak, key=lambda page: abs(page - midpoint)), weak[-1]))
    if text_pages:
        candidates.extend([text_pages[0] + 1, text_pages[-1] + 1])
    return PdfEvidence(
        len(indices), tuple(index + 1 for index in inspected), len(text_pages),
        tuple(index + 1 for index in tall), checked_regions, webpage, profile, reason,
        tuple(sorted(set(candidates))), narrow, image_pages, unit_war_diary, archive_reference_pages,
    )


def privacy_cost_preview(provider, estimated_units, *, article_only=False, adaptive=False):
    if article_only or provider == "offline":
        return "Processing is local. No pages are uploaded and there is no provider charge."
    extra = " Flagged pages can add an Argon retry." if adaptive else " Retries can add usage."
    return (
        f"Planned provider: {provider}. Selected content may be sent as text, images or PDF segments. "
        f"Estimated workload: {estimated_units} work units.{extra} "
        "Provider rates, generated tokens and account quota determine the charge."
    )


def estimate_token_charge(input_tokens, output_tokens, input_rate, output_rate):
    try:
        numbers = tuple(Decimal(str(value)) for value in (input_tokens, output_tokens, input_rate, output_rate))
        if any(not number.is_finite() or number < 0 or number > Decimal("1e12") for number in numbers):
            raise ValueError
        if any(number != number.to_integral_value() for number in numbers[:2]):
            raise ValueError
    except (InvalidOperation, ValueError):
        raise ValueError("Enter non-negative whole token counts and non-negative prices.") from None
    return (numbers[0] * numbers[2] + numbers[1] * numbers[3]) / Decimal("1000000")
