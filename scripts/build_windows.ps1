$ErrorActionPreference = "Stop"
python -m pip install --break-system-packages -r requirements-dev.txt
pyinstaller --noconfirm --onefile --windowed --name Zipora src/zipora/__main__.py
