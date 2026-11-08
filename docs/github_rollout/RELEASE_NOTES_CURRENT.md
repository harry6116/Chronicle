# Chronicle 1.1.6

Chronicle 1.1.6 updates Gemini reading engines, improves comic-page and handwriting recovery, makes API-key guidance clearer and keeps local Mac build output current.

## Improvements

- Automatic reading uses Gemini 3.8 Flash and Gemini 3.1 Pro Preview, selected by document type and difficulty. Handwriting and comics use 3.8 Flash; military records use 3.1 Pro Preview. Manual Gemini 2.5 choices remain available. Preview availability, processing time and provider charges can differ from the older engines.
- Handwriting and war-diary reading preserve page continuations and cancelled text more clearly. Printer imprints and longer acronyms are protected from inappropriate expansion.
- Reading transformations preserve HTML attributes, CSS focus colours, scripts and code examples.

- Comic scans preserve colour and use a full-page view with closer views of dense lettering and narration. Comic PDFs with small printed page dimensions are rendered at a more readable resolution.
- Comic reading scripts distinguish actual frames from numbered caption fragments, preserve printed spellings, and keep useful image descriptions as readable text rather than broken image references.
- Benchmark summaries distinguish structural accessibility grades from source-transcription accuracy. Difficult text and visual descriptions still need review against the original.
- Help now distinguishes Google One AI credits from the separate Gemini API billing used by Chronicle.
- The Google Gemini key field asks for one Google AI Studio API key. Its guidance no longer suggests adding a second authorisation key.
- Mac builds verify the app version, build stamp and signature, then refresh the configured distribution folder. Copied apps are checked file by file, including symbolic links.
- If verification fails during replacement, the previous distribution app is restored. Successful refreshes remove the temporary replacement backup.

Google authorisation keys, older Gemini keys, Claude keys and OpenAI keys remain supported. Saving a key stores it locally; provider access and billing are checked during extraction.
