# Why Chronicle

Chronicle is built for hard documents.

It is designed for the files people usually describe with phrases like:

- "the scan is awful"
- "the pages are out of order"
- "the OCR is almost right but keeps breaking the prose"
- "I need this to be readable, reviewable, and traceable back to the source"

## What Chronicle Is Best At

Chronicle is strongest when the source is difficult, messy, or inconsistent:

- degraded scans
- long-form books and memoirs
- archival records and historical documents
- newspapers and multi-column layouts
- forms, reports, and mixed-format batches
- material that needs accessibility-aware restructuring, not just plain OCR dumping

Chronicle is designed to reduce manual cleanup and help users reach review-ready output faster, while still assuming human review before anything is treated as final.

## Why People Use Chronicle

### 1. It is built for difficult recovery work

Chronicle is not just trying to "get text out." It is trying to recover a usable reading experience from hard real-world material while preserving fidelity to the source.

That includes:

- paragraph continuity across bad scan wrapping
- suppression of repeated page furniture when it harms reading flow
- optional preservation of printed page references when transcription or source tracking matters
- structured outputs that are easier to review in HTML or Word
- specialist prompt rules for books, archives, newspapers, legal material, military records, forms, and other difficult source classes

### 2. It gives the operator control

Chronicle is designed for users who need to inspect, adjust, and rerun difficult material instead of hoping a single blind pass gets everything right.

Key strengths include:

- document-specific presets
- queue-first workflow
- seamless merge for many-page or many-image sources
- runtime controls for punctuation, abbreviations, units, image descriptions, and page-reference handling
- automatic engine routing with manual override when needed
- visible progress and readable logs
- explicit collision controls so users can skip, overwrite, or auto-number outputs instead of losing work blindly

### 3. It is built around accessibility from the start

Chronicle is meant to produce outputs that are easier to navigate and review with assistive technology, not merely extract raw text.

That includes:

- semantic HTML and structured Word-oriented output
- clearer headings, lists, and tables where faithful reconstruction is possible
- screen-reader-conscious reading order
- options that balance reading flow against transcription/reference needs

### 4. It works well for iterative review workflows

Chronicle is especially useful when the job is:

1. run a difficult source
2. inspect the output
3. adjust the preset or settings
4. rerun with better expectations

Chronicle's default behavior is not "always use the biggest model." Clean born-digital PDFs in easier profiles can start on the faster engine first, while hard pages and structurally risky PDFs still stay on, or escalate to, the deeper engine.

This makes it a strong fit for:

- archivists
- accessibility reviewers
- transcription-heavy projects
- users working through large difficult books or scan batches

## What Users Should Expect

Chronicle prioritizes quality, fidelity, and navigable structure over raw speed on difficult material.

- clean files may process quickly
- difficult books, newspapers, and degraded PDFs may take substantially longer
- the extra time is often spent preserving reading order, paragraph continuity, and usable structure rather than simply dumping raw OCR-like output

If the document is easy, many tools can do a reasonable job.

Chronicle is most valuable when the document is hard.

## Short Version

Chronicle is for people who need better results on ugly documents, not just faster results on easy ones.

It is designed to reduce manual cleanup, not eliminate human verification.

For reusable short-form messaging and longer public-facing summaries, see:

- [CHRONICLE_BLURBS.md](CHRONICLE_BLURBS.md)
- [CHRONICLE_ONE_PAGE.md](CHRONICLE_ONE_PAGE.md)
