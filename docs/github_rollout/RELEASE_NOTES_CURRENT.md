# Chronicle 1.1.8

Chronicle 1.1.8 resolves conflicting scanning instructions so source text and the selected output format receive clearer priority.

## Scanning improvements

- Source quotation marks, diacritics and mathematical symbols are preserved instead of being changed solely for ASCII compatibility. Punctuation cleanup retains source word hyphens.
- Optional currency and abbreviation reading aids keep the original text alongside an unambiguous spoken expansion. Clinical shorthand, acronyms, initials and reference identifiers remain unchanged.
- CSV, Markdown and Word instructions no longer compete with generic plain-text or HTML table instructions. Table labels do not invent subtotals, date ranges or source headers.
- Newspaper strip recovery shares the source-boundary and character-fidelity safeguards used by the main reader and checks every readable region instead of accepting partial coverage.
- Book paragraph recovery follows visible paragraph structure. Familiar-looking words are not a reason to replace visible source letters.
- Academic prompts preserve readable mathematical symbols and no longer require every expression to become LaTeX.

The optional Gemini 4 Argon engine, existing automatic model choices and support options are retained. Difficult handwriting, small comic lettering, specialist signs and spoken maths still need checking against the source. These changes do not certify every scan as accurate.
