# Mac Tooling Inventory

This folder contains macOS launchers for Chronicle build, release, public-repo, and diagnostic workflows.

## Release-Critical

- `build.command` and `build_mac.py`: build the macOS app bundle.
- `Package_Release_Apps.command`: verifies offline-ready Mac and Windows app folders, creates `Chronicle.mac.zip` and `Chronicle.windows.zip`, and rebuilds the curated public release snapshot.
- `Publish_GitHub_Release.command`: creates or updates the GitHub release and uploads the release ZIPs. The default tag is derived from `docs/github_rollout/RELEASE_NOTES_CURRENT.md`.
- `Update_GitHub_Release_Notes_Only.command`: updates an existing GitHub release body. The default tag is derived from `docs/github_rollout/RELEASE_NOTES_CURRENT.md`.
- `release_helpers.sh`: shared release-version parsing helpers for Mac release scripts.

## Public Repository

- `Prepare_Public_Repo.command`: rebuilds the curated public snapshot only. This remains useful for checking the snapshot without packaging release ZIPs.
- `Push_Public_Repo.command`: copies the prepared public snapshot into the public repo clone, commits it, and pushes it.
- `Docs_Only_Public_Update.command`: one-step docs/minor public snapshot update and push. Use this for public docs changes that do not need new app ZIPs.

## Build And Artifact Helpers

- `Run_Windows_GitHub_Build.command`: commits/pushes private-repo changes and watches the Windows GitHub Actions build.
- `Download_Latest_Windows_Artifact.command`: downloads the latest successful Windows build artifact for the current branch.
- `Check_GitHub_Download_Counts.command`: reports GitHub release download counts.

## Test And Diagnostic Helpers

- `run_a11y_harness.command`
- `run_native_queue_harness.command`
- `mac_native_queue_harness.py`
- `run_packaged_memory_stress.command`
- `Run_Safe_Batch.command`

## Maintenance Helpers

- `Sync_from_GitHub.command`
- `Update_Samples.command`

## Legacy Or Lower-Priority

- `Push_to_GitHub.command`: broad private/canonical repo commit-and-push helper. Prefer narrower release/public scripts when doing release work.

## Generated Files

Do not keep generated Finder metadata or Python cache directories in this folder. If they appear, they can be deleted.
