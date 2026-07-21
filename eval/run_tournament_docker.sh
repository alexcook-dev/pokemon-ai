#!/usr/bin/env bash
# Swiss tournament inside Linux Docker (libcg is Linux x86_64 only).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
IMAGE="python:3.11-slim-bookworm"
docker pull "$IMAGE" >/dev/null
docker run --rm \
  --platform linux/amd64 \
  -v "$ROOT:/work" \
  -w /work \
  "$IMAGE" \
  bash -c '
    set -e
    pip install -q "kaggle-environments>=1.14.10"
    python eval/run_tournament.py "$@"
  ' -- "$@"
