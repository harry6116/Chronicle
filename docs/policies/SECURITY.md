# Security Policy

This document describes Chronicle's current public security posture and reporting expectations.

## Supported Scope

Security reports are accepted for:

- `chronicle_gui.py`
- `chronicle_runtime.py`
- `chronicle_core.py`
- `chronicle_app/`
- build and packaging scripts
- published release artifacts
- local secret-handling and session-recovery behavior

## Reporting a Vulnerability

Please do not publicly disclose unpatched vulnerabilities.

A useful private report should include:

- a clear description of the issue
- affected component or file
- reproduction steps
- impact assessment
- proof-of-concept when safe and minimal
- any known mitigations or environment requirements

If no dedicated security mailbox is published, contact the repository owner privately and request coordinated disclosure handling.

## What to Report

Examples of in-scope reports:

- code execution vectors
- arbitrary file write or delete paths
- path traversal issues
- credential or API key exposure risks
- insecure local secret handling
- release artifact integrity or supply-chain issues
- unsafe archive extraction behavior
- session-recovery leaks that expose sensitive data unexpectedly

## What Not to Report

Out of scope unless they create a genuine security impact:

- model hallucination or extraction quality issues by themselves
- feature requests
- unsupported environment setup failures without security impact
- provider privacy terms that are controlled externally rather than by Chronicle's code

## Current Security Boundaries

Chronicle's present boundary model is:

- API keys are stored locally by the user-facing app.
- Keychain/keyring storage is preferred when available.
- Local app-data storage remains a fallback for some environments.
- Document content is transmitted to the user-selected provider for processing.
- Provider-side retention and training behavior is controlled by the provider and account tier, not by Chronicle.

## Responsible Use Notes

To reduce risk:

- keep dependencies current
- enable local git hooks with `bash tools/install_git_hooks.sh`
- avoid committing keys, session files, or machine-local config data
- test builds from clean paths before distribution
- verify staged Windows bundles do not include secrets

## Disclosure Process

1. acknowledge receipt
2. validate and triage severity
3. develop and test remediation
4. coordinate patch release timing
5. publish a brief advisory after the fix is available

## Safe Harbor

Good-faith, responsible testing is welcome. Do not exfiltrate data, damage systems, or disrupt user workflows while testing.
