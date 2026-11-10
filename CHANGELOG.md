# Changelog

This history describes changes users may notice. The desktop app release series began at 1.0.0 in April 2026. Earlier version numbers below belong to the original project and follow a different sequence.

## [1.1.9] - 2026-11-10

- Added the separate Automatic Flash/Argon option for PDF and image pages, preserving existing Automatic behaviour.
- Started each page with Flash and retried flagged pages with Argon without changing the next page's starting engine.
- Buffered page attempts so only the selected reading is written, with bounded retries and explicit review needs.
- Explained API credit, processing-time and automatic-detection limits in the guide and engine help.

## [1.1.8] - 2026-11-10

- Resolved overlapping punctuation, abbreviation, table and output-format instructions.
- Kept originals alongside optional reading aids, with protected clinical shorthand and identifiers.
- Shared source-fidelity safeguards with newspaper strip recovery.
- Preserved Unicode maths and used visible book paragraph boundaries without contextual word replacement.

## [1.1.7] - 2026-11-10

- Added optional Gemini 4 Argon in Engine Override while retaining existing automatic presets.
- Preserved source quotation marks and page-number gaps, with stronger column and uncertainty guidance.
- Reported token-limited responses as incomplete and removed the command-line newspaper character cutoff.
- Corrected current-model help and added Ko-fi to optional support choices.
- Updated the website address and added accessible source/result comparisons with explicit accuracy limits.

## [1.1.6] - 2026-11-08

- Updated automatic Gemini engines to 3.8 Flash and 3.1 Pro Preview, with manual 2.5 compatibility choices retained.
- Improved handwriting/war-diary reading and page-continuation handling, with safer printer-code and acronym preservation.
- HTML-safe currency, punctuation and abbreviation transformations preserve markup and keyboard focus colours.

- Colour-preserving comic scans with full-page context and closer views of lettering, captions and irregular frames.
- Clearer comic panel, printed-text and description handling, including higher-resolution rendering for small-dimension comic PDFs.
- Benchmark reporting that distinguishes structural accessibility from transcription fidelity.
- Clearer Gemini key-field guidance that asks for one API key.
- Mac build verification and automatic refresh of the configured distribution folder, with checked replacement and recovery after verification failure.

## [1.1.5] - 2026-11-08

- Support for new Google AI Studio authorisation keys alongside older Gemini keys.
- API-key entry checks for Gemini, Claude and OpenAI without fixed prefix or length requirements, with clear correction guidance and focus on the affected field.
- New Google authorisation keys are redacted from logs and support bundles.
- Updated provider setup instructions and a save confirmation that distinguishes local storage from provider authentication and billing.

## [1.1.4] - 2026-11-08

- New Chronicle website with downloads, the user guide, document examples, and release news: https://harry6116.github.io/.
- Direct email contact at chronicle.vir@gmail.com on the website and in the app.
- About Chronicle includes labelled website, email, and GitHub actions, selectable contact details, and separate contact and optional-support rows.
- Optional one-time and monthly GitHub sponsorship in About and the Support menu.

## [1.1.3] - 2026-11-01

- Built-in update checks and installation for Mac and Windows, with readable release notes and a Remind Me Later action.
- F1 help for the control you are using, with keyboard navigation and return focus when help closes.
- More predictable focus when opening dialogs from menus.
- Safer updates that prepare the replacement first, stop if Chronicle is still running, and attempt to restore the previous app if replacement or the restart command fails.
- A Mac first-launch helper for systems that require approval before opening Chronicle.
- Clearer public guides and release notes.

## [1.1.2] - 2026-09-15

- Published Mac and Windows downloads with PDF, accessibility and offline-processing improvements.

## [1.1.1] - 2026-06-29

- Updated Claude support to Sonnet 4.6. Older saved selections are updated automatically.
- Private Offline Mode accepts only an Ollama connection on the same computer.
- Improved PDF reliability, including password-protected files and medical reports.
- Improved page references, page navigation and accessible output structure.
- Added extraction receipts and review reports for supported completed jobs.
- Improved privacy in saved settings, logs and support bundles.
- Smaller app downloads use a separately installed Ollama model for offline processing.
- Fixed errors affecting offline setup and completion sounds.
- Repaired documentation links and screen-reader navigation in public pages.

## [1.0.7] - 2026-04-27

- Added a Modern Newspapers / E-Papers preset, separate from Historical Newspapers.
- Clarified preset names for personal diaries and military records.
- Improved abbreviation expansion for military records, newspapers and medical documents.
- Improved reading of scanned PDFs and dense historical newspapers.
- Reduced stalls when saving large documents. If saving certain output formats fails, Chronicle can preserve completed text in a recovery file.

## [1.0.2] - 2026-04-11

- Added a Comics / Manga / Graphic Novels preset with panel order, dialogue, captions, sound effects and optional scene descriptions.
- Added a public-domain Little Nemo example.
- Improved recovery of completed work after an interruption during saving.
- Removed more repeated headings, broken image placeholders and unwanted formatting from magazine output.
- Made final-save progress easier to diagnose from the processing log.

## [1.0.0] - 2026-04-06

- First standalone desktop app release for Mac and Windows.
- Added document presets, page selection, a First 5 Pages trial, scheduling and queue controls.
- Added checks before reading, processing logs, support bundles and output comparison tools.
- Added options for printed page references, abbreviation expansion and modern equivalents for older units.
- Improved reading of books, forms, office documents, government records, medical notes and newspapers.
- Improved headings, lists and tables in HTML and Word output.
- Improved progress reporting for Word documents and other files without fixed pages.
- Added recovery files for interrupted work and stronger protection against losing completed output during saving.
- Moved saved settings and API keys to the user's application-data storage, with system keychain support where available.
- Improved provider selection when a key is missing and added a manual engine choice in Preferences.
- Improved PDF processing on Windows and reduced memory use during long runs.
- Added a warning before quitting with unfinished work on Mac.

## Earlier project history

These entries describe the original project before the standalone desktop release. Old setup and updater scripts mentioned in that history are not installation instructions for the current app.

### [1.8.3] - 2026-03-09

- Added page and slide selection, including First 5, Odd, Even and Last 10 shortcuts.
- Added choices to keep, expand or replace abbreviations and older units.
- Improved queue summaries, book endings and recovery from unreadable PDF pages.
- Improved protection of locally saved API keys.

### [1.8.2] - 2026-03-08

- Made next-run settings and engine selection clearer.
- Improved punctuation spacing, HTML structure and PDF saving.
- Expanded testing across different public document types.

### [1.8.1] - 2026-03-07

- Added scheduled runs and improved merging of page images in order.
- Added academic footnote options, optional confidence notes and PDF completeness checks.
- Improved handling of busy providers and removed unwanted formatting from text and Word output.

### [1.8.0] - 2026-03-02

- Added setup helpers and published accessibility guidance.
- Improved headings, tables, language information, equations and academic notes.
- Improved handling of unclear text in damaged documents.

### [1.7.0] - 2026-03-01

- Added temporary working files and recovery support for interrupted processing.
- Improved saving of merged documents and skipping of already completed files.

### [1.6.0] - 2026-02-28

- Added update and dependency setup helpers for the original script-based project.
- Kept user documents and saved keys separate from updated program files.

### [1.5.0] - 2026-02-28

- Added EPUB e-books, JSON and CSV output.
- Improved legal document structure, merged output and accessible tables.
- Added a war-diary example.

### [1.4.0] - 2026-02-28

- Added Excel workbook reading and more accessible table output.
- Rewrote installation guidance for people without programming experience.

### [1.3.2] - 2026-02-28

- Added TIFF image support and restored provider privacy guidance.
- Fixed a launch error.

### [1.3.0] - 2026-02-27

- Added an option to omit confidence and condition notes for uninterrupted reading.
- Improved merging of multipage documents.

### [1.2.1] - 2026-02-27

- Restored document processing and preferences after an earlier regression.
- Updated Gemini support to resolve provider errors.

### [1.2.0] - 2026-02-27

- Updated the Gemini connection and improved file uploads.

### Other March 2026 improvements

- Reduced Windows PDF failures caused by temporary-file permissions.
- Improved headings and removal of broken image text in historical records.
