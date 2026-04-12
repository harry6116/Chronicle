# Changelog

All notable changes to Chronicle will be documented in this file.

## [1.0.2] - 2026-04-11
### Added
- **Comics / Manga / Graphic Novels Preset:** Added a built-in visual-storytelling profile with panel-order, speech/thought balloon, caption, SFX, textless-panel, image-description, and right-to-left manga-flow guidance, plus one-page PDF slicing and default merge/page-reference settings for page-image sequences.
- **Comic Profile Live Validation:** Ran live single-page validation on `Bound by Law?`, Pepper & Carrot, and Little Nemo samples, then tightened comic HTML cleanup and the benchmark scorecard so comic A+ requires panel headings, non-empty panel sections, image descriptions, and semantic image-description wrapping.
- **Public-Domain Comics Showcase:** Added a public-domain Little Nemo before/after showcase sample for public repo/demo use.

### Changed
- **Magazine HTML Cleanup Hardening:** Chronicle's HTML finalization for dense periodicals now strips leaked markdown headings inside HTML, removes page-wrapper comment noise, drops broken placeholder-image tags more aggressively, dedupes adjacent repeated paragraph blocks, and suppresses repeated short running-head section labels that were polluting magazine tables of contents and article starts.

### Fixed
- **Magazine Validation Regressions:** The dense magazine validation run now completes cleanly on the rebuilt app without the earlier Gemini quota dead-end, and the saved HTML no longer carries the worst magazine regressions from the first pass such as raw markdown heading leakage, visible page wrapper markers, `IMAGE_URL` / `IMAGE_PLACEHOLDER` image junk, empty image sources, or footer-to-section HTML splices.

## [Unreleased]
### Added
- **Adaptive Fast-First PDF Routing:** Automatic engine routing can now start supported easy PDFs on `Gemini 2.5 Flash` first, keep `Gemini 2.5 Pro` in reserve for hard pages, and stay on the deeper path for hard/specialist cases.
- **Medical / Clinical Preset:** Added a dedicated `Medical / Clinical Notes / Handwriting` preset with conservative prompt rules for clinical notes, doctor handwriting, medication-style shorthand, and explicit uncertainty tagging instead of guessed expansions.
- **Public Site Rewrite:** Rewrote the single-page public site in clearer, plainer language and added an accessible proof section with real benchmark-based before/after comparison images.
- **Expanded Short-Form Preset Surface:** Added dedicated presets for `Letters / Memos / Notices`, `Handwritten Pages / Notes / Drafts`, `Forms / Checklists / Worksheets`, `Flyers / Posters / One-Page Notices`, `Brochures / Catalogues / Pamphlets`, and `Slides / Decks / Handouts`.
- **Official-Safe Benchmark Pack:** Removed the private hospital-letter image from the canonical gold-mix benchmark set so formal benchmark reporting uses only official-safe/public-safe cases, while private local checks can still be run separately when needed.
- **Sampled Legal Benchmark Pages:** Added representative opening, midpoint, and closing one-page benchmark cases for the `Aged Care Bill 2024` source so Chronicle's live benchmark pack can spot-check long Australian legislative PDFs without running all 574 pages every time.
- **War Diary Benchmark Samples:** Added representative one-page benchmark cases for `WO-95-1668-1`, `WO-95-1668-2`, `WO-95-1668-3_1`, and `WO-95-1668-3_2` so Chronicle can track military/diary quality on real archival material beyond the original single-image sample.
- **Gold-Mix Benchmark Corpus:** Added a broader sampled benchmark set spanning manuals, legal texts, intelligence scans, archival letters, military history, newspapers, academic material, and structured tabular files so Chronicle can be judged against a more realistic cross-document mix.
- **Original Page Number Toggle:** Added a user-facing setting so readers can choose whether Chronicle suppresses standalone printed page numbers/folios or preserves them as explicit original-page references in the output.
- **Broader Document Presets:** Added `Office Docs / Reports / Word / HTML` and `Government Reports / Public Records` presets so ordinary business/government files and messy exported documents have stronger accessibility-first defaults without losing specialist presets.
- **Accessibility Remediation Rules:** Shared prompt rules now explicitly allow faithful repair of malformed HTML, damaged Word exports, duplicate OCR overlays, broken list structure, damaged paragraph wrapping, and weak table structure when Chronicle can reconstruct a more accessible equivalent.
- **DOCX Page-Break Support:** Word-oriented output can now honor the `[[PAGE BREAK]]` marker so major report sections, appendices, and form boundaries become cleaner DOCX navigation points.
- **Visible In-Progress Temp Outputs:** Every extraction format now creates a readable `.progress.txt.tmp` sidecar in the destination folder during processing so long scans have a visible work-in-progress artifact even when the final format is DOCX, PDF, EPUB, JSON, or CSV.
- **Active-Tree Parity Guard:** Added `tests/test_active_tree_parity.py` to catch cross-tree drift in critical runtime/build files before a missing helper or wrapper leaks into someone else's build.
- **Timestamped Processing Logs:** Engine-event log lines now include wall-clock timestamps and elapsed run time so long extraction runs are easier to judge at a glance.
- **Repeatable macOS Memory Harness:** Added `tools/mac_packaged_memory_stress.py` plus `Mac/run_packaged_memory_stress.command` to measure packaged-app startup RSS and a calibrated extraction memory pass after macOS builds.
- **Seven-Day Continuity Refresh:** Updated continuity and handoff notes on 2026-03-20 so launch context, wake-phrase handling, and current high-risk extraction rules stay aligned.
- **Preferences Engine Override:** Added an `Engine Override` control in Preferences so users can keep automatic preset routing or force Gemini 2.5 Flash, Gemini 2.5 Pro, Claude 3.5 Sonnet, or GPT-4o from one place.
- **Public Repo Snapshot Tooling:** Added `tools/prepare_public_repo_snapshot.py` to assemble a clean GitHub-facing Chronicle repo snapshot locally, with modern root docs swapped in and private/generated clutter excluded.
- **Claude Model Alias Upgrade:** Chronicle now transparently upgrades the retired Anthropic model id `claude-3-5-sonnet-20241022` to `claude-sonnet-4-20250514` so older saved settings keep working.
- **Provider Billing Guidance Refresh:** Core docs now explicitly distinguish Google Gemini free-tier API access from Anthropic Claude Console billing, so users are told that Gemini keys can work on Google's free tier while Claude API usage still requires separate Console/API billing or prepaid credits.
## [1.0.0] - 2026-04-06
### Added
- **First Standalone Public App Release:** Chronicle now has a clear first public app release line separate from the older terminal-first public repository history.
- **Packaged Release Assets Prepared:** The current first public release assets are `Chronicle 1.0 mac.zip` and `Chronicle 1.0 windows.zip`, prepared for attachment to the public GitHub release.

### Changed
- **Public Repo Messaging Reset:** Public-facing repo rollout docs now frame Chronicle as a `1.0.0` standalone app launch rather than a minor continuation of the older public repo snapshot.
- **GUI API Key Storage Path:** The GUI now uses per-user app-data storage paths in development and packaged runs, so locally remembered API keys live on the user's own machine instead of the working repository tree.

### Fixed
- **Release Safety for Local Credentials:** Existing GUI-side local settings and key files are migrated out of the repository root into per-user app-data storage, reducing the risk of local secrets being swept into a public release workflow.

### Changed
- **Preset Picker Clarity Pass:** Reordered and relabeled the live document preset picker into clearer user-facing families, renamed the fallback to `Miscellaneous / Mixed Files`, sharpened the difference between `Letters / Correspondence`, `Reports / Business Files`, and `Government Reports / Records`, clarified that photographed handwritten pages belong under `Handwritten Letters / Notes / Diaries` unless they are clearly clinical, and removed the stale UI remap that previously restored `forms` as `manual`.
- **Preset Naming and User Guidance:** Public/user-facing preset names and explanations now reflect the newer separated taxonomy instead of older blended labels such as `Technical Manuals / Forms`.
- **Automatic Engine Documentation:** Public and user docs now explain that `Automatic` can use the faster engine first on easier PDFs, while a manual engine override disables that adaptive path.
- **File Collision Guidance:** User docs and help now explicitly explain `Skip`, `Overwrite`, and `Auto-Number`, plus the rule that source deletion only happens after a successful run.
- **Standard Profile Defaults:** The general `Standard` preset now leans harder toward accessible recovery for ordinary PDFs and mixed office documents, with punctuation modernization and abbreviation expansion enabled by default.
- **Claude Engine Defaults:** Claude-facing defaults, labels, and overrides now point to Claude Sonnet 4 instead of the retired Claude 3.5 Sonnet id.
- **Preset Surface Expansion:** Chronicle's preset guidance now explicitly covers `Office Docs / Reports / Word / HTML`, `Government Reports / Public Records`, `Books / Novels / Long-Form Prose`, and the existing specialist profiles in README/help/methodology docs.
- **Word Output Guidance:** Documentation and prompt rules now explain that DOCX output is structured for headings, lists, tables, and major section/page boundaries rather than merely acting as plain dumped text.
- **Readable Progress Logging:** File headers now identify each queued file once, page progress lines are shorter, and a quiet-run heartbeat reports that work is still continuing during long pauses.
- **Throughput Guidance:** General, Manual, and Legal prompt rules now explicitly prioritize high-speed structural accuracy for dense specification tables, control lists, and repetitive grid data.
- **System Requirements Docs:** Expanded runtime guidance in `docs/user/SYSTEM_REQUIREMENTS.md` and surfaced a concise system requirements summary directly in `docs/user/README.md`.
- **Seven-Day Build/Packaging Audit:** The March 14-20 cycle also aligned packaging expectations across the primary Mac tree and the current Windows beta shipping tree, including build-path cleanup, artifact verification, and refreshed release notes.
- **Provider Availability Routing:** Preset-driven engine selection now resolves only to providers with configured API keys, and the Preferences override follows the same provider-availability guardrails instead of silently sticking to an unavailable engine.
- **Main Window Settings Layout:** The `Apply Current Settings To Selected` action now appears below the source-deletion safety options so it follows the settings it acts on more naturally.
- **Documentation Sync:** README/help/changelog language now reflects the Preferences engine override, automatic provider-key fallback, the relocated apply-settings control, and the current three-tree lockstep workflow.
- **PDF Skip/Fallback Visibility:** Chronicle now logs a direct OpenAI-specific reason when PDF processing must fall back to the text layer, and collision-mode skips now state that an output file already exists and `File Collisions` is set to `Skip`.
- **Claude PDF Transport:** Chronicle now prefers Anthropic's current Files API for Claude PDF slices when the SDK supports it, then falls back to inline PDF mode with an explicit log message if Files API upload is unavailable.
- **Public Repo Hygiene:** Local ignore rules now also catch `.venv/`, dated source zips, review archives, and staged public-repo output so migration prep does not keep re-dirtying the repo.

### Fixed
- **Split-Chunk Inline Image Payload Cleanup:** Chronicle now strips malformed `data:image/...;base64,...` and `about:blank...` payloads more aggressively across streamed HTML writes, final HTML normalization, and benchmark temp outputs so form/manual cover pages do not bloat temp files or hang finalization when image blobs are split across chunks.
- **Military Order / Continuation Heading Recovery:** HTML normalization now recognizes additional `WO-95` diary shapes, including ordered military operation orders and bare-text continuation pages, and promotes them into stable `h1`/`h2` structure during continuous benchmark runs.
- **Manual Cover-Page Heading Recovery:** Image-heavy manual opening pages now recover stable heading structure from document-title metadata and cover-page context, improving deterministic results for Zoom/YUNZII-style first pages during benchmark runs.
- **Academic Index Heading Recovery:** Index pages that arrive as nested section/header blocks rather than clean paragraph headings are now normalized into consistent `INDEX` / `Index Entries` heading structure.
- **Inline Base64 HTML Payload Scrubbing:** HTML/EPUB sanitization now strips inline `data:image/...;base64,...` payloads before they can bloat streamed benchmark/form outputs, with regression coverage to keep giant embedded image blobs out of normalized HTML.
- **Sparse Heading Recovery for Legal and Military Pages:** HTML normalization now promotes sparse opening blocks into semantic headings more reliably, including military diary title blocks and legal pages that begin at `h2`/`h3` depth, so benchmark pages do not lose their top-level heading structure.
- **Broad Benchmark Table Determinism:** `Tabular Data & Spreadsheets` HTML output now has a direct deterministic renderer for CSV/XLSX sources, so large table benchmarks like `titanic.csv` and `trivia.xlsx` no longer depend on slow model streaming just to emit accessible headings and semantic tables.
- **Benchmark Watchdog Startup Grace:** The benchmark harness now gives slow-starting deep-engine cases a longer initial idle window before the first content bytes arrive, which stops dense legal pages from being marked as hung simply because the model needed extra startup time.
- **Headingless Index / Figure / Military Continuation Pages:** HTML normalization now recovers headings for index-style academic pages, figure-led academic pages, and headingless `WO-95` continuation pages more consistently, reducing page-to-page benchmark drift in the gold-mix and war-diary corpora.
- **DOCX Markdown Emphasis Leakage:** Tightened the Word/DOCX prompt rules so novel/report output no longer has permission to leak literal inline markdown styling such as `**bold**` or `*italics*` into final Word-bound text.
- **Novel Folios and Clipped-Tail Handling:** Tightened the long-form prose prompt again so ornamental folio markers like `• 24 •`, fused-word joins, and clipped end-of-page/end-of-file fragments are treated as explicit novel cleanup targets instead of leaking into the reading flow.
- **Novel Corruption Containment:** Hardened the `Books / Novels / Long-Form Prose` prompt so damaged OCR bursts are isolated as local uncertainty instead of bleeding scanner garbage into surrounding prose, with stronger chapter-break and front/back-matter separation guidance for bad novel scans.
- **GUI Chunk-Progress Bridge:** Fixed a runtime mismatch where DOCX/EPUB chunk progress could crash immediately because the main GUI wrappers were still calling older `process_text()` / `process_epub()` signatures without the new progress-callback parameter.
- **Truthful Non-PDF Progress Reporting:** DOCX, EPUB, and other text-like inputs no longer pretend they are `0/1 page(s)` jobs. Chronicle now reports chunk-based progress for those formats so long Word-style files reveal ongoing internal work instead of a fake single-page counter.
- **Crash-Friendly Output Recovery:** Non-streaming save formats now preserve an inspectable in-progress sidecar on failure, clean it up on success, and can materialize final output from that disk-backed temp path instead of relying only on late-stage in-memory state.
- **Gemini In-Memory PDF Upload Compatibility:** Chronicle's shared Gemini PDF path now uploads in-memory PDF slices as seekable binary streams with explicit SDK upload config instead of a legacy tuple payload, eliminating the noisy tuple-type fallback on current `google-genai` builds while preserving the normal visual PDF reading path.
- **Cross-Provider PDF Temp Permission Failures:** Shared PDF processing now keeps normal Gemini, Claude, and OpenAI PDF-slice handling in memory first, so Chronicle no longer depends on creating a local temp PDF just to upload or base64-encode a slice. When a Gemini SDK build still refuses in-memory upload, Chronicle falls back to a system-temp file only for that one upload attempt and cleans it up immediately after.
- **Windows Packaged PDF Temp Cleanup Failure:** Shared PDF processing now writes temporary PDF slices into the system temp directory instead of the packaged app/runtime folder, prefers in-memory Gemini PDF uploads, waits for Gemini uploads to become `ACTIVE`, and downgrades temp-slice cleanup errors to warnings so a denied delete like `_internal\\temp_0.pdf` no longer aborts the whole extraction run.
- **Dense Newspaper PDF Stalls:** Short but unusually heavy historical newspaper PDFs now drop to single-page slices based on file weight per page, and the processing log explains that Chronicle is shrinking slices to avoid long upload stalls.
- **Cross-Tree Script Drift:** Restored missing root wrapper scripts in Beta/Windows Beta, aligned `build_windows.bat` on the safer diagnostic-first entry path, and covered the lockstep surface with parity tests.
- **Long-Run Memory Pressure:** Added a cross-format performance and memory guard with tighter PDF cleanup, explicit PyMuPDF raster disposal in the legacy path, forced garbage collection checkpoints, and more aggressive non-merge buffer purging.
- **Mac Quit Guarding:** `Command+Q` now routes through Chronicle's guarded close path so active or unfinished extractions cannot close without the warning/session-save dialog.
- **Butler Memory Clearing Guard:** Active bounded extraction buffers are explicitly held to a `2`-page clear cadence, with regression coverage to prevent drift back to larger thresholds.
- **Missing Processing-Speed Helper in Built Apps:** Restored the GUI `get_processing_speed_warning()` wrapper in every active Chronicle tree and added regression coverage so frozen builds cannot ship with that unhandled script exception again.
- **Cross-Tree Queue Wording Drift:** Re-aligned the empty-queue announcement and related regression expectations so the active program scripting stays identical across the main, Beta, and Windows Beta trees.
- **OpenAI PDF Fallback Messaging:** OpenAI PDF attempts no longer disappear behind a generic gearshift error loop; Chronicle now drops directly into text-layer recovery with an explicit log reason and regression coverage.
- **Stale Claude PDF Beta Path:** Removed Chronicle's old always-on Claude PDF beta-header path and replaced it with current Claude Files API routing plus tested fallback behavior.

## [1.8.3] - 2026-03-09
### Added
- **Advanced Page Selection (GUI):** Added per-row advanced page/slide scope controls with explicit custom selection support for PDF and PPTX input.
- **Quick Scope Presets:** Added one-click scope helpers (`First 5`, `Odd`, `Even`, `Last 10`) and custom text spec input (hyphen ranges like `30-45`; commas only for multiple groups such as `1-5,8,11`).
- **Three-State Units/Currency Mode:** Added `Keep original`, `Keep + bracketed modern equivalent`, and `Replace with modern equivalent only`.
- **Three-State Abbreviation Mode:** Added `Keep original`, `Expand in brackets`, and `Replace with expanded form only`.
- **Release Security Hooks:** Added repository pre-commit secret scanner tooling (`tools/precommit_secret_scan.sh`, `.githooks/pre-commit`, `tools/install_git_hooks.sh`).
- **Release Gate Tooling:** Added `tools/release_fileset_check.py` and `tools/release_regression_offline.py` for repeatable local release validation.

### Changed
- **Settings Persistence Model:** Added explicit `unit_mode`, `abbrev_mode`, `page_scope_mode`, and `page_spec` settings with backward compatibility for older boolean settings.
- **Queue Settings Summary:** Row summaries now include units mode, abbreviation mode, and page-scope state for clearer review before run.
- **Version Alignment:** GUI runtime version now reports `1.8.3` to match release documentation and changelog metadata.
- **Privacy Documentation Alignment:** Updated help/architecture/methodology/README key-storage wording to match current app-data + keyring behavior.
- **Dependencies:** Added `python-pptx` to `requirements.txt` for explicit PPTX processing parity in source environments.

### Fixed
- **Novel Ending Continuity:** Adjusted the long-form prose preset so damaged late-page or end-of-file fragments are isolated locally without encouraging the model to stop early; Chronicle should now continue extracting later readable prose instead of clipping the rest of a damaged ending.
- **Novel Prompt Leak Cleanup:** Removed a generic plain-text prompt prefix that could bleed instruction-like junk such as `Format content logically` into DOCX novel output, and tightened the book preset to suppress non-authored helper fragments while repairing only obvious OCR word errors conservatively.
- **Resume/Decompression Resilience:** Hardened per-file processing so decompression failures are contained to the current file and do not abort the entire queued run.
- **PDF Text-Layer Audit Robustness:** Audit now skips unreadable/decompression-failing pages safely instead of escalating to run-fatal exceptions.
- **Advanced Scope Control Gating:** Runtime scope controls now disable when target queue rows include unsupported source formats (scope is valid for PDF/PPTX rows).
- **Credential Exposure Hardening:** The GUI runtime and benchmark key-loading paths now use app-data key storage and auto-migrate/purge legacy workspace-root key files.

## [1.8.2] - 2026-03-08
### Added
- **Web Corpus Benchmark Harness:** Added `tools/web_corpus_benchmark.py` to run live multi-source, multi-format validation against public internet documents and produce audit reports (`benchmark_web_report.json`, `benchmark_web_summary.md`).
- **Targeted Benchmark Controls:** Added harness options for scoped reruns (`--formats`, `--source-regex`) to accelerate fix verification cycles.

### Changed
- **GUI Extraction Settings Layout:** Repositioned model and format selectors below queue action controls and relabeled them as next-run settings for clearer workflow.
- **GUI Engine Selection Semantics:** Engine selection now propagates to queued/paused rows when idle, and Start Extraction enforces the selected engine across queued rows for that run.
- **Audit Log Wording:** Updated PDF text-layer audit wording to clarify that coverage is character-based and missing lines are heuristic.
- **Hardcoded Fidelity Prompt Rules (`chronicle.py`):** Explicitly reinforced zero-guessing/no-hallucination and no-spelling-corrections behavior. Modern punctuation mode is now documented and prompted as punctuation/spacing-only (no wording or token edits).
- **Documentation Alignment:** Updated core technical docs to explicitly state hardcoded zero-guessing, no spelling correction, and punctuation-only modernization semantics.
- **Hardcoded Modern Punctuation Spacing Repair (`chronicle_core.py`):** Updated `apply_modern_punctuation()` so archaic `.-` and `,-` cleanup injects a single space when a letter follows, preventing jammed output such as `Friday.Mrs.` after dash removal.

### Fixed
- **HTML Wrapper Nesting:** Added post-stream HTML normalization to strip nested document wrappers (`<!DOCTYPE html>`, `<html>`, `<head>`, `<body>`) emitted by model output.
- **PDF Fallback Stability:** Fixed HTML-to-PDF fallback path to always reinitialize a fresh PDF instance before flat-text write, preventing fallback state errors (for example "No page open...").
- **Benchmark Harness HTML Finalization:** Applied the same HTML wrapper normalization in benchmark-run save flow so harness audits align with production behavior.

## [1.8.1] - 2026-03-07
### Added
- **Main Window Scheduling Control:** Added a `Schedule Extraction...` action next to `Start Extraction` so queued jobs can be started at a chosen local date/time.
- **Seamless Merge Execution (GUI):** Merge mode now supports continuous merged output with page-sequence lock for `page XX` filenames and cleanup of synthetic filename headings (for example `page 002.JPG`).
- **Academic Footnote/Annotation Controls:** Added explicit Academic mode toggles for footnote handling (endnotes/inline/strict) and annotation handling (inline/endnotes/strict).
- **PDF Omission Audit:** Added optional post-pass PDF text-layer audit to estimate coverage and append recovered lines/safety appendix when mismatch is detected.
- **Page Confidence Scoring:** Added optional per-page confidence output (score out of 10) plus condition notes; image scoring can flag likely degradation patterns such as faded writing or possible stain artifacts.
- **Rate-Limit Hardening:** Added request pacing plus capped exponential backoff with jitter and bounded retries to reduce API pressure.
- **Post-Benchmark Prompt Hardening:** Added explicit non-HTML purity directives (`NON-HTML OUTPUT RULE`, `NO RAW BINARY`, `NO FENCE WRAPPERS`) to reduce format contamination in text-oriented outputs.
- **Benchmark-Driven Exam Directives:** Added benchmark-driven exam rules for strict multiple-choice layout, handwriting-scaffold removal, and mark-allocation line preservation.
- **Deterministic Non-HTML Sanitizer:** Added code-level cleanup in Chronicle output paths to strip leaked Base64 payloads, structural HTML tags, and accidental fence wrappers from non-HTML formats.
### Changed
- **Primary Action Naming:** Main extraction action is standardized as `Start Extraction` across the GUI and help/docs language.
- **Preset + Engine Behavior:** Selecting a document preset now pre-fills preset options without forcibly changing the user-selected engine.
- **Chunking Documentation:** Clarified runtime defaults: Chronicle uses `PDF_CHUNK_PAGES=3` and `TEXT_CHUNK_CHARS=10000`; Academic PDF mode still forces one-page chunks.
- **Help & Methodology Documentation Sync:** Updated help, methodology, architecture, and accessibility documentation to match current engine behavior and controls.
### Fixed
- **Non-HTML Contamination Regressions:** Closed benchmark-discovered leakage paths where TXT/MD/PDF/DOCX pipelines could contain HTML tags, Base64 data URIs, or wrapper fences.

## [1.8.0] - 2026-03-02
### Added
- **Automated Setup Scripts:** Added dedicated `update_mac.sh` and `update_windows.bat` scripts to handle automatic dependency installation and repository pulling across operating systems.
- **Accessibility Compliance:** Published the `Chronicle_Accessibility_Compliance_Statement.md` documenting strict WCAG 2.2 Level AA, US Section 508, and AS EN 301 549 adherence.
- **Advanced Semantic Formatting:** Enforced strict programmatic semantics for HTML and EPUB outputs, including null alt attributes for toggled visual descriptions, strict table scopes, dynamic title tags, and auto-linking internal Tables of Contents.
- **Dynamic Language & Cultural Preservation:** Added dynamic ISO language code detection and inline span tags (e.g., `<span lang="mi">` for te reo Māori). This ensures screen readers correctly switch pronunciation profiles and voice critical diacritical marks like macrons.
- **Academic & Epigraphic Engine:** The engine now reconstructs visual formulas into LaTeX/MathML, safely anchors footnotes, flattens dense multi-column layouts, and extracts ancient scripts (including Egyptian Hieroglyphs and Sanskrit) alongside structured transliterations.
- **Anti-Hallucination Directives:** Implemented algorithmic Lanczos resampling for degraded media and a strict "Zero-Guessing" policy that systematically outputs `[Illegible Micro-text]` rather than hallucinating text.
- **Streamlined Run Scripts:** Optimized Mac and Windows execution files with immediate screen reader audio feedback upon launch.
### Removed
- Removed GUI testing mockups from the production environment to keep the main directory clean.

## [1.7.0] - 2026-03-01
### Added
- **Atomic Saving (`.tmp` Protocol):** Overhauled the file-saving architecture to stream active outputs to temporary files. Files are only converted to their final extension upon 100% successful generation, completely eliminating the risk of corrupted or truncated files during system crashes.
- **Smart Skip Batching:** The engine now validates the output directory before processing. If an extraction was interrupted by a power failure, rerunning the script will automatically skip all fully completed documents and resume exactly where the crash occurred.
- **Live Save Merging:** Modified the `merge_files` logic to incrementally write to the master document on the hard drive after every individual file loop, protecting massive continuous archives from memory-loss during unexpected shutdowns.
- **Testing Documentation:** Added `Chronicle_Fail_Safe_Testing_Report.md` detailing the extreme hardware stress tests used to validate the new resilient architecture.

## [1.6.0] - 2026-02-28
### Added
- **One-Click Auto-Updaters:** Introduced initial updater scripts allowing non-technical users to seamlessly download the latest version of the `chronicle.py` script directly from GitHub without needing to navigate git commands. 
- **Automated Dependency Management:** Updater scripts automatically scan for and install any newly required Python libraries in the background, preventing crashes.
- **Data Safety Protocol:** Updater scripts use secure routing to ensure that user-generated directories (`input_files`, `output_html`, etc.) and the sensitive `api_key.txt` file are completely ignored and protected during the update process.

## [1.5.0] - 2026-02-28
### Added
- **New Export Formats:** Added native support for exporting to EPUB (`.epub`), JSON (`.json`), and CSV (`.csv`). 
- **EPUB Engine:** Integrated `EbookLib` to generate native, accessible eBooks directly from raw document scans, perfect for compiling large historical diaries.
- **JSON & CSV Engines:** Created structured data pipelines allowing Chronicle to be seamlessly integrated into enterprise APIs, legal databases, and financial spreadsheets.
- **Legal & Statutory Directives:** Added explicit AI prompt rules to recognize and meticulously preserve the strict hierarchy of legal documents (Parts, Divisions, Sections, Subsections) and defined terms.
- **Accessibility Showcase:** Added a new `assets/samples/war_diary_showcase/` directory containing an accessible HTML "Before and After" comparison using highly degraded WWI War Diaries.
### Changed
- **Format System Expansion:** Expanded the early format-selection system to accommodate 8 distinct output formats.
- **Merge Mode Logic:** Updated the `merge_files` function to natively handle the invisible stitching of EPUB chapters and the concatenation of JSON data arrays.
- **PDF Engine Upgrade:** Transitioned the PDF generation backend from the legacy `fpdf` to `fpdf2`, utilizing `latin-1` encoding replacement to completely resolve crashes caused by obscure historical symbols.
- **Git Automation:** Updated repository scripts for flawless handling of deleted and moved files.
### Fixed
- **Memory Buffer Overloads:** Resolved an early runtime issue where pushing large batches of images failed by permanently increasing the `http.postBuffer` limit.
- **HTML Table Semantics:** Fixed an issue where parsed historical rosters were flattening into raw text; enforced strict `<th>` and `<td>` scoping for VoiceOver compatibility.

## [1.4.0] - 2026-02-28
### Added
- **Excel Support (.xlsx):** Implemented the `openpyxl` library to natively support multi-page Excel workbooks.
- **Spreadsheet Flattening:** Added a new dynamic prompt rule to transform raw, spatial tabular data into highly readable, linear text summaries and data tables specifically designed for screen readers.
### Changed
- **Installation Documentation:** Major overhaul of the README to assist non-developers. 

## [1.3.2] - 2026-02-28
### Added
- **TIF Support:** Explicitly added `.tif` to the supported extensions list and routing logic.
- **API Privacy Documentation:** Restored the API tier pricing and data privacy breakdown to the README.
### Fixed
- **Syntax Error:** Removed a stray character in the extensions list that prevented the script from launching.

## [1.3.0] - 2026-02-27
### Added
- **Menu 10 (Technical Appendix):** Added a dedicated toggle to completely disable all transcription confidence scores, dates, and condition profiles from the output.
### Changed
- **True Seamless Merge:** When processing multi-page documents (like continuous letters), removing the technical appendix now creates a 100% seamless reading experience. 

## [1.2.1] - 2026-02-27
### Fixed
- **Engine Restoration:** Restored full processing logic, including PDF chunking, recursive batch scanning, and the complete preference menu system.
- **Model Upgrade:** Fixed API 404 crashes by updating targets to Google's newest `gemini-2.5-pro` and `gemini-2.5-flash` models.

## [1.2.0] - 2026-02-27
### Changed
- **Modernized AI Engine:** Migrated from the deprecated `google.generativeai` library to the official `google-genai` SDK to ensure stability and eliminate runtime warnings.
- **Optimized File Processing:** Replaced legacy base64 encoding with the native `client.files.upload()` API, significantly improving upload speeds.
# 2026-03-21
- Hardened shared PDF-slice handling so Chronicle now writes temporary PDF slices into the system temp directory instead of the app/runtime folder, preventing frozen Windows builds from trying to delete `_internal\\temp_*.pdf` files in place.
- Updated the shared Gemini PDF path to prefer in-memory slice uploads, wait for Gemini uploads to become `ACTIVE`, and treat temp-slice cleanup failures as non-fatal warnings instead of file-ending extraction errors.

# 2026-03-26
- Tightened streamed HTML cleanup so Chronicle now strips malformed `about:blank...` image tails, recovers running-header titles into real `h1` headings, and promotes continuation-page military list sections into accessible heading structure.
- Updated the local benchmark scorecard so military pages only require strikethrough recovery when the output actually contains struck-through content, preventing false benchmark penalties on clean continuation pages.
- Hardened the local benchmark runner with per-case subprocess watchdogs and idle-output timeouts, so flaky live cases fail cleanly instead of hanging the whole benchmark batch.
