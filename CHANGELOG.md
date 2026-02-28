# Changelog

All notable changes to the Chronicle Document Extractor will be documented in this file.

## [1.5.0] - 2026-02-28
### Added
- **New Export Formats:** Added native support for exporting to EPUB (`.epub`), JSON (`.json`), and CSV (`.csv`). 
- **EPUB Engine:** Integrated `EbookLib` to generate native, accessible eBooks directly from raw document scans, perfect for compiling large historical diaries.
- **JSON & CSV Engines:** Created structured data pipelines allowing Chronicle to be seamlessly integrated into enterprise APIs, legal databases, and financial spreadsheets.
- **Legal & Statutory Directives:** Added explicit AI prompt rules to recognize and meticulously preserve the strict hierarchy of legal documents (Parts, Divisions, Sections, Subsections) and defined terms.
- **Accessibility Showcase:** Added a new `assets/samples/war_diary_showcase/` directory containing an accessible HTML "Before and After" comparison using highly degraded WWI War Diaries.
### Changed
- **Menu System UI:** Expanded the terminal menu system to accommodate 8 distinct output formats.
- **Merge Mode Logic:** Updated the `merge_files` function to natively handle the invisible stitching of EPUB chapters and the concatenation of JSON data arrays.
- **PDF Engine Upgrade:** Transitioned the PDF generation backend from the legacy `fpdf` to `fpdf2`, utilizing `latin-1` encoding replacement to completely resolve crashes caused by obscure historical symbols.
- **Git Automation:** Updated the `Push_to_GitHub.command` script to use `git add -A` for flawless handling of deleted and moved files.
### Fixed
- **Memory Buffer Overloads:** Resolved a terminal issue where pushing large batches of images to GitHub failed by permanently increasing the `http.postBuffer` limit.
- **HTML Table Semantics:** Fixed an issue where parsed historical rosters were flattening into raw text; enforced strict `<th>` and `<td>` scoping for VoiceOver compatibility.

## [1.4.0] - 2026-02-28
### Added
- **Excel Support (.xlsx):** Implemented the `openpyxl` library to natively support multi-page Excel workbooks.
- **Spreadsheet Flattening:** Added a new dynamic prompt rule to transform raw, spatial tabular data into highly readable, linear text summaries and data tables specifically designed for screen readers.
### Changed
- **Installation Documentation:** Major overhaul of the README to assist non-developers. Added explicit instructions for downloading via ZIP, installing Python (including the Windows PATH trap and Mac Homebrew option), and a critical warning to re-run setup scripts after every version update.

## [1.3.2] - 2026-02-28
### Added
- **TIF Support:** Explicitly added `.tif` to the supported extensions list and routing logic to ensure comprehensive batch scanning for older scanner file outputs.
- **API Privacy Documentation:** Restored the API tier pricing and data privacy breakdown to the README for users handling sensitive historical archives.
### Fixed
- **Syntax Error:** Removed a stray character in the extensions list that prevented the script from launching.

## [1.3.0] - 2026-02-27
### Added
- **Menu 10 (Technical Appendix):** Added a dedicated toggle to completely disable all transcription confidence scores, dates, and condition profiles from the output.
### Changed
- **True Seamless Merge:** When processing multi-page documents (like continuous letters), removing the technical appendix now creates a 100% seamless reading experience. The script invisibly stitches the text together without announcing file names or page breaks.

## [1.2.1] - 2026-02-27
### Fixed
- **Engine Restoration:** Restored full processing logic, including PDF chunking, recursive batch scanning, and the complete preference menu system.
- **Model Upgrade:** Fixed API 404 crashes by updating targets to Google's newest `gemini-2.5-pro` and `gemini-2.5-flash` models.

## [1.2.0] - 2026-02-27
### Changed
- **Modernized AI Engine:** Migrated from the deprecated `google.generativeai` library to the official `google-genai` SDK to ensure stability and eliminate terminal warnings.
- **Optimized File Processing:** Replaced legacy base64 encoding with the native `client.files.upload()` API. This streamlines the codebase and significantly improves upload speeds for large archival PDFs and image batches.