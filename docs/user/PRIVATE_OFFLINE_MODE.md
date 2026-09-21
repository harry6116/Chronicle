# Private Offline Mode

Private Offline Mode lets Chronicle attempt document extraction without uploading the document to Gemini, Claude, OpenAI, or any other online provider. It is intended for moments when privacy or connectivity matters more than using the strongest cloud model.

Use it when the document must stay on the computer, the internet is unavailable, or a user needs an emergency accessible scan rather than no scan at all.

Private Offline Mode requires a user-managed local Ollama installation. Install and open Ollama, then make `qwen2.5vl:7b` available with:

```bash
ollama pull qwen2.5vl:7b
```

When the Ollama command-line tool is available, Chronicle can ask Ollama to install the model from inside the app.

## What Works Best Offline

Offline mode works best when the source is visually clear, modern, typed, and not too visually complex.

Best candidates:

- clean modern typed PDFs
- bank statements and transaction summaries with clear print
- invoices, receipts, statements, and account notices
- typed medical forms and claim forms
- typed legal forms, contracts, notices, and regulations
- government forms with clear labels and checkboxes
- tax records and identity-like forms with clear fields
- simple product manuals and operation guides
- typed letters, memos, and short reports
- text-backed PDFs where the embedded text is already usable

These are the documents users can often get away with offline, especially if the goal is reviewable HTML or text in an outage.

## What Works Acceptably Offline With Care

These sources may be usable offline, but users should review them more carefully:

- moderately complex tables
- forms with many boxes, checkmarks, and repeated labels
- dense legal pages with exact numbering requirements
- short medical or insurance forms
- simple academic articles
- manuals with light diagrams
- clean scanned pages with strong contrast
- single-page or short multi-page excerpts

For these, offline mode can produce useful accessible structure, but users should verify numbers, names, dates, totals, checkbox states, and table relationships before relying on the output.

## What To Avoid Offline

Use online mode when accuracy, layout reasoning, or image understanding is critical.

Avoid offline mode for:

- degraded handwriting
- cursive diaries and personal manuscripts
- very faded scans
- skewed, stained, torn, or low-contrast pages
- historical newspapers and dense broadsheets
- magazines with complex multi-column design
- comics, manga, graphic novels, and panel-based storytelling
- long books where paragraph continuity across many pages matters
- mathematical papers where equations must be exact
- complex tables spanning pages
- diagrams where labels, arrows, and relationships must be interpreted
- photos, maps, charts, and technical drawings that need detailed visual description
- public accessibility remediation where final WCAG or legal sign-off is required

Offline mode can still be tried for these in an emergency, but the result should be treated as a rough draft.

## Advantages

- Documents stay on the local computer.
- It still works when there is no internet connection.
- It gives users a private fallback for sensitive material.
- It avoids provider quotas, rate limits, and temporary online-provider outages.
- It uses the user's local Ollama installation rather than a Chronicle-hosted offline pack.
- Users can enable it by installing Ollama and running `ollama pull qwen2.5vl:7b`.
- It uses Chronicle's accessibility cleanup, including semantic HTML, headings, lists, tables, and readable form-control markers.

## Disadvantages

- It is usually less accurate than the best online Gemini path on hard documents.
- It may be slower than online mode on some machines.
- It uses more local RAM, disk, and CPU/GPU resources than online mode.
- It is not the right default for difficult scans, handwriting, newspapers, comics, or complex visual documents.
- It should not be treated as final legal, medical, financial, or accessibility sign-off without human review.

## Accessibility Behavior

Private Offline Mode follows the same accessibility direction as Chronicle's online output:

- semantic HTML is preferred for review
- reading order is prioritized over visual facsimile layout
- headings, paragraphs, lists, definition lists, and tables are used where helpful
- blank form controls are converted into readable markers such as `[Checkbox: Empty]`, `[Radio Button: Selected]`, and `[Text Field: Empty]`
- generated interactive controls such as `input`, `textarea`, `select`, and `button` are removed from saved document HTML
- prompt leakage, model reasoning leakage, empty list items, and invented remote image sources are cleaned before output is saved

Human review is still required for final accessibility compliance, especially before distributing a document publicly or relying on it for legal, medical, educational, or workplace accommodation purposes.

## Practical System Requirements

Private Offline Mode requires a local Ollama installation with `qwen2.5vl:7b` installed. Chronicle does not ship the offline runtime or model pack.

Recommended for Private Offline Mode:

- RAM: 16 GB or more
- Constrained/emergency RAM: 8 GB may work for very small, clean, short-document runs, but users should expect slower performance or swapping
- Comfortable RAM for long or repeated offline work: 24-32 GB
- Free disk space: at least 12 GB for the app package plus working room
- Recommended free disk space: 20 GB or more
- CPU: modern 4+ core CPU recommended
- Storage: SSD strongly recommended

Chronicle limits offline processing to one parallel request. Offline PDF processing also uses small page batches so Chronicle does not try to process large PDFs as one huge local model request.

On lower-memory systems, use Private Offline Mode conservatively:

- process short documents first
- avoid large queues
- avoid merge-heavy offline runs
- prefer HTML or TXT output
- close other heavy apps before starting
- use online mode for difficult documents when confidentiality and connectivity allow it

## Current Offline Validation

Current 1.0.2 offline testing favors the `qwen2.5vl:7b` local vision-language model.

Validation results from the current test cycle:

- full offline benchmark suite: 13 cases, average score 99.43, average grade A
- emergency-usable benchmark cases: 12/13
- private A-range benchmark cases: 11/13
- modern typed PDF cases: 4/4 A+
- tested modern typed sources included a legal/financial regulation page, an academic article page, a product manual page, and an operation manual page
- blank medical-form cleanup reached A+ accessible HTML with generated form controls removed
- packaged-app live tests completed successfully on a medical claim example and a government form example

This means Private Offline Mode is suitable as a serious emergency/private fallback for clear typed documents. It does not mean offline mode replaces the best online model for every document family.

The one persistent miss in the full suite was a handwriting-heavy war-diary cover page that produced too little text to count as emergency-usable. That is why the app and this guide explicitly steer handwriting, old newspapers, comics, magazines, dense image layouts, and other visually complex sources back to Online AI Mode whenever confidentiality and connectivity allow it.

## Local Model Comparison

Chronicle currently recommends `qwen2.5vl:7b` because it is the best tested balance of output quality, speed, and local model size for this release line.

Comparison notes from the current offline model check:

- `qwen2.5vl:7b`: about 6.0 GB locally; reached 99.43 average on the 13-case offline suite with 12/13 emergency-usable cases.
- `qwen3-vl:8b`: about 6.1 GB locally and promising on paper, but under Chronicle's current local runtime contract it averaged 80.48 on the same 13-case suite, produced no emergency-usable cases at the normal output budget, and was much slower. A larger output budget helped a tiny text-only probe, but it was still too slow and reasoning-heavy to make a safe default.
- Larger 12B-class vision candidates increase package size and did not improve the overall offline grade enough to justify the footprint.
- An 11B Llama vision candidate was rejected for this package line because it did not load reliably in the local Ollama runtime path.

The practical conclusion is simple: use the installed local model for private, clean, typed documents; use Online AI Mode for the hard visual families Chronicle is otherwise known for.
