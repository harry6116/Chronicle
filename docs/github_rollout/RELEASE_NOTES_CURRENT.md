# Chronicle 1.1.7

Chronicle 1.1.7 adds an optional newer reading engine, clearer handling of incomplete scans and another way to support the project.

## Improvements

- Gemini 4 Argon is available in Engine Override for difficult pages. Automatic presets retain their existing engines; the new option can still make transcription errors.
- Book reading preserves source quotation marks and no longer invents printed page numbers to fill gaps.
- Table-reading instructions preserve every column and meaningful empty cell. Uncertain handwriting and signatures remain explicit rather than being replaced with plausible text.
- Provider responses that hit a token limit are reported as incomplete. The command-line newspaper reader continues past the old character cutoff.
- Engine guidance describes the selected current model rather than falling back to older Gemini help.
- Ko-fi joins GitHub Sponsors, Buy Me a Coffee and PayPal. About Chronicle includes a labelled Ko-fi action and links to chroniclevir.com.
- Website examples pair source descriptions with accessible saved results and explain known errors. Donations remain optional.

Difficult handwriting, small comic lettering and specialist scripts still need checking against the original. These changes do not certify every extraction as accurate.
