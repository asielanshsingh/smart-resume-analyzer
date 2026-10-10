#!/usr/bin/env bash
# build.sh — Render build script
# Runs during the build phase before the service starts.
set -euo pipefail

echo "==> Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Downloading spaCy language model (en_core_web_sm)..."
python -m spacy download en_core_web_sm

echo "==> Downloading NLTK data..."
python - <<'PYEOF'
import nltk
# Download only the corpora actually used; extend this list as needed.
for pkg in ("punkt", "stopwords", "wordnet"):
    try:
        nltk.download(pkg, quiet=True)
        print(f"  nltk: {pkg} OK")
    except Exception as exc:
        print(f"  nltk: {pkg} WARNING — {exc}")
PYEOF

echo "==> Build complete."
