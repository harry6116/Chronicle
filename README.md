# Chronicle (Version 9.3)

An accessibility-first AI-powered document extraction engine designed for complex manuals, archival material, structured forms, and historical research.

Chronicle is a local Python application that connects securely to the Google Gemini API to convert unstructured PDFs, images, and code files into structured, screen-reader-friendly output.

Licensed under GNU GPLv3.

Commercial licensing options are available for proprietary integration. Contact: YOUR_EMAIL_HERE.

---

## Why Chronicle Exists

Most document scanners perform character-level OCR.

Chronicle performs contextual reconstruction using a Vision-Language model. It is designed specifically for:

- Screen reader users
- Historical researchers
- Technical manual parsing
- Military and archival document reconstruction
- Structured form flattening

Accessibility is not an afterthought — it is the foundation.

---

## Core Features

### Accessibility-First Processing
- Semantic HTML output
- Checkbox state detection
- Strikethrough recovery
- Clean ASCII encoding
- Mojibake prevention

### Technical Manual Translation
- Converts icon-only UI symbols into spoken text
- Rebuilds device schematics into linear descriptions
- Preserves configuration logic

### Military Archive Intelligence
- Telegraph STOP decoding
- Grid reference isolation for screen readers
- Classification stamp extraction
- Casualty table reconstruction

### Form Flattening
- Converts XY-based layouts into clean key-value lists
- Checkbox detection (Selected / Empty)

### Batch Processing
- Recursive folder scanning
- 5-page strict chunking for stability
- Optional cleanup mode after successful conversion

### Latest Updates
* **Handwriting Support:** The Vision-Language engine now officially supports JPEGs and PDFs of handwritten documents (invoices, letters, diaries).
* **Character Resilience:** Fixed a bug where non-standard handwritten symbols caused a "terminator" error.
* **Professional Interface:** The Windows command window now features a dedicated "Chronicle" title for better visibility.
---

## Installation

### Windows
1. Install Python from python.org
2. Run Setup_Windows.bat
3. Launch with Run_Chronicle.bat

### macOS
1. Install Python (python.org or Homebrew)
2. Run Setup_Mac.applescript
3. Launch with Run_Chronicle.command

---

## Manual Installation

python -m pip install pypdf python-docx fpdf2 google-genai

---

## API Key

Chronicle requires your own Google Gemini API key.

You can either set an environment variable:

export GOOGLE_API_KEY=your_key_here

Or paste it when prompted.

Your documents are encrypted and processed via Google's Gemini API.
Chronicle does not store your files locally beyond runtime memory.

---

## Data Privacy

Chronicle is stateless.
No database.
No persistent logs.
Temporary artifacts are deleted after processing.

Sensitive documents should be uploaded only if you are comfortable with Google Cloud policies.

---

## Contributing

Community improvements are welcome.

Please read CONTRIBUTING.md before submitting pull requests.

---

## Support the Project

Chronicle is a free, open-source tool developed to make historical and technical documents accessible to everyone. 

If this program has improved your workflow, saved you time, or helped you access complex documents, please consider supporting its ongoing development. Donations are always appreciated and help cover the API testing costs required to maintain the engine.

[Donate via PayPal](https://paypal.me/MarshallVoiceovers)

---

## Commercial Use

Chronicle is licensed under GPLv3.

If you wish to integrate Chronicle into proprietary or closed-source software, commercial licensing arrangements are available. Please contact the author.

---

## Disclaimer

This project was developed using AI-assisted engineering and independently tested by the author.

It is provided "as is" without warranty.
Do not rely on this software for medical, legal, financial, or safety-critical interpretation without independent verification.

See DISCLAIMER.md for full details.

Created by Michael Marshall.
