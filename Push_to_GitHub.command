#!/bin/bash
cd "$(dirname "$0")"
clear
echo "What did you update or fix? (Type a short message and press Enter):"
read commit_message
git add .
git commit -m "$commit_message"
git push
echo ""
echo "=========================================="
echo "SUCCESS! Your updates are live on GitHub."
echo "=========================================="
