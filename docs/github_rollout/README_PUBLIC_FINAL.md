# Chronicle

Chronicle is an accessibility-first document recovery tool for difficult real-world material.

Current public release line: **Chronicle 1.1.3**.

It is especially strong on degraded scans, long-form books, archival records, legal and policy material, tables, handwriting, multi-column layouts, comics, manga, graphic novels, and mixed-format batches where preserving reading order, usable structure, and review workflow matters more than raw one-click speed.

Chronicle provides a desktop interface designed for keyboard and screen-reader use. You can queue files, choose settings for each document, and save results in several formats.

Chronicle is a desktop GUI application. This repository publishes the current app source code, build scripts, and documentation for the same release line. There is no separate supported Chronicle CLI product.

## Download Chronicle

- Mac: [Download Chronicle for macOS (Apple silicon)](https://github.com/harry6116/Chronicle/releases/latest/download/Chronicle.mac.zip)
- Windows: [Download Chronicle for Windows (64-bit)](https://github.com/harry6116/Chronicle/releases/latest/download/Chronicle.windows.zip)
- Release page: [Latest Chronicle release](https://github.com/harry6116/Chronicle/releases/latest)

**Built for hard documents.**

Chronicle is for the files people usually describe as:

- "the scan is awful"
- "the OCR is almost right but keeps breaking the prose"
- "the repeated headers and page numbers keep getting in the way"
- "I need something I can actually review, not just raw extracted text"

Chronicle is especially useful when you need:

- better recovery on degraded scans
- stronger paragraph continuity for books and long-form prose
- panel-by-panel recovery for comics, manga, and graphic novels
- accessible reading scripts for speech balloons, captions, visible sound effects, and textless comic panels
- clearer review output in HTML or Word
- control over document presets, combining files and reading settings
- a queue-and-rerun workflow for difficult material
- a faster path to review-ready output on messy source material

## Updating Chronicle

Choose **Help > Check for Updates** (or press **Shift+F1**) to read about the latest version. In the installed Mac or Windows app, **Install and Restart Now** downloads and installs it while keeping your settings and API keys. **Remind Me Later** keeps the app open and adds a quiet reminder at the next launch. Updates start only when you choose to install them.

Use **Go to Release** for the download page and **Help > Version History** for release notes. Press **F1** for help with the current control, or choose **Help > Open User Guide** for the full guide.

## Private Offline Mode

Chronicle offers Private Offline Mode for sensitive documents and outages through the user's local Ollama installation. To use it, install Ollama, open it, and run `ollama pull qwen2.5vl:7b`.

Chronicle checks the local Ollama service for `qwen2.5vl:7b`, shows the exact pull command when needed, and can ask Ollama to install the model when the command-line tool is available.

Offline mode is best for clear modern typed documents:

- bank statements, invoices, receipts, tax records, and account notices
- typed medical forms and claim forms
- typed legal forms, contracts, notices, and regulations
- government forms with clear labels and checkboxes
- simple manuals, operation guides, letters, memos, and short reports

It is an emergency/private fallback, not a full replacement for Chronicle's strongest online Gemini path. Avoid offline mode for degraded handwriting, historical newspapers, magazines, comics, manga, graphic novels, long books, complex diagrams, equation-heavy papers, and public accessibility-remediation work that needs final compliance sign-off.

Tests with a small set of sample documents found offline mode most useful for clear typed pages. Results vary, so check important text against the original.

The recommended model balances download size, speed and reading quality on the documents tested.

Practical requirements for Private Offline Mode: 16 GB RAM recommended, 24-32 GB comfortable for repeated offline batches, 8 GB RAM constrained/emergency-only for very small clean files, 12 GB free disk minimum, and 20 GB+ free SSD space recommended.

Full guidance: `docs/user/PRIVATE_OFFLINE_MODE.md`.

## Why Use Chronicle

- Built for hard documents, not just clean born-digital files
- Strong on books, archives, newspapers, comics, manga, graphic novels, forms, and mixed-format recovery work
- Gives operators control through presets, queue workflow, merge behavior, and runtime toggles
- Produces outputs that are easier to review in HTML or Word
- Prioritizes fidelity, continuity, and accessibility over blind OCR dumping

## Key Features

- Accessibility-first GUI with keyboard and screen-reader oriented workflows
- Multi-provider AI support:
  - Google Gemini (`gemini-2.5-flash`, `gemini-2.5-pro`)
  - Anthropic Claude (`claude-sonnet-4-6`)
  - OpenAI (`gpt-4o`)
- Input support:
  - `PDF`, `DOCX`, `TXT`, `MD`, `RTF`, `CSV`, `XLSX`, `PPTX`, `EPUB`, common image formats
- Output support:
  - `HTML`, `TXT`, `DOCX`, `MD`, `PDF`, `JSON`, `CSV`, `EPUB`
- Queue operations:
  - add files / add folder / scanner discovery / NAPS2 import
  - pause / resume / stop / delete / open folder
- Safety controls:
  - preserve source folder structure
  - optional delete originals after successful extraction
  - session recovery
  - merge mode and page/slide scope controls

## What Users Should Expect

- Easy files may move quickly.
- Difficult books, degraded PDFs, and dense historical material can take longer.
- Chronicle deliberately spends more time on hard cases when that improves paragraph continuity, structural recovery, and accessibility-friendly output.
- Chronicle is designed to reduce manual cleanup and help users reach review-ready output more quickly, but human review is still required.

## Current Public Release

Chronicle `1.1.3` improves PDF extraction reliability, accessibility, security, packaging, recovery-workbench output, and Private Offline Mode through user-managed local Ollama.

Current release downloads:

- macOS ZIP: [Chronicle.mac.zip](https://github.com/harry6116/Chronicle/releases/latest/download/Chronicle.mac.zip)
- Windows ZIP: [Chronicle.windows.zip](https://github.com/harry6116/Chronicle/releases/latest/download/Chronicle.windows.zip)

## Contact

- Feedback is welcome through GitHub Issues: `https://github.com/harry6116/Chronicle/issues`
- Repository home: `https://github.com/harry6116/Chronicle`
- Release page: `https://github.com/harry6116/Chronicle/releases`

## Support Chronicle

If Chronicle helps your work and you want to support ongoing development, you can donate here:

- [GitHub Sponsors](https://github.com/sponsors/harry6116)
- [Make a one-time contribution](https://github.com/sponsors/harry6116?frequency=one-time) — no monthly commitment.

Support is optional. On GitHub Sponsors, choose **One-time** for a single payment or **Monthly** for recurring support. GitHub requires sign-in to sponsor.

- Buy Me a Coffee: `https://buymeacoffee.com/thevoiceguy`
- PayPal: `https://paypal.me/MarshallVoiceovers`

## Build and Run

### Build or run the app from source

1. Install Python 3.11.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Run GUI:
   - `python chronicle_gui.py`

Source mode is for building, testing, and developing the Chronicle GUI app from the published source tree.

### Build standalone apps

- macOS:
  - `./build.command`
- Windows:
  - `build_windows.bat` (calls `build_windows.ps1`)

### Portable Windows build staging

- Run `./stage_windows_bundle.command`
- Copy `dist_windows_bundle/Chronicle_Windows_Bundle` to the Windows machine
- Run `build_windows.bat` from the staged bundle root
- Ensure the staged bundle includes `build_windows.ps1`, `build_windows.bat`, `chronicle_app/`, `assets/`, and `docs/`

## API Keys and Provider Boundary

Chronicle stores API keys locally, but extracted content is sent to the selected provider API for processing.

- Keys are stored locally on the user's own machine in Chronicle app-data storage.
- Keys are not intended to be embedded in release artifacts or committed to the repository.
- Chronicle cannot enforce provider retention/training policy.
- Provider privacy/confidentiality behavior depends on account tier and provider settings.
- Google Gemini API keys from Google AI Studio can work on Google's free tier, subject to current quotas, rate limits, model availability, and region support.
- Important practical warning: free Gemini API keys may be enough to test Chronicle, but they can hit quota or rate-limit failures quickly on hard PDFs, long batches, magazines, newspapers, or repeated reruns. If you need dependable extraction rather than casual testing, a higher-quota Gemini API setup is strongly recommended.
- Anthropic Claude API access is separate from Claude.ai chat plans and should be treated as requiring Claude Console/API billing or credits.

Detailed guidance:

- `docs/github_rollout/PROVIDER_PRIVACY_AND_TIER_GUIDE.md`
- `docs/github_rollout/LEGAL_DISCLAIMER_GITHUB.md`

## Contributing and Security

- Contribution guide: `docs/github_rollout/CONTRIBUTING_GITHUB.md`
- Security policy: `docs/github_rollout/SECURITY_GITHUB.md`
- Local commit safety:
  - run `bash tools/install_git_hooks.sh` to enable the pre-commit secret scanner

## License

Current source-repository license: GNU AGPLv3.

That means the source code published in this repository is available under AGPLv3 terms.
