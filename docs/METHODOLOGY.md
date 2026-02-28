# Chronicle: Technical Methodology & Architecture

This document outlines the architectural decisions, processing logic, and prompt engineering strategies that power the Chronicle extraction engine.

## 1. System Architecture

Chronicle operates as a client-side Python wrapper for the Google Gemini API. It is designed to act as an accessibility-first "Vision-Language" processor, converting unstructured visual data (PDFs, images) and code files into structured, semantic text.

**Data Flow Pipeline:**
`[Local Input File] -> [Python Pre-Processor] -> [Encrypted API Upload] -> [Gemini Vision-Language Model] -> [Text Stream] -> [Python Post-Processor] -> [Local Output File]`

## 2. Ingestion and Chunking Strategy

Large Language Models (LLMs) possess finite context windows and can suffer from degradation or "hallucinations" when processing massive documents. To process extensive archival records (e.g., a 500-page military war diary) without crashing, Chronicle employs a strict high-resolution chunking strategy.

* **PDF Chunking:** The `pypdf` library slices documents into strict 5-page temporary artifacts. This limitation forces the AI engine to scrutinize dense pages (like tables of contents or complex technical diagrams) without summarizing or skipping content.
* **Text and Code Chunking:** The script splits raw text and code files (`.txt`, `.md`, `.js`, `.docx`) using a strict 15,000-character limit to ensure optimal processing speed and memory management.
* **Batch Directory Scanning:** The engine utilizes a recursive `os.walk` scan to traverse nested sub-folders. This allows entire archival directory trees to be processed sequentially, with an optional memory-management toggle to automatically delete source files post-conversion.

## 3. The "Vision-Language" Engine

Chronicle relies on a multimodal processing approach. It does not merely execute character-level Optical Character Recognition (OCR); it analyzes spatial relationships and visual context.

* **Technical Manual Translation:** The system prompt explicitly forces the model to act as a UI translator. When processing instruction manuals that use standalone visual icons (e.g., a gear, a triangle, a trash can) instead of text, the model converts the pixel data into explicit, bracketed text (e.g., `[Settings Icon]`).
* **Device Schematic Reconstruction:** Visual diagrams that map device parts via numbered arrows are actively rebuilt into linear, spatially-aware descriptive lists.
* **Form Flattening Logic:** When the vision model detects a structured form (e.g., tax documents, applications), it is instructed to ignore visual X/Y coordinates and "flatten" the data into a clean key-value pair list.
* **Checkbox State Detection:** The engine analyzes the pixel data of visual checkboxes to determine their state, outputting explicit semantic tags: `[Checkbox: Selected]` or `[Checkbox: Empty]`.

## 4. Military Archive Intelligence

Historical military documents present unique accessibility challenges due to abbreviations, damage, and rigid layouts. Chronicle addresses these programmatically:

* **Telegraph Decoding:** Automatically converts the word "STOP" in telegraph cables into standard punctuation and paragraph breaks.
* **Grid Reference Formatting:** Forces the spacing of topographic map coordinates (e.g., `1 2 3 - 4 5 6`) to guarantee precise audio dictation cadence for screen readers.
* **Routing Block Parsing:** Reconstructs unformatted chain-of-command headers (From/To) and isolates diagonal security stamps (e.g., `TOP SECRET`) at the document's peak.
* **Nominal Rolls:** Rebuilds densely packed casualty and service lists into strictly scoped data structures.

## 5. Guardrails and Output Safety

### The "Double-Lock" Encoding Fix (Mojibake Prevention)
Encoding errors (Mojibake) occur when AI generates "smart" punctuation that older text readers misinterpret as garbage characters (e.g., `â€™` or `Â`), which severely disrupts screen reader audio. Chronicle solves this via a two-layer system:
1.  **Prompt Level:** The system explicitly forbids the AI from generating non-ASCII punctuation.
2.  **Python Scrubber:** A dedicated post-processing function (`clean_text_artifacts`) scans every incoming chunk for byte-order marks and corrupted UTF-8 artifacts, replacing them with standard ASCII equivalents before writing the output.

### Historical Fidelity and Verbatim Transcription
Historical and archival documents often contain period-accurate language, including terminology, profanity, or expressions that may be considered sensitive by modern standards. For accessibility and research integrity, Chronicle instructs the model to preserve the source material verbatim wherever possible.

The system prompt emphasizes faithful transcription of the original document without euphemistic substitution, redaction, or contextual reinterpretation. Content is treated as an immutable historical record and reproduced exactly as written to maintain archival accuracy.

### Terminal Noise Suppression
Archival PDFs frequently contain corrupted internal cross-reference tables (e.g., `offset 0` errors). To prevent these structural errors from flooding the terminal and overwhelming VoiceOver dictation, Chronicle actively suppresses non-critical warnings from the `pypdf` logger.

## 6. Output Generation

* **Semantic HTML:** The script constructs valid HTML5 without wrapper tags during chunking, concatenating them into a valid DOM structure upon completion. It utilizes proper heading hierarchy and table scope attributes for maximum screen reader compatibility.
* **PDF Generation:** Chronicle utilizes the `fpdf2` library. To prevent encoding crashes during PDF creation, it forces a Latin-1 compatible character set.

## 7. Data Privacy

Chronicle is a strictly stateless application. It holds user data in RAM only for the duration of the API session. Temporary chunked files are immediately deleted from the local disk after upload. The application does not maintain a database or persistent log of user content.
