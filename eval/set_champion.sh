#!/usr/bin/env bash
# Pin the champion snapshot for --opponent snapshot (protocol v2,
# human-approved 2026-07-20). Snapshot = main.py + agent/ + deck.csv + data/
# from a git commit, extracted to eval/champion/ (gitignored).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMMIT="${1:?usage: eval/set_champion.sh <commit>}"
DEST="$ROOT/eval/champion"
rm -rf "$DEST"
mkdir -p "$DEST"
git -C "$ROOT" archive "$COMMIT" main.py agent deck.csv data | tar -x -C "$DEST"
git -C "$ROOT" rev-parse --short "$COMMIT" > "$DEST/COMMIT"
echo "champion set to $(cat "$DEST/COMMIT") at $DEST"
