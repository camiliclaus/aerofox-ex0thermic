#!/usr/bin/env sh
# AeroFox local launcher for macOS / Linux:  ./start_aerofox.sh
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then exec python3 scripts/launch.py "$@"; fi
if command -v python >/dev/null 2>&1; then exec python scripts/launch.py "$@"; fi
echo "[AeroFox] ERROR: Python 3.10+ not found. Install it from https://www.python.org/downloads/"; exit 1
