#!/bin/bash
cd "$(dirname "$0")"
clear
echo "Downloading the latest community updates from GitHub..."
git pull
echo ""
echo "=========================================="
echo "SUCCESS! Your Mac is now perfectly synced with GitHub."
echo "=========================================="
