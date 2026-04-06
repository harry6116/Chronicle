# Chronicle

Chronicle is an accessibility-first document recovery tool for difficult real-world material: archival scans, war diaries, laws and regulations, academic journals, tables, handwriting, newspapers, forms, office reports, government records, long-form books, and mixed-format batches.

Last Updated: March 21, 2026

## Current Release State

Chronicle is maintained as the main release track with special attention to Windows runtime behavior, screen-reader usability, portability, and frozen-build reliability.

The current codebase includes a modularized GUI layout under `chronicle_app/` while keeping the familiar root entrypoints (`chronicle_gui.py`, `build.command`, `build_windows.bat`) intact.

## What Chronicle Does

Chronicle reads source documents and restructures them into accessible output formats while preserving fidelity to the original material.

When a source file is structurally poor but still readable, Chronicle aims to produce something better in return: a more accessible equivalent with clearer headings, lists, tables, and reading order, while still preserving the source meaning and visible content.

Chronicle is strongest when the source is messy, inconsistent, or simply unpleasant to work with:

- degraded scans that need careful visual recovery rather than blind OCR dumping
- books and long-form prose where paragraph continuity matters
- historical or archival pages with repeated furniture, folios, damage, or marginal noise
- mixed-format queues where a human operator wants to tune behavior rather than accept a one-size-fits-all pass

Chronicle is designed for better recovery on hard documents, not just faster output on easy ones. Its advantage is control: specialist document presets, transparent progress, queue workflow, and fidelity-first recovery for hard real-world material.

## What Users Should Expect

Chronicle prioritizes quality, structural fidelity, and accessibility over raw speed, especially on difficult scans.

- Straightforward office files may move quickly.
- Difficult PDFs, newspapers, war diaries, and long-form book scans can take substantially longer.
- Book-quality extraction in particular may run for a long time because Chronicle is deliberately trying to preserve paragraph continuity, suppress scan junk, and avoid misleading truncation or false structure.
- Some options, such as punctuation modernization, abbreviation expansion, and transcription-style printed page references, can add extra work to the run.

If your priority is "recover the hard document as faithfully and accessibly as possible," Chronicle is designed for that. If your priority is "finish as quickly as possible regardless of edge-case quality," you may prefer lighter settings or a lighter source profile.

Chronicle aims to produce review-ready output and reduce manual cleanup, but human review is still required before final reliance.

For a short product summary focused specifically on hard-document workflows, see [public/WHY_CHRONICLE.md](public/WHY_CHRONICLE.md).

It is designed for:

- ordinary office documents, Word exports, and messy HTML reports
- government reports, annexes, appendices, and public records
- historical archives and handwritten correspondence
- military records, war diaries, dispatches, and telegrams
- intelligence cables and routing-heavy documents
- newspapers and multi-column print layouts
- technical manuals and structured forms
- laws, regulations, and contracts
- academic journals with citations, notes, and mathematical content
- museum labels, exhibit cards, and provenance notes
- spreadsheets, slide decks, and mixed office-document batches

## Core Capabilities

### Input Support

Chronicle accepts:

- PDF
- DOCX
- TXT
- MD
- RTF
- CSV
- XLSX / XLS
- PPTX / PPT
- EPUB
- JPG / JPEG / PNG / BMP / TIFF / TIF / WEBP

### PDF Vision Pipeline

Chronicle now uses `PyMuPDF` (`fitz`) for PDF ingestion in the Vision path. PDF pages are rasterized into high-resolution PNG images before being sent to Vision-capable models, which improves OCR fidelity on difficult archival, legal, and historical material.

### Output Support

Chronicle can export to:

- HTML
- TXT
- DOCX
- Markdown
- PDF
- JSON
- CSV
- EPUB

DOCX output notes:

- Chronicle maps heading markers, list structure, and plain-text tables into Word-friendly structure.
- Major report boundaries can be expressed as `[[PAGE BREAK]]` internally so DOCX exports are easier to navigate in Word's Navigation Pane and page view.
- During processing, Chronicle may create a readable sidecar temp file next to the final Word output, such as `My File.docx.progress.txt.tmp`. This is intentional: it is a crash-friendly in-progress text snapshot, not the final DOCX itself.
- For the strongest assistive-technology reading experience, HTML is still the preferred final reading format; DOCX remains the best editing/review format.
- Chronicle is designed to help users reach review-ready output more quickly, not to replace human verification.

### AI Provider Support

Chronicle supports multiple providers. On the main screen, the selected document profile chooses the reading engine automatically, and Chronicle can start easier PDFs on the faster Gemini path while keeping or escalating hard pages to the deeper path. Manual engine overrides remain available in Preferences when you want to force a specific provider/model yourself.

Supported providers/models in the current GUI:

- Google Gemini
  - `Gemini 2.5 Flash`
  - `Gemini 2.5 Pro`
- Anthropic
  - `Claude Sonnet 4`
- OpenAI
  - `GPT-4o`

Current provider guidance:

- Gemini remains Chronicle's strongest general-purpose PDF path.
- With `Engine Override` left on `Automatic`, Chronicle can start cleaner PDFs on `Gemini 2.5 Flash` first and keep `Gemini 2.5 Pro` in reserve for hard pages or harder whole-document cases.
- Claude is now the strongest non-Gemini PDF option in Chronicle. The app prefers Anthropic's Files API for Claude PDF slices when the local SDK supports it, then falls back to inline PDF document mode if needed.
- OpenAI remains available, but Chronicle does not yet use OpenAI's newer dedicated PDF file-input route. Inside Chronicle, OpenAI PDF handling should therefore be treated as a fallback path rather than the preferred PDF engine.
- Automatic engine selection now skips providers whose API keys are missing instead of trying to use them anyway.
- Live-provider note: Chronicle depends on online AI providers, so occasional provider-side demand spikes can still cause temporary `503`, `UNAVAILABLE`, quota, or retry events even when Chronicle itself is behaving correctly. When that happens, rerunning later is often the right first check before treating the result as a Chronicle regression.

### Accessibility-First GUI Features

Chronicle's GUI is designed to be workable with screen readers, including NVDA, JAWS, and VoiceOver.

Current accessibility-oriented GUI behavior includes:

- native picker-driven controls for multi-choice settings
- queue-first workflow so every queued file is eligible to run without requiring manual highlight selection
- saved processing log export for offline review
- contextual tooltips and accessible control names
- keyboard shortcuts for the most common menu actions
- reduced-noise engine logging designed to be informative without being excessively chatty
- semantic HTML output with language and direction metadata for downstream assistive reading

### Queue and Run Control Features

Chronicle includes:

- add files
- add folders
- recursive folder scanning
- remove selected rows
- select all / deselect all
- row-level application of current reading settings
- start reading now
- schedule extraction for a chosen local date/time
- pause / resume / stop controls
- session recovery support
- merge mode for seamless combined outputs
- row-level page or slide scope controls for PDF/PPTX files

### Device and Page-Import Features

Chronicle includes page-import workflow support in the GUI:

- `File > Find Connected Devices...`
- `File > Scan via NAPS2...`
- Windows device lookup fallback when NAPS2 device lookup is unavailable
- macOS device lookup fallback when NAPS2 device lookup is unavailable
- auto-add of imported pages back into the Chronicle queue
- saved last-used input-device preferences

### Document Profiles

Chronicle includes document presets tuned for different source classes:

- Everyday Mixed Documents
- Work Reports / Office Documents
- Government Reports / Public Records
- Letters / Memos / Notices
- Archives / Ledgers / Manuscripts
- Handwritten Notes / Drafts / Diary Pages
- Medical Notes / Clinical Forms / Doctor Handwriting
- War Diaries / Military Orders / Service Records
- Cables / Intelligence Briefings / Signals
- Newspapers / Multi-Column Pages
- Books / Novels / Long-Form Prose
- Manuals / Instructions / SOPs
- Forms / Checklists / Worksheets
- Flyers / Posters / Event Notices
- Brochures / Catalogues / Pamphlets
- Slides / Decks / Handouts
- Spreadsheets / CSV / Registers
- Research Papers / Equations / Footnotes
- Transcripts / Interviews / Plays
- Poetry / Verse / Line-Break Layouts
- Laws / Regulations / Contracts
- Museum Labels / Captions / Exhibit Text

These presets pre-fill recommended behavior and automatically select the most suitable reading engine behind the scenes. When automatic routing is active, Chronicle can keep easier PDFs moving on the faster engine while still escalating hard pages or hard documents when needed.

### In-Progress Temp Files

Chronicle now writes a visible in-progress temp file in the destination folder for every output format.

- Streamable formats such as HTML, TXT, and Markdown still build their primary `.tmp` output directly.
- Non-streaming formats such as DOCX, PDF, EPUB, JSON, and CSV now also write a readable sidecar file ending in `.progress.txt.tmp`.
- Example: if the final target is `Artemis Fowl and the lost colony.docx`, Chronicle may temporarily show `Artemis Fowl and the lost colony.docx.progress.txt.tmp` while extraction is running.
- The `.txt` suffix is intentional. The sidecar is a human-readable recovery snapshot so you can inspect progress even if the final DOCX/PDF/EPUB has not been finalized yet.
- Progress wording is format-aware: PDFs report pages, slide decks report slides, and DOCX/text-like inputs report chunks so long Word files no longer misleadingly claim they are a single page.
- On successful completion, Chronicle removes the sidecar temp file after the final output is saved.
- If the run fails or is interrupted, Chronicle preserves the sidecar so you can inspect recovered text instead of losing all visible progress.

### Original Page Number References

Chronicle now includes an `Original Page Numbers` setting in the main Extraction Settings and Preferences.

- `Suppress original page numbers`: removes standalone printed folios/page numbers when they are just page furniture.
- `Preserve original page-number references`: keeps visible page numbers as explicit references in the output so readers can track back to the source pagination.
- For novels and long-form prose, the default remains suppression, because mechanical folios usually hurt narrative flow more than they help.
- This setting is especially useful for transcription, proofreading, citation, and source cross-checking workflows. For screen-reader-first leisure reading, suppression is usually the better default.

### Seamless Merge in the Main Window

Chronicle's main Extraction Settings now include a `Seamless Merge` control.

- `Save each source as its own output`: normal one-file-per-source behavior.
- `Merge selected sources into one continuous output`: combine queued files or page images into a single continuous reading result.
- This is especially useful for multi-page photo captures, sequential scan folders, books split into many images, or any document where many source files really belong to one output.
- In merge mode, Chronicle also applies sequence lock for `page 01`, `page 02`, and similar filename patterns so the combined output stays in reading order.

### Extraction Safeguards and Fidelity Controls

Chronicle enforces strict fidelity-oriented behavior.

Key protections include:

- zero-guessing / anti-hallucination posture
- no broad spelling correction beyond narrow column-splicing and obvious print-artifact repair
- accessibility remediation for malformed but recoverable source structure, including broken HTML, duplicated OCR layers, damaged paragraph wrapping, broken list structure, and weak table text
- punctuation-only modernization when enabled
- reading may take a bit longer when modern punctuation or abbreviation expansion is enabled, because Chronicle has to correct punctuation and expand abbreviations
- hardcoded archaic-dash spacing repair prevents cleaned `.-` and `,-` sequences from jamming adjacent words together
- intelligent column splicing and print artifact correction for multi-column and damaged print layouts
- novel-mode corruption containment keeps local OCR collapse from poisoning otherwise readable paragraphs; damaged spans should be isolated instead of merged into fluent prose
- book-mode paragraph continuity rules now explicitly suppress fake hard returns from wrapped scan lines unless the visible prose clearly supports a true paragraph or dialogue break
- book-mode quote disambiguation now explicitly distinguishes apostrophes inside words from dialogue quotation marks and can normalize dialogue-style single quotes into double quotation marks when the page evidence clearly supports that reading
- tabular profile can produce a single semantic HTML5 table with narrated summaries, row headers, filtered empty columns, and marked subtotal rows for screen-reader review
- deterministic cleanup for non-HTML outputs
- HTML wrapper normalization for streamed HTML
- bounded chunking defaults for stability
- academic PDF downshift to one-page chunking where needed
- dense scanned newspaper PDFs can automatically downshift to one-page slices when file weight per page suggests a heavy short scan
- sequential merge cleanup and synthetic filename heading removal
- per-file resilience so one bad item does not abort the whole queue
- temporary-file saving strategy to reduce corrupted partial outputs
- DOCX structure mapping for headings, bullets, numbered lists, pipe tables, and major section page breaks

### Preferences and Advanced Controls

Chronicle exposes detailed behavior controls through Preferences, including:

- default document profile
- engine override (`Automatic`, Gemini 2.5 Flash, Gemini 2.5 Pro, Claude Sonnet 4, or GPT-4o)
- translation mode
- translation target language
- legacy punctuation mode
- historical units and currency mode
- abbreviation expansion mode
- image description mode
- large-print PDF mode
- merge mode
- academic footnote mode
- academic annotation mode
- custom prompt additions
- custom command/rule text
- PDF text-layer omission audit
- page confidence scoring
- low-memory mode
- file collision behavior
- delete-source-file behavior

When `Engine Override` is left on `Automatic`, Chronicle follows the document preset recommendation, can start easier PDFs on the faster Gemini path, and then falls back only to providers that actually have configured API keys. If you force a specific engine in Preferences, Chronicle stays on that manual choice instead of using the adaptive fast-first routing.

File handling behavior in Preferences:

- `File Collision Mode: Skip` leaves an existing output untouched and marks the new run as skipped.
- `File Collision Mode: Overwrite` replaces the existing output with the newly completed run.
- `File Collision Mode: Auto-Number` preserves the older file and writes the new output using an incremented filename.
- `Delete Source File` removes the source only after a successful output write. It does not delete a source file after a failed or interrupted run.

### Provider-Specific PDF Notes

- Gemini: recommended default for degraded scans, archival material, and complex PDF layouts.
- Gemini automatic routing: for supported profiles, clean born-digital PDFs can start on `Gemini 2.5 Flash` first while `Gemini 2.5 Pro` remains available for escalation on hard pages.
- Claude: recommended non-Gemini PDF alternative. Chronicle now prefers Claude Files API uploads for PDF slices, which reduces inline encoding overhead when that route is available locally.
- OpenAI: still useful for general multimodal fallback, but Chronicle's current OpenAI integration is not yet the preferred PDF route. If OpenAI PDF handling cannot continue on the direct path, Chronicle now logs that reason and falls back to PDF text-layer recovery.
- Historical Newspapers: dense short scans can trigger a file-size heuristic that shrinks PDF slicing to one page at a time, and Chronicle logs that decision so slow upload waits are easier to interpret.

### Diagnostics and QA Features

Chronicle includes:

- processing log export
- PDF text-layer omission audit
- optional page confidence scoring
- benchmark harnesses under `tools/`
- release validation helpers under `tools/`
- staged Windows bundle creation for portable Windows builds

Chronicle is particularly well suited to iterative review workflows:

- run a difficult source
- inspect the structured output or `.progress.txt.tmp` sidecar
- adjust preset/toggles
- rerun only the sections or files that need another pass

That makes Chronicle a strong fit for archivists, accessibility reviewers, transcription-heavy projects, and anyone working through genuinely difficult scan quality rather than clean born-digital inputs.

### Intelligent Column Splicing and Print Artifact Correction

Chronicle now includes Intelligent Column Splicing and Print Artifact Correction for difficult printed layouts. The Vision prompt can rejoin words broken across line or column boundaries, suppress false punctuation caused by physical layout artifacts, and correct minor optical print defects when the intended reading is clearly recoverable.

This keeps the reading flow more seamless for screen reader users while preserving historical accuracy at the factual level.

## Project Layout

Chronicle now uses a modularized application package while preserving root launch/build commands.

Key paths:

- `chronicle_gui.py`: primary GUI entrypoint
- `chronicle.py`: shared prompt and processing logic
- `chronicle_core.py`: shared cleanup and output-normalization helpers
- `chronicle_app/config.py`: profile and model configuration maps
- `chronicle_app/services/`: shared prompting, runtime policy, and scanner-discovery services
- `chronicle_app/ui/dialogs.py`: Preferences and API key dialogs
- `chronicle_app/ui/menus.py`: menu bar wiring
- `chronicle_app/ui/queue_panel.py`: queue UI panel
- `Mac/`: macOS helper scripts
- `tools/`: local validation, release, and benchmark tooling

## Installation and Runtime Modes

Chronicle can be used in two main ways:

- frozen app mode
- source mode

## System Requirements

Chronicle currently supports 64-bit desktop builds on macOS 12+ and Windows 10+.

Practical guidance:

- Minimum: 8 GB RAM, dual-core CPU, stable internet, and 5 GB free storage
- Recommended: 16 GB RAM or more, modern 4+ core CPU, SSD storage, and 20 GB free space
- Heavy workloads: 16-32 GB RAM is strongly recommended for large PDFs, long sessions, and merge-heavy runs

See the full requirements guide in `docs/user/SYSTEM_REQUIREMENTS.md`.

### Frozen App Mode

Frozen builds bundle runtime dependencies and are the preferred path for end users.

Expected outputs:

- macOS: `Chronicle.app`
- Windows: `Chronicle.exe`

Frozen app users do not need to install Python separately.

### Source Mode

Source mode is intended for development, testing, and local builds.

Requirements:

- Python 3.11 or compatible local build environment used by the project scripts
- dependencies from `requirements.txt`
- write access to local output/config locations

Run from source:

```bash
python chronicle_gui.py
```

## Build and Packaging

### macOS Build

Use:

```bash
./build.command
```

The build flow resolves project resources from the current workspace and is intended to remain portable when the repo moves to a new path or machine.

### macOS Packaged Memory Stress Check

After a macOS build, you can run the repeatable packaged-app memory harness:

```bash
./Mac/run_packaged_memory_stress.command
```

This checks:

- packaged `Chronicle.app` startup RSS
- a calibrated save-plus-PDF-audit stress pass using Chronicle's extraction code paths

Optional markdown report output:

```bash
./Mac/run_packaged_memory_stress.command --report-md docs/github_rollout/MAC_MEMORY_STRESS_REPORT_LATEST.md
```

### Windows Build

Use:

```bat
build_windows.bat
```

`build_windows.bat` launches `build_windows.ps1`, which performs dependency preflight and PyInstaller packaging.

### Staged Windows Bundle Workflow

When preparing a Windows build on another machine, use the staged bundle workflow.

On the source machine:

1. Run `./stage_windows_bundle.command`
2. Copy `dist_windows_bundle/Chronicle_Windows_Bundle` to the Windows machine

On the Windows machine:

1. Open `Chronicle_Windows_Bundle`
2. Run `build_windows.bat`
3. If the build fails, inspect `%APPDATA%\Chronicle\logs\windows_build_YYYYMMDD_HHMMSS.log`

Minimum staged bundle contents now include:

- `build_windows.bat`
- `build_windows.ps1`
- `run_a11y_harness.bat`
- `chronicle_gui.py`
- `chronicle.py`
- `chronicle_core.py`
- `chronicle_app/`
- `requirements.txt`
- `LICENSE`
- `assets/`
- `docs/`

Recommended Windows bundle destination:

- a normal user-writable folder such as `C:\Users\<you>\Documents\Chronicle_Windows_Bundle`

Avoid:

- `Program Files`
- the drive root
- admin-protected folders
- read-only cloud-synced paths when possible

## API Keys and Provider Boundary

Chronicle supports API keys for Gemini, Claude, and OpenAI models.

Provider key mapping:

| Vault key | Required for |
| --- | --- |
| `gemini` | Gemini models |
| `claude` | Claude models |
| `openai` | OpenAI models |

Important behavior:

- Chronicle stores keys locally in the user app-data profile.
- When supported, keys can be stored in the OS keychain/keyring and this is the preferred path.
- If keychain/keyring is unavailable, Chronicle falls back to local app-data storage.
- Chronicle does not maintain a local document-content database.
- Document content is transmitted to the selected AI provider for processing.
- Chronicle cannot override provider retention, training, or confidentiality policies.

Current provider billing/access notes:

- Google Gemini keys created in Google AI Studio can work on Google's free API tier, subject to current free-tier quotas, rate limits, and region availability.
- Google documents separate Free and Paid tiers for the Gemini API, and some Gemini models are explicitly listed as free of charge on the free tier.
- In practice, a Gemini API key may be enough for Chronicle testing without enabling paid billing first.
- Anthropic Claude API access is separate from the consumer Claude.ai chat plans. A Claude free account does not include API access, and even paid Claude chat subscriptions do not include Claude Console/API usage automatically.
- Anthropic's current help center says Claude Console/API usage requires Console access plus billing or prepaid credits on the Console side.
- In practice, treat Claude API access for Chronicle as a separate paid developer setup, not as part of a normal Claude chat subscription.

If confidentiality matters:

- verify the provider's current terms yourself
- use plans/settings that meet your privacy and compliance requirements
- avoid free tiers for sensitive or regulated material unless the provider explicitly guarantees the needed protections

## Recommended Workflow

A practical Chronicle workflow is:

1. Save provider keys in `File > API Keys...`
2. Set default model/output format/profile
3. Add files or a folder, or acquire scans via NAPS2
4. Review queue rows and any per-row settings
5. Use `Start Reading` or `Schedule Reading...`

### PDF Page Scoping

Chronicle now supports per-job PDF page scoping from the main window through the `PDF Pages` field. You can enter values such as `1,3,5-7` to read only those pages, or leave the field blank to process the full document.

Benefits:
- Faster testing when you only need to validate a few pages from a long PDF.
- Lower API cost for spot checks, prompt tuning, and regression testing.
- Safer partial reruns when one difficult section needs attention but the rest of the document is already confirmed.
- More truthful progress reporting, because Chronicle now counts only the selected PDF pages as work units for that job.

Important behavior:
- The page scope is stored with the queued row, so different PDFs can use different page selections in the same queue.
- Page scope affects PDF files only; other file types ignore it.
- Chronicle validates the requested pages before a run starts and will stop with a clear message if the scope exceeds the PDF length.
6. Review outputs in HTML first when accessibility is the priority
7. Save the processing log when you need audit or troubleshooting evidence

## Screen Reader Validation Guidance

Chronicle is intended to be workable with NVDA and JAWS on Windows, but real-host validation remains essential before calling a build release-ready.

Recommended Windows validation areas:

- app launch and initial focus landing
- menu bar access with Alt shortcuts
- queue review and row announcements
- Preferences dialog traversal
- API Keys dialog traversal and masked/unmasked key entry
- status updates during queue runs
- saved processing log export
- connected-device lookup messaging
- NAPS2 import dialog traversal and results returning to queue
- HTML output review in browser with NVDA/JAWS heading, landmark, and table navigation

Recommended menu shortcut checks:

- `F1`: open help guide
- `Alt+P`: Preferences
- `Alt+K`: API Keys
- `Alt+S`: Find Connected Devices
- `Alt+N`: Scan via NAPS2
- `Alt+L`: Save Processing Log

## Documentation Map

Main docs worth reading:

- `docs/user/chronicle_help.html`
- `docs/reference/Chronicle_Accessibility_Compliance_Statement.md`
- `docs/user/SYSTEM_REQUIREMENTS.md`
- `docs/policies/DISCLAIMER.md`
- `docs/policies/SECURITY.md`
- `docs/reference/CHANGELOG.md`
- `PLATFORM_LAYOUT.md`

## License

Chronicle is licensed under the GNU Affero General Public License v3.0.

See the top-level `LICENSE` file.

If you want commercial or proprietary licensing arrangements, treat those as separate licensing terms rather than as a replacement for the AGPL terms attached to this source distribution.

## Legal and Safety Reminder

Chronicle is an AI-assisted document-reading and restructuring tool, not a substitute for professional review or qualified advice.

Do not rely on Chronicle output as the sole basis for:

- medical decisions
- legal advice or court filing conclusions
- financial decisions
- safety-critical decisions
- compliance or evidentiary conclusions without human verification

Always verify important outputs against the original source documents.

## Support the Project

If Chronicle helps your work, community support is appreciated. This donation language should not be treated as a substitute for a formal pricing/licensing page if Chronicle is sold commercially.

- [Buy Me a Coffee](https://buymeacoffee.com/thevoiceguy)
- [Donate via PayPal](https://paypal.me/MarshallVoiceovers)
