#!/bin/bash
echo "Starting Chronicle..."
cd "$(dirname "$0")" || exit
python3 chronicle.py
