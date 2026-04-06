# Contributing to Chronicle

Thank you for your interest in improving Chronicle.

## Contribution Priorities

Please preserve Chronicle's core values when contributing:

- accessibility-first interaction design
- semantic output quality
- portability of build and staging workflows
- strong fidelity rules for difficult historical material
- conservative handling of secrets and local machine data

## Development Expectations

When proposing changes:

1. document user-facing behavior changes clearly
2. avoid introducing non-ASCII encoding artifacts without reason
3. preserve queue accessibility and keyboard usability
4. keep build scripts portable across moved workspaces where practical
5. note any prompt-logic or provider-boundary changes in docs

## Submitting Changes

1. Fork the repository.
2. Create a feature branch.
3. Install local git hooks:
   - `bash tools/install_git_hooks.sh`
4. Ensure commits pass the local secret scan.
5. Submit a pull request with a clear explanation of the change, risk, and any testing performed.

## Licensing of Contributions

All contributions must be compatible with the GNU Affero General Public License v3.0.

By submitting code or documentation, you agree that your contribution may be redistributed under the project's AGPLv3 licensing terms unless explicitly stated otherwise.
