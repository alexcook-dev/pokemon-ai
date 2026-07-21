#!/usr/bin/env bash
# Pin the champion snapshot for --opponent snapshot (protocol v2,
# human-approved 2026-07-20). Snapshot = main.py + agent/ + deck.csv + data/
# from a git commit, extracted to eval/champion/ (gitignored).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMMIT="${1:?usage: eval/set_champion.sh <commit>}"
DEST="$ROOT/eval/champion"

# Build into a temp dir and atomically `mv` into place (fixed 2026-07-21,
# pre-merge adversarial review). The previous rm-then-build was non-atomic:
# a git-archive/tar failure after the rm left eval/champion/ deleted with
# no replacement, silently breaking --opponent snapshot until someone
# noticed and re-ran with a valid commit. Building to a sibling temp dir
# means a failure here never touches the working champion.
TMP="$(mktemp -d "$ROOT/eval/.champion-build.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

git -C "$ROOT" archive "$COMMIT" main.py agent deck.csv data | tar -x -C "$TMP"
git -C "$ROOT" rev-parse --short "$COMMIT" > "$TMP/COMMIT"

rm -rf "$DEST"
mv "$TMP" "$DEST"
trap - EXIT

echo "champion set to $(cat "$DEST/COMMIT") at $DEST"
