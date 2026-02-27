do shell script "python3 -m pip install --upgrade pip"
do shell script "python3 -m pip install pypdf python-docx fpdf2 google-genai"
display dialog "Chronicle dependencies installed successfully." buttons {"OK"} default button "OK"
