#!/usr/bin/env bash
set -euo pipefail

# Install build dependencies
python -m pip install --break-system-packages -r requirements-dev.txt

# Build a single-file app executable
pyinstaller --noconfirm --onefile --windowed --name Zipora src/zipora/__main__.py
