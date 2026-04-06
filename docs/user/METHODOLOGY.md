# Chronicle: Technical Methodology & Architecture

This document describes Chronicle's current extraction methodology, including prompt/rule enforcement, queue execution behavior, accessibility guarantees, and fail-safe recovery paths.

> Development note: Chronicle was built using AI-assisted ("vibe-coded") workflows, with final integration, review, and testing directed by the author.

## 1. System Architecture

Chronicle is a local desktop orchestrator for multimodal AI extraction. It runs client-side, reads local files, applies preprocessing/guardrails, sends bounded model requests, and writes outputs atomically.

Chronicle is intentionally optimized for difficult real-world recovery work rather than the narrowest possible turnaround time. The architecture favors:

- operator visibility over black-box simplicity
- specialist presets over one universal rule set
- queue/review/rerun workflows over one-shot bulk conversion assumptions
- fidelity and navigable structure over superficially fast but brittle output

Session update (2026-03-18):
- GUI file and folder dialog handlers now use lazy-loading from the main frame so handler modules are imported only when invoked.
- On macOS, this reduces circular dependency risk and keeps dialog launch on a safer event-loop path for thread-safe modal behavior.

Data flow:
`[Local Input File] -> [Pre-Processing + Rule Assembly] -> [Model Request Stream] -> [Safety/Audit Passes] -> [Atomic Save]`

Supported model providers in current GUI:
- Google Gemini
- Anthropic Claude
- OpenAI GPT

Current provider/PDF routing state:
- Gemini remains the strongest default PDF path in Chronicle.
- Claude PDF handling now prefers Anthropic's Files API for PDF slices when the local SDK exposes that route, then falls back to inline PDF document blocks if Files API upload is unavailable.
- OpenAI support remains available, but Chronicle's current OpenAI integration does not yet use OpenAI's newer dedicated PDF file-input route. In Chronicle, OpenAI PDF handling should therefore be treated as a fallback path rather than the primary PDF engine.
- Automatic engine selection now avoids providers whose API keys are missing instead of preserving an unavailable preset recommendation.
- Operational billing note: Gemini can still be exercised from Google AI Studio free-tier API keys within Google's current quotas, but Claude API usage should be assumed to require Claude Console billing/prepaid credits rather than a consumer Claude.ai chat subscription.
- Operational availability note: because Chronicle is an online-provider orchestrator, temporary provider-demand events can still surface as `503 UNAVAILABLE`, quota pressure, or transient retry/fallback behavior during otherwise healthy runs. Repeating the same benchmark later can be necessary to separate provider noise from a true Chronicle defect.

## 2. Ingestion and Chunking Strategy

Chronicle uses strict chunk controls to reduce omissions and improve degraded-page recovery.

- Current runtime defaults:
  - PDF chunk size: `3` pages (`PDF_CHUNK_PAGES = 3`).
  - Text chunk size: `10,000` characters (`TEXT_CHUNK_CHARS = 10000`).
- Academic profile PDF pass: chunk size forced to one page for high-fidelity math/footnote handling.
- Dense historical newspaper scans can also downshift to single-page PDF slices when file size per page indicates a short but unusually heavy newsprint scan.
- Folder ingestion supports both flat and recursive scan modes.

Session update (2026-03-08):
- Benchmark harness-only truncation was introduced for runtime control in `tools/web_corpus_benchmark.py`:
  - PDF benchmark subsets can be limited (`--max-pdf-pages`, default `1` in harness).
  - Large benchmark `.txt/.md/.csv` inputs can be trimmed in the harness.
- This does **not** alter normal production extraction behavior.

## 3. Prompt and Rule Enforcement

Chronicle assembles a structured extraction prompt with hard constraints:

- No omissions (headers, footers, marginalia, stamps, inline annotations).
- No summarization.
- Zero guessing / zero hallucination (never infer missing words, names, dates, or numbers).
- No broad spelling correction under any mode; only narrow line-break, column-splicing, and obvious print-artifact repairs are allowed when they improve screen-reader readability without changing factual meaning.
- Accessibility remediation and recovery: malformed HTML, broken Word exports, duplicated OCR overlays, broken list structure, weak table text, and damaged paragraph wrapping can be repaired into a more accessible equivalent when the source meaning remains clear.
- Letter-level fidelity for legible characters.
- Dense-page iterative re-read behavior.
- Anti-hallucination fallback markers for illegible segments.
- Modern punctuation mode is punctuation/spacing-only; wording and spelling must remain unchanged.
- Reading may take a bit longer when modern punctuation or abbreviation expansion is enabled, because Chronicle has to correct punctuation and expand abbreviations before finalizing the output.
- Hardcoded punctuation post-processing now preserves a single space when archaic `.-` or `,-` combinations are cleaned ahead of a following word, preventing jammed output such as `Friday.Mrs.`.
- Intelligent Column Splicing and Print Artifact Correction: Chronicle repairs words split across line/column breaks, removes false punctuation created by layout artifacts, and corrects minor optical print errors when the intended reading is clearly recoverable.
- Long-form prose recovery includes dedicated paragraph-continuity rules so wrapped scan lines are not mistaken for true paragraph breaks.
- Long-form prose recovery also includes quote disambiguation rules so apostrophes inside words are distinguished from quotation marks around speech when the visible page evidence supports that reading.
- Tabular Data & Spreadsheets profile: CSV/XLS sources can be mapped to a single semantic HTML table with `<th scope="col">`, row-header `<th scope="row">`, narrated summaries, filtered empty columns, and subtotal rows marked with `chronicle-total-row`.
- Profile-specific directives (office, government, academic, military, intelligence, newspaper, legal, book, etc.).
- Post-benchmark non-HTML purity directives:
  - `NON-HTML OUTPUT RULE` (no literal HTML tags in non-HTML formats)
  - `NO RAW BINARY` (no `data:image/...;base64,...` emissions)
  - `NO FENCE WRAPPERS` (no accidental markdown code-fence wrapping)
- Benchmark-driven exam directives:
  - strict vertical formatting for multiple-choice options
  - removal of handwriting scaffolding artifacts (underscores/dotted answer lines/empty grids)
  - mark allocations preserved on the same line as the relevant question

Advanced prompt controls exposed in Preferences:
- Custom Prompt Additions
- Custom Command/Rule Strings

## 4. Dense-Page and Fail-Safe Recovery

For PDF processing, Chronicle applies progressive recovery:

1. Standard chunk pass.
2. Automatic chunk throttle-down on failures.
3. Dense-page recheck pass for failing single pages.
4. Text-layer fail-safe mode with sentence/segment-level replay when needed.

This sequence is designed to minimize missed text in heavily degraded or layout-dense pages.

Users should expect this quality-first approach to cost time on hard material. Chronicle is willing to spend more runtime on:

- ugly scan layouts
- dense newspapers
- long-form fiction with broken wrapping
- damaged late-page or late-file segments
- mixed-content documents where preserving true reading order matters

This is a deliberate product choice rather than an accidental slowdown.

For historical newspapers, Chronicle now also applies a proactive dense-scan heuristic before failure recovery: if a short newspaper PDF is unusually heavy for its page count, Chronicle shrinks to one-page slices immediately and logs a `[PDF Heuristic]` note so the run does not appear frozen on an oversized upload.

Provider-specific PDF notes:
- Gemini uses Chronicle's established PDF upload and raster recovery path and remains the preferred default for difficult PDF workloads.
- Claude now attempts file-backed PDF slices first when possible, which reduces inline encoding overhead and aligns Chronicle more closely with Anthropic's current PDF guidance.
- OpenAI now logs a provider-specific fallback reason if Chronicle cannot continue on the direct PDF path, then drops to PDF text-layer recovery rather than silently skipping the file.
- Original page-number handling is user-selectable: Chronicle can suppress standalone folios/page numbers as page furniture or preserve them as explicit original-page references in the output.

## 4.1 Intelligent Column Splicing and Print Artifact Correction

Chronicle now injects explicit Vision-model directives for line-break and column repair:

- Hyphenated words split by physical column or margin layout are rejoined into continuous words when the hyphen is clearly structural rather than semantic.
- False punctuation introduced by broken columns, print damage, or visual separators is removed so sentences read continuously.
- Minor optical print defects can be corrected contextually when the intended word is obvious and the correction improves screen-reader readability without altering factual truth.

This is designed to produce a smoother, more continuous reading experience for screen reader users while preserving the document's historical meaning and factual content.

## 4.3 Malformed-Source Recovery

Chronicle now explicitly treats malformed but readable source structure as something it may repair rather than mirror blindly.

- Broken HTML/tag soup may be reconstructed into cleaner heading/list/table structure.
- Poor Word exports and copy-pasted office documents may be rebuilt into clearer section order and paragraph boundaries.
- Duplicate OCR overlays may be collapsed when they are obviously repeating the same text.
- True tables are reconstructed only when row/column relationships are clear enough to do so faithfully.
- If structure is too ambiguous, Chronicle falls back to explicit plain-text structure instead of inventing a false semantic model.

## 4.2 Tabular Data & Spreadsheets

Chronicle now includes a dedicated Tabular Data & Spreadsheets profile for CSV and Excel-style material.

- Structured datasets are prompted toward a single valid HTML5 table for each logical dataset.
- Column headers are preserved as `<th scope="col">`, and the primary row key is promoted to `<th scope="row">` where appropriate.
- A concise summary paragraph is added ahead of the table so screen reader users get the overall shape of the data before navigating cell-by-cell.
- `Total` and `Summary` rows are specially marked with `chronicle-total-row` and an ARIA label for clearer subtotal announcements.
- Entirely empty or redundant metadata columns can be omitted to reduce VoiceOver clutter.

## 5. Seamless Merge Behavior

When Merge Mode is enabled in GUI:

- Chronicle can process the queue as one continuous merged output.
- The main Extraction Settings now expose Seamless Merge directly so users do not have to rely on hidden/default preset behavior.
- Sequence lock is applied for `page XX` filename patterns.
- Prompt rules explicitly require seamless continuity across page/file boundaries.
- Synthetic filename headings (for example `page 002.JPG`) are stripped from merged output unless they appear in source content.

## 6. Post-Pass Omission Audit (PDF Text Layer)

Chronicle includes a configurable PDF text-layer audit:

- Toggle: `Enable PDF text-layer omission audit` (default: enabled).
- Compares extracted output against PDF text-layer coverage.
- Logs estimated coverage and potential missing lines.
- Can append recovered lines or a full text-layer safety appendix when coverage falls below thresholds.

## 7. Page Confidence Scoring

Chronicle includes an optional page confidence system (default: off):

- Toggle: `Enable page confidence scoring`.
- PDF pages receive confidence estimates with method tags:
  - `vision`
  - `dense-recheck`
  - `text-layer-fallback`
- Image files get heuristic quality scoring out of 10 with short condition notes (for example faded writing, blur, possible staining/water damage).

## 8. Academic Mode Footnotes and Annotations

Academic profile now includes explicit control of scholarly apparatus:

- Footnote handling options:
  - relocate to endnotes section
  - keep inline
  - strict original placement
- Annotation handling options:
  - keep inline
  - move to endnotes section
  - strict verbatim preservation

These controls are persisted in user configuration and injected into academic prompt rules.

## 9. Accessibility and Output Semantics

Chronicle enforces accessibility-first output behavior:

- Semantic heading hierarchy and table scopes in HTML.
- Language/direction metadata where applicable.
- Image description or null-alt behavior based on user mode.
- Accessible processing log (engine-focused) with Save Log action.

Primary accessibility-oriented output for review/distribution is HTML.

DOCX remains the primary review/editing format. Chronicle now maps heading markers, lists, pipe tables, and major `[[PAGE BREAK]]` boundaries into Word-friendly output so downstream accessibility review in Microsoft Word is less manual.

For damaged novel scans, Chronicle's long-form prose prompt now explicitly quarantines scanner-garbage bursts as local uncertainty so broken OCR fragments are less likely to contaminate neighboring readable prose.

## 10. Request Pacing and Backoff Controls

To prevent provider overload and improve stability:

- Minimum inter-request pacing is enforced.
- Exponential backoff with jitter is used on transient/rate-limit conditions.
- Delay is capped and retries are bounded.

## 11. Queue Engine Binding and Run Controls (GUI)

Session update (2026-03-08):
- Engine and format selectors were repositioned under queue actions as explicit "next run" controls.
- Engine selection now propagates to queued/paused rows when not running.
- Start Extraction now enforces the currently selected engine across queued rows for that run.
- This closes a class of mismatches where UI selection showed Pro while queued rows still contained Flash.
- Row assignment and runtime picker behavior now track per-file settings so selection changes reflect each file's assigned extraction rules.

## 12. Output Sanitization Layer (Post-Benchmark)

Chronicle now applies deterministic sanitization on non-HTML outputs in addition to prompt constraints.

- Removes leaked Base64 image payloads (`data:image/...;base64,...`) from non-HTML formats.
- Removes common structural HTML tags in non-HTML formats.
- Removes accidental wrapper fences (for example ```` ```html ```` and ```` ``` ````).
- Applied during stream ingestion and before final save dispatch.

Session update (2026-03-08):
- Added HTML wrapper normalization for streamable HTML finalization.
- If model output includes nested `<!DOCTYPE html>`, `<html>`, `<head>`, or `<body>` wrappers, Chronicle strips nested wrappers before final save.

## 13. Output Safety and Atomic Writes

Chronicle writes stream outputs to temporary files first and only finalizes on success. This prevents corrupted partial output files on interruption.

- Streamable formats (`html`, `txt`, `md`) write incrementally.
- Non-stream formats are dispatched through format-specific save handlers.
- All output formats now create a visible in-progress artifact in the destination folder while the run is active.
- For non-stream formats (`docx`, `pdf`, `epub`, `json`, `csv`), Chronicle writes a readable sidecar file ending in `.progress.txt.tmp` so users can inspect partial progress before final packaging completes.
- Example: `My Novel.docx.progress.txt.tmp` means the final target is `My Novel.docx`, while the sidecar is a crash-friendly text snapshot of the extraction in progress.
- Runtime progress language is format-specific: PDFs count pages, PowerPoint files count slides, and DOCX/text-like inputs count extraction chunks so non-page formats do not present fake `0/1 page(s)` status lines.
- On success, Chronicle removes the sidecar after the final output is saved.
- On failure/interruption, Chronicle preserves the sidecar and logs its path so partially recovered text remains inspectable.
- Optional source-file deletion occurs only after successful output completion.

Session update (2026-03-08):
- PDF fallback hardening: if HTML->PDF rendering fails, Chronicle now rebuilds a fresh PDF instance for flat-text fallback.
- This prevents fallback-path failures such as "No page open, you need to call add_page() first".

## 14. Data Handling and Privacy

Chronicle is stateless with respect to extracted document content:

- No local content database.
- No persistent memory of extracted body text across sessions.
- Lightweight queue/progress session metadata is persisted for recovery of interrupted runs.
- Processing logs are user-visible and can be saved manually.
- API keys remain local and use OS keychain/keyring when available (preferred path).

## 15. Benchmark Validation References

The benchmark cycle on March 7, 2026 validated the prompt/sanitizer hardening and documents residual risks:

- `docs/reference/BENCHMARKS_2026-03-07.md`

Session update (2026-03-08):
- Internet corpus benchmark harness added: `tools/web_corpus_benchmark.py`
- Session benchmark artifacts:
  - `artifacts/benchmarks/web/benchmark_web_outputs/`
  - `artifacts/benchmarks/web/benchmark_web_report.json`
  - `artifacts/benchmarks/web/benchmark_web_summary.md`

Session update (2026-03-17):
- The main window was simplified back to a user-facing reading workflow.
- The visible engine selector was removed from the main UI.
- Document presets now determine the reading engine automatically on the main screen.
- Quick Actions now emphasize `Add Files...` and `Start Reading` as the primary flow.
- Scanner/discovery wording was removed from the main surface in favor of document-reader language, while advanced import tools remain available from the File menu.

Session update (2026-03-17):
- The PDF Vision path now uses PyMuPDF (`fitz`) instead of `pypdf` for ingestion.
- Chronicle rasterizes PDF pages at 2x resolution before sending them to Vision-capable models.
- This keeps the existing prompt and sanitization architecture intact while giving the Vision pipeline image-first PDF handling.
- Text-layer probing and newspaper metadata sampling were also moved onto the PyMuPDF-backed path.
- Active-tree parity tests now cover critical build/runtime files so cross-tree scripting regressions are surfaced during testing instead of surfacing later in packaged builds.

- PDF page scoping was added to the main interface for testing and targeted reruns. Users can enter ranges such as `1,3,5-7` to limit a PDF job to specific pages.
- The page-scope setting is stored per queued row, validated before a run starts, and carried through the PDF processing path rather than being treated as a cosmetic UI filter.
- Progress estimation now respects selected PDF pages, which makes the progress gauge and summary more accurate during partial test runs and focused regression checks.
- Practical benefits: faster QA loops, lower API spend during testing, and easier reproduction of difficult page-level extraction failures without reprocessing an entire long document.
