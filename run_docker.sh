#!/usr/bin/env bash
# Run cabt self-play inside Linux (required on macOS — libcg.so is Linux x86_64 only).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

IMAGE="python:3.11-slim-bookworm"

echo "Pulling $IMAGE (first time only)..."
docker pull "$IMAGE" >/dev/null

echo "Running self-play in Docker (linux/amd64)..."
docker run --rm \
  --platform linux/amd64 \
  -v "$ROOT:/work" \
  -w /work \
  "$IMAGE" \
  bash -c '
    set -e
    pip install -q "kaggle-environments>=1.14.10"
    python run_local.py
  '

echo "Done."
