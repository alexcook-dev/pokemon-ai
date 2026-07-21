#!/usr/bin/env bash
# Interactive human-vs-AI game inside Linux Docker (libcg is Linux x86_64 only).
# You pilot $HUMAN_DECK (default: Grant Walworth Hydrapple) vs the live agent.
#
#   ./play_human_docker.sh                       # play Hydrapple vs AI
#   HUMAN_DECK=deck_hydrapple.csv ./play_human_docker.sh   # other deck
#   HUMAN_AUTO=first ./play_human_docker.sh      # non-interactive smoke test
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

IMAGE="python:3.11-slim-bookworm"
TTY_FLAGS="-it"
# no TTY (CI / piped smoke test) → -i only
[ -t 0 ] || TTY_FLAGS="-i"

docker run --rm $TTY_FLAGS \
  --platform linux/amd64 \
  -v "$ROOT:/work" \
  -w /work \
  -e HUMAN_DECK="${HUMAN_DECK:-deck_grant-walworth-hydrapple-naic2026.csv}" \
  -e HUMAN_AUTO="${HUMAN_AUTO:-}" \
  -e HUMAN_SEAT="${HUMAN_SEAT:-0}" \
  "$IMAGE" \
  bash -c '
    set -e
    pip install -q "kaggle-environments>=1.14.10"
    python play_human.py
  '
