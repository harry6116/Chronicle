# Chronicle 1.0.2

This release adds Chronicle's first dedicated preset for comics, manga, and graphic novels, and tightens cleanup for dense magazine-style PDFs.

## Highlights

- New `Comics / Manga / Graphic Novels` preset for panel-based visual storytelling.
- Better accessible reading output for speech balloons, thought balloons, captions, visible sound effects, textless panels, and page-level art descriptions.
- Conservative support for manga reading flow, including right-to-left order when the page visibly calls for it.
- Comic PDFs now use one-page slices by default so page art, panel order, and visual context stay together.
- The comic preset stays on Chronicle's deep reading engine by default for stronger visual reasoning.
- New comic-specific quality checks require panel headings, image descriptions, non-empty panel sections, clean semantic wrapping, and no structural wrapper/fence regressions.
- Added a public-domain Little Nemo before/after showcase sample.
- Hardened magazine cleanup for leaked markdown headings, broken placeholder image tags, wrapper/comment noise, repeated paragraph blocks, and repeated running-head labels.

## Comics, Manga, And Graphic Novels

The new preset is designed for material where the reading order is visual rather than purely linear. Chronicle now asks the model to preserve panel sequence, capture dialogue and captions separately, call out visible `SFX`, describe meaningful artwork, and avoid inventing speaker names when the page does not make them clear.

For manga and translated comics, Chronicle keeps the order conservative: it follows right-to-left flow only when the page visibly supports that direction. Otherwise it uses the clearest visible page order.

## Validation

- Public/open comics validation reached `9/9 A+` under comic-specific checks.
- Additional local validation reached `12/12 A+` under the same checks without adding private source material to public-facing docs.
- Focused comics, routing, runtime policy, and benchmark scorecard tests passed.
- Magazine cleanup regressions were checked against the focused output-regression suite.

## Notes

Free Gemini API keys are useful for testing, but they may not be dependable for sustained hard-PDF work such as long magazines, newspapers, comics, graphic novels, and reruns. For demanding batches, use a paid or higher-quota provider key where possible.
