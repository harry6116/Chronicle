Chronicle 1.0.7

- The document preset picker is clearer and less ambiguous: `Newspapers` is now `Historical Newspapers`, and `Handwritten Letters / Notes / Diaries` is now `Handwritten Notes / Personal Diaries`.
- Added a new `Modern Newspapers / E-Papers` preset for contemporary newspaper PDFs, e-paper pages, article cards, bylines, timestamps, section labels, captions, advertisements, sponsored content, jump lines, and digital publication furniture.
- War diaries and unit logs are now explicitly guided toward `Military Records`; personal handwritten diaries remain under the handwriting preset.
- Historical newspaper behavior remains attached to the existing historical newspaper path, including dense scan handling, NLA/Trove-style OCR safeguards, old newsprint recovery, and archive-oriented publication metadata recovery.
- Modern newspaper handling avoids historical OCR/newsprint assumptions and keeps contemporary news structure distinct from `Magazines / Periodicals`, which remains focused on feature-led magazine layouts, reviews, interviews, sidebars, pull quotes, and contents-page furniture.
- Gemini remains the primary transport path for Gemini processing. Chronicle still uploads PDFs to Gemini by default; rendered image transport is reserved for narrow scanned/image-only cases where direct PDF upload is unreliable or under-reads.
- Image-only scanned military/archive-style PDFs on Gemini Pro now render a visible `chronicle_temp_...png` beside the source while active, send that rendered page to Gemini as an image, and remove the temp file after completion.
- The war diary completion bug is fixed: Chronicle no longer accepts a tiny title-only Gemini PDF response as a valid full extraction for image-only scanned pages.
- OCR-backed dense NLA newspaper PDFs continue to use their embedded local OCR layer immediately, avoiding the previous first-page hang and final-save stalls on dense newspaper runs.
- Release documentation has been cleaned so public-facing notes do not expose maintainer-only build trees, machine paths, or internal rollout directories.
