# Public Repo Bootstrap (Copy Order)

Use this when you are ready to replace content in the public Chronicle repository.

Suggested first public tag: `v1.0.0`

## Step 1: Core Repo Files

Copy/adapt these first:

1. `docs/github_rollout/README_PUBLIC_FINAL.md` -> `README.md`
2. `docs/github_rollout/CONTRIBUTING_GITHUB.md` -> `CONTRIBUTING.md`
3. `docs/github_rollout/SECURITY_GITHUB.md` -> `SECURITY.md`
4. `docs/github_rollout/LEGAL_DISCLAIMER_GITHUB.md` -> `DISCLAIMER.md` (or link from README)
5. `LICENSE`

## Step 2: Community Templates

Ensure these exist in the public repo:

- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `.github/ISSUE_TEMPLATE/config.yml`
- `.github/pull_request_template.md`

## Step 3: Build Workflow

Ensure the public repo contains:

- `build.command`
- `build_windows.bat`
- `build_windows.ps1`
- `stage_windows_bundle.command`
- `chronicle_app/`

Then verify green CI runs on push/PR/manual.

## Step 4: Release Messaging

Use:

- `docs/github_rollout/RELEASE_MESSAGES.md`
- `docs/github_rollout/LAUNCH_RUNBOOK.md`
- release assets from `/Users/michaelsmac/Documents/Chronicle Release Apps/`
  - `Chronicle 1.0 mac.zip`
  - `Chronicle 1.0 windows.zip`

## Step 5: Provider and Legal Notes

Link these in README and release notes:

- `docs/github_rollout/PROVIDER_PRIVACY_AND_TIER_GUIDE.md`
- `docs/github_rollout/LEGAL_DISCLAIMER_GITHUB.md`
