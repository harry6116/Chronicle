import time

DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-20250514"
LEGACY_MODEL_ALIASES = {
    "claude-3-5-sonnet-20241022": DEFAULT_CLAUDE_MODEL,
}

MODEL_VENDOR_BY_PREFIX = (
    ("claude", "claude"),
    ("gpt", "openai"),
    ("gemini", "gemini"),
)

MODEL_FALLBACK_ORDER = {
    "gemini-2.5-flash": (
        "gemini-2.5-flash",
        DEFAULT_CLAUDE_MODEL,
        "gpt-4o",
    ),
    "gemini-2.5-pro": (
        "gemini-2.5-pro",
        DEFAULT_CLAUDE_MODEL,
        "gpt-4o",
    ),
    DEFAULT_CLAUDE_MODEL: (
        DEFAULT_CLAUDE_MODEL,
        "gpt-4o",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
    ),
    "gpt-4o": (
        "gpt-4o",
        DEFAULT_CLAUDE_MODEL,
        "gemini-2.5-pro",
        "gemini-2.5-flash",
    ),
}


def normalize_model_name(model_name):
    key = str(model_name or "").strip()
    if not key:
        return "gemini-2.5-flash"
    return LEGACY_MODEL_ALIASES.get(key, key)


def persist_runtime_settings_to_cfg(cfg, settings):
    cfg.update(settings)
    return cfg


def get_preferred_profile_model(profile_key, *, cfg, profile_presets):
    raw_override = str(cfg.get("model_override", "") or "").strip()
    if raw_override:
        return normalize_model_name(raw_override)
    return normalize_model_name(
        profile_presets.get(profile_key, profile_presets["standard"]).get("model_name", "gemini-2.5-flash")
    )


def get_model_vendor(model_name):
    key = normalize_model_name(model_name).lower()
    for prefix, vendor in MODEL_VENDOR_BY_PREFIX:
        if prefix in key:
            return vendor
    return "gemini"


def resolve_model_for_available_keys(model_name, *, has_vendor_key_fn):
    preferred_model = normalize_model_name(model_name)
    for candidate in MODEL_FALLBACK_ORDER.get(preferred_model, (preferred_model,)):
        if has_vendor_key_fn(get_model_vendor(candidate)):
            return candidate
    return preferred_model


def get_pdf_chunk_pages(model_name, doc_profile, total_pages, *, file_size_mb=None):
    model = normalize_model_name(model_name).lower()
    profile = str(doc_profile or "").lower()
    avg_page_mb = None
    if file_size_mb is not None and total_pages:
        try:
            avg_page_mb = float(file_size_mb) / max(1, int(total_pages))
        except (TypeError, ValueError):
            avg_page_mb = None
    if total_pages >= 30 and profile == "newspaper":
        if "claude" in model or "gpt" in model:
            return 1
        if "gemini-2.5-pro" in model:
            return 2
    if profile in {"legal", "government"}:
        if total_pages >= 150:
            return 1
        if "gemini-2.5-pro" in model and total_pages >= 60:
            return 2
    if profile == "newspaper" and avg_page_mb is not None and avg_page_mb >= 0.9:
        return 1
    return 2


def wait_for_gemini_upload_ready(
    client,
    uploaded,
    *,
    poll_sec,
    max_wait_sec,
    time_fn=time.time,
    sleep_fn=time.sleep,
    log_cb=print,
):
    start = time_fn()
    current = uploaded
    while True:
        state = getattr(getattr(current, "state", None), "name", "")
        if state == "ACTIVE":
            return current
        if time_fn() - start >= max_wait_sec:
            raise TimeoutError(f"Timed out waiting for Gemini upload to become ACTIVE: {getattr(current, 'name', 'unknown')}")
        if log_cb:
            log_cb(f"[Upload Wait] Waiting for Gemini file to become ACTIVE: {getattr(current, 'name', 'unknown')}")
        sleep_fn(poll_sec)
        current = client.files.get(name=current.name)


def get_model_tradeoff_text(model_name):
    key = normalize_model_name(model_name).lower()
    if key == "gemini-2.5-flash":
        return "Fastest option for clean pages and large batches. Best when you want speed and lower cost."
    if key == "gemini-2.5-pro":
        return "Deep Engine for the hardest scans. Slowest, but strongest on difficult layouts and degraded pages."
    if "claude" in key:
        return "Strong on polished structure and difficult instructions, but slower on large visual batches."
    if "gpt" in key:
        return "Broad multimodal fallback with strong general reasoning, but slower than the fastest Gemini path."
    return "General-purpose model."


def get_processing_speed_warning(profile_key, model_name):
    profile = str(profile_key or "").lower()
    model = normalize_model_name(model_name).lower()

    slow_profiles = {
        "office": "Warning: Reports / Business Files can take longer when Chronicle reconstructs headings, lists, and damaged tables for accessible output.",
        "government": "Warning: Government Reports / Records can take longer on dense tables, appendices, and repeated headers or footers.",
        "letters": "Warning: Letters / Correspondence can slow down when Chronicle is preserving routing lines, annotations, and sign-off structure faithfully.",
        "newspaper": "Warning: Newspapers can be much slower, especially on long scanned PDFs and dense multi-column layouts.",
        "book": "Warning: Books / Novels can take longer on scanned PDFs because Chronicle tries to preserve paragraph continuity across page turns.",
        "archival": "Warning: Archives / Historical can take noticeably longer on handwriting, ledgers, and degraded pages.",
        "handwritten": "Warning: Handwritten Letters / Notes / Diaries can be slow because Chronicle reads them conservatively and avoids guessing unclear words.",
        "medical": "Warning: Medical Records / Clinical Handwriting can be slow because Chronicle treats abbreviations, uncertain handwriting, and medication-like shorthand conservatively.",
        "military": "Warning: Military Records can take longer on dense metadata, chronology, and marginal notes.",
        "academic": "Warning: Academic / Research can be much slower because Chronicle reads dense references, equations, and note structure more conservatively.",
        "manual": "Warning: Manuals / Procedures can take longer on long manuals, dense tables, and diagram-heavy pages.",
        "forms": "Warning: Forms / Checklists can take longer on checkbox-heavy pages and dense field grids.",
        "brochure": "Warning: Brochures / Catalogues can take longer when Chronicle reconstructs multi-panel reading order and product grids.",
        "slides": "Warning: Slides / Presentations can take longer when Chronicle separates slide titles, bullets, diagrams, and repeated template furniture.",
        "legal": "Warning: Legal / Contracts / Laws can take longer because Chronicle reads clause hierarchy, cross-references, and dense tables more conservatively.",
    }
    if profile in slow_profiles:
        return slow_profiles[profile]
    if model == "gemini-2.5-pro":
        return "Warning: Deep Engine is Chronicle's slowest option. Expect longer runs on difficult scans and large files."
    if "claude" in model or "gpt" in model:
        return "Warning: This engine is slower than Chronicle's fastest Gemini path on large visual batches."
    return ""


def build_profile_selection_summary(profile_key, current_model_name, *, profile_label_map, profile_presets):
    profile_label = profile_label_map.get(profile_key, "Standard")
    current_model_name = normalize_model_name(current_model_name)
    recommended = normalize_model_name(
        profile_presets.get(profile_key, profile_presets["standard"]).get("model_name", "gemini-2.5-flash")
    )
    model_label_map = {
        "gemini-2.5-flash": "Fast Engine (Gemini 2.5 Flash)",
        "gemini-2.5-pro": "Deep Engine (Gemini 2.5 Pro)",
        DEFAULT_CLAUDE_MODEL: "Claude Sonnet 4",
        "gpt-4o": "GPT-4o",
    }
    profile_notes = {
        "letters": "Letters / Correspondence favor sender-recipient structure, routing lines, salutations, and sign-off recovery without forcing a report layout.",
        "office": "Reports / Business Files favor accessible heading recovery, list repair, and cleaner business-document structure from messy inputs.",
        "government": "Government Reports / Records favor repeated-header cleanup, appendix structure, and accessible table reading order.",
        "legal": "Legal / Contracts / Laws favor the slower deep-reading path for clause hierarchy, defined terms, and strict cross-reference fidelity.",
        "forms": "Forms / Checklists favor field-by-field recovery, checkbox states, and explicit blank-value handling.",
        "tabular": "Tables / Spreadsheets favor careful semantic table mapping and narrated summaries for accessible review.",
        "manual": "Manuals / Procedures favor step order, warnings, specification tables, and diagram-aware reading order.",
        "slides": "Slides / Presentations favor compact presentation structure, bullet order, and chart-aware narration.",
        "flyer": "Flyers / Posters favor strong short-form hierarchy so dates, places, and calls-to-action stay easy to hear.",
        "brochure": "Brochures / Catalogues favor panel reconstruction, feature grouping, and clean product or service summaries.",
        "book": "Books / Novels favor long-form paragraph continuity, chapter structure, and scanned-page reading order.",
        "newspaper": "Newspapers favor the slowest, most careful engine on dense layouts.",
        "academic": "Academic / Research favors careful handling of citations, equations, footnotes, and scholarly structure.",
        "transcript": "Transcripts / Dialogue favor speaker turns, dialogue flow, and script-like pacing.",
        "poetry": "Poetry / Verse favors preserving stanza shape, line breaks, and indentation.",
        "handwritten": "Handwritten Letters / Notes / Diaries favor conservative reading with strong uncertainty tagging instead of guessed cleanups.",
        "archival": "Archives / Historical favor high-fidelity reading of historical handwriting and ledger structure.",
        "medical": "Medical Records / Clinical Handwriting favors conservative transcription, explicit uncertainty tags, and exact preservation of clinical abbreviations.",
        "military": "Military Records benefit from deeper reading on dense metadata, chronology, and marginal notes.",
        "intelligence": "Intelligence / Cables favor routing headers, codewords, classifications, and terse signal-style formatting.",
        "museum": "Museum Labels / Captions favor short descriptive text, object metadata, and provenance notes.",
    }
    current_label = model_label_map.get(current_model_name, current_model_name)
    recommended_label = model_label_map.get(recommended, recommended)
    lines = [profile_label, profile_notes.get(profile_key, "General-purpose reading profile for mixed documents.")]
    lines.append(f"Recommended engine: {recommended_label}.")
    if current_model_name != recommended:
        lines.append(f"Current override: {current_label}.")
        lines.append("Engine manually overridden.")
    speed_warning = get_processing_speed_warning(profile_key, current_model_name)
    if speed_warning:
        lines.append(speed_warning)
    return " ".join(lines)
