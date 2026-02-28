# Chronicle Document Extractor

Chronicle is a highly accessible, multi-modal document extraction and transcription tool powered by Google's Gemini AI. It is specifically designed for high-fidelity transcription of complex historical archives, military documents, handwritten letters, technical manuals, financial spreadsheets, and complex legal legislation.

## 🚀 What's New in v1.5.0 (The Enterprise & Accessibility Expansion)
* **New Export Formats:** Added native support for exporting to EPUB (`.epub`), JSON (`.json`), and CSV (`.csv`). Chronicle can now generate native eBooks for e-readers, or structured data for corporate API and database integration.
* **Legal & Statutory Engine:** Overhauled the OCR prompt to recognize and meticulously preserve the strict hierarchical structure of legal contracts and legislation (Parts, Divisions, Sections, Subclauses) without flattening the text.
* **The WWI War Diary Showcase:** Added a comprehensive HTML showcase in `assets/samples/` demonstrating Chronicle's ability to reconstruct highly degraded, handwritten cursive that completely breaks standard OCR software.

## ✨ Core Features

* **Universal Input:** Supports PDFs, Word Documents, Excel Workbooks (.xlsx), plain text, and multiple image formats (JPG, PNG, TIFF, TIF, WEBP).
* **Universal Export:** Generates clean, semantic HTML specifically optimized for screen readers, alongside EPUB, JSON, CSV, TXT, DOCX, Markdown, and PDF output options.
* **10-Step Customization:** A comprehensive, audio-friendly terminal menu system to control everything from AI engine speed to historical punctuation modernization.
* **Smart Stitching:** Merge dozens of individual scanned images or pages into a single, seamless reading experience or continuous database file.
* **Archival Precision:** Features a custom ruleset to handle historical unit conversions, telegraph decoding (STOP to period), military grid references, and strikethrough text recovery.
* **Visual Scene Descriptions:** Automatically translates diagrams, photographs, and UI icons into detailed, descriptive text strings.
* **Advanced Batch Scanning:** Supports single-file processing, directory flat-scanning, and recursive scanning.
* **PDF Chunking:** Automatically and safely splits massive archival PDFs in 5-page chunks to prevent memory timeouts.

## 🛠️ Prerequisites & Installation

Chronicle is a Python script, not a compiled binary application. You will not find an installer in the GitHub "Releases" tab.

### 1. How to Download Chronicle
1. Click the green **Code** button at the top of the repository page.
2. Select **Download ZIP** from the dropdown menu.
3. Extract the ZIP file to a folder on your computer (e.g., your Documents folder).

### 2. Installing Python
To run Chronicle, you must have Python installed on your system.

* **Windows Users (⚠️ CRITICAL):** Download Python from the official website. When running the installer, **you must check the box that says "Add Python.exe to PATH"** at the bottom of the very first screen. If you miss this, Chronicle will not run.
* **Mac Users:** You can download Python from the official website, or install it via the Terminal using Homebrew by running: `brew install python`

### 3. Installing Dependencies
Chronicle requires specific libraries to read documents and communicate with AI. Open your terminal or command prompt and run this exact command to install everything you need:

```bash
pip install --upgrade google-genai pypdf python-docx fpdf2 openpyxl EbookLib

## Support the Project

Chronicle is an open-source project that I offer to the community completely free of charge. 

Developing this tool required hundreds of hours of coding, testing, and refining, along with significant personal financial investment in AI API costs to ensure the extraction engine is as accurate and accessible as possible.

If Chronicle has helped you decipher a family diary, made your archival research easier, or saved you hours of manual transcription, please consider supporting its continued development. Your support helps cover ongoing testing costs and fuels future updates!

* **[Buy Me a Coffee](https://buymeacoffee.com/thevoiceguy)**
* **[Donate via PayPal](https://paypal.me/MarshallVoiceovers)**

Thank you for your support, and happy archiving!