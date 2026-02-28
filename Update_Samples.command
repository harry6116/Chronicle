#!/bin/bash
cd "$(dirname "$0")"
echo "--- CHRONICLE SHOWROOM UPDATER ---"
echo "What are you adding? (e.g., 1947 Newspaper):"
read msg
git add assets/
git commit -m "ASSETS: $msg"
git push
echo "--- SUCCESS! ---"
read -p "Press Enter to close..."
