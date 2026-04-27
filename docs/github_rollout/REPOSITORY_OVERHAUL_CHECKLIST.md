# Repository Overhaul Checklist (For `harry6116/Chronicle`)

Use this checklist when replacing the outdated public repository with the current Chronicle codebase.

Target public app release: `1.0.7`

## Phase 1: Pre-Migration Controls

- [ ] Freeze public repo updates during migration window.
- [ ] Create a full backup of current public repo state.
- [ ] Confirm the release candidate is clean and tested.
- [ ] Build and review the public repository package before publishing.
- [ ] Confirm packaged release assets exist and are the intended public files:
  - [ ] `Chronicle.mac.zip`
  - [ ] `Chronicle.windows.zip`
- [ ] Confirm build outputs are reproducible for:
  - [ ] macOS
  - [ ] Windows
- [ ] Confirm updated docs/legal pack is approved.

## Phase 2: Structure and Content Replacement

- [ ] Replace outdated root files with current maintained versions.
- [ ] Add/update documentation set:
  - [ ] top-level `README.md`
  - [ ] changelog
  - [ ] help/user guide references
  - [ ] accessibility/compliance docs
  - [ ] legal disclaimer / security / contributing docs
- [ ] Remove obsolete scripts and dead files no longer used.
- [ ] Ensure build scripts match current code paths.
- [ ] Ensure Windows docs mention `build_windows.ps1` as part of the build flow.

## Phase 3: Build and CI Verification

- [ ] Confirm build commands succeed:
  - [ ] `./build.command`
  - [ ] `build_windows.bat` (on Windows host)
- [ ] Confirm staged Windows bundle includes:
  - [ ] `build_windows.bat`
  - [ ] `build_windows.ps1`
  - [ ] `chronicle_app/`
  - [ ] `assets/`
  - [ ] `docs/`
- [ ] Add/verify GitHub Actions workflow for dual builds.
- [ ] Confirm artifact upload paths are correct.

## Phase 4: Release Preparation

- [ ] Draft release notes in `RELEASE_NOTES_CURRENT.md`.
- [ ] Prepare version tag `v1.0.7` and changelog entry.
- [ ] Confirm API/privacy wording is current and accurate.
- [ ] Confirm install and quick-start instructions are current.
- [ ] Validate links (donation, docs, issue tracker).
- [ ] Confirm license text and contribution language consistently state AGPLv3.

## Phase 5: Public Launch

- [ ] Push updated repository state.
- [ ] Create release tag `v1.0.7` + publish release notes.
- [ ] Attach or link `Chronicle.mac.zip` and `Chronicle.windows.zip`.
- [ ] Post short announcement.
- [ ] Open post-release tracking issue for early bug reports.
