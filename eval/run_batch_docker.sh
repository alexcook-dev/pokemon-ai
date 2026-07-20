#!/usr/bin/env bash
# Batch eval inside Linux (required on macOS — libcg.so is Linux x86_64 only).
# Defaults: --games 10 --opponent random
# v1 gate:  --games 50 --opponent random  (target win rate ≥70%)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

IMAGE="python:3.11-slim-bookworm"
# Forward all CLI args; apply defaults only when none were passed.
if [[ $# -eq 0 ]]; then
  set -- --games 10 --opponent random
fi

echo "Pulling $IMAGE (first time only)..."
docker pull "$IMAGE" >/dev/null

echo "Running batch eval in Docker (linux/amd64): python eval/run_batch.py $*"
docker run --rm \
  --platform linux/amd64 \
  -v "$ROOT:/work" \
  -w /work \
  "$IMAGE" \
  bash -c '
    set -e
    pip install -q "kaggle-environments>=1.14.10"
    python eval/run_batch.py "$@"
  ' -- "$@"

echo "Done."
