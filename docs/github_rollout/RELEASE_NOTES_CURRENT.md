# Chronicle 1.1.9

Chronicle 1.1.9 adds a separate automatic reading option that uses Flash first and gives flagged scan pages an Argon retry.

## Highlights

- Choose Automatic Flash/Argon (PDFs and images) in Preferences, under Engine Override. The existing Automatic setting keeps its preset-based behaviour.
- Each scan page starts with Gemini 3.8 Flash. A flagged page gets one retry pass with Gemini 4 Argon. The next page starts with Flash again.
- Argon retries use additional API credit and time. Automatic checks cannot catch every confidently wrong reading; compare important results with the source.

## How it works

A page can be flagged when its reading is empty, contains explicit uncertainty, has a document-structure warning, or reaches the model's output limit. These are warning signals rather than a complete measure of page difficulty or accuracy.

Chronicle keeps the first reading out of the final output until the retry decision is complete. It writes the selected reading once. If an optional Argon retry fails, an already complete Flash reading is retained for review. A page without a complete reading is reported as an error. Automatic-page logging reports engine and review needs without assigning a transcription-accuracy grade. Remaining uncertainty stays visible. Originals are retained when this mode leaves pages marked for review, even if deletion after reading is enabled.

The new option requires a Gemini API key. It handles PDF pages and supported image files. Other file formats use Flash without automatic page escalation. Existing manual model choices and Private Offline Mode remain available. Existing saved preferences are preserved; select the new option explicitly to use it. For files already queued, select them and use Apply Current Settings To Selected.

The earlier source-fidelity, original-preserving reading aids, table handling and incomplete-response safeguards are retained. The new routing does not certify every scan as accurate.
