#!/bin/bash
# Chronicle macOS Updater

echo "Starting Chronicle update for macOS..."

# Pull the latest changes from the repository
git pull origin main

# Update Python dependencies
pip install --upgrade -r requirements.txt

# Rebuild the Rust components
cargo build --release

echo "Update complete! Chronicle is ready to use."
