#!/usr/bin/env bash
# Build submission.tar.gz for Kaggle (main.py + deck.csv + agent/ at top level).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
OUT=submission.tar.gz
rm -f "$OUT"
# Exclude caches / bytecode (--exclude must come before file args on BSD tar)
tar -czvf "$OUT" \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  main.py \
  deck.csv \
  agent
echo "Created $OUT ($(du -h "$OUT" | cut -f1))"
ls -la "$OUT"
