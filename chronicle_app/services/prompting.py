import re

from chronicle_core import get_newspaper_profile_rules


def get_translation_target(cfg, translation_targets):
    target = str(cfg.get("translate_target", "English")).strip()
    lookup = {name.lower(): (name, code) for name, code in translation_targets}
    return lookup.get(target.lower(), ("English", "en"))


def get_output_lang_code(cfg, translation_targets):
    if cfg.get("translate_mode", "none") == "none":
        return "und"
    _, code = get_translation_target(cfg, translation_targets)
    return code


def get_output_text_direction(cfg, translation_targets, rtl_language_codes):
    if cfg.get("translate_mode", "none") == "none":
        return "auto"
    code = get_output_lang_code(cfg, translation_targets)
    return "rtl" if code in rtl_language_codes else "ltr"


def build_prompt(
    cfg,
    *,
    translation_targets,
    rtl_language_codes,
    format_type,
):
    target_name, target_code = get_translation_target(cfg, translation_targets)
    unit = (
        "Convert all pre-decimal, historical, or shorthand currency formats into full, spoken words so they are "
        "natively understood by screen readers. For example, convert '£5/10/-' to '5 pounds, 10 shillings', "
        "convert '3d.' to '3 pence', and convert '5/-' to '5 shillings'."
        if cfg.get("unit_conversion")
        else "Leave all historical currency/measurements untouched with no conversion."
    )
    trans_mode = cfg.get("translate_mode")
    if trans_mode == "none":
        trans = "Do not translate. Preserve all source-language text exactly."
    elif trans_mode == "both":
        trans = (
            f"Translate to {target_name}, keeping original-language text inline in brackets "
            "after each translated segment."
        )
    else:
        trans = f"Translate fully to {target_name} and output only translated text."
    punct = (
        "You must act as an accessibility formatting layer. Your goal is to make the text fully readable for "
        "text-to-speech engines without altering any factual words. You must aggressively remove archaic "
        "typesetting quirks (e.g., dash-appended periods like '.-' or ',-' and unnecessary hyphens in street names). "
        "CRITICAL SPACING RULE: When removing these archaic punctuation marks, you MUST ensure that proper, "
        "single spacing is preserved between words and sentences. Never jam words together (e.g., output "
        "'Friday. Mrs.' not 'Friday.Mrs.')."
        if cfg.get("modernize_punctuation")
        else "Legacy punctuation mode disabled: maintain exact original punctuation, including old-style marks."
    )
    img = (
        "Describe images in brackets [Image Description: ...]. For any meaningful visual content, including "
        "title-page artwork, photographs, seals, insignia, maps, diagrams, or illustrated advertisements, "
        "include a concrete image description instead of omitting it or substituting a source filename."
        if cfg.get("image_descriptions")
        else 'Output <img alt=""> for all images to hide them from screen readers.'
    )
    page_number_rule = (
        "Preserve visible original printed page numbers as standalone reference markers when they are clearly present. "
        "Use the explicit transcription-friendly form `[Original Page Number: X]` at the relevant boundary, but do not let those markers interrupt a paragraph mid-flow. "
        "When the source shows a visible printed folio, preserve it once as a stable boundary marker instead of leaving a bare number line behind."
        if cfg.get("preserve_original_page_numbers", False)
        else "Suppress standalone printed page numbers, folios, and running page-number furniture unless they are essential to the meaning of the document."
    )
    abbrev = (
        "To ensure WCAG-compliant screen reader accessibility, you must expand all historical, military, or "
        "shorthand abbreviations into their full, spoken-word equivalents based on the context of the sentence "
        "(e.g., expand 'Lieut.' to 'Lieutenant', 'Sgt.' to 'Sergeant', 'St.' to 'Street' or 'Saint'). Do not "
        "change the underlying meaning of the text."
        if cfg.get("abbrev_expansion")
        else "Maintain exact original abbreviations."
    )
    wcag = (
        "WCAG 2.2 COMPLIANCE:\n"
        "- Strict semantic HTML heading hierarchies (H1 -> H2 -> H3).\n"
        '- Tables MUST use <th> with scope="col" or scope="row".\n'
        "- TABULAR DATA ENFORCEMENT: You must identify any text that is visually arranged in a grid or column-based table (such as Commencement Information in legislation or Muster Rolls in military documents). You MUST output this data using standard HTML `<table>`, `<tr>`, `<th>`, and `<td>` tags. Ensure each column has a clear header (`<th>`) with a `scope=\"col\"` attribute. Never render these grids as blocks of text or lists, as they must be navigable row-by-row for screen reader users."
    )
    ascii_guard = (
        "ENCODING SAFETY: Use plain ASCII punctuation where possible; avoid smart punctuation that can cause "
        "mojibake in older readers."
    )
    if trans_mode == "none":
        lang = (
            'LANGUAGE DETECTION: Detect primary language and set `<html lang="...">`. Preserve Maori macrons/'
            'diacritics and wrap inline language spans where needed (e.g., `<span lang="mi">...`).'
        )
    else:
        lang = (
            f'LANGUAGE OUTPUT: Output language is {target_name} (`{target_code}`). Set `<html lang="{target_code}">`. '
            "If preserving source text (bracket mode), wrap source-language spans with accurate `lang` attributes."
        )
    bidi_rules = (
        "BIDIRECTIONAL TEXT ACCESSIBILITY:\n"
        '- Set root direction with `dir` (`ltr` for left-to-right languages, `rtl` for right-to-left languages).\n'
        '- In mixed-language inline runs, wrap fragments with `<bdi>` or `<span dir="..." lang="...">` '
        "to prevent punctuation/number reordering.\n"
        "- Keep bracketed translations directionally isolated so screen readers read them in natural order."
    )
    translation_quality = (
        "TRANSLATION INTEGRITY:\n"
        "- Preserve names, place names, military unit labels, and quoted archival identifiers unless a "
        "standard target-language exonym exists.\n"
        "- Keep dates, numbers, and references exact; do not invent missing expansions.\n"
        "- FRACTION PRESERVATION: Never decimalize, simplify, or rewrite historical fractions during translation. "
        "Preserve exact fraction form and meaning (e.g., `3/8`, `1 5/16`, `1/8` -> `\\frac{1}{8}` when in math context).\n"
        "- If a phrase is uncertain, keep the source phrase and add `[Translator Uncertain]`."
    )
    recovery_rules = (
        "ACCESSIBILITY REMEDIATION & RECOVERY:\n"
        "- If the source file is structurally broken, malformed, duplicated, or poorly exported, produce a more accessible equivalent while preserving the source meaning and visible content.\n"
        "- MALFORMED SOURCE RECOVERY: Repair broken HTML/tag soup, broken list structure, duplicated OCR overlays, damaged paragraph wrapping, and malformed table text conservatively. Do not preserve inaccessible source defects when a faithful accessible reconstruction is possible.\n"
        "- HEADING RECOVERY: Promote only true visible titles/section heads into headings. Never create fake headings just for decoration, and never skip heading levels.\n"
        "- LIST RECOVERY: Reconstruct true ordered/unordered lists so each item is distinct and screen-reader navigable.\n"
        "- TABLE RECOVERY: Reconstruct true tables when row/column relationships are clear. If they are not clear enough for a faithful table, keep them as explicit row-wise text instead of inventing structure.\n"
        "- DUPLICATE SUPPRESSION: When the same text clearly appears twice due to OCR layers, copy/paste corruption, or malformed exports, keep one faithful instance and note `[Duplicate Artifact Removed]` only when necessary.\n"
        "- OUTPUT IMPROVEMENT RULE: The output may be cleaner and more accessible than the source, but never less complete, less faithful, or less navigable."
    )
    execution_protocol = (
        "EXECUTION PROTOCOL:\n"
        "- STEP 1: Detect page type first (letter, ledger/table, form, telegram/cable, newspaper layout, comic/manga page, book/novel page, diagram/image, mixed).\n"
        "- STEP 2: Apply global CRITICAL RULES and TOGGLES before any profile-specific transformations.\n"
        "- STEP 3: Apply the selected profile rules only where they match visible evidence on the page.\n"
        "- STEP 4: If a page is mixed-content, keep each region in source order and tag transitions clearly.\n"
        "- STEP 5: Never invent headings/fields/values to force a profile pattern. Unknown content must remain explicit as uncertain.\n"
        "- STEP 6: Prefer structure-preserving output over readability rewrites when there is conflict.\n"
        "- STEP 7: On dense pages, iterate/re-read before finalizing output to avoid omissions.\n"
        "- STEP 8: For multi-column pages, slide decks, and mixed tables/figures, preserve human reading order and keep captions/legends with their nearest object.\n"
        "- STEP 9: Preserve declassification/release markings, distribution headers, and document control numbers exactly as printed."
    )
    pdf_scan_rules = (
        "PDF / SCANNED PAGE RULES:\n"
        "- Treat visual page turns, gutter shadows, skew, and scan borders as layout artifacts, not content.\n"
        "- Preserve paragraph continuity across page breaks. Do not turn every wrapped scan line into a new paragraph.\n"
        "- Rejoin words split by line-wrap or page-wrap hyphenation only when the hyphen is clearly caused by physical layout.\n"
        "- Keep running headers, folios, and repeated page furniture out of the body flow when they are clearly repetitive page decorations rather than unique document content.\n"
        "- If the PDF text layer disagrees with the visible page, prioritize the visible reading order and recover omitted visible text conservatively.\n"
        "- For scanned PDFs with mixed prose and illustrations, keep captions with their nearest figure and resume the prose where it continues."
    )
    word_mode_rules = (
        "WORD / DOCX OUTPUT RULES:\n"
        "- Output must remain plain text with Word-friendly structure only. Do not emit literal HTML tags.\n"
        "- Use markdown-style headings (`#`, `##`, `###`) for document title and section titles so Chronicle can map them cleanly into Word headings.\n"
        "- Do not use inline markdown emphasis markers such as `**bold**`, `*italics*`, `_italics_`, or backticks in DOCX-bound output. Preserve emphasis in plain wording only, except for heading markers and pipe tables that Chronicle explicitly converts.\n"
        "- Separate paragraphs with blank lines. Do not hard-wrap every visual line from the scan into its own paragraph.\n"
        "- Use `- ` for bullet lists and `1. ` style numbering for ordered lists.\n"
        "- When a true table is present and plain-text output is required, render it as a pipe table (`| Col | Col |`) with one header row so Chronicle can convert it into a Word table.\n"
        "- Use the standalone marker `[[PAGE BREAK]]` only when a true major boundary should become a new Word page, such as a title page, appendix start, form section, or major report section.\n"
        "- Never leak filenames, page-image names, OCR helper labels, or decorative folio/page-furniture markers into Word output unless they are visibly printed in the source and the page-number toggle explicitly requires preservation."
    )
    merge_continuity = ""
    if cfg.get("merge_files", False):
        merge_continuity = (
            "MERGE CONTINUITY RULES:\n"
            "- Merge mode is enabled. Treat sequential input files/pages as one continuous document.\n"
            "- Keep transitions seamless; do not insert extra separators or repetitive headings between consecutive pages.\n"
            "- Add a minimal heading only when a true section/document boundary exists.\n"
            "- If a page boundary occurs mid-paragraph, continue the paragraph without introducing a new heading.\n"
            "- NEVER output source filenames (e.g., `page 002.JPG`) as headings or body text unless that filename is visibly printed inside the scanned document."
        )
    core_default_contract = (
        "CORE DEFAULT CONTRACT:\n"
        "- ABSOLUTE JUNK SUPPRESSION: Universally identify and excise non-narrative and non-clause page furniture before assembling final output. This includes repeated running headers, repeated footers, date stamps used only as page furniture, repeated report/bill titles, and scanner speckling or visual debris. Do not allow these artifacts to leak into body text. Page-number preservation is governed separately by the page-number toggle rules above and is not overridden by this suppression rule.\n"
        "- STRICT SEMANTIC NESTING: Output must follow rigid HTML5 semantic structure optimized for screen readers. Hierarchy must remain strictly descending and navigable (`H1`, `H2`, `H3`, then lower levels only when genuinely needed). Paragraph tags must contain prose only and must never be used as containers for standalone headings or nested list structures. Ordered and unordered lists must be properly opened, scoped, and closed, and each list must encapsulate only valid list items.\n"
        "- ANTI-HALLUCINATION & VERBATIM ENFORCEMENT: Output must contain only extracted/transcribed document content. Never add conversational filler, helper commentary, summaries, appendix-style explanations, audit notes, or invented end matter. Do not append cleanup explanations or model-facing reasoning to the final extraction.\n"
        "- TABLE & GRID PRESERVATION: Any source content spatially arranged in rows and columns must remain structurally bound in semantic tables or, when a faithful table is impossible, in tightly nested lists that preserve row/column relationships. Never flatten tabular or grid-shaped source data into loose prose or word-salad text.\n"
    )

    custom_prompt = str(cfg.get("custom_prompt", "")).strip()
    custom_commands = str(cfg.get("custom_commands", "")).strip()
    academic_footnote_mode = cfg.get("academic_footnote_mode", "endnotes")
    academic_annotation_mode = cfg.get("academic_annotation_mode", "inline")

    base = f"""CRITICAL RULES:
- ZERO-CENSORSHIP: Transcribe all historical slurs/profanity verbatim. Do not redact.
- NO OMISSIONS: Do not skip any text. Preserve complete reading order, including headers, footers, marginalia, stamps, and inline annotations.
- LETTER-LEVEL FIDELITY: Preserve exact characters where legible; do not rewrite, normalize, or infer missing letters beyond local uncertainty tags.
- ABSOLUTE FIDELITY: You are a transcriptionist, not a general editor. Preserve names, dates, numbers, identifiers, and factual claims exactly as printed. Only make the narrowly allowed readability repairs described below for line-break/column artifacts and obvious physical print defects.
- ZERO GUESSING POLICY: Never guess, infer, autocomplete, or hallucinate missing text. If uncertain, mark uncertainty explicitly and preserve visible source text exactly.
- HANDWRITING UNCERTAINTY POLICY: For handwritten text, do not complete words from context. If only fragments are legible, preserve those fragments and mark the uncertain part locally as `[Unclear Word: ...]` or `[Unclear Letters: ...]`. do not substitute a cleaner dictionary word from context. Do not expand abbreviated or broken handwritten words unless the missing letters are genuinely visible.
- LINE BREAK AND COLUMN SPLICING: You must intelligently stitch together words that are hyphenated across line or column breaks. If a word is split (for example, `Mc-` on one line and `Kay` on the next), output it as a single, unhyphenated word (`McKay`). Do not preserve hyphens that exist solely because of physical margin constraints.
- FALSE PUNCTUATION RESOLUTION: Never insert hallucinated periods or double punctuation caused by column breaks or visual artifacts. Ensure sentences flow continuously across lines. For example, do not output `bare feet. was cleaning`; output `bare feet was cleaning`.
- CONTEXTUAL ARTIFACT CORRECTION: If physical print damage, broken type, or poor ink quality creates an obvious minor print typo, you must correct it contextually to preserve screen-reader readability while strictly preserving the factual truth of the document. This exception is narrow: fix optical print artifacts such as `tuhe` -> `tube` only when the intended reading is visually/contextually clear.
- DENSE DOCUMENT RULE: If layout is crowded, re-read iteratively and recover all legible text before final output.
- NO SUMMARIZATION: Do not compress, paraphrase, or condense content. Preserve document tone and structure.
- STRUCTURE FIDELITY: Preserve hierarchical numbering/chains (e.g., 1, 1.1, 1.1.a) where present.
- CONTINUOUS FORM FLOW: When extracting multi-page administrative forms, military logs, or diaries, treat the entire extraction as a single continuous document. DO NOT output repeated page headers, form titles (for example `WAR DIARY or INTELLIGENCE SUMMARY`), or instructional text (`Erase heading not required`) if they simply repeat at the top of subsequent physical pages. Map continuing tabular data seamlessly into a single unified HTML structure wherever possible.
- OUTPUT PURITY: Return only extracted/transcribed content. No conversational preamble or postscript.
- FORMAT DISCIPLINE: Respect requested output format strictly. Do not output full HTML documents unless HTML/EPUB format is requested.
- NON-HTML OUTPUT RULE: When output format is not HTML/EPUB, do not emit literal HTML tags (for example <figure>, <figcaption>, <table>). Use plain-text structural markers instead.
- NO RAW BINARY: Never emit raw binary/blob payloads or Base64 data URIs (for example `data:image/...;base64,...`). Describe visuals in text instead.
- NO FENCE WRAPPERS: Do not wrap final output in markdown code fences unless the source text itself contains literal fences.
- FLUID HEADINGS: Do NOT use <br> inside headings to mimic visual line wraps; keep heading text as one continuous spoken string.
- SEMANTIC METADATA: Wrap publication metadata (title/date/page) in `<header><cite>...</cite></header>` when present.
- SEMANTIC ATTRIBUTION: Wrap source/library attribution and source URL in `<footer><cite>...</cite></footer>` when present.
- ANTI-HALLUCINATION: If text is degraded, output [Illegible Micro-text: approx X words].
- ARCHIVE RECOVERY: Read underneath diagonal stamps/ranks. Format censors as `[Redacted by Censor]`.
- STAMPS & SIGNATURES: Format stamps as `[STAMP: ...]` and signatures as `[SIGNED]` or `[ILLEGIBLE SIGNATURE]` when unreadable.
- STRIKETHROUGH RECOVERY: If struck text is legible, preserve it as `[Struck through: ...]`.
- CORRUPTION CONTAINMENT: If a local span collapses into scanner garbage, OCR burst noise, or character soup, do not spread that corruption across an otherwise readable sentence. Keep the readable text, isolate the damaged segment with a local uncertainty tag, and never invent a fluent repair.

TOGGLES:
- {unit}
- {trans}
- {punct}
- {img}
- {page_number_rule}
- {abbrev}

{wcag}
{ascii_guard}
{lang}
{bidi_rules}
{translation_quality}
{recovery_rules}
{execution_protocol}
{pdf_scan_rules}
{merge_continuity}
{core_default_contract}

GENERAL THROUGHPUT RULES:
- For dense specification tables, control lists, or repetitive grid data, prioritize high-speed structural accuracy over descriptive prose. Minimize spatial reasoning overhead to ensure rapid throughput across large documents.

"""

    profile = cfg.get("doc_profile", "standard")
    if profile == "archival":
        base += (
            "ARCHIVAL CORRESPONDENCE RULES:\n"
            "- Even if the source document lacks explicit titles, you MUST begin the transcription with a descriptive <h1> title (for example `Handwritten Correspondence`).\n"
            "- Use <h2> tags to divide logical sections such as `Header/Date`, `Body`, and `Sign-off` so archival outputs maintain strict WCAG heading compliance for screen readers.\n"
            "- Preserve ledger structure: keep row relationships, account headings, and running totals in reading order.\n"
            "- Preserve date/address/sign-off blocks exactly for letters and memoranda.\n"
            "- Keep docket numbers, folio references, accession IDs, and filing marks verbatim.\n"
            "- Preserve uncertain handwriting with local uncertainty tags only (e.g., [Unclear Word: ...]) without rewriting whole lines."
        )
    elif profile == "letters":
        base += (
            "LETTERS / MEMOS / NOTICES RULES:\n"
            "- Preserve sender, recipient, address, date, subject line, salutation, body, and sign-off as separate navigable units in source order.\n"
            "- Keep office memo routing lines, carbon copy lines, reference lines, and attachments notices explicit when they are visibly printed.\n"
            "- Treat noticeboards, circulars, and typed announcements as short formal documents rather than generic prose blocks.\n"
            "- Do not invent archival headings or ledger structure when the page is simply a letter, memo, or typed notice.\n"
            "- Preserve local handwriting uncertainty tags if handwritten annotations or corrections appear on an otherwise typed page."
        )
    elif profile == "handwritten":
        base += (
            "HANDWRITTEN PAGE RULES:\n"
            "- Prioritize letter-level fidelity over fluency. Do not clean up handwriting into a smoother modern sentence when the source is uncertain.\n"
            "- Keep line order, visible insertions, strike-throughs, marginal notes, and notebook-style fragments explicit in reading order.\n"
            "- Use local uncertainty tags aggressively for partial words, uncertain names, and unclear numerals instead of guessing from context.\n"
            "- Treat rough notes, diary fragments, draft pages, and loose manuscript leaves as fragmentary documents when that is what the page visibly shows.\n"
            "- Do not force a business-letter, report, or legal structure onto informal handwritten material.\n"
            "- HEADING DISCIPLINE: Even informal handwritten pages must begin with a concise accessible `<h1>` that reflects the visible page type, such as `Handwritten Diary Page`, `Handwritten Notes`, or `Notebook Page`.\n"
            "- SECTION DISCIPLINE: After the `<h1>`, add at least one `<h2>` for the main transcription block, such as `Transcription` or a visible page/date marker when present.\n"
            "- DIARY PAGE COMPLETION: Re-read the bottom quarter of the page before finalizing. Do not stop at the last fluent sentence if additional handwritten lines remain visible near the lower edge.\n"
            "- PAGE-END HONESTY: If the page genuinely cuts off mid-thought, preserve the visible text and end with a local uncertainty tag rather than silently truncating the final line."
        )
    elif profile == "medical":
        base += (
            "MEDICAL / CLINICAL NOTE RULES:\n"
            "- Treat the page as high-stakes transcription support. Preserve exactly what is visible. Do not invent a cleaner medical reading when the handwriting is uncertain.\n"
            "- Preserve clinical abbreviations, medication names, dosages, frequencies, measurements, and shorthand exactly as written when legible. Do not silently expand them.\n"
            "- If a medication name, diagnosis term, dosage, frequency, body part, or clinician name is uncertain, mark it locally with `[Unclear Word: ...]` or `[Unclear Letters: ...]` instead of guessing from context.\n"
            "- Keep referral headings, patient identifiers, dates, provider names, signatures, and note sections such as history, assessment, plan, medications, and observations in visible source order.\n"
            "- Rebuild simple clinical forms, checklists, and observation tables into accessible structure when row/field relationships are clear.\n"
            "- Preserve illegible signatures, initials, and stamp lines explicitly. Do not replace them with guessed clinician names.\n"
            "- Do not normalize clinical shorthand into polished prose. If the source is fragmentary, keep it fragmentary.\n"
            "- If the page contains typed text plus handwritten additions, keep the typed base text and handwritten insertions clearly distinct in reading order.\n"
            "- Never convert an uncertain term into a specific diagnosis, medication, or instruction just because it seems plausible.\n"
            "- HEADING DISCIPLINE: Every medical HTML extraction must begin with a concise `<h1>`. Use the visible form or note title when present; otherwise use a neutral fallback such as `Clinical Note`, `Medical Form`, or `Transcribed Page`.\n"
            "- SECTION DISCIPLINE: Add at least one `<h2>` for the main note body, table block, medication list, or transcription section so the page is screen-reader navigable.\n"
            "- CLINICAL PAGE COMPLETION: Re-read the bottom quarter of the page before finalizing. Do not stop early if additional handwritten or typed lines remain visible near the lower edge.\n"
            "- PAGE-END HONESTY: If the page visibly continues off-page or ends in damage, preserve the readable text and mark the final uncertainty locally instead of stopping silently."
        )
    elif profile == "military":
        base += (
            "MILITARY RULES:\n"
            "- Convert 'STOP' to paragraph breaks.\n"
            "- Format map grid references with spaces (1 2 3 - 4 5 6).\n"
            "- HEADING DISCIPLINE: War diary title blocks must use semantic headings. Use `<h1>` for the top formation/title line (for example division, operation, or narrative heading), `<h2>` for the next unit/brigade/subheading line, and keep later unit labels or context lines as paragraphs unless they are true headings.\n"
            "- FALLBACK HEADING RULE: Even when a diary/log page lacks a clean printed title, begin the extraction with a concise descriptive `<h1>` based on the visible page context so military outputs never start as heading-less body text.\n"
            "- TABULAR DATA ENFORCEMENT: You must identify any text that is visually arranged in a grid or column-based table (such as Commencement Information in legislation or Muster Rolls in military documents). You MUST output this data using standard HTML `<table>`, `<tr>`, `<th>`, and `<td>` tags. Ensure each column has a clear header (`<th>`) with a `scope=\"col\"` attribute. Never render these grids as blocks of text or lists, as they must be navigable row-by-row for screen reader users.\n"
            "- Preserve military/technical acronyms exactly; do not normalize.\n"
            "- Rebuild dense casualty rolls into scoped tables.\n"
            "- Preserve war-diary time/location sequencing and operation-log chronology exactly.\n"
            "- STRIKETHROUGH RECOVERY: If a date, rank, unit, or note is visibly struck through, preserve it explicitly as `[Struck through: ...]`. Do not flatten struck text into ordinary spans or plain paragraph text.\n"
            "- Capture stamp overlays and handwritten marginal updates as separate tagged lines when they overlap body text."
        )
    elif profile == "intelligence":
        base += (
            "INTELLIGENCE CABLE RULES:\n"
            "- Preserve routing headers and precedence chains (FROM/TO/INFO/DTG/REF) in exact order.\n"
            "- Preserve classification banners and caveats verbatim (e.g., SECRET, NOFORN, ORCON) as separate lines.\n"
            "- Keep codewords, operation names, and alphanumeric references exactly; never normalize or expand unless explicitly defined.\n"
            "- Preserve distribution blocks, annex labels, and source reliability notes.\n"
            "- Preserve declassification/release stamps (for example FOIA release lines and control numbers) verbatim.\n"
            "- Preserve routing slips, tick-box matrices, and copy/distribution indicators in explicit structured lines."
        )
    elif profile == "office":
        base += (
            "OFFICE REPORTS / BUSINESS DOCUMENTS RULES:\n"
            "- Best-effort repair malformed Word exports, pasted HTML, presentation handouts, board papers, meeting packs, and damaged report structure into a cleaner accessible reading order.\n"
            "- Preserve title pages, executive summaries, agenda headings, action lists, numbered procedures, and appendices as distinct navigable sections.\n"
            "- Reconstruct ordinary business tables, schedules, timelines, and contact lists when their structure is clear.\n"
            "- For Word output, use heading markers aggressively where true section titles exist and use `[[PAGE BREAK]]` at major report boundaries when that improves navigation.\n"
            "- Remove email/client/export chrome, duplicate headers, and repeated boilerplate only when clearly non-substantive.\n"
            "- Do not treat business documents as government publications, legal clauses, or marketing collateral unless the page visibly behaves that way."
        )
    elif profile == "government":
        base += (
            "GOVERNMENT REPORTS / PUBLIC RECORDS RULES:\n"
            "- Preserve report titles, agency names, dates, section numbering, annexes, appendices, consultation notes, and publication metadata exactly.\n"
            "- Suppress repeated page headers/footers, folios, and boilerplate page furniture when they repeat mechanically across pages.\n"
            "- Rebuild public tables, schedules, and appendix listings into accessible structures when row/column relationships are clear.\n"
            "- Preserve legislative, policy, procurement, and consultation numbering chains exactly.\n"
            "- For Word output, use headings and `[[PAGE BREAK]]` at major report divisions such as title page, contents, chapters, annexes, and appendices.\n"
            "- Keep publication furniture and public-record metadata that identify provenance, but do not let repeated report furniture leak into the body."
        )
    elif profile == "newspaper":
        base += get_newspaper_profile_rules(format_type)
    elif profile == "book":
        base += (
            "BOOK / NOVEL / LONG-FORM PROSE RULES:\n"
            "- ARTIFACT ERADICATION: Aggressively strip margin debris, scanner speckling, floating orphan characters, embedded folios, and repeated running headers when they are clearly scan noise or page furniture rather than authored prose. Never let these artifacts interrupt the narrative flow.\n"
            "- OCR WRAPPER MARKER SUPPRESSION: Remove generic scan/export wrapper markers such as `==Start of OCR for page X==`, `==End of OCR for page X==`, or similar machine labels. They are process artifacts, not book text.\n"
            "- NARRATIVE LINEARIZATION: Rejoin all line-break and page-wrap hyphen fragments that exist only because of scan layout. Keep dialogue and descriptive paragraphs contiguous, and never preserve hard visual returns that would fracture normal prose reading.\n"
            "- HARD-RETURN FILTER FOR PROSE: Treat ordinary wrapped scan lines as one continuous paragraph unless the preceding line clearly ends a paragraph or dialogue unit. Keep a hard paragraph break only when the preceding visible line ends with a full stop, question mark, exclamation mark, or closing quotation mark, or when the source clearly shows a true scene/chapter break.\n"
            "- LITERARY PUNCTUATION: Standardize structural punctuation for readable literary prose, including clean smart quotes for dialogue, while strictly preserving the author's intentional em-dashes, ellipses, and colloquial or dialect-specific spellings. Do not sanitize the narrative voice.\n"
            "- QUOTE DISAMBIGUATION: Distinguish apostrophes inside words from quotation marks around speech or quoted phrases. Keep true apostrophes in contractions and possessives (for example `don't`, `I'm`, `father's`) as apostrophes, and treat standalone opening/closing single marks around dialogue as quotation marks when the visible prose clearly shows they are speech marks rather than word-internal punctuation.\n"
            "- DIALOGUE QUOTE NORMALIZATION: When a prose page is clearly using single quotation marks as dialogue quotes because of scan/OCR behavior rather than authorial style, normalize those dialogue quotes into proper double quotation marks. Convert opening and closing dialogue quotes consistently across the paragraph, and do not leave speech lines trapped in apostrophe-style quoting when the surrounding evidence shows ordinary dialogue. Do not rewrite apostrophes, dialect contractions, elisions, or possessives just to make the punctuation look tidier.\n"
            "- GLOBAL QUOTE NORMALIZATION: Apply quote standardization globally across the extraction, not just in main narrative dialogue. Enforce clean, paired quotation marks in review blurbs, front-matter endorsements, lists of praise, and similar non-narrative literary matter whenever mixed single/double scan punctuation is clearly not authorial.\n"
            "- CORRUPTION QUARANTINE: When a prose line contains partial OCR collapse, scanner smear, or mixed garbage characters, keep the readable narrative, isolate only the damaged segment with `[Unclear Text: ...]` or `[Illegible Text]`, and do not let broken fragments contaminate surrounding sentences.\n"
            "- STRAY PROMPT/JUNK PHRASE SUPPRESSION: Treat generic helper phrases, export boilerplate, or instruction-like fragments such as `Format content logically`, `beginning`, or similar non-authored glue text as contamination when they intrude into prose. Remove them unless they are visibly part of the original book text.\n"
            "- CHAPTER AND BREAK RECOVERY: Recognize chapter headings even when scan damage affects capitalization or spacing, and keep them distinct from body paragraphs. Do not allow damaged heading text to merge into the first sentence of the chapter.\n"
            "- HEADING FUSION PREVENTION: If prose, ellipses, or end-of-paragraph text runs into a true heading marker such as a chapter title, contents heading, or book-list heading, separate them cleanly. Never leave a heading glued onto the tail end of a sentence.\n"
            "- FRONT/BACK MATTER SEPARATION: Keep blurbs, copyright pages, title pages, review quotes, advertisements, and end matter distinct from the main narrative so they do not accidentally fuse into chapter text.\n"
            "- FRONT-MATTER ISOLATION: Do not attempt to narrative-merge front matter. Treat review blurbs, `Books by` lists, contents pages, copyright blocks, endorsements, and publisher matter as isolated structural units. Force hard paragraph or block breaks between them whenever needed to prevent text smashing.\n"
            "- FOLIO SUPPRESSION FOR PROSE: Unless the page-number toggle is explicitly set to preserve them, remove ornamental folio markers and bare page labels such as `Page 7`, `• 24 •`, or isolated running numbers when they are only page furniture.\n"
            "- PRINTED PAGE REFERENCE DISCIPLINE: When printed page references are enabled, preserve each visible printed folio exactly once using `[Original Page Number: X]`. Do not leave duplicate bare number lines, contents-list carryover, or mixed page-label styles beside the preserved marker.\n"
            "- CHAPTER-FOLIO PRESERVATION: When page references are enabled and a visible printed folio appears on a chapter-opening page, decorative chapter page, or first narrative page after a chapter title, still preserve it as `[Original Page Number: X]`. Do not let decorative layout cause chapter-start folios to disappear.\n"
            "- MATHEMATICAL PAGINATION & BLIND FOLIOS: Page markers must remain perfectly sequential. If a printed folio is visually absent because the page is a chapter opener, decorative divider, blank-verso style page, or otherwise omits the number, mathematically infer the correct page number from the surrounding sequence and insert the standard `[Original Page Number: X]` marker instead of leaving a gap.\n"
            "- FOLIO DE-DUPLICATION (ANTI-FUSION): When generating `[Original Page Number: X]`, explicitly eradicate the raw physical page number from nearby transcribed text so it cannot survive as a duplicate or fuse into the marker. Never output artifacts such as `[Original Page Number: 82]81` or a marker followed by the same bare number.\n"
            "- WORD-JOIN REPAIR: If scan damage jams or splits a word but the intended prose reading is locally obvious, repair the boundary conservatively (for example missing spaces, doubled fragments, or obvious scan-splice joins) without rewriting the sentence.\n"
            "- OBVIOUS OCR WORD REPAIR: Correct only locally obvious OCR misreads inside otherwise readable prose, such as a wrong adjacent letter, broken capitalization, or a split/jammed common word, when the intended reading is clear from the visible text itself. Do not paraphrase, modernize dialect, or substitute a different phrase just because it reads more smoothly.\n"
            "- TAIL-END SAFETY: If the final lines of a page or document contain clipped fragments, do not output a misleading half-sentence as though it were complete. Preserve the readable text, mark only the damaged local fragment, and continue with any later readable prose that resumes after it. Only end the extraction when the visible source itself truly ends.\n"
            "- ENDING CONTINUITY: Never abandon the remainder of a chapter, scene, or file just because one late sentence is damaged. If the source continues after a corrupt fragment, keep extracting the surviving continuation in order.\n"
            "- Preserve chapter, part, and section titles exactly, and promote them to clear heading markers in the requested output format.\n"
            "- Preserve true paragraph boundaries and dialogue paragraphing exactly. Do not collapse prose into a single block, and do not convert wrapped scan lines into separate paragraphs just because the scan shows a visual line ending.\n"
            "- Preserve scene-break markers exactly as printed (for example `* * *`, ornaments, or centered separators).\n"
            "- If a paragraph continues across a page turn, continue it seamlessly without inserting repeated headers, folios, or page numbers into the middle of the paragraph.\n"
            "- Keep front matter, contents pages, epigraphs, footnotes, appendices, and end matter distinct from the main narrative flow.\n"
            "- Preserve italics, small caps, and emphasis cues as plainly as the requested format allows without inventing formatting not visible in the source.\n"
            "- WORD-READY SEMANTICS: For Accessible Word Document conversion, use explicit heading markers for chapter, part, and other true navigational titles so Chronicle can map them into Microsoft Word heading styles for screen-reader navigation.\n"
            "- HTML SEMANTICS: When HTML output is requested, use clean semantic headings for chapter and part titles, preserve paragraphs as true `<p>` blocks, keep scene breaks as meaningful separators, and maintain a screen-reader-friendly reading order without decorative wrapper clutter.\n"
            "- For scanned novels and memoirs, favor stable reading order and paragraph continuity over literal line-by-line visual wrapping."
        )
    elif profile == "manual":
        base += (
            "TECHNICAL MANUAL RULES:\n"
            "- Preserve task order, numbered procedures, warnings, cautions, equipment lists, parts lists, legends, and troubleshooting flows in the clearest accessible order.\n"
            "- Output title first, then steps/bullets, then callouts/tables/legends in reading order.\n"
            "- Preserve control labels, device names, specification tables, and maintenance intervals exactly.\n"
            "- Keep repeated instructional chrome out of the body when it is only page furniture.\n"
            "- For dense specification tables, control lists, or repetitive grid data, prioritize high-speed structural accuracy over descriptive prose. Minimize spatial reasoning overhead to ensure rapid throughput across large documents.\n"
            "- If identical adjacent fragments are clear overlay artifacts from layered text extraction, keep one and annotate [Duplicate OCR Artifact Removed]."
        )
    elif profile == "forms":
        base += (
            "FORMS / CHECKLISTS / WORKSHEETS RULES:\n"
            "- Checkbox State: Explicitly output [Checkbox: Selected] or [Checkbox: Empty].\n"
            "- Form Flattening: Ignore visual X/Y placement and output clean key-value content.\n"
            "- Signatures: Indicate [Signature: Name] or [Illegible Signature].\n"
            "- Preserve field labels, handwritten form entries, date fields, tick boxes, and yes/no selections as explicit accessible text.\n"
            "- Keep blank fields visible where they matter so a completed or partially completed form remains faithful.\n"
            "- Device/Diagram Cues: Convert visual icons to explicit bracketed labels.\n"
            "- If identical adjacent fragments are clear overlay artifacts from layered text extraction, keep one and annotate [Duplicate OCR Artifact Removed]."
        )
    elif profile == "flyer":
        base += (
            "FLYERS / POSTERS / ONE-PAGE NOTICES RULES:\n"
            "- Treat the page as short-form public-facing material with a strong visual hierarchy. Recover headline, subheadline, date/time/location, pricing, call-to-action, and contact details in the order a listener needs them.\n"
            "- Keep slogans, event names, and highlighted offers distinct from supporting details so the page does not collapse into an undifferentiated paragraph.\n"
            "- Preserve poster-style emphasis, but never invent marketing copy or smooth away awkward original phrasing.\n"
            "- Capture logos, seals, and hero images with concise image descriptions only when they materially help the listener understand the flyer.\n"
            "- Suppress decorative repetition, isolated design words, and layout-only fragments that do not carry unique meaning."
        )
    elif profile == "brochure":
        base += (
            "BROCHURES / CATALOGUES / PAMPHLETS RULES:\n"
            "- Treat the source as multi-panel promotional or informational material. Reconstruct the panel order into one continuous accessible reading path.\n"
            "- Keep headings, teaser summaries, feature lists, pricing blocks, product names, contact details, and closing calls-to-action as separate navigable units.\n"
            "- Preserve catalog item names, measurements, prices, and comparison tables exactly when present.\n"
            "- Do not flatten a brochure into generic prose if the visible structure is a sequence of short sections, product tiles, or panels.\n"
            "- Use image descriptions when photographs or product shots carry essential meaning beyond decorative atmosphere."
        )
    elif profile == "comic":
        base += (
            "COMICS / MANGA / GRAPHIC NOVELS RULES:\n"
            "- Treat each page as sequential visual storytelling, not ordinary prose, a newspaper, or a brochure. Preserve story reading order before decorative layout fidelity.\n"
            "- PANEL ORDER: Identify panels, caption boxes, speech balloons, thought balloons, signs, labels, and sound effects. Output them in the most likely human reading order for the source.\n"
            "- READING DIRECTION: If the page visibly follows manga/right-to-left flow, use right-to-left panel order and note the page flow once near the start. Otherwise default to left-to-right, top-to-bottom order.\n"
            "- PANEL STRUCTURE: For HTML output, you MUST begin with one `<h1>` page/comic title, then use `<h2>Panel 1</h2>`, `<h2>Panel 2</h2>`, and so on for each panel or story beat. Even a single-panel page must have `<h1>...</h1>` followed by `<h2>Panel 1</h2>`. Never leave a comic HTML page as loose paragraphs without headings. For DOCX/TXT output, use plain labels such as `Page 3`, `Panel 1`, `Caption`, `Speech`, `Thought`, `SFX`, and `Image Description`.\n"
            "- NO EMPTY PANELS: Never emit an empty panel heading. Every `Panel N` section must contain at least one concrete item: an image description, visible dialogue, caption/narration, sign/label, or SFX line.\n"
            "- SPEECH BALLOONS: Preserve balloon text verbatim. Attribute speakers only when the visual evidence is clear from balloon tails, repeated character labels, or visible context. If uncertain, use `Speaker uncertain` rather than guessing a character name.\n"
            "- CAPTIONS AND NARRATION: Keep narrator boxes, location cards, dates, and editorial captions distinct from spoken dialogue.\n"
            "- SOUND EFFECTS: Preserve visible sound effects and stylized lettering as a separate `SFX: ...` line when legible. Do not bury visible SFX only inside an image description. Do not invent sound words from the art alone.\n"
            "- ART DESCRIPTIONS: Every panel/story-beat section must include a concise `[Image Description: ...]` for meaningful action, setting, expressions, and scene changes, even when the panel also contains dialogue or captions. Do not describe every decorative stroke or reproduce artwork as visual layout code.\n"
            "- PAGE SPREADS: If a two-page spread is visible, keep spread-level reading order explicit and avoid mixing unrelated pages into one panel sequence.\n"
            "- TEXTLESS PANELS: Do not omit silent panels that carry story action. Emit a panel label with an image description when the panel has no readable text.\n"
            "- ACCESSIBILITY GOAL: Produce a reviewable accessible reading script for the comic page. Do not claim to recreate the visual comic, and do not summarize or replace panels with broad plot commentary."
        )
    elif profile == "slides":
        base += (
            "SLIDES / DECKS / HANDOUTS RULES:\n"
            "- Treat each slide or handout panel as a compact presentation unit: preserve title, subtitle, bullets, callouts, chart summaries, speaker notes, and captions in clear order.\n"
            "- Prevent bullet fragments, decorative slide numbers, or repeated template footers from leaking into the reading flow.\n"
            "- If a slide contains a chart, diagram, or dense visual, provide a concise but concrete [Image Description: ...] before continuing with the text content.\n"
            "- Keep agenda slides, section divider slides, and summary slides distinct so the deck remains navigable.\n"
            "- Do not rewrite concise slide bullets into long prose unless extra wording is required to preserve meaning."
        )
    elif profile == "tabular":
        base += (
            "TABULAR DATA & SPREADSHEETS RULES:\n"
            "- When processing structured data (CSV/XLS), you must output a single, valid HTML5 table.\n"
            '- Every column header must be tagged with `<th scope="col">`.\n'
            '- Every row\'s primary key (for example, the `Date`) must be tagged with `<th scope="row">`.\n'
            "- At the beginning of every table, provide a concise, high-level summary paragraph for screen reader users. For example: `This table tracks Trivia scores from 2018 to 2026. There are 3 columns: Date, Caroline, and Bruce. Bruce currently leads in the 2025 totals.`\n"
            "- Identify `Total` or `Summary` rows in the data. You must apply a specific CSS class `chronicle-total-row` to these rows and add an ARIA-label so the screen reader announces `Subtotal for [Date Range]` when the user lands on that row.\n"
            "- If a column is entirely empty or contains redundant technical metadata that does not serve the user, omit it from the final HTML output to reduce clutter for VoiceOver users.\n"
            "- Preserve useful sheet or section labels, but keep all structured data inside a single semantic table per logical dataset whenever possible."
        )
    elif profile == "academic":
        footnote_rule = {
            "endnotes": "Footnotes: Automatically relocate and anchor footnotes to a dedicated section at the document's end.",
            "inline": "Footnotes: Preserve footnotes in-place at original reference points.",
            "strict": "Footnotes: Preserve exact footnote numbering and placement; do not rewrite or relocate.",
        }.get(academic_footnote_mode, "Footnotes: Automatically relocate and anchor footnotes to a dedicated section at the document's end.")
        annotation_rule = {
            "inline": "Annotations: Preserve editorial/author annotations inline at their source location.",
            "endnotes": "Annotations: Collect non-body annotations into a dedicated annotations section at the end.",
            "strict": "Annotations: Preserve all annotations verbatim with source anchors and no normalization.",
        }.get(academic_annotation_mode, "Annotations: Preserve editorial/author annotations inline at their source location.")
        base += (
            "ACADEMIC & MATH RULES:\n"
            "- STRICT MATH FORMATTING: NEVER use Unicode math symbols (e.g., do not use ∑, use \\sum). ALL equations, formulas, and inline math MUST be written in pure LaTeX formatting. Use $$ for block equations and $ for inline math.\n"
            "- FRACTION STRICTNESS: Preserve fractions exactly as fractions. Do not convert to decimals, percentages, or words unless the source does. For math output, represent fractions as LaTeX `\\frac{a}{b}` while preserving mixed-number form (e.g., `1 5/16` -> `1\\frac{5}{16}`).\n"
            "- MATH ACCESSIBILITY STRUCTURE: Preserve equation numbering and references exactly. Keep superscripts/subscripts/fractions/matrices/operators faithful to source semantics; never linearize by dropping structure.\n"
            "- MATH UNCERTAINTY POLICY: If part of an equation is unclear, keep the readable math and insert `[Unclear Math: ...]` only at the uncertain segment; do not rewrite the whole equation.\n"
            "- FIGURE DESCRIPTIONS: All charts, graphs, and diagrams MUST be wrapped in semantic <figure> tags with a corresponding <figcaption>. You MUST write an exhaustive [Image Description: ...] that details the axes, data trends, variables, and visual relationships BEFORE providing the caption.\n"
            "- Preserve theorem/lemma/proposition/corollary labels and proof blocks exactly.\n"
            "- Preserve algorithm/pseudocode blocks line-by-line with numbering and indentation intact.\n"
            "- Preserve bibliography/reference entries verbatim, including DOI/arXiv identifiers and citation numbering.\n"
            f"- {footnote_rule}\n"
            f"- {annotation_rule}\n"
            '- Multi-Column: Flatten dense layouts into continuous narrative sequences.\n'
            '- Indigenous/Ancient: Preserve all diacritics (Maori macrons). Wrap detected indigenous languages in <span lang="mi"> (or appropriate ISO code).'
        )
    elif profile == "transcript":
        base += "TRANSCRIPT RULES:\n- Wrap stage directions and sound effects in semantic italics/brackets so screen readers pause."
    elif profile == "poetry":
        base += (
            "POETRY & LITERATURE RULES:\n"
            "- Preserve stanza breaks, line breaks, and deliberate indentation exactly.\n"
            "- Keep speaker attributions and dialogue cadence intact.\n"
            "- Preserve punctuation rhythm and line enjambment; do not prose-flatten poetic structure."
        )
    elif profile == "legal":
        base += (
            "LEGAL & POLICY RULES:\n"
            "- LEGISLATIVE DRAFT CONTRACT: For Parliamentary Bills, exposure drafts, Acts, schedules, commencement tables, explanatory legal layouts, and similar legislative material, you MUST apply a strict legislative reconstruction contract before emitting any output.\n"
            "- LINE NUMBER ERADICATION (ANTI-FUSION): Parliamentary drafts often contain marginal or embedded line numbers such as `1`, `2`, `3` at the start or end of lines. You MUST aggressively identify and strip these standalone digits before assembling body text. Never fuse a line number into adjacent words or numbering. For example, `Part 2` plus line number `3` must never become `Part 23`, and `2 Commencement` must never become `22 Commencement` or `2 2 Commencement`.\n"
            "- EXCISE LEGAL FURNITURE: Completely strip repeated running headers, footer labels, folios, page numbers, and repeated bill-title furniture such as `Aged Care Bill 2024`, chapter breadcrumbs, or repeated section breadcrumbs when they are page furniture rather than body text. They must not interrupt clauses, tables, or definitions.\n"
            "- STRICT SEMANTIC NESTING: Legal hierarchy must be represented as strict accessible structure. Sections and clauses such as `47 Content of notice` or `2 Commencement` must be emitted as heading tags, not flattened body paragraphs. Subsections such as `(1)` and `(2)` must remain structurally scoped and must not be flattened into unrelated paragraphs when they introduce nested paragraphs, subparagraphs, or tables. Paragraphs such as `(a)`, `(b)`, `(i)`, and `(ii)` must be nested inside their parent subsection using proper ordered or unordered list structures and must remain completely contained within that parent clause's scope.\n"
            "- SPATIAL RE-FLOW: Rejoin ordinary wrapped legislative sentences and clauses across scan/layout line breaks. Do not preserve hard visual returns in the middle of a clause, definition, or sentence unless the source is clearly beginning a new structural unit.\n"
            "- Preserve section numbering and clause hierarchy exactly (e.g., 1, 1.1, 1.1(a)).\n"
            "- Keep defined terms and capitalization exactly as written.\n"
            "- Preserve cross-references, exhibits, schedules, and footnotes without paraphrase.\n"
            "- Preserve amendment history notes, commencement/application clauses, and schedule notes exactly.\n"
            "- Never emit nested full-document wrappers inside the content body. Do not output extra `<!DOCTYPE html>`, `<html>`, `<head>`, `<body>`, or `<main>` blocks for individual pages or chunks.\n"
            "- Treat contents pages and other front matter as distinct structural material. Preserve them as contents lists or tables, but do not merge them into the legislative body text.\n"
            "- Suppress repeated running heads, bare line numbers, isolated folio digits, and repeated page furniture unless the printed-page-reference rule explicitly requires a single preserved page marker.\n"
            "- For dense specification tables, control lists, or repetitive grid data, prioritize high-speed structural accuracy over descriptive prose. Minimize spatial reasoning overhead to ensure rapid throughput across large documents.\n"
            "- Preserve legislative tables and notes blocks as structured tables with row/column relationships."
        )
    elif profile == "museum":
        base += (
            "MUSEUM & EXHIBIT RULES:\n"
            "- Preserve object labels, dates, materials, provenance, and accession identifiers exactly.\n"
            "- Keep caption-to-object association explicit in reading order.\n"
            "- Preserve multilingual labels and maintain language tags when languages switch."
        )

    if custom_prompt:
        base += f"\nUSER CUSTOM PROMPT ADDITIONS:\n{custom_prompt}\n"
    if custom_commands:
        base += f"\nUSER CUSTOM COMMAND/RULE STRINGS:\n{custom_commands}\n"

    if format_type not in ("html", "epub"):
        base += (
            "\nSTRICT NON-HTML RENDERING MODE:\n"
            "- Output MUST be plain text for this format.\n"
            "- Never emit any literal HTML/XML tag tokens (for example `<figure>`, `<table>`, `<tr>`, `<td>`, `<div>`, `<span>`).\n"
            "- If you internally draft markup, rewrite it to plain text BEFORE final output.\n"
            "- If a table is present, render as plain-text rows/columns using delimiters; do not use HTML tables.\n"
            "- For CSV/tabular sources, keep all headers and express rows in explicit row-wise form (for example `Row N: col=value | col=value`).\n"
            "- Reconstruct headings, lists, and major section boundaries using plain-text markers when that improves accessibility and faithfulness.\n"
            "- Final self-check before returning: no `<` or `>` tag pairs except literal characters that are visibly printed in source text.\n"
        )
    if format_type == "docx":
        base += f"\n{word_mode_rules}\n"
    if format_type == "csv":
        base += (
            "\nCSV OUTPUT MODE:\n"
            "- Output only CSV rows.\n"
            "- No prose, no headings, no markdown, no HTML tags.\n"
            "- Keep column consistency and escape quotes per CSV rules.\n"
        )
    if format_type == "html":
        return f"Format strictly as HTML. No markdown wrappers.\n{base}"
    if format_type == "md":
        return f"Format as strict Markdown.\n{base}"
    if format_type == "epub":
        return f"Format as semantic HTML for EPUB processing (split chapters with <h2>).\n{base}"
    return base


def strip_synthetic_page_filename_headings(content, fmt):
    if not content:
        return content
    if fmt == "html":
        content = re.sub(
            r'<h[1-6][^>]*>\s*page[\s._-]*0*\d+\.(?:jpg|jpeg|png|bmp|tiff|tif|webp)\s*</h[1-6]>',
            "",
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(
            r'<p[^>]*>\s*page[\s._-]*0*\d+\.(?:jpg|jpeg|png|bmp|tiff|tif|webp)\s*</p>',
            "",
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(
            r'((?:reference|file|filename)\s+[^<]*?)\.(jpg|jpeg|png|bmp|tiff|tif|webp)(?=</cite>)',
            r"\1",
            content,
            flags=re.IGNORECASE,
        )
        return content
    lines = content.splitlines()
    keep = []
    pat = re.compile(
        r'^\s{0,3}(?:#{1,6}\s*)?page[\s._-]*0*\d+\.(?:jpg|jpeg|png|bmp|tiff|tif|webp)\s*$',
        flags=re.IGNORECASE,
    )
    for line in lines:
        if pat.match(line):
            continue
        keep.append(line)
    return "\n".join(keep)


def enforce_archival_heading_structure(content, fmt, doc_profile):
    if not content or fmt != "html" or doc_profile not in {"archival", "medical", "handwritten", "comic"}:
        return content

    lower = content.lower()
    has_h1 = "<h1" in lower
    has_h2 = "<h2" in lower
    if doc_profile == "comic":
        content = re.sub(
            r"(?im)^([ \t]*)(\[(?:Image Description|Panel Description):[^\n<]*\])\s*$",
            r"\1<p>\2</p>",
            content,
        )
        has_panel_h2 = bool(re.search(r"<h2\b[^>]*>\s*panel\b", content, flags=re.IGNORECASE))
        if has_h1 and has_panel_h2:
            return content

        main_match = re.search(r"(<main\b[^>]*>)", content, flags=re.IGNORECASE)
        if not main_match:
            return content

        def _clean_text(raw):
            return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", raw or "")).strip()

        title_match = re.search(r"<h1\b[^>]*>(.*?)</h1>", content, flags=re.IGNORECASE | re.DOTALL)
        if title_match:
            title_text = _clean_text(title_match.group(1)) or "Comic Page"
        else:
            title_text = "Comic Page"
            for p_match in re.finditer(r"<p\b[^>]*>(.*?)</p>", content, flags=re.IGNORECASE | re.DOTALL):
                candidate = _clean_text(p_match.group(1))
                if not candidate:
                    continue
                if candidate.lower().startswith("[image description:"):
                    continue
                if len(candidate) <= 90:
                    title_text = candidate
                    break

        if not has_h1:
            insert_pos = main_match.end()
            content = content[:insert_pos] + f"<h1>{title_text}</h1>" + content[insert_pos:]

        if not has_panel_h2:
            h1_match = re.search(r"</h1>", content, flags=re.IGNORECASE)
            if h1_match:
                insert_pos = h1_match.end()
            else:
                refreshed_main = re.search(r"(<main\b[^>]*>)", content, flags=re.IGNORECASE)
                insert_pos = refreshed_main.end() if refreshed_main else 0
            content = content[:insert_pos] + "<h2>Panel 1</h2>" + content[insert_pos:]

        return content

    if doc_profile in {"medical", "handwritten"}:
        page_marker = None
        page_match = re.search(
            r"<p\b[^>]*>\s*(\d{1,4}[A-Za-z]?)\s*</p>",
            content,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if page_match:
            page_marker = f"Page {page_match.group(1)}"

        if not has_h1:
            promoted = re.sub(
                r"(<\/nav>\s*)<h2\b([^>]*)>(.*?)</h2>",
                r"\1<h1\2>\3</h1>",
                content,
                count=1,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if promoted == content:
                promoted = re.sub(
                    r"<h2\b([^>]*)>(.*?)</h2>",
                    r"<h1\1>\2</h1>",
                    content,
                    count=1,
                    flags=re.IGNORECASE | re.DOTALL,
                )
            if promoted != content:
                content = promoted
                lower = content.lower()
                has_h1 = True
                has_h2 = "<h2" in lower

        if has_h1 and has_h2:
            return content

        main_match = re.search(r"(<main\b[^>]*>)", content, flags=re.IGNORECASE)
        if not main_match:
            return content

        insert_pos = main_match.end()
        prefix = content[:insert_pos]
        suffix = content[insert_pos:]

        fallback_h1 = "Clinical Note" if doc_profile == "medical" else "Handwritten Page"
        fallback_h2 = page_marker or "Transcription"
        heading_html = ""
        if not has_h1:
            heading_html += f"<h1>{fallback_h1}</h1>"
        if not has_h2:
            heading_html += f"<h2>{fallback_h2}</h2>"
        return prefix + heading_html + suffix

    if has_h1 and has_h2:
        return content

    main_match = re.search(r"(<main\b[^>]*>)", content, flags=re.IGNORECASE)
    if not main_match:
        return content

    insert_pos = main_match.end()
    prefix = content[:insert_pos]
    suffix = content[insert_pos:]

    def _pick_title_candidate(body):
        for match in re.finditer(r"<p\b[^>]*>(.*?)</p>", body, flags=re.IGNORECASE | re.DOTALL):
            text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
            if not text:
                continue
            if text.lower().startswith("[image description:"):
                continue
            if len(text) > 90:
                continue
            return match.span(), text
        return None, None

    heading_html = ""
    candidate_span, candidate_text = _pick_title_candidate(suffix)

    if not has_h1:
        title_text = candidate_text or "Handwritten Correspondence"
        heading_html += f"<h1>{title_text}</h1>"
        if candidate_span:
            suffix = suffix[:candidate_span[0]] + suffix[candidate_span[1]:]

    if not has_h2:
        heading_html += "<h2>Body</h2>"

    return prefix + heading_html + suffix
