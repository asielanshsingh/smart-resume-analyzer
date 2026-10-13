#!/usr/bin/env bash
set -euo pipefail

echo "==> Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Downloading spaCy model (en_core_web_sm)..."
python -m spacy download en_core_web_sm

echo "==> Build complete."