#!/bin/bash

# Navigate to the directory where the script is located
cd "$(dirname "$0")"

echo "---------------------------------------------------"
echo "         Chronicle Auto-Updater (Mac)"
echo "---------------------------------------------------"
echo ""
echo "Fetching the latest version of Chronicle from GitHub..."
echo "(Please ensure you are connected to the internet)"
echo ""

curl -H "Cache-Control: no-cache, no-store" -o chronicle.py -L "https://raw.githubusercontent.com/harry6116/Chronicle/main/chronicle.py"
curl -H "Cache-Control: no-cache, no-store" -o requirements.txt -L "https://raw.githubusercontent.com/harry6116/Chronicle/main/requirements.txt"

echo ""
echo "Scanning for new required libraries..."
pip install -r requirements.txt --upgrade --quiet

echo ""
echo "---------------------------------------------------"
echo "Update Complete! Chronicle is perfectly up to date."
echo "You can now run the program normally."
echo "---------------------------------------------------"
echo "Press Enter to close this window..."
read