tell application "Terminal"
	activate
	do script "echo '===================================================' ; echo '    Chronicle Document Extractor - Mac Setup' ; echo '===================================================' ; echo '' ; echo 'Installing required Python libraries...' ; echo '' ; pip3 install pypdf python-docx fpdf2 google-genai openpyxl ; echo '' ; echo '===================================================' ; echo 'Setup complete! You can now run Run_Chronicle.command' ; echo '==================================================='"
end tell