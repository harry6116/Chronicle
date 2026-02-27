# Chronicle Document Extractor

Chronicle is a highly accessible, multi-modal document extraction and transcription tool powered by Google's Gemini AI. It is specifically designed for high-fidelity transcription of complex historical archives, military documents, handwritten letters, and technical manuals.

## 🚀 What's New in v1.2.0
* **Modernized AI Engine:** Migrated to the official `google-genai` SDK for improved stability, faster document processing, and the elimination of deprecation warnings.
* **Native File Handling:** Replaced legacy base64 encoding with Google's native File API, streamlining the processing of massive, multi-page archival PDFs.

## ✨ Core Features

* **Universal Input:** Supports PDFs, Word Documents, plain text, and multiple image formats (JPG, PNG, TIFF, WEBP).
* **Accessible Output:** Generates clean, semantic HTML specifically optimized for screen readers, alongside TXT, DOCX, Markdown, and PDF output options.
* **Archival Precision:** Features a custom ruleset to handle historical unit conversions, telegraph decoding (STOP to period), military grid references, and strikethrough text recovery.
* **Visual Scene Descriptions:** Automatically translates diagrams, photographs, and UI icons into detailed, descriptive text strings.
* **Advanced Batch Scanning:** Supports single-file processing, directory flat-scanning, and recursive scanning (with options to keep or delete original files).
* **PDF Chunking:** Automatically safely splits and processes massive archival PDFs in 5-page chunks to prevent memory timeouts.

## 🛠️ Prerequisites & Installation

To run Chronicle, you will need Python installed on your system along with a few specific libraries. 

1. Open your terminal.
2. Run the following command to install all required dependencies (updated for the modern Gemini API):

   ```bash
   pip install pypdf python-docx fpdf2 google-genai