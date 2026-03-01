# Chronicle Document Extractor

Chronicle is a highly accessible, multi-modal document extraction and transcription tool powered by Google's Gemini AI. It is specifically designed for high-fidelity transcription of complex historical archives, military documents, handwritten letters, technical manuals, financial spreadsheets, and complex legal legislation.

## 🚀 What's New in v1.7.0 (The Resilience Update)
* **Stateless Fail-Safes (Atomic Saving):** Chronicle is now virtually crash-proof. It uses temporary `.tmp` streaming to ensure that if your computer crashes or loses power mid-scan, no files are ever corrupted. 
* **Smart Skip Batching:** If you are scanning 1,000 pages and your computer restarts, simply run the script again. Chronicle will automatically skip the pages it already finished and pick up exactly where it left off, requiring zero manual sorting.
* **Live Save Merging:** When stitching massive archives into a single eBook or database, the engine incrementally saves to your hard drive after every page, ensuring zero data loss if the process is interrupted.

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
Chronicle requires specific libraries to read documents and communicate with AI. If this is your **first time** installing Chronicle, open your terminal or command prompt and run this exact command to install everything you need:

```bash
pip install --upgrade google-genai pypdf python-docx fpdf2 openpyxl EbookLib
### 🔑 Gemini API Key & Pricing
You will need a **Google Gemini API Key** to power the engine. The script will prompt you for this on your first run and save it securely in an `api_key.txt` file. 

Google offers two API tiers:
| Tier | Cost | Rate Limits | Data Privacy |
| :--- | :--- | :--- | :--- |
| **Free Tier** | $0.00 | 15 Requests Per Minute | Data *may* be used to train Google's models. |
| **Pay-as-you-go** | Paid per Token | High/Custom | Data is strictly private and **not** used for training. |

*Note: If you are processing highly sensitive personal archives, legal contracts, or financial data, the **Pay-as-you-go** tier is strictly recommended to ensure absolute data privacy.*

## ⚙️ Usage

1. Place your historical documents, PDFs, Excel files, or images into the `input_files` or `Input_Scans` folder.
2. Open your terminal and run the script:
   * Mac: Run `./Run_Chronicle.command`
   * Windows: Run `Run_Chronicle.bat`
   * Or manually via terminal: `python chronicle.py`
3. Follow the 10-step audio-friendly menu system to configure your extraction.
4. Your processed, clean-reading files will be saved in the corresponding output directory.

## 🔄 Keeping Chronicle Updated

You no longer need to manually download new ZIP files when Chronicle updates. Inside your folder, you will find an **Update_Chronicle** script (one for Mac, one for Windows). 

Simply run this script to instantly pull the latest code and install any new dependencies. **This process is 100% safe.** It will only update the core engine; it will never overwrite your extracted documents, your input files, or your API key.

## 📜 License & Commercial Integration

Chronicle is available under the open-source **GNU AGPLv3** license. 

For commercial integration, proprietary licensing, or enterprise deployment (e.g., embedding Chronicle into closed-source legal tech suites or private university databases), please contact the developer to arrange a Commercial License.

## Support the Project

Chronicle is an open-source project that I offer to the community completely free of charge. 

Developing this tool required hundreds of hours of coding, testing, and refining, along with significant personal financial investment in AI API costs to ensure the extraction engine is as accurate and accessible as possible.

If Chronicle has helped you decipher a family diary, made your archival research easier, or saved you hours of manual transcription, please consider supporting its continued development. Your support helps cover ongoing testing costs and fuels future updates!

* **[Buy Me a Coffee](https://buymeacoffee.com/thevoiceguy)**
* **[Donate via PayPal](https://paypal.me/MarshallVoiceovers)**

Thank you for your support, and happy archiving!