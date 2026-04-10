# Provider Privacy and Tier Guide (Legal + Operational)

This guide is for repository documentation and user awareness. It is not legal advice.

## Core Boundary

Chronicle is a client application. It does not override provider retention/training policies.

When extraction runs:

- API keys are handled locally by Chronicle.
- When available, keys are saved to OS keychain/keyring (including macOS Keychain) as the preferred storage path.
- Local app-data/key files are fallback storage when keychain/keyring is unavailable.
- source content is sent to the selected provider API for processing.
- privacy, retention, and model-improvement behavior depend on provider policy and your account/tier/settings.

## Free vs Paid (General)

| Dimension | Free/Trial Tiers (Typical) | Paid API Tiers (Typical) |
| --- | --- | --- |
| Throughput/Quotas | Lower and more restrictive | Higher and more predictable |
| Rate Limits | Tighter; easier to throttle | Generally more generous |
| SLA/Support | Limited or none | Better support pathways |
| Data Controls | May be limited; policy varies | Usually stronger enterprise controls |
| Suitability for Sensitive Data | Often poor unless policy explicitly allows | Better, if contractual/privacy terms are appropriate |

Always verify current provider terms at time of use.

## Gemini-Specific Guidance (Practical)

### 1) Key Types and Project Context

- Ensure you are using the intended Google project and API key scope.
- Mis-scoped keys, disabled APIs, or project restrictions can cause auth/permission failures.

### 2) Free vs Paid Planning (Operational)

Google AI Studio Gemini API keys can work on Google's free tier, subject to current model availability, region support, quotas, and rate limits. Free-tier throughput can be acceptable for experimentation but is usually volatile for production runs.

Treat free Gemini access as a test path, not as dependable operating capacity. In practice, difficult PDFs, long queue runs, and dense magazine/newspaper jobs can still stop with quota or rate-limit errors before the document is finished, even when the app is otherwise working correctly.

The safest public guidance is simple: use paid Gemini API billing for sustained work and treat free-tier Gemini as best-effort only.

Practical planning examples (rough only, can change):

- Gemini 2.5 Pro: around 500 pages/day in light workloads.
- Gemini 2.5 Flash: around 1,000 pages/day in light workloads.

Actual throughput depends on:

- page complexity and scan quality
- retries/backoff behavior
- concurrent queue volume
- provider-side quota/rate changes

### 3) Privacy and Training Expectations

- Do not assume “API usage” automatically means “no training.”
- Confirm current Google terms and product-level privacy controls for your specific plan.
- For sensitive workloads, prefer paid plans/settings with explicit data-use guarantees.

### 4) Recommended Compliance Posture

- Treat free-tier usage as non-confidential unless terms explicitly guarantee otherwise.
- Classify documents before upload and route sensitive classes to approved provider/tier only.
- Keep audit logs of provider, model, date/time, and document class for governance.

## Anthropic/OpenAI Note

Anthropic should be treated differently from Google's free-tier Gemini guidance:

- Claude API access is separate from the consumer Claude.ai chat product.
- A free Claude.ai account is not enough for Chronicle API use.
- Even paid Claude chat plans do not automatically include Claude Console/API usage.
- Current Anthropic help guidance describes Claude Console/API use as requiring separate billing or prepaid credits.

OpenAI follows the same broad principle that account tier and settings determine privacy posture. Chronicle cannot enforce upstream provider policy.

## API Key Legal/Security Baseline

- Store keys locally only; prefer OS keychain/keyring when available; never commit to git.
- Rotate keys if exposed.
- Use least-privilege project/account scoping where possible.
- Restrict machine/user access to key files.

## Suggested README Disclaimer Snippet

“Chronicle stores API keys locally. When available, keys are saved to OS keychain/keyring (including macOS Keychain) as the preferred storage path, with local app-data/key files as fallback. Extracted content is sent to the selected provider for processing. Provider retention/training and confidentiality terms are controlled by your provider plan/settings. For sensitive data, use paid plans/settings with explicit privacy guarantees and verify provider terms before use.”
