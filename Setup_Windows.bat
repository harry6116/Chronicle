@echo off
echo ===================================================
echo     Chronicle Document Extractor - Windows Setup
echo ===================================================
echo.
echo Installing required Python libraries...
echo.

pip install pypdf python-docx fpdf2 google-genai openpyxl

echo.
echo ===================================================
echo Setup complete! You can now run Run_Chronicle.bat
echo ===================================================
pause