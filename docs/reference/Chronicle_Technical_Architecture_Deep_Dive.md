# Chronicle Technical Architecture & Inner Workings

This document provides a minute, comprehensive breakdown of Chronicle's underlying systems, artificial intelligence protocols, and fail-safe mechanisms. It is designed for users who require a deep understanding of how the extraction engine processes data, enforces accessibility, and interacts with local hardware.

> Development note: Chronicle was built using AI-assisted ("vibe-coded") workflows, with final integration, review, and testing directed by the author.

## 1. The Artificial Intelligence Engine
Chronicle operates as a localized bridge to cloud AI providers. The application does not run a local Large Language Model (LLM); it securely transmits files to supported APIs for processing.

Current provider support in GUI:
* Google Gemini
* Anthropic Claude
* OpenAI GPT

Default model guidance:
* **Gemini 2.5 Flash:** fast, lower-cost high-volume extraction.
* **Gemini 2.5 Pro:** higher-fidelity extraction for degraded or complex archives.
* **Claude 3.5 Sonnet / GPT-4o:** supported alternatives for specific instruction-following and multimodal scenarios.

## 2. Stateless Processing & Data Privacy
Chronicle is engineered with a strict "Stateless" architecture.
* **No Local Content Database:** The application does not use a local database for extracted document body text and does not keep prior extraction content as reusable memory.
* **Session Recovery Metadata:** Chronicle does persist lightweight local run state (queue rows, statuses, and resumable progress metadata) so interrupted extractions can be resumed safely.
* **Provider Data Policies:** Files are processed by the selected cloud provider. Retention/training behavior is controlled by your provider account tier/settings and terms, not by Chronicle.

## 3. Atomic Saving & Smart Skip Batching
To protect against system crashes, power failures, or API timeouts during massive archival scans, Chronicle utilizes an Atomic Saving protocol.
* **The `.tmp` Protocol:** When a document is actively being processed, the text is streamed directly to your hard drive into a temporary file (e.g., `document.html.tmp`). The file is only renamed to its final extension upon 100% successful generation. 
* **Crash Resilience:** If your computer loses power halfway through processing a 500-page archive, no files are corrupted.
* **Smart Skip Batching:** When you restart a batch extraction after a crash, Chronicle scans the output directory. It will automatically skip any documents that have fully completed files, immediately resuming the extraction exactly where the failure occurred.
* ## 4. Archival Fidelity & Anti-Hallucination Directives
Generative AI models are prone to hallucination (guessing missing words) when faced with illegible text. Chronicle hardcodes strict algorithmic and behavioral directives to prevent this and preserve archival integrity.
* **Algorithmic Lanczos Resampling:** Before an image is sent to the AI, Chronicle intercepts it using the `opencv-python` library. It algorithmically doubles the resolution using Lanczos4 interpolation and converts it to grayscale. This allows the engine to extract microscopic text from degraded microfilm or projector slides without destroying the original file.
* **The Zero-Guessing Policy:** The AI is strictly prompted to never hallucinate. If a section of a document is physically destroyed (e.g., by water damage or torn edges) and the text cannot be resolved even after resampling, the engine is forced to output a standardized marker: `[Illegible Micro-text: approximately X words]`.
* **No-Spelling-Correction Policy:** Chronicle is hardcoded to preserve original spelling and OCR artifacts exactly. It never "fixes" typos or historical spelling variants.
* **Modern Punctuation Safety:** When modern punctuation mode is enabled, only punctuation/spacing normalization is allowed. Wording, spelling, names, dates, and numeric tokens must remain unchanged. The hardcoded post-processing layer also preserves a single space after cleaned `.-` and `,-` sequences when a word follows, preventing layout-driven word collisions.
* **Strikethrough Recovery:** The engine is specifically trained to read and preserve crossed-out historical text, outputting it as `[Struck through: text]` rather than ignoring it.

## 5. WCAG 2.2 Semantic Enforcement
Unlike standard AI wrappers that output flat text or unformatted Markdown, Chronicle programmatically forces the AI to structure its output using strict HTML5 semantics.
* **Heading Hierarchies:** The engine maps document structures to `<h1>`, `<h2>`, and `<h3>` tags. It is forbidden from using visual formatting (like bold text) to simulate structural meaning.
* **Table Scoping:** All extracted tabular data (e.g., historical census forms) is formatted with strict `<th>`, `scope="col"`, and `scope="row"` associations, guaranteeing that screen readers announce the correct column and row headers as a user navigates individual cells.
* **Image Nullification:** If the user toggles visual descriptions off, the engine generates null attributes (`alt=""`) on any HTML `<img>` tags to completely hide the visual elements from assistive technologies, preventing screen reader clutter.
* ## 6. The Academic Engine
When toggled on, the Academic Engine fundamentally alters how Chronicle handles complex document layouts.
* **Mathematical & Chemical Reconstruction:** Visual formulas and equations are parsed and reconstructed into strict LaTeX-oriented structure for accessible review.
* **Configurable Footnote Strategy:** Academic mode supports user-selectable footnote handling (endnotes, inline, or strict original placement).
* **Multi-Column Flattening:** Dense, newspaper-style multi-column layouts are strictly flattened into continuous, vertical narrative sequences.
* **Configurable Annotation Strategy:** Academic mode supports inline, endnotes, or strict verbatim annotation preservation.

## 7. Dynamic Language & Cultural Preservation
Chronicle features dynamic ISO language code detection to ensure assistive technologies correctly voice foreign or indigenous text.
* **Inline Span Tags:** When processing bilingual documents, the engine utilizes strict language span tags (e.g., `<span lang="mi">` for te reo Māori or `<span lang="fr">` for French). 
* **Pronunciation Profiles:** This forces Apple VoiceOver, NVDA, and JAWS to dynamically switch their internal pronunciation dictionaries mid-sentence, ensuring critical diacritical marks (like macrons or accents) are voiced accurately.
* **Ancient Scripts:** The engine is capable of extracting ancient scripts (e.g., Egyptian Hieroglyphs, Sanskrit) and providing the original Unicode characters alongside structured English transliterations.

## 8. Additional Reliability Layers
Recent reliability improvements include:
* **PDF text-layer omission audit:** optional post-pass coverage check that can append recovered lines or a safety appendix when mismatch is detected.
* **Page confidence scoring (optional):** per-page confidence output (score out of 10) with method/condition notes.
* **Seamless merge sequencing:** merge mode can lock page-order patterns (for example `page 01`, `page 02`) and strip synthetic filename headings from merged output.
* **Run-engine binding integrity (GUI):** engine selection now updates queued/paused rows when idle, and Start Extraction enforces selected engine across queued rows for that run.
* **HTML wrapper normalization:** post-stream save finalization now strips nested document wrappers accidentally emitted by model output (`<!DOCTYPE html>`, `<html>`, `<head>`, `<body>` blocks inside body content).
* **PDF fallback hardening:** if HTML-to-PDF rendering fails, Chronicle now creates a fresh fallback PDF object for plain-text write, preventing fallback-path state errors.

## 9. Session Validation Note (2026-03-08)

To verify these fixes under live provider conditions, an internet corpus benchmark harness was run across all supported output formats (`html`, `txt`, `docx`, `md`, `pdf`, `json`, `csv`, `epub`) using `gemini-2.5-pro`.

Validation artifacts:
* `tools/web_corpus_benchmark.py`
* `benchmark_web_report.json`
* `benchmark_web_summary.md`

Important scope clarification:
* Benchmark harness truncation controls (PDF subset pages / large text trims) are test-runtime controls only.
* Production GUI extraction pipelines were not changed to truncate user documents.
