#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
IMAGE="python:3.11-slim-bookworm"
docker pull "$IMAGE" >/dev/null
echo "Running deck.csv vs deck_b.csv ..."
docker run --rm --platform linux/amd64 -v "$ROOT:/work" -w /work "$IMAGE" bash -c '
  set -e
  pip install -q "kaggle-environments>=1.14.10"
  python run_match.py
'
echo "Done."
