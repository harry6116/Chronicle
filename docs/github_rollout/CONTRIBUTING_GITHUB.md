# Contributing to Chronicle

Thank you for contributing.

## Contribution Principles

- Accessibility first: preserve screen-reader usability and keyboard workflows.
- Reproducibility first: keep build and runtime behavior deterministic.
- Safety first: avoid changes that can increase data loss risk.
- Documentation parity: update docs whenever behavior changes.

## Development Setup

1. Install Python 3.11.
2. Install dependencies: `pip install -r requirements.txt`
3. Run GUI from source: `python chronicle_gui.py`
4. Validate local builds when relevant:
   - macOS: `./build.command`
   - Windows: `build_windows.bat`

## Pull Request Expectations

- Describe user-facing impact clearly.
- Include testing notes (what you ran and what passed).
- Include screenshots/log excerpts for UI changes where possible.
- Keep PR scope focused; prefer smaller PRs over large mixed changes.

## Required Checks Before Merge

- No syntax/runtime regressions in touched files.
- No obvious accessibility regressions in queue/task workflows.
- No breakage to build scripts or packaging entrypoints.
- Updated docs for behavior/config changes.

## Security and Privacy Notes

- Never commit API keys, tokens, credentials, or private data.
- Do not include real sensitive documents in test fixtures.
- Preserve existing warning language around provider-side processing.

## Code of Conduct

By participating, you agree to follow the repository `CODE_OF_CONDUCT.md`.

## License

By contributing, you agree that your contribution is licensed under the project license (GNU AGPLv3 unless otherwise specified).

