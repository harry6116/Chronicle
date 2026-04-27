# Launch Runbook

## Objective

Perform a controlled public release.

Current target release: `Chronicle 1.0.7`

## T-48h

- Lock feature scope for the launch candidate.
- Confirm no unresolved high-severity defects.
- Run full build verification:
  - macOS build command
  - Windows build command on a Windows host
- Final pass on README, help, legal, install, and accessibility docs.

## T-24h

- Create release candidate tag for `v1.0.7`.
- Run CI dual-platform build and verify artifact integrity.
- Validate basic smoke test from built binaries:
  - app opens
  - API key screen works
  - queue add/start flow works
  - output files are produced
- Confirm safety controls and portability notes are still accurate.

## T-4h

- Freeze non-launch commits.
- Prepare the release body only in `docs/github_rollout/RELEASE_NOTES_CURRENT.md`; do not update versioned draft release-note files for current messaging.
- Verify repository permissions and release access.
- Confirm Windows staged bundle docs mention `build_windows.ps1`.
- Confirm the public release files are final:
  - `Chronicle.mac.zip`
  - `Chronicle.windows.zip`
- Rebuild and review the public repository package.

## T-0 (Launch)

1. Push the verified public repository package.
2. Publish the GitHub release `v1.0.7`.
3. Publish or attach `Chronicle.mac.zip` and `Chronicle.windows.zip`.
4. Announce release.

## T+2h

- Monitor issue tracker and CI status.
- Triage incoming reports.
- Patch critical regressions if needed.

## Immediate Post-Launch Checks

- validate Windows host build instructions from a clean path
- validate NVDA menu, queue, dialog, and log flow
- validate JAWS menu, queue, dialog, and log flow
