# Chronicle 1.1.3

Chronicle 1.1.3 makes difficult documents easier to read and review, with built-in updates, clearer help, and more reliable saving.

## Updates and help

- Choose **Help > Check for Updates** to find the latest Mac or Windows version and read what has changed.
- Choose **Install and Restart Now** when you are ready. Chronicle downloads the update and restarts, keeping your settings and API keys.
- Choose **Remind Me Later** to keep working. A quiet reminder appears next time you open Chronicle; the app will not restart on its own.
- Choose **Go to Release** to open the download page, or **Help > Version History** to read release notes.
- Press **F1** for help with the control you are using, including in settings dialogs. Press **Escape** to close help and return to that control. **Shift+F1** checks for updates.
- Release notes support arrow-key reading, text selection and copying. Use **Tab** and **Shift+Tab** to move between actions, and **Escape** to close the window.
- Menu commands open dialogs with more predictable keyboard focus.

## More reliable reading and saving

- Unlock password-protected PDFs before reading them. Chronicle remembers the password temporarily during your session, so changing settings does not keep asking for it.
- Improved handling of difficult PDFs and dense historical newspapers reduces stalls during reading and final saving.
- Interrupted work has better recovery support. If saving a Word, PDF or e-book result fails, Chronicle can preserve the recovered text for review.
- Medical records have clearer handling of test results, units, reference ranges and form fields. Optional abbreviation expansion covers more common medical terms.
- Page references and page jump links follow your chosen settings more consistently.
- Improved headings, tables, reading order and navigation make results easier to use with a screen reader.
- Some completed extractions include a receipt and a separate review report with warnings and suggested checks. Always compare important results with the original.

## Privacy and offline use

- Support bundles hide more private folder details, and processing logs hide more secret values.
- Saved settings and API keys receive tighter file permissions where supported.
- Review reports avoid creating an extra copy of the extracted document text.
- Private Offline Mode keeps processing on your computer. It requires a separate Ollama installation and the `qwen2.5vl:7b` model; Chronicle does not include that download.
- Offline mode works best with clear typed documents. Difficult handwriting, newspapers, comics and complex scans still need careful review and may work better with online processing.

## Other changes

- Older saved Claude selections are updated to Claude Sonnet 4.6.
- Mac and Windows downloads are smaller because they do not include an offline model.
- The Mac download includes **Open Me First.command** to help with first-launch approval. Follow its instructions if macOS blocks the app.
- Updates prepare the new copy before replacing the old one and attempt to restore the previous app if replacement or the restart command fails.
- Scanner capture remains deferred while broader device testing continues.
