# Chronicle

Chronicle is an accessibility-first document recovery tool for difficult real-world material.

Current public launch line: **Chronicle 1.0.0**.

It is especially strong on degraded scans, long-form books, archival records, legal and policy material, tables, handwriting, multi-column layouts, and mixed-format batches where preserving reading order, usable structure, and review workflow matters more than raw one-click speed.

Chronicle provides a screen-reader-friendly GUI, queue/task controls, scan-ingestion workflows, and structured output generation across multiple AI providers.

**Built for hard documents.**

Chronicle is for the files people usually describe as:

- "the scan is awful"
- "the OCR is almost right but keeps breaking the prose"
- "the page furniture keeps getting in the way"
- "I need something I can actually review, not just raw extracted text"

Chronicle is especially useful when you need:

- better recovery on degraded scans
- stronger paragraph continuity for books and long-form prose
- clearer review output in HTML or Word
- operator control over presets, merge behavior, and runtime settings
- a queue-and-rerun workflow for difficult material
- a faster path to review-ready output on messy source material

## Why Use Chronicle

- Built for hard documents, not just clean born-digital files
- Strong on books, archives, newspapers, forms, and mixed-format recovery work
- Gives operators control through presets, queue workflow, merge behavior, and runtime toggles
- Produces outputs that are easier to review in HTML or Word
- Prioritizes fidelity, continuity, and accessibility over blind OCR dumping

## Key Features

- Accessibility-first GUI with keyboard and screen-reader oriented workflows
- Multi-provider AI support:
  - Google Gemini (`gemini-2.5-flash`, `gemini-2.5-pro`)
  - Anthropic Claude (`claude-sonnet-4-20250514`)
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

## First Public Release

Chronicle `1.0.0` is the first public release of the current standalone app line.

It should be presented as a fresh release track, separate from the older terminal-first public repository history.

Planned public release assets:

- macOS: `Chronicle 1.0 mac.zip`
- Windows: `Chronicle 1.0 windows.zip`

## Contact

- General enquiries and evaluation requests: `hello.chronicle.app@gmail.com`
- Product support: `chronicle.app+support@gmail.com`
- Press and media: `chronicle.app+press@gmail.com`

## Build and Run

### Run from source

1. Install Python 3.11.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Run GUI:
   - `python chronicle_gui.py`

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
- Anthropic Claude API access is separate from Claude.ai chat plans and should be treated as requiring Claude Console/API billing or prepaid credits.

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

Chronicle's commercial/offline desktop licensing direction is being prepared separately and should be described explicitly as a separate licensing path if published. Do not present the current AGPL repository snapshot as simple donationware if the intended public model is paid desktop licensing.
