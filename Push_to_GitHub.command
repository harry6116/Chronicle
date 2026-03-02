#!/bin/bash

# Navigate to the directory where the script is located
cd "$(dirname "$0")"

echo "--- CHRONICLE GLOBAL UPDATER ---"
echo "This will sync your Code, Documentation, and Methodology."
echo "Enter a brief summary of your changes (e.g., Fixed JPEG bug):"
read commit_message

# Stage all changes, deletions, and new files automatically
git add -A

# Commit the changes
git commit -m "UPDATE: $commit_message"

# Push to GitHub
git push

echo "--- ALL SYSTEMS SYNCED ---"
echo "Press Enter to close..."
read