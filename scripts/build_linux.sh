#!/usr/bin/env bash
set -euo pipefail

# Install build dependencies
python -m pip install --break-system-packages -r requirements-dev.txt

# Build a single-file executable
pyinstaller --noconfirm --onefile --windowed --name zipora src/zipora/__main__.py
