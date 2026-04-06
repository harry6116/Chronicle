# Chronicle System Requirements

This document defines practical minimum and recommended requirements for running Chronicle reliably.

## Supported Operating Systems

Chronicle currently targets desktop use on:

- macOS 12 Monterey or newer
- Windows 10 or newer

Chronicle is built and documented for 64-bit desktop systems only. Linux and mobile platforms are not currently supported release targets.

## Minimum vs Recommended at a Glance

For most users:

- Minimum: 8 GB RAM, 64-bit dual-core CPU, stable internet, and at least 5 GB free disk space
- Recommended: 16 GB RAM or more, modern 4+ core CPU, SSD storage, and at least 20 GB free space

For larger extraction jobs:

- Long manuals, merge-heavy sessions, or large PDF audits are much more comfortable on 16-32 GB RAM systems
- Large office-report remediation, appendix-heavy government PDFs, and long-form book reconstruction are also much more comfortable on 16-32 GB RAM systems
- Older 8 GB machines can still run Chronicle, but should favor smaller queues and Low-Memory Mode

## Runtime Modes

- **Frozen app mode**: packaged app (`Chronicle.app` / `Chronicle.exe`)
- **Source mode**: run with Python (`python chronicle_gui.py`)

## Platform Requirements

| Category | Minimum | Recommended |
| --- | --- | --- |
| Operating system | macOS 12+ or Windows 10+ | Latest supported macOS / Windows 11 |
| CPU | 64-bit dual-core | Modern 4+ core CPU |
| RAM | 8 GB | 16 GB+ |
| Storage free space | 5 GB | 20 GB+ SSD |
| Network | Stable internet | Low-latency reliable broadband |

## Source Mode Requirements

- Python 3.11
- Dependencies from `requirements.txt`
- Local write access to project directory (config/session/output files)

## Packaging and Build Notes

- macOS packaged builds are produced as `Chronicle.app`
- Windows packaged builds are produced as `Chronicle.exe`
- End users should prefer packaged builds over source mode whenever possible
- Frozen app users do not need to install Python separately

## Accessibility and Runtime Expectations

- Chronicle is designed for desktop screen-reader workflows, including VoiceOver on macOS and NVDA/JAWS validation targets on Windows
- A reliable internet connection is required because extraction work is sent to the selected provider API
- At least one supported provider API key is required before extraction can run

## Workload Guidance

| Workload Type | Recommended RAM | Notes |
| --- | --- | --- |
| Small batches (text/docs) | 8 GB | Suitable for light extraction |
| Mixed medium batches | 16 GB | Better stability and throughput |
| Large PDFs / long sessions / merge-heavy | 16-32 GB | Strongly recommended for comfort |

## Low-Memory Operation

Chronicle includes low-memory controls for constrained systems:

- Enable **Low-Memory Mode** in Preferences.
- Keep queue sizes smaller.
- Avoid large merge jobs on low-RAM machines.
- Use memory telemetry when diagnosing long-run usage.

## Temp Files and Working Space

Chronicle uses temporary working files during extraction, and user-visible temp behavior now differs slightly by output type.

- Streamable outputs such as HTML, TXT, and Markdown write directly to their normal `.tmp` working file during the run.
- DOCX, PDF, EPUB, JSON, and CSV runs now also create a readable sidecar file ending in `.progress.txt.tmp` in the destination folder so users can inspect progress while the final file is still being assembled.
- These sidecar files are expected behavior, not corruption.
- Successful runs remove the sidecar automatically after final save.
- Failed or interrupted runs may leave the sidecar behind intentionally for recovery/review.
- Keep enough free disk space for source files, final outputs, processing logs, and temporary progress files during long or merge-heavy runs.

## API and Provider Requirements

At least one valid API key is required:

- Gemini (`gemini`)
- Claude (`claude`)
- OpenAI (`openai`)

Operational guidance:

- Gemini is still the safest default for heavy PDF workloads in Chronicle.
- Chronicle's broader `Everyday Mixed Documents`, `Work Reports / Office Documents`, and `Government Reports / Public Records` presets may spend more effort rebuilding headings, lists, and tables from damaged source files than earlier conservative defaults.
- Claude is now the strongest non-Gemini PDF option in Chronicle because the app prefers Anthropic Files API transport for PDF slices when available.
- OpenAI remains supported, but Chronicle's current OpenAI integration is still less capable for PDFs than the Gemini and Claude paths.
- Dense short historical newspaper PDFs may now process in one-page slices when Chronicle detects unusually heavy file size per page; the processing log will call this out explicitly instead of leaving the slowdown unexplained.
- If a provider key is missing, Chronicle's automatic engine selection now skips that provider instead of trying to use it anyway.
- With `Engine Override` left on `Automatic`, Chronicle can start supported easy PDFs on `Gemini 2.5 Flash` first and keep `Gemini 2.5 Pro` reserved for harder documents or page-level escalation.

### Free vs Paid (Operational + Policy)

- **Free or trial access**:
  - usually best for testing, not dependable production use
  - lower quotas, stricter rate limits, and more variable availability
  - privacy posture may be weaker or less predictable depending on the provider
- **Paid API access**:
  - higher throughput and better operational consistency
  - generally clearer privacy/commercial controls for production workloads

### Gemini Note

Gemini API keys from Google AI Studio can work on Google's free API tier, subject to current model availability, quota, rate limits, and region support. Google documents separate Free and Paid Gemini API tiers, and some Gemini models are explicitly available free of charge on the free tier. In practice, this means a Gemini key may be enough for Chronicle testing without paid billing enabled. Production and sensitive workloads should still generally use paid plans/settings with explicit privacy guarantees.

### Claude Note

Claude API access should be treated differently from Gemini. Anthropic's current help center says Claude Console/API access is separate from Claude.ai chat subscriptions, and Console/API usage requires Console billing or prepaid credits. In practice, a Claude free chat account is not enough for Chronicle API use, and even a paid Claude chat subscription does not automatically provide API access. For Chronicle, think of Claude API access as a separate paid developer setup, not as part of the ordinary Claude chat product.

## Legal and Privacy Reminder

Chronicle stores keys locally, but extracted content is processed by the selected provider API. Chronicle cannot enforce provider retention/training policy. You are responsible for compliance, confidentiality, and data-handling obligations for your workload.

Chronicle is designed to improve accessibility and downstream usability, but final legal/accessibility sign-off for public distribution should still include human review in the target reading environment.
