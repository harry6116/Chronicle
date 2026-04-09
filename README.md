# Chronicle

Chronicle is an accessibility-first document recovery tool for difficult real-world material.

Current public launch line: **Chronicle 1.0.0**.

It is especially strong on degraded scans, long-form books, archival records, tables, handwriting, multi-column layouts, and mixed-format batches where reading order and reviewability matter more than one-click speed.

Chronicle provides a screen-reader-friendly GUI, queue/task controls, scan-ingestion workflows, and structured output generation across multiple AI providers.

Chronicle is a desktop GUI application. This repository publishes the current app source code, build scripts, and documentation for the same release line. There is no separate supported Chronicle CLI product.

## Download Chronicle

- Mac: [Download Chronicle for macOS](https://github.com/harry6116/Chronicle/releases/download/v1.0.0/Chronicle.1.0.mac.zip)
- Windows: [Download Chronicle for Windows](https://github.com/harry6116/Chronicle/releases/download/v1.0.0/Chronicle.1.0.windows.zip)
- Release page: [Chronicle 1.0.0 release](https://github.com/harry6116/Chronicle/releases/tag/v1.0.0)

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

- It is built for hard documents, not just clean born-digital files.
- It is strongest when preserving reading order, structure, and review workflow matters.
- It gives operators visible control instead of treating every document as the same problem.
- It is designed to reduce cleanup time, not replace human verification.

## Why I Built It

Chronicle began with family history.

I wanted to read the First World War diaries of the Manchester Regiment and other difficult historical material that ordinary OCR kept mangling. That work turned into a broader effort to recover readable, reviewable output from documents that are technically legible but practically unusable.

The fuller founder story is here:

- `docs/public/WHY_CHRONICLE.md`

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

## Transparency

Chronicle was built using AI-assisted ("vibe-coded") workflows, with final integration, review, and testing directed by the author.

Important public references:

- Founder story: `docs/public/WHY_CHRONICLE.md`
- Root disclaimer: `DISCLAIMER.md`
- Public repo disclaimer source: `docs/github_rollout/LEGAL_DISCLAIMER_GITHUB.md`

## First Public Release

Chronicle `1.0.0` is the first public release of the current standalone app line.

It should be presented as a fresh release track, separate from the older public repository state.

Current release downloads:

- macOS ZIP: [Chronicle.1.0.mac.zip](https://github.com/harry6116/Chronicle/releases/download/v1.0.0/Chronicle.1.0.mac.zip)
- Windows ZIP: [Chronicle.1.0.windows.zip](https://github.com/harry6116/Chronicle/releases/download/v1.0.0/Chronicle.1.0.windows.zip)

## Contact

- Feedback is welcome through GitHub Issues: `https://github.com/harry6116/Chronicle/issues`
- Repository home: `https://github.com/harry6116/Chronicle`
- Release page: `https://github.com/harry6116/Chronicle/releases`

Public email contact addresses have been temporarily removed from the repository while the dedicated Chronicle account setup and authentication are being stabilized.

## Free for Non-Commercial Use

The packaged Chronicle desktop app is intended to be free to use for non-commercial work.

That includes personal use, study, home archiving, family history, volunteer/community work, nonprofit use, and other genuinely non-commercial use.

Commercial use of the packaged desktop app requires a paid Chronicle license.

If you want to use Chronicle for paid professional work, client services, business operations, or commercial organizational workflows, open a GitHub issue requesting the current contact path.

## Support Chronicle

If Chronicle helps your work and you want to support ongoing development, you can donate here:

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

That means the source code published in this repository is available under AGPLv3 terms.

Chronicle's packaged desktop-app licensing position is intended to be:

- free for non-commercial use
- paid commercial licensing for business and paid professional use

These desktop-app terms should be presented as a separate distribution/licensing path. They do not retroactively replace the AGPL terms attached to copies of the source code distributed from this repository.

If you need commercial desktop-app licensing, use the repository issue tracker to request the current contact path.
