# Chronicle 1.1.1

Chronicle 1.1.1 improves PDF extraction reliability, accessibility, security, and packaging. This release also keeps Private Offline Mode available for clean sensitive documents through a user-managed local Ollama setup.

Private Offline Mode no longer ships as a large Chronicle-hosted offline pack. Release packaging now creates and publishes only the Mac and Windows app downloads, while Chronicle guides users to install Ollama locally and run `ollama pull qwen2.5vl:7b` when they want offline processing.

The Mac and Windows app build scripts still block accidental embedded offline model/runtime payloads, keeping release downloads slim and making app-only updates much easier to package and publish.

The release publisher now also detects app ZIPs that exceed GitHub release asset size limits before upload, so release notes can still be updated while oversized app delivery is moved to an appropriate hosting path.

The local offline backend is stopped after each offline extraction so model memory is released promptly after use.

The File menu has also been simplified by removing the dormant license-import action while license work remains paused. Scanner capture options have been held back from this release because flatbed and multifunction printer/scanner support needs broader device, driver, and operating-system testing before it should be exposed to users.

## Highlights

- Private Offline Mode is now a visible selectable processing mode for sensitive documents that should stay on the user's computer.
- Chronicle now uses the user's local Ollama installation for Private Offline Mode.
- The File menu includes local Ollama setup guidance and the required `ollama pull qwen2.5vl:7b` command.
- Mac and Windows app builds no longer support embedding the Private Offline Mode model/runtime payload.
- Mac and Windows app downloads are scrubbed of accidental embedded offline resources during release packaging.
- Release packaging now keeps the app ZIPs slim and does not create or upload a separate offline pack.
- Release publishing now reports GitHub asset-size limit issues before attempting a release upload.
- Windows build staging no longer requires offline model/runtime files.
- The API key setup flow now explains that if no API keys are entered, Chronicle will still open, but only Private Offline Mode will be available.
- The offline model path targets a compact local vision-language pack instead of a very large 20 GB-class model bundle.
- Private Offline Mode remains intended for clean PDFs and simple sensitive documents, not difficult handwriting, historical newspapers, comics, magazines, or visually complex scans.
- The File menu no longer exposes the paused license-import workflow.
- Flatbed scanner capture is being deferred to a later release so it can receive proper hardware and driver validation.
- More reliable page boundaries for PDF extraction across HTML, EPUB, TXT, Markdown, DOCX, and PDF outputs.
- One source page is now processed per model request for PDF workflows, improving isolation and recovery when difficult pages fail.
- Better accessible HTML output, including stable page anchors, page navigation links, skip links, document landmarks, and improved focus styling.
- Image notes are normalized into clearer image descriptions where appropriate.
- Long manuals and diagram-heavy PDFs now use smaller PDF slices so individual pages are easier to process.
- Security hardening keeps API keys out of subprocess command arguments.
- The macOS app package has been refreshed and verified for release distribution.

## Private Offline Mode

Chronicle now includes a visible processing-mode selector so users can choose between normal online AI processing and Private Offline Mode. Offline mode is designed for sensitive document categories such as bank statements, medical forms, legal paperwork, invoices, receipts, tax records, tables, and identity-like documents.

The app now states this boundary more clearly in the processing-mode guidance: Private Offline Mode is best for clean, text-based PDFs and simple sensitive documents. Users should choose Online AI Mode for complex documents with handwriting, dense images, comics, magazines, historical newspapers, or layout-heavy scans.

The offline path uses a separate local prompt and local model runtime so offline behavior remains isolated from online Gemini, Claude, and GPT workflows. It also includes safeguards against model reasoning or prompt instructions appearing in saved output.

After an offline extraction completes, Chronicle stops its bundled local backend process so the local model is not kept resident in memory between jobs.

Current offline testing favors `qwen2.5vl:7b` as the local vision-language model users should install through Ollama. Accuracy remains under active validation and should be treated as a secure offline option for clean sensitive PDFs, not a replacement for top-tier online extraction on the hardest scans.

Additional local candidates were also checked during this round. A 12B Gemma vision model completed the private-document acceptance set, but it did not improve the overall grade and was substantially slower while increasing the model footprint. An 11B Llama vision candidate was rejected for this package because it failed to load reliably in the local Ollama runtime path. A similarly sized Qwen 3-VL 8B candidate was also tested; it was much slower under Chronicle's current local runtime contract and did not produce reliable final document content at the normal output budget. For this release, Qwen 2.5-VL 7B remains the best balance of included size, speed, and emergency offline usability.

Private Offline Mode includes an accessibility-first prompt contract and output guardrails. Offline HTML outputs are expected to preserve logical reading order, use semantic headings, paragraphs, lists, and tables where helpful, and avoid visual-only structure. If the local model echoes prompt instructions, returns unusable output for a text-backed PDF, invents remote image sources, or emits interactive form controls for a scanned document, Chronicle cleans or replaces that output before saving. Blank-form controls are represented as readable text markers such as checkbox, radio button, and text-field states rather than inaccessible pseudo-web forms.

Chronicle keeps offline requests conservative for broad hardware support: one parallel offline request at a time and small PDF page batches instead of one huge local model request. Temporary rendered PDF page images are cleaned after the offline request completes.

## PDF Reliability

Chronicle no longer depends on the model to preserve every page heading in PDF workflows. If a single-page extraction path returns content without a visible page boundary, Chronicle inserts the correct source-page boundary before writing the output.

HTML and EPUB outputs receive semantic page headings, while text-like outputs receive plain page markers. This makes page transitions visible across output formats and helps prevent later page content from being folded into an earlier page.

PDF processing now uses one source page per model request across profiles, models, and document sizes. This can increase the number of provider requests for long PDFs, but each request is smaller and failures are isolated to one source page.

## Accessibility

Generated HTML now includes accessible page jump links for multi-page extractions. Chronicle assigns stable anchors such as `#page-1` and `#page-2` to page headings and adds a labelled page-navigation landmark near the top of the document.

The page-link option is enabled by default and remains available in the main run controls as `Page Links` and in Preferences as `Page Navigation Links`. When page links are disabled, Chronicle preserves `Page N` headings without injecting page-navigation landmarks, anchors, or Table of Contents links to page headings.

This release also strengthens generated HTML contrast checks and keeps meaningful image descriptions available across document families, including books, tabular material, transcripts, poetry, manuals, and newspaper-style scans.

Private Offline Mode follows the same accessibility direction: generated offline HTML is wrapped with a document landmark and heading, and local fallback output avoids image-only structure, empty list items, and layout-only formatting.

Offline document outputs now also remove generated interactive form markup from saved document HTML. This keeps private-document output closer to an accessible transcription that can be reviewed with assistive technology, rather than a partially functional form surface.

## Online Provider Runtime

Chronicle now centralizes online-provider runtime settings so the app and streaming model code use the same bounded behavior. Power users and packaged test runs can tune provider pacing with these environment variables:

- `CHRONICLE_API_MIN_REQUEST_INTERVAL_SEC`
- `CHRONICLE_API_BACKOFF_BASE_SEC`
- `CHRONICLE_API_BACKOFF_MAX_SEC`
- `CHRONICLE_API_MAX_RETRIES`
- `CHRONICLE_API_MAX_CONCURRENT_REQUESTS`
- `CHRONICLE_API_MAX_PENDING_REQUESTS`
- `CHRONICLE_API_REQUEST_QUEUE_POLL_SEC`
- `CHRONICLE_API_CACHE_MAX_ENTRIES`
- `CHRONICLE_STREAM_CHUNK_TIMEOUT_SEC`
- `CHRONICLE_GEMINI_GENERATE_TIMEOUT_MS`

Overrides are bounded and invalid values are ignored, so a bad environment setting cannot remove Chronicle's provider-pressure guardrails. Defaults are unchanged for normal users.

## Security

Gemini REST fallback requests now keep API keys in request headers instead of command-line arguments. Chronicle also includes stronger checks against unsafe subprocess usage, accidental token exposure in subprocess calls, dynamic execution in runtime code, and unexpected widening of the Gemini fallback endpoint.

## Maintainability

Chronicle's core extraction, cleanup, handwriting/form handling, page-boundary handling, PDF rendering, HTML navigation, and newspaper processing code has been reorganized for clearer ownership while preserving existing user-facing behavior.

The legacy interactive command-line runner has been retired. Chronicle's shared runtime support remains available for supported app workflows and validation tools.

## Validation

This release was validated with focused coverage for PDF processing, page boundaries, HTML accessibility, output cleanup, newspaper-style scans, handwriting/forms, runtime policy, security checks, worker finalization, exporting, syntax checks, offline runtime checks, and macOS app packaging.

Private Offline Mode validation included live local-runtime scans against sensitive-document-style benchmark PDFs, including government-form, legal, medical-claim, blank-medical-form, and private text examples. The final Qwen 2.5-VL 7B full offline benchmark suite averaged 99.43 across 13 cases, with 12/13 cases emergency-usable and 11/13 in the private A range. The blank medical form cleanup produced A+ accessible HTML with no generated form controls, and the modern typed PDF cases reached 4/4 A+ across legal/financial regulation, academic article, product manual, and operation-manual pages. The CMS-1500 run produced semantic HTML with no prompt leakage, no reasoning leakage, no empty list items, and no leftover local model processes.

Free Gemini API keys remain useful for testing, but they may not be dependable for sustained hard-PDF work such as long manuals, magazines, newspapers, comics, graphic novels, and reruns. For demanding batches, use a paid or higher-quota provider key where possible.
