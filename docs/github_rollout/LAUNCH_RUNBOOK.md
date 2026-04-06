# Launch Runbook (Test Phase -> Public Rollout)

## Objective

Perform a controlled transition from private testing to public release.

Current target release: `Chronicle 1.0.0`

## T-48h

- Lock feature scope for the launch candidate.
- Confirm no unresolved high-severity defects.
- Run full local build verification:
  - macOS build command
  - Windows build command on a Windows host
- Final pass on README, help, legal, install, and accessibility docs.

## T-24h

- Create release candidate tag internally for `v1.0.0`.
- Run CI dual-platform build and verify artifact integrity.
- Validate basic smoke test from built binaries:
  - app opens
  - API key screen works
  - queue add/start flow works
  - output files are produced
- Confirm safety controls and portability notes are still accurate.

## T-4h

- Freeze non-launch commits.
- Prepare release body and short announcement.
- Verify repository permissions and release access.
- Confirm Windows staged bundle docs mention `build_windows.ps1`.
- Confirm the public release files are final:
  - `/Users/michaelsmac/Documents/Convert/Chronicle 1.0 mac.zip`
  - `/Users/michaelsmac/Documents/Convert/Chronicle 1.0 windows.zip`
- Rebuild the curated public repo snapshot with `Prepare_Public_Repo.command`.

## T-0 (Launch)

1. Push repository overhaul to public repo from the staged public snapshot only, not from the full private working tree.
2. Tag release `v1.0.0` and publish release notes.
3. Publish or attach `Chronicle 1.0 mac.zip` and `Chronicle 1.0 windows.zip`.
4. Announce release.

## T+2h

- Monitor issue tracker and CI status.
- Triage incoming reports.
- Patch critical regressions if needed.

## Immediate Post-Launch Checks

- validate Windows host build instructions from a clean path
- validate NVDA menu, queue, dialog, and log flow
- validate JAWS menu, queue, dialog, and log flow
