@echo off
title Chronicle Document Extractor - Setup
echo ===================================================
echo     Chronicle Document Extractor Setup (Windows)
echo ===================================================
echo.
echo Installing and upgrading required Python libraries...
echo (This may take a minute or two)
echo.

pip install --upgrade google-genai pypdf python-docx fpdf2 openpyxl EbookLib

echo.
echo ===================================================
echo Setup Complete! 
echo You can now run Chronicle by double-clicking Run_Chronicle.bat
echo ===================================================
pause