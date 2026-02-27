@echo off
echo Installing Chronicle dependencies...
python -m pip install --upgrade pip
python -m pip install pypdf python-docx fpdf2 google-genai
echo Installation complete.
pause
