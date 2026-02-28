tell application "Terminal"
    activate
    do script "echo '--- Chronicle Document Extractor Setup (Mac) ---'; echo 'Installing required Python libraries...'; pip install --upgrade google-genai pypdf python-docx fpdf2 openpyxl EbookLib; echo ''; echo 'Setup Complete! You can now close this window and run Run_Chronicle.command.'"
end tell