Chronicle 1.0.8

May 14 NLA newspaper quality rescue update:

- Chronicle now attempts article-level Trove/NLA OCR rescue for historical newspaper PDFs that expose `nla.news-page` identifiers. When available, this uses Trove's article zones and OCR renditions before falling back to the visual image-strip path, which greatly improves dense NLA pages that otherwise produce chopped strip fragments.
- The existing dense NLA local-OCR fast path now updates page progress correctly after emitting a rescued page, so the UI does not appear stuck after a non-model rescue completes.
- A representative dense NLA newspaper output was rebuilt as a hybrid best-output file: the cleaner Chronicle visual page 1 is retained, and pages 2-4 use Trove article-order OCR. The current output has all four page headings, 49 article sections, no `Source page`/`strip`/provider/internal label leakage, and a much stronger page 4 honor-roll/article reconstruction.
- Regression coverage now includes the Trove article-OCR rescue, offline fallback to image strips, and the dense NLA local-OCR progress update. Focused output/PDF/log suites passed (`207` tests, `OK`) plus compile checks for the touched files, and the Mac app bundle was rebuilt with build stamp `2026-05-14 11:06:42`.

May 14 output-label and scan-log clarity update:

- Chronicle now strips internal processing labels from final outputs across every document preset, including dense newspaper markers, source-page strip labels, provider/routing status tags, progress-state headers, and Chronicle-specific audit note wording.
- Dense newspaper HTML output now writes clean reader-facing page headings only. The completed validation scan was cleaned so no `Source page`, `strip/stripe`, provider tag, or Chronicle-internal class label remains in the saved HTML.
- Safety and handwriting audit notices now use generic reader-facing `Note` / `Audit flag` wording and a neutral `audit-note` class instead of Chronicle-branded labels.
- Live scan logs are now formatted for users while scans are happening: dense newspaper tile work reads as “Scanning page N, part X of Y,” recovery/status prefixes are relabeled in plain language, and the log panel is labeled as a readable processing log rather than raw engine output.
- Regression coverage now checks the output-label scrubber across every preset, verifies dense newspaper output does not emit source strip labels, and covers the scan-log formatter. Focused output/PDF/log suites passed (`206` tests, `OK`) plus compile checks for the touched files, and the Mac app bundle was rebuilt with build stamp `2026-05-14 10:53:43`.

May 14 CPU stability update:

- Chronicle no longer hard-exits the GUI when a model stream goes quiet. Silent API streams now log a network-stall alert and keep the app open for recovery, while the bounded stream reader can still time out normally and leave readable recovery evidence.
- Fixed a live historical-newspaper CPU hang where the app could pin a full CPU core inside Python's regex engine before page 1 produced any output. The repeated-paragraph cleanup pass now uses a bounded token walk instead of a high-risk backreference regex over OCR-heavy HTML.
- Stale run recovery was cleaned after the live hang investigation: empty newspaper `.tmp`/`.progress.txt.tmp` sidecars and the stale active-session file were removed so the next launch starts cleanly.
- Focused CPU-hang verification passed with the output-regression and PDF-processor suites (`193` tests, `OK`) plus compile checks for the touched files, and the Mac app bundle was rebuilt with build stamp `2026-05-14 10:21:13`.

- PDF extraction now enforces Chronicle's model-first contract: documents use Gemini by default, and deep-scan profiles such as historical newspapers, legal material, military records, academic scans, archival/handwritten material, medical records, intelligence files, magazines, modern newspapers, and comics stay on Gemini 2.5 Pro under automatic routing.
- Embedded PDF text layers are no longer used as a silent fast path for normal extraction. Local/raw text-layer recovery is now treated as an explicit emergency fallback, not a substitute for Gemini scanning.
- Preferences now includes an off-by-default emergency PDF text-layer fallback control. When it stays off, provider/model failures fail loudly instead of silently returning raw embedded PDF text.
- Dense NLA newspaper PDFs no longer complete instantly from embedded OCR during normal launches. They route through Gemini Pro image/PDF processing unless the internal/user emergency fallback is deliberately enabled.
- Benchmark validation was rerun against the local Chronicle Benchmark Pack after the routing fix. The routing audit covered all 35 benchmark cases with zero Gemini/default-engine violations; the live benchmark pass produced model-based outputs or loud provider/time-out failures rather than silent raw-text output.
- Chronicle now accepts a broader set of user files: HTML/HTM, JSON, JSONL, XML, TSV, LOG, EML, GIF, AVIF, HEIC, HEIF, JP2, J2K, PPM, PGM, PBM, SVG, XPS, OXPS, CBZ, MOBI, and FB2.
- HEIC/HEIF support now uses the bundled `pillow-heif` runtime for cross-platform scanning, with the existing macOS conversion path retained as a fallback.
- New image-style formats are staged through temporary PNG conversion before visual scanning, so the model upload path stays consistent on both Mac and Windows.
- SVG, XPS/OXPS, and CBZ files are rendered page-by-page through PyMuPDF before Chronicle scans them visually.
- HTML/HTM, JSON/JSONL, XML, TSV, LOG, EML, MOBI, and FB2 use direct source-text extraction where possible, reducing unnecessary OCR-style drift on already-readable files.
- Online fixture testing passed against public samples from Example.com, JSONPlaceholder, W3Schools, Hugging Face, SampleFile, Wikimedia Commons, libheif, Pillow's image corpus, GitHub gist/raw sources, and the `sample_reading_media` archive.
- Public-source validation covered text extraction, temporary PNG staging, and rendered-document scanning for HEIC, AVIF, JP2, J2K, GIF, PPM, PGM, PBM, SVG, CBZ, HTML, JSON, JSONL, XML, TSV, LOG, EML, MOBI, and FB2. XPS/OXPS routing is covered by regression tests; a reliable direct public fixture was not found during this pass.
- The primary Chronicle regression suite passed (`498` tests), focused Beta and Windows Beta extension suites passed (`36` tests each), and the Mac app bundle was rebuilt with build stamp `2026-05-08 13:04:25`.
