#!/usr/bin/env bash
# FROZEN train-eval protocol for ptcg-train (autoresearch).
# Do not change args casually — keep experiments comparable.
#
# Default: 50 games vs random, seed 0.
# Override only when the human opens a new protocol version.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GAMES="${TRAIN_GAMES:-50}"
OPPONENT="${TRAIN_OPPONENT:-random}"
SEED="${TRAIN_SEED:-0}"
TAG="${TRAIN_TAG:-latest}"
OUT="eval/results_train_${TAG}.jsonl"

exec "$ROOT/eval/run_batch_docker.sh" \
  --games "$GAMES" \
  --opponent "$OPPONENT" \
  --seed "$SEED" \
  --out "$OUT"
