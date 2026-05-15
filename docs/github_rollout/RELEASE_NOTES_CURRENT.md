Chronicle 1.0.9

Dense newspaper queue speed update:

- Dense historical newspaper pages now use adaptive Gemini image-strip sizing instead of a fixed four-strip split. Typical NLA broadsheet pages, from the National Library of Australia / Trove newspaper context, use two wider visual strips, cutting large queue request counts roughly in half while preserving the Gemini visual extraction path.
- The periodical chunk policy now checks dense scanned page weight before long-edition chunking, so 30+ page dense newspaper issues stay on single-page strip processing instead of falling back into slower multi-page PDF uploads.
- Chronicle also hard-guards the PDF processor so dense historical newspaper pages with a Gemini Pro route cannot accidentally bypass strip processing because of preset or queue chunk settings.
- Live smoke testing on a 36-page dense National Library of Australia newspaper issue completed through the real Gemini streaming inline-image route with two strips and 53k saved characters. Local smoke checks across the seven supplied dense NLA/Trove issues confirmed chunk policy `1` and two strips per page, reducing the set from 472 strip requests to 236.

Gemini Pro streaming and newspaper reliability update:

- Historical newspaper extraction still uses Gemini 2.5 Pro for deep visual scanning, including dense newspaper pages that need image-strip handling.
- Dense historical-newspaper image strips now use Gemini REST streaming where available, so Chronicle can begin receiving and saving useful output sooner instead of waiting for a full non-streaming response.
- Chronicle keeps the safer model-first routing contract: emergency PDF text-layer recovery remains off by default and must be deliberately enabled when raw embedded PDF text is acceptable.
- The normal historical-newspaper path no longer uses Trove/NLA article OCR by default. That route remains reserved for internal rescue testing because visual Gemini extraction is usually cleaner on dense scanned newspapers.
- Reader-facing newspaper HTML is cleaner: internal strip labels, provider tags, routing markers, and Chronicle processing labels are removed from saved output.
- Scan logs now describe newspaper work in plain language, such as page and part progress, without exposing internal transport details to readers.

Broader chunking and recovery improvements:

- Chronicle now has a shared trusted-chunk stream path for output that Chronicle has already converted into safe HTML/text chunks.
- Gemini REST string chunks are accepted by the shared stream handler, allowing practical Pro REST fallback paths and scanned-image inline requests to stream while preserving final cleanup behavior.
- Arbitrary model-generated HTML still waits for complete-chunk sanitization before writing, reducing the risk of leaking malformed wrappers, style blocks, or provider artifacts.
- Quiet model streams no longer hard-exit the app. Chronicle logs a network-stall alert and keeps the app open for recovery while bounded readers can still time out normally.
- OCR-heavy cleanup is safer on large newspaper outputs after replacing a high-risk repeated-paragraph regex path with bounded cleanup logic.

Validation and fixtures:

- Updated the current release-note fixture for version `1.0.9` and removed older accumulated release sections from this release body.
- Regression coverage confirms the Gemini Pro newspaper route avoids Trove OCR by default, dense newspaper strip output does not expose internal strip labels, and scan-log formatting stays user-readable.
- Current focused transport and active-tree parity suites passed across the primary, Beta, and Windows Beta trees.
- The primary regression suite passed (`512` tests, `OK`).
- A fresh Mac app bundle was rebuilt and deployed with build stamp `2026-05-15 19:10:37`.
