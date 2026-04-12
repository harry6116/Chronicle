# Release Messages (Draft Set)

Use these as templates when moving the new Chronicle codebase into the public repository.

## Current Commit Message

`Add validated comics preset and harden magazine cleanup`

Public-safe summary:
- Adds the built-in `Comics / Manga / Graphic Novels` preset for accessible
  panel-by-panel reading output.
- Keeps comic PDFs on one-page slices and the deep reading engine by default.
- Adds comic-specific benchmark gates for panel headings, image descriptions,
  non-empty panel sections, clean semantic wrapping, and structural regressions.
- Adds a public-domain Little Nemo before/after showcase sample.
- Hardens dense magazine cleanup for leaked markdown headings, broken image
  placeholders, wrapper/comment noise, repeated blocks, and short running-head
  labels.
- Updates the release draft, changelog, continuity trail, and focused tests for
  the comics preset and magazine cleanup pass.

Public validation wording:
- Public/open comics validation reached `9/9 A+` under comic-specific checks.
- Additional local validation reached `12/12 A+` under the same checks without
  adding any private source material to public-facing docs.

---

## 1. Full Release Post (GitHub Release Body)

## Chronicle 1.0.0

This release replaces the outdated legacy public repository state with the current standalone Chronicle app.

Chronicle 1.0.0 is the first public release of the new app line.

### Highlights

- Accessibility-first GUI workflows optimized for screen readers.
- Multi-provider AI support (Gemini, Claude, GPT-4o).
- First packaged public builds for macOS and Windows.
- HTML is now the default output format.
- Queue productivity upgrades:
  - `Select All` / `Deselect All`
  - keyboard selection controls (`Cmd/Ctrl+A`, `Escape`, `Space`)
  - task action menu (`Stop`, `Pause`, `Resume`, `Delete`, `Open Folder`)
- Scanner workflow support:
  - scanner discovery
  - NAPS2 scan import into queue
- New safety controls:
  - preserve source folder structure when scanning directories
  - optional delete originals after successful extraction (with caution + confirmation)
- Scheduled extraction and interrupted-session recovery.
- Platform build pipeline:
  - local scripts for macOS and Windows builds
  - CI workflow for automated macOS + Windows artifacts

### Notes

- This is a fresh public release line, not a small update to the older terminal-first repo snapshot.
- Please read updated docs before upgrading or integrating.
- Bug reports and migration issues are welcome via GitHub Issues.
- Release assets:
  - `Chronicle 1.0 mac.zip`
  - `Chronicle 1.0 windows.zip`

---

## 2. Short Release Post

Chronicle 1.0.0 is here.

This replaces the old public repo snapshot with the current standalone Chronicle app: accessibility-first GUI, queue/task controls, scanner ingestion, safer output options, session recovery, and first packaged builds for macOS and Windows.

Key updates include:
- HTML default output
- Select All / Deselect All queue controls
- Preserve scanned folder structure option
- Optional delete-originals with warning confirmation
- Mac and Windows release ZIPs

---

## 3. Social Post (X/LinkedIn)

Chronicle 1.0.0 is live.

New release includes:
- accessibility-first GUI and queue controls
- scanner import + scheduling
- safer extraction options (preserve folder structure + optional delete originals)
- cross-platform builds (macOS + Windows)

Public repo refresh replaces the older Chronicle snapshot with the new standalone app line.
