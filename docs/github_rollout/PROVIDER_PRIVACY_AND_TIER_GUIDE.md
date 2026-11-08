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

Google AI Studio now creates authorisation keys by default. Chronicle accepts these keys (usually beginning with `AQ.`) and older `AIza` keys without a fixed prefix or length requirement. Paste the key into **File > API Keys... > Google Gemini API Key**. See [Google’s API-key guide](https://aistudio.google.com/docs/api-key). Saving only stores the key locally; provider authentication, permissions, quota and billing are checked during extraction. Replacing a key does not transfer credits between Google Cloud projects.

- Ensure you are using the intended Google project and API key scope.
- Mis-scoped keys, disabled APIs, or project restrictions can cause auth/permission failures.

Google One AI credits, including purchased credit packs, are separate from Gemini API billing. They do not fund Chronicle’s requests. Subscription benefits in the AI Studio web interface also differ from usage through an API key. Check billing for the Google Cloud project associated with the key. See [Google’s plan and credit explanation](https://aistudio.google.com/docs/google-ai-plans).

### 2) Free vs Paid Planning (Operational)

Google AI Studio Gemini API keys can work on Google's free tier, subject to current model availability, region support, quotas, and rate limits. Free-tier throughput can be acceptable for experimentation but is usually volatile for production runs.

Treat free Gemini access as a test path, not as dependable operating capacity. In practice, difficult PDFs, long queue runs, and dense magazine/newspaper jobs can still stop with quota or rate-limit errors before the document is finished, even when the app is otherwise working correctly.

The safest public guidance is simple: use a higher-quota Gemini API setup for sustained work and treat free-tier Gemini as best-effort only.

There is no fixed pages-per-day allowance in Chronicle. Check the quotas shown for your provider account and model.

Actual throughput depends on:

- page complexity and scan quality
- retries/backoff behavior
- concurrent queue volume
- provider-side quota/rate changes

### 3) Privacy and Training Expectations

- Do not assume “API usage” automatically means “no training.”
- Confirm current [Google Gemini API terms](https://ai.google.dev/gemini-api/terms) and product-level privacy controls for your specific plan.
- For sensitive workloads, prefer provider plans/settings with explicit data-use guarantees.

### 4) Recommended Compliance Posture

- Treat free-tier usage as non-confidential unless terms explicitly guarantee otherwise.
- Classify documents before upload and route sensitive classes to approved provider/tier only.
- Keep audit logs of provider, model, date/time, and document class for governance.

## Anthropic/OpenAI Note

Anthropic should be treated differently from Google's free-tier Gemini guidance:

- Claude API access is separate from the consumer Claude.ai chat product.
- A free Claude.ai account is not enough for Chronicle API use.
- Claude chat subscriptions do not automatically include Claude Console/API usage.
- Current Anthropic help guidance describes Claude Console/API use as requiring separate billing or credits.

OpenAI follows the same broad principle that account tier and settings determine privacy posture. Chronicle cannot enforce upstream provider policy.

## OpenAI and Claude Key Setup

Use a project API key from the [OpenAI developer platform](https://platform.openai.com/api-keys). OpenAI API access and billing are separate from ChatGPT access. See [OpenAI’s authentication reference](https://developers.openai.com/api/reference/overview#authentication).

For Claude, create a key in the [Claude Console](https://platform.claude.com/settings/keys) scoped to the workspace you intend to use. Workspace-scoped keys select the workspace without an additional ID. An unscoped key requires an extra workspace-ID header, which Chronicle’s key vault does not configure. Existing workspace API keys remain supported by Claude, although its current guidance prefers personal or service-account keys. See [Claude’s authentication guide](https://platform.claude.com/docs/en/manage-claude/authentication). Choose the key type and scope appropriate to your account; Claude chat access does not provide API access.

## API Key Legal/Security Baseline

- Store keys locally only; prefer OS keychain/keyring when available; never commit to git.
- Rotate keys if exposed.
- Use least-privilege project/account scoping where possible.
- Restrict machine/user access to key files.

## Suggested README Disclaimer Snippet

“Chronicle stores API keys locally. When available, keys are saved to OS keychain/keyring (including macOS Keychain) as the preferred storage path, with local app-data/key files as fallback. Extracted content is sent to the selected provider for processing. Provider retention/training and confidentiality terms are controlled by your provider plan/settings. For sensitive data, use provider settings with explicit privacy guarantees and verify provider terms before use.”
