# Chronicle

Chronicle is an accessibility-first document recovery tool for archival, academic, legal, newspaper, military, book, comics, manga, graphic-novel, and other difficult mixed-format material. It provides a screen-reader-friendly GUI, queue controls, scan-ingestion workflows, and structured output generation across multiple AI providers.

Chronicle is a desktop GUI application. The public repository is intended to publish the current app source code, build scripts, and documentation for that GUI app. There is no separate supported Chronicle CLI product.

Current public release target: **Chronicle 1.0.7**.

**Built for hard documents.**

Chronicle is aimed at the kinds of files where ordinary extraction tends to struggle:

- degraded scans
- long-form books and memoirs
- comics, manga, graphic novels, and comic strips
- archival records with repeated page furniture
- awkward multi-column or mixed-layout pages
- difficult review-and-rerun workloads

## Why Chronicle

- Built for screen-reader-first operation.
- Designed for degraded scans, books, comics, manga, graphic novels, handwriting, dense tables, multi-column layouts, and archival edge cases.
- Supports practical workflows: queueing, scheduling, pause/resume, scanner import, log export, and merge modes.
- Gives users specialist presets and visible control instead of treating every document as the same problem.
- Strong when preserving reading order, paragraph continuity, and review workflow matters more than raw one-click speed.

## Positioning Summary

Chronicle is most useful when the document is hard: messy scans, damaged prose, repeated page furniture, mixed layouts, or long queues that need careful reruns. It is designed for users who want better recovery and more control, not just the fastest possible pass on easy files.

Chronicle aims to help users reach review-ready output faster on difficult material, while still assuming human review before final reliance.

## Current Core Capabilities

- Multi-provider AI engine support:
  - Google Gemini (`gemini-2.5-flash`, `gemini-2.5-pro`)
  - Anthropic Claude (`claude-sonnet-4-20250514`)
  - OpenAI (`gpt-4o`)
- Input formats:
  - `PDF`, `DOCX`, `TXT`, `MD`, `RTF`, `CSV`, `XLSX`, `PPTX`, `EPUB`, and common image formats
- Output formats:
  - `HTML` (default), `TXT`, `DOCX`, `MD`, `PDF`, `JSON`, `CSV`, `EPUB`
- Queue operations:
  - add files/folders, scanner discovery, NAPS2 scan import
  - select all / deselect all
  - task actions (`Stop`, `Pause`, `Resume`, `Delete`, `Open Folder`)
- Safety and workflow controls:
  - preserve source folder structure for directory scans
  - optional delete originals after successful extraction
  - scheduled extraction start
  - interrupted session recovery
  - merge mode and per-row page/slide scope controls
- Document presets include dedicated profiles for historical newspapers, modern newspapers/e-papers, military records, handwriting, comics/manga/graphic novels, magazines, books, legal material, forms, reports, and other difficult source classes.

## Build and Distribution

- Local build scripts:
  - macOS: `./build.command`
  - Windows: `build_windows.bat` (calls `build_windows.ps1`)
- Portable Windows staging workflow:
  - `./stage_windows_bundle.command`
  - staged bundle must include `build_windows.bat`, `build_windows.ps1`, `chronicle_app/`, `assets/`, and `docs/`
- CI workflow prepared for both platforms:
  - `.github/workflows/build-mac-windows.yml`

Current public release assets:

- `Chronicle.mac.zip`
- `Chronicle.windows.zip`

Public feedback and contact path:

- GitHub Issues: `https://github.com/harry6116/Chronicle/issues`
- Repository: `https://github.com/harry6116/Chronicle`
- Releases: `https://github.com/harry6116/Chronicle/releases`

Public email addresses are intentionally not listed in the repository until the dedicated Chronicle account setup is stable.

## Quick Start (Source Build / Dev)

1. Install Python 3.11.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Launch GUI:
   - `python chronicle_gui.py`
4. Add API keys in the app (`API Keys...`).
5. Queue files, choose engine/format/profile, and run extraction.

## Privacy and Responsibility

- API keys are stored locally.
- In the current app line, local storage should live in per-user app-data paths rather than the repository tree or release bundle contents.
- Document content is sent to the selected AI provider for processing.
- Provider retention/training behavior depends on provider account/plan settings.
- Google Gemini API keys from Google AI Studio can work on Google's free tier, subject to current quotas, rate limits, model availability, and region support.
- Practical reliability note: free Gemini API keys are best treated as testing access, not guaranteed production capacity. Hard PDFs and long magazine/newspaper runs can still fail with provider quota errors even when Chronicle itself is healthy.
- Anthropic Claude API access is separate from Claude.ai chat plans and should be treated as requiring Claude Console/API billing or prepaid credits.
- Users are responsible for validating privacy/compliance requirements for their workload.

## License

Current source-repository license: GNU AGPLv3.

If Chronicle is offered under separate commercial or proprietary terms later, that path should be described as a distinct licensing arrangement rather than implied to replace the AGPL terms already attached to public repository copies.

## Status

This project is the active standalone Chronicle GUI app line. Chronicle 1.0.7 focuses on clearer preset taxonomy, modern newspaper/e-paper handling, historical newspaper safeguards, and more reliable image-only scanned PDF recovery.
