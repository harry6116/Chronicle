# Why Chronicle

Chronicle is built for hard documents.

## Why I Built It

Chronicle began with family history.

I wanted to read and understand the First World War diaries of the Manchester Regiment, where my great-grandfather, Albert Henry Wharton, served after lying about his age to join the British Army at just 15 years old.

I was not trying to run a generic OCR experiment. I was trying to follow a real boy into a real war and understand, as faithfully as I could, what he may have seen and endured.

Conventional OCR was hopeless on those diaries. The text came back jumbled, out of order, and so badly broken that I could not trust it enough to track movements or reconstruct events with any confidence. I tried different tools, different passes, and the same disappointment kept coming back.

Even when I asked other people to help read some of the war material to me, the problem did not go away. Certain pages were so faded and difficult that even sighted people I asked to help could not read them with confidence. That mattered to me. It meant this was not just a matter of software performing badly; it was an access problem as well.

The same thing happened with old newspapers, especially material from the Australian Trove archive. I found an article mentioning my great-grandmother on my father's side and wanted simply to read it properly. Once again, standard OCR returned something fragmented, confused, and unreliable.

Then I started seeing the same pattern everywhere else: product manuals, historical records, mixed layouts, specialist documents, difficult scans, things that were technically readable in theory but not genuinely usable in practice.

That is why I built Chronicle.

Late one night, with modern AI tools finally becoming practical enough to experiment with, I decided to try to build the system I wished I had when I started. I did not want a tool that merely "got text out." I wanted something that could recover reading order, structure, meaning, and source fidelity well enough that a difficult document could become readable again.

That became a much larger piece of work than I first imagined.

Large language models hallucinate. Historical material is often damaged, irregular, and chaotic. Newspapers, war diaries, legal files, medical pages, intelligence records, manuals with diagrams, handwritten letters, flyers, legislation, and mixed-format scans all break in different ways. A prompt rule that helps one category can damage another.

So Chronicle became a long exercise in patient iteration: running thousands upon thousands of pages of public-domain material through AI models, spending what little money I could spare on testing, tuning prompts in exacting detail, and fixing one problem after another as it revealed itself.

One of the central goals was teaching the system not to overconfidently "improve" the source. Older documents often contain unusual spelling, degraded print, offensive historical language, uncertain wording, or damaged passages. I wanted Chronicle to stay as verbatim as possible, not silently correct, modernize, sanitize, or smooth over what was actually on the page.

Every major document family needed its own careful handling. Accessibility also mattered from the beginning, not as an afterthought. The aim was not only extraction, but output that could be reviewed, navigated, and used more easily under modern accessibility expectations.

Chronicle is still a work in progress, and I expect it always will be. This kind of work is never really finished. The goal is not one dramatic leap to perfection. The goal is to keep improving, keep testing, and keep building a tool that can do justice to difficult documents that other systems flatten, scramble, or abandon.

It is designed for the files people usually describe with phrases like:

- "the scan is awful"
- "the pages are out of order"
- "the OCR is almost right but keeps breaking the prose"
- "I need this to be readable, reviewable, and traceable back to the source"

## What Chronicle Is Best At

Chronicle is strongest when the source is difficult, messy, or inconsistent:

- degraded scans
- long-form books and memoirs
- comics, manga, graphic novels, and comic strips
- archival records and historical documents
- newspapers and multi-column layouts
- forms, reports, and mixed-format batches
- material that needs accessibility-aware restructuring, not just plain OCR dumping

Chronicle is designed to reduce manual cleanup and help users reach review-ready output faster, while still assuming human review before anything is treated as final.

## Preset Overview

Chronicle does not treat every document as the same problem. Different source classes break in different ways, so the app includes document presets that steer recovery behavior toward the needs of that material.

Some of the main preset families include:

- `Miscellaneous / Mixed Files` for general-purpose starting points when the document type is unclear
- `Letters / Correspondence` for typed or scanned letters, notices, and other communication-heavy pages
- `Government Reports / Records` for public-sector reports, appendices, numbered sections, and record-style documents
- `Legal / Contracts / Laws` for legal hierarchy, clause fidelity, and more cautious handling of structured legal text
- `Books / Novels` for long-form prose, page-to-page paragraph continuity, and chapter structure
- `Comics / Manga / Graphic Novels` for panel order, speech balloons, captions, visible SFX, image descriptions, and right-to-left manga flow when visibly supported
- `Newspapers` for multi-column layouts, publication metadata, and dense press-style reading order recovery
- `Handwritten Letters / Notes / Diaries` for more conservative reading of handwritten material with stronger uncertainty handling

The point of these presets is not to make the app feel complicated. It is to avoid forcing newspapers, books, handwriting, legal texts, reports, and mixed files through one blunt generic workflow when they clearly need different treatment.

## Feature Overview

Chronicle also includes practical workflow features built around difficult document recovery rather than one-click OCR:

- queue-first processing with pause, resume, and stop controls
- seamless merge mode for combining many pages, scans, or source files into one continuous output
- row-level page or slide scope controls for PDF and PPTX files
- automatic engine routing, with manual engine override when you want to force a specific provider or model
- scanner and page-import workflow support, including NAPS2 import
- session recovery support after interrupted runs
- collision controls so users can skip, overwrite, or auto-number outputs instead of losing work blindly
- original page-number preservation when source tracking matters, or suppression when reading flow matters more
- run-time controls for punctuation, abbreviations, units and currency, and image descriptions
- visible in-progress temp files so long runs have a readable work-in-progress artifact
- structured export support across HTML, TXT, DOCX, Markdown, PDF, JSON, CSV, and EPUB

For advanced users, Chronicle also exposes more detailed controls in Preferences, including custom prompt additions, engine override, and other fidelity-oriented settings for people who want to push or fine-tune the reading behavior more deliberately.

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

Chronicle is designed for users who need to inspect, adjust, and rerun difficult material instead of trusting a single blind pass.

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

Chronicle's default behavior is not "always use the biggest model." Cleaner PDFs in easier profiles can start on the faster engine first, while hard pages and structurally risky PDFs stay on, or escalate to, the deeper engine.

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
