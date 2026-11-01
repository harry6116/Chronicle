# How Chronicle Reads Documents

Chronicle turns source documents into text and structured files that are easier to read, edit and review. It aims to preserve the original meaning while improving headings, tables and reading order.

## Choose settings for the source

Document presets provide a starting point for books, letters, military records, newspapers, forms, medical notes and other material. A preset can affect reading order, abbreviation handling, image descriptions and the choice of reading engine.

Start with a few pages of a difficult document. Review the result before processing the whole file. You can select PDF pages such as `1,3,5-7`, or use First 5 Pages Trial.

## Reading text and scans

Chronicle can use text already present in a file or read a page visually. A scan may need more work than a document created digitally, especially when it contains handwriting, narrow columns, faded print or complex tables.

PDF processing handles pages separately so difficult pages are easier to identify and retry. Progress reports pages for PDFs, slides for presentations and sections of text for other documents.

## Choosing an online engine

With Engine Override set to Automatic, Chronicle chooses an available provider for the preset. It can use a faster engine for easier PDFs and a more detailed reading for difficult pages. You can choose an engine yourself in Preferences.

Online processing sends document content to the selected provider. An API key and any required provider billing are separate from a normal chat subscription. Provider limits or outages can delay a run or require another attempt.

## Private Offline Mode

Offline processing uses Ollama and a model installed on your own computer. After setup, documents can be processed without sending them to an online AI provider.

It works best with clean typed documents. Handwriting, damaged scans, complex layouts and detailed visual descriptions are harder. See the [Private Offline Mode guide](PRIVATE_OFFLINE_MODE.md) for setup and limitations.

## Preserving the source

Chronicle asks the reading engine to preserve names, dates, numbers and the relationships between parts of the document. Unclear text should be marked rather than guessed, but AI output can still contain mistakes or omissions.

Optional settings can modernise punctuation, expand abbreviations, describe images or add modern equivalents for older units. Keep those options off when your task requires the closest possible transcription, and check any changes against the source.

Specialist presets give extra guidance for material such as legal numbering, clinical result tables, newspaper articles, comic panels and book chapters. They do not guarantee accuracy or replace expert review.

## Accessible results

HTML is the preferred format for reading with a screen reader. Chronicle aims to provide useful headings, lists, tables, page navigation and language information. Word output is useful when you need to edit the result.

The quality of the source and the selected settings affect the result. Check reading order, headings, table relationships and image descriptions in your usual browser or editor.

## Progress, saving and recovery

Chronicle writes temporary working files while reading. Some formats also use a hidden text recovery file while the final document is being assembled. These files help preserve work after an interruption; they are not the finished document.

A successful run normally removes its recovery file. An interrupted run may keep it for review or resume. Chronicle can also recover some completed results on the next launch if saving was interrupted. Recovery is a safeguard, not a replacement for backups.

If an output already exists, File Collision Mode controls whether Chronicle skips it, replaces it after successful processing or creates a numbered copy. Optional deletion of source files happens only after a successful run.

## Review before relying on the result

Compare important passages with the original, especially names, dates, measurements, medical values, legal wording and totals. A confidence score is an estimate, not proof of accuracy.

Some completed jobs create an extraction receipt and review report. Use their warnings to guide checks. Complex or sensitive documents still need human review before publication or professional use.

## Privacy

Chronicle saves settings, API keys and recovery information locally. It uses the system keychain where available. Output and temporary recovery files may contain document text, so keep them in a suitable location.

Online providers set their own privacy and retention terms. Review those terms before uploading confidential material. Support bundles hide many sensitive values, but inspect a bundle before sharing it.

For implementation details, see the [technical architecture reference](../reference/Chronicle_Technical_Architecture_Deep_Dive.md).
