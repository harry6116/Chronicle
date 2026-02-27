# Chronicle Document Extractor

Chronicle is a highly accessible, multi-modal document extraction and transcription tool powered by Google's Gemini AI. It is specifically designed for high-fidelity transcription of complex historical archives, military documents, handwritten letters, and technical manuals.

## 🚀 What's New in v1.3.1
* **Expanded Scanner Support:** Added explicit support for `.tif` files, ensuring older scanner outputs are seamlessly picked up during recursive batch processing.
* **Bug Fix:** Resolved a syntax error that prevented the script from launching.

## 🚀 What's New in v1.3.0
* **True Seamless Merge:** Added **Menu 10**, allowing users to completely disable technical metadata and confidence scores. When merging multi-page letters or continuous documents, this creates a 100% seamless reading experience with zero page-boundary interruptions.
* **Modernized AI Engine:** Upgraded to the official `google-genai` SDK and the `gemini-2.5` models for improved stability, faster document processing, and the elimination of deprecation warnings.
* **Native File Handling:** Replaced legacy base64 encoding with Google's native File API, streamlining the processing of massive, multi-page archival PDFs.

## ✨ Core Features

* **Universal Input:** Supports PDFs, Word Documents, plain text, and multiple image formats (JPG, PNG, TIFF, TIF, WEBP).
* **Accessible Output:** Generates clean, semantic HTML specifically optimized for screen readers, alongside TXT, DOCX, Markdown, and PDF output options.
* **10-Step Customization:** A comprehensive, audio-friendly terminal menu system to control everything from AI engine speed to historical punctuation modernization.
* **Archival Precision:** Features a custom ruleset to handle historical unit conversions, telegraph decoding (STOP to period), military grid references, and strikethrough text recovery.
* **Visual Scene Descriptions:** Automatically translates diagrams, photographs, and UI icons into detailed, descriptive text strings.
* **Advanced Batch Scanning:** Supports single-file processing, directory flat-scanning, and recursive scanning (with options to keep or delete original files).
* **PDF Chunking:** Automatically and safely splits massive archival PDFs in 5-page chunks to prevent memory timeouts.

## 🛠️ Prerequisites & Installation

To run Chronicle, you will need Python installed on your system along with a few specific libraries. 

1. Open your terminal.
2. Run the following command to install all required dependencies:

   ```bash
   pip install pypdf python-docx fpdf2 google-genai