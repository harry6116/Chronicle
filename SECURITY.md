# Security Policy

## Supported Scope

Security reports are accepted for the actively maintained codebase and release artifacts.

## Reporting a Vulnerability

Please do not open public issues for undisclosed vulnerabilities.

Report privately with:

- clear description of the issue
- affected file/component
- reproduction steps
- impact assessment
- proof-of-concept (if safe)

Current private reporting path:

- `chronicle.app+support@gmail.com`

If a dedicated security mailbox is introduced later, update this policy to point security reports there instead of the general support inbox.

## What to Report

- code execution vectors
- credential/API key exposure risks
- unsafe file handling/deletion paths
- path traversal or arbitrary write/delete behavior
- CI/CD supply-chain or artifact integrity concerns

## What Not to Report

- provider-model hallucination quality issues (non-security)
- feature requests
- unsupported runtime environments without a security impact

## Disclosure Process

1. Acknowledge report receipt.
2. Validate and triage severity.
3. Develop and test remediation.
4. Coordinate patch release and disclosure timing.
5. Publish advisory summary when fixed.

## Safe Harbor

Good-faith research and responsible disclosure are welcome. Do not exfiltrate private data or disrupt services while testing.
