# Migration Notes: Old Public Repo -> Current Codebase

These notes help map the outdated public repository state to the current project organization.

## High-Level Change

- The old repository is no longer representative of current runtime behavior.
- The current codebase centers on:
  - `chronicle_gui.py` (primary GUI app)
  - shared extraction backend modules used by the GUI runtime
  - platform build scripts and PyInstaller packaging
  - expanded docs and testing artifacts

## Migration Priorities

1. Replace outdated implementation files with current maintained versions.
2. Keep only active build/update scripts.
3. Publish refreshed docs set aligned with current features.
4. Enable dual-platform CI for build verification.

## Current Feature Areas to Preserve in Public Repo

- Accessibility-focused queue controls and task actions.
- Scheduling, pause/resume, and session recovery.
- Scanner discovery and NAPS2 import.
- Output format controls with HTML default.
- Safety toggles:
  - preserve scanned folder structure
  - delete originals with explicit warning/confirmation

## Cleanup Guidance

- Remove stale files that reference retired behavior.
- Avoid multiple conflicting README/changelog copies.
- Ensure script names in docs match real files in root.
- Keep versioned release notes concise and accurate.

## Documentation Baseline for Public Repo

At minimum, include:

- `README.md` (from `PROJECT_OVERVIEW_GITHUB.md`, adapted)
- `CHANGELOG.md` (updated to launch version)
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- user help link/guide path that exists in repo
