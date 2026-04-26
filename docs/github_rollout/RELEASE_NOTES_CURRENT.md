Chronicle 1.0.6
API-key safety was tightened across GUI logs, status echoes, crash capture, saved processing logs, support bundles, diagnostic JSON, and frozen CLI crash output with shared redaction for provider keys, bearer tokens, URL keys, and private-key blocks.
- Request caching now skips very large generated chunks and clears at the end of GUI runs, reducing memory retention after hard newspaper pages have already been written to output.
- The Gemini REST fallback no longer shells out through `curl`, keeping API keys inside the Python process instead of exposing them in process arguments.
- Dense scanned newspaper PDFs now stay on Gemini 2.5 Pro for the hard newspaper path, can render very heavy pages into ordered page strips, and avoid the Flash path for historical newspaper scans.
- Malformed NLA newspaper PDFs now avoid unnecessary PDF slice rebuilding whenever Gemini Pro rendered strips are available, including Flash-first runs that escalate to Pro; if strip OCR fails, Chronicle falls back to the local NLA OCR text layer instead of starting a runaway recovery pass.
- Long Gemini Pro newspaper requests now emit bounded "still waiting" checkpoints during both SDK and REST generation, so a difficult first page no longer looks silent while Chronicle is waiting for provider output.
- Gemini PDF upload, upload-status polling, streamed generation, and related cleanup calls now use explicit timeouts so Chronicle does not hang indefinitely before its stream heartbeat starts.
- A macOS background activity guard now runs during extraction so command-tabbing away from Chronicle does not let App Nap pause provider or network work.
- Queue preflight now opens every queued PDF before launch, even without a custom page range, and reports unreadable PDFs before the worker starts.
- Per-file setup failures now mark only that document as `Error`, log the traceback, and continue the remaining batch instead of killing the whole worker.
- Work-unit estimation failures now fall back to a conservative progress estimate instead of aborting the run before extraction starts.
