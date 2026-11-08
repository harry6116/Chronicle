# Chronicle 1.1.5

Chronicle 1.1.5 supports Google’s new authorisation keys and improves API-key entry for Gemini, Claude and OpenAI.

## API keys

- Save new Google AI Studio authorisation keys, usually beginning with `AQ.`, in **File > API Keys...**. Older `AIza` keys remain supported.
- Key entry no longer assumes a fixed key prefix or length. Gemini, Claude and OpenAI fields check for unsupported characters and explain how to correct a pasted key. An error returns focus to the affected field and selects its text for replacement.
- Existing saved keys and settings are preserved. Unused provider fields may stay blank, including all three fields for Private Offline Mode.
- Saving keys does not contact a provider or verify authentication, permissions or billing. The confirmation message now explains this distinction.
- Logs and support bundles also redact Google’s new authorisation-key format. Existing OpenAI and Claude key redaction remains supported.
- Updated help and setup instructions link to each provider’s API-key page and explain project billing and separate API access.

The Chronicle website, email contact, update checks and Private Offline Mode remain available.
