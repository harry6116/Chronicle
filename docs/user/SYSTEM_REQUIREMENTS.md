# Chronicle System Requirements

This document defines practical minimum and recommended requirements for running Chronicle reliably.

## Supported Operating Systems

Chronicle currently targets desktop use on:

- macOS 12 Monterey or newer
- Windows 10 or newer

Chronicle is built and documented for 64-bit desktop systems only. Linux and mobile platforms are not currently supported release targets.

## Minimum vs Recommended at a Glance

For online provider mode:

- Minimum: 8 GB RAM, 64-bit dual-core CPU, stable internet, and at least 5 GB free disk space
- Recommended: 16 GB RAM or more, modern 4+ core CPU, SSD storage, and at least 20 GB free space

For Private Offline Mode after installing Ollama and the recommended local model:

- Constrained/emergency: 8 GB RAM may work for very small, clean, short-document offline runs, but users should expect slower performance or swapping
- Recommended: 16 GB RAM or more for regular offline use
- Comfortable: 24-32 GB RAM for repeated offline batches, larger PDFs, or long sessions
- Disk: at least 12 GB free for the local model, Ollama, and working room
- Recommended disk: 20 GB or more free SSD space

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
| RAM | 8 GB for online mode; 8 GB offline is constrained/emergency-only | 16 GB+; 24-32 GB for comfortable repeated offline work |
| Storage free space | 5 GB for Chronicle; additional space for the local Ollama model | 20 GB+ SSD |
| Network | Stable internet for online providers; not required for Private Offline Mode | Low-latency reliable broadband for online mode |

## Source Mode Requirements

- Python 3.11
- Dependencies from `requirements.txt`
- Local write access to project directory (config/session/output files)

## Packaging and Build Notes

- macOS packaged builds are produced as `Chronicle.app`
- Windows packaged builds are produced as `Chronicle.exe`
- End users should prefer packaged builds over source mode whenever possible
- Frozen app users do not need to install Python separately
- Private Offline Mode requires a user-managed Ollama installation with `qwen2.5vl:7b` installed

## Accessibility and Runtime Expectations

- Chronicle is designed for desktop screen-reader workflows, including VoiceOver on macOS and NVDA/JAWS validation targets on Windows
- A reliable internet connection is required for online provider mode because extraction work is sent to the selected provider API
- At least one supported provider API key is required for online extraction
- If no API keys are configured, Chronicle can still run Private Offline Mode after Ollama is installed and `ollama pull qwen2.5vl:7b` has completed

## Workload Guidance

| Workload Type | Recommended RAM | Notes |
| --- | --- | --- |
| Small batches (text/docs) | 8 GB | Suitable for light extraction |
| Mixed medium batches | 16 GB | Better stability and throughput |
| Large PDFs / long sessions / merge-heavy | 16-32 GB | Strongly recommended for comfort |
| Private Offline Mode, short clean PDFs | 16 GB recommended; 8 GB emergency-only | Best for modern typed PDFs and sensitive forms |
| Private Offline Mode, repeated batches | 16-32 GB | Keep queues small on lower-memory systems |

## Low-Memory Operation

Chronicle includes low-memory controls for constrained systems:

- Enable **Low-Memory Mode** in Preferences.
- Keep queue sizes smaller.
- Avoid large merge jobs on low-RAM machines.
- Use memory telemetry when diagnosing long-run usage.
- In Private Offline Mode, prefer short documents, HTML or TXT output, and one job at a time on 8 GB systems.
- Close other heavy apps before starting offline scans on constrained machines.

Chronicle keeps offline requests conservative by default:

- one parallel offline request at a time
- small PDF page batches instead of one huge local model request
- temporary rendered PDF page images are cleaned after the offline request completes

## Temp Files and Working Space

Chronicle uses temporary working files during extraction, and user-visible temp behavior now differs slightly by output type.

- Streamable outputs such as HTML, TXT, and Markdown write directly to their normal `.tmp` working file during the run.
- DOCX, PDF, EPUB, JSON, and CSV runs now also create a readable sidecar file ending in `.progress.txt.tmp` in the destination folder so users can inspect progress while the final file is still being assembled.
- These sidecar files are expected behavior, not corruption.
- Successful runs remove the sidecar automatically after final save.
- Failed or interrupted runs may leave the sidecar behind intentionally for recovery/review.
- Keep enough free disk space for source files, final outputs, processing logs, and temporary progress files during long or merge-heavy runs.
- Private Offline Mode also needs working space for temporary rendered page images and local model runtime files. Keep at least 12 GB free, and prefer 20 GB or more.

## API and Provider Requirements

At least one valid API key is required:

- Gemini (`gemini`)
- Claude (`claude`)
- OpenAI (`openai`)

This requirement applies to online provider mode. Private Offline Mode does not require an API key, but it does require a local Ollama installation with `qwen2.5vl:7b` available.

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
  - generally clearer privacy controls for production workloads

### Gemini Note

Gemini API keys from Google AI Studio can work on Google's free API tier, subject to current model availability, quota, rate limits, and region support. Google documents separate Free and higher-quota Gemini API tiers, and some Gemini models are explicitly available free of charge on the free tier. In practice, this means a Gemini key may be enough for Chronicle testing without provider billing enabled. Production and sensitive workloads should still generally use provider plans/settings with explicit privacy guarantees.

### Claude Note

Claude API access should be treated differently from Gemini. Anthropic's current help center says Claude Console/API access is separate from Claude.ai chat subscriptions, and Console/API usage requires Console billing or credits. In practice, a Claude free chat account is not enough for Chronicle API use, and a Claude chat subscription does not automatically provide API access. For Chronicle, think of Claude API access as a separate developer setup, not as part of the ordinary Claude chat product.

## Legal and Privacy Reminder

Chronicle stores keys locally, but extracted content is processed by the selected provider API. Chronicle cannot enforce provider retention/training policy. You are responsible for compliance, confidentiality, and data-handling obligations for your workload.

Chronicle is designed to improve accessibility and downstream usability, but final legal/accessibility sign-off for public distribution should still include human review in the target reading environment.
