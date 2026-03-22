#!/bin/bash
set -e

cd "$(dirname "$0")"

# Find python3 or python
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "Python not found. Install Python 3.10+ from https://python.org and try again."
    read -p "Press Enter to close..."
    exit 1
fi

# Create venv if missing
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON -m venv .venv
fi

# Install/update dependencies
echo "Installing dependencies..."
.venv/bin/pip install -r requirements.txt -q

# Run
.venv/bin/python visualize_spendings.py --index --open
