#!/bin/bash
set -e
cd "$(dirname "$0")/.."
VENV=".site-manager-venv"
if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi
source "$VENV/bin/activate"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r tools/requirements.txt
python tools/site_manager.py
