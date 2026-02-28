# Chronicle Document Extractor

Chronicle is a highly accessible, multi-modal document extraction and transcription tool powered by Google's Gemini AI. It is specifically designed for high-fidelity transcription of complex historical archives, military documents, handwritten letters, technical manuals, and financial spreadsheets.

## 🚀 What's New in v1.4.0
* **Spreadsheet Flattening (.xlsx):** Added native support for multi-page Excel workbooks. Chronicle now reads every tab in a workbook and automatically flattens complex spatial grids into clear, linear, screen-reader-friendly data tables and summaries.
* **Overhauled Installation Guide:** Added explicit setup instructions for non-developers, including Python installation traps and Homebrew commands.

## ✨ Core Features

* **Universal Input:** Supports PDFs, Word Documents, Excel Workbooks (.xlsx), plain text, and multiple image formats (JPG, PNG, TIFF, TIF, WEBP).
* **Accessible Output:** Generates clean, semantic HTML specifically optimized for screen readers, alongside TXT, DOCX, Markdown, and PDF output options.
* **10-Step Customization:** A comprehensive, audio-friendly terminal menu system to control everything from AI engine speed to historical punctuation modernization.
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

### 3. Installing Dependencies (The Setup Scripts)
Chronicle requires specific libraries to read documents and communicate with AI.
1. Open your extracted Chronicle folder.
2. Run your system's setup script (`Setup_Windows.bat` or `Setup_Mac.applescript`). This will automatically install everything you need.

*⚠️ **IMPORTANT UPDATE WARNING:** Whenever you download a new version of Chronicle, you must re-run your Setup script! New features often require new libraries (like Excel support), and the script will crash if your local machine does not have them installed.*

### 🔑 Gemini API Key & Pricing
You will need a **Google Gemini API Key** to power the engine. The script will prompt you for this on your first run and save it securely in an `api_key.txt` file. 

Google offers two API tiers:
| Tier | Cost | Rate Limits | Data Privacy |
| :--- | :--- | :--- | :--- |
| **Free Tier** | $0.00 | 15 Requests Per Minute | Data *may* be used to train Google's models. |
| **Pay-as-you-go** | Paid per Token | High/Custom | Data is strictly private and **not** used for training. |

*Note: If you are processing highly sensitive personal archives or financial data, the **Pay-as-you-go** tier is recommended to ensure strict data privacy.*

## ⚙️ Usage

1. Place your historical documents, PDFs, Excel files, or images into the `input_files` or `Input_Scans` folder.
2. Open your terminal and run the script:
   * Mac: Run `Run_Chronicle.command`
   * Windows: Run `Run_Chronicle.bat`
3. Follow the 10-step audio-friendly menu system to configure your extraction.
4. Your processed, clean-reading files will be saved in the corresponding output directory.