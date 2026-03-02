# Chronicle Document Extractor

Chronicle is a highly accessible, multi-modal document extraction and transcription tool powered by Google's Gemini AI. It is specifically designed for high-fidelity transcription of complex historical archives, military documents, handwritten letters, technical manuals, financial spreadsheets, and complex legal legislation.

## 🚀 What's New in v1.8.0 (The Academic & Compliance Update)
* **Strict WCAG 2.2 Compliance:** The extraction engine now hardcodes strict HTML semantics, including proper table scopes, unbreakable heading hierarchies, and dynamic language/title tags to meet US Section 508 and Australian AS EN 301 549 standards.
* **The Academic Engine:** Chronicle can now process dense scientific, theological, and musicology journals. It automatically converts complex mathematical equations into LaTeX, preserves ancient inline languages (Greek, Hebrew), flattens multi-column layouts, and safely anchors footnotes to the end of the document.
* **Automated Setup Scripts:** We have introduced dedicated Mac and Windows scripts to streamline dependency management.
* **Stateless Fail-Safes (Atomic Saving):** Chronicle uses temporary `.tmp` streaming to ensure that if your computer crashes mid-scan, no files are ever corrupted. 

## ✨ Core Features

* **Universal Input:** Supports PDFs, Word Documents, Excel Workbooks (.xlsx), plain text, and multiple image formats.
* **Universal Export:** Generates clean, semantic HTML specifically optimized for screen readers, alongside EPUB, JSON, CSV, TXT, DOCX, Markdown, and PDF output options.
* **10-Step Customization:** A comprehensive, audio-friendly terminal menu system to control everything from AI engine speed to historical punctuation modernization.
* **Archival Precision:** Features a custom ruleset to handle historical unit conversions, telegraph decoding, military grid references, and strikethrough text recovery.
* **PDF Chunking:** Automatically and safely splits massive archival PDFs in 5-page chunks to prevent memory timeouts.
* ## 🛠️ Prerequisites & Installation

Chronicle is a Python script, not a compiled binary application. You will not find an installer in the GitHub "Releases" tab.

### 1. How to Download Chronicle
1. Click the green **Code** button at the top of the repository page.
2. Select **Download ZIP** from the dropdown menu, or clone the repository to your machine.
3. Extract the ZIP file to a folder on your computer (e.g., your Documents folder).

### 2. Installing Python
To run Chronicle, you must have Python installed on your system.

* **Windows Users (⚠️ CRITICAL):** Download Python from the official website. When running the installer, **you must check the box that says "Add Python.exe to PATH"** at the bottom of the very first screen. If you miss this, Chronicle will not run.
* **Mac Users:** You can download Python from the official website, or install it via the Terminal using Homebrew by running: `brew install python`

### 3. Installing Dependencies & First-Time Setup
Users can use the Mac or Windows Update scripts (`update_mac.sh` and `update_windows.bat`) to automatically update the software and dependencies, rather than manually running `pip install` or re-downloading ZIP files. 

For your very first setup, simply open your terminal or command prompt in the Chronicle folder and run the script corresponding to your operating system. This will automatically install required libraries like `google-genai`, `pypdf`, `fpdf2`, `openpyxl`, and `EbookLib`.

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

Users can use the Mac or Windows Update scripts (`update_mac.sh` and `update_windows.bat`) to automatically update the software and dependencies, rather than manually running pip install or re-downloading ZIP files.

Simply run the script for your operating system to instantly pull the latest code and install any new dependencies. **This process is 100% safe.** It will only update the core engine; it will never overwrite your extracted documents, your input files, or your API key.

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