#!/usr/bin/env bash
# One-time setup for a fresh clone of this repo on a new machine.
#
# What this actually needs to do (verified 2026-07-21, not assumed):
#   - The cabt simulator engine (libcg.so) ships INSIDE the
#     `kaggle-environments` pip package, Linux x86_64 only. Every
#     *_docker.sh script in this repo already runs `pip install
#     kaggle-environments` fresh inside its own ephemeral container, so
#     there is no binary artifact to copy in by hand — libcg_docker.so
#     at the repo root is a leftover, unused by any script (grepped),
#     and stays gitignored on purpose.
#   - What a fresh machine actually needs: Docker installed and running,
#     the base image pulled once (so the first real eval isn't also
#     eating a slow first-pull), and one real container boot that proves
#     kaggle-environments installs AND the "cabt" engine actually loads
#     (dlopen failures are exactly the kind of thing that's silent until
#     you try to use it) — plus the champion snapshot initialized so
#     --opponent snapshot works without a separate manual step.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
IMAGE="python:3.11-slim-bookworm"

echo "== 1/4: Docker =="
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker not found. Install Docker Desktop: https://www.docker.com/products/docker-desktop/"
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: docker is installed but not running. Start Docker Desktop and re-run this script."
  exit 1
fi
echo "OK: Docker is installed and running."

echo ""
echo "== 2/4: pull the eval base image (one-time, ~100MB) =="
docker pull --platform linux/amd64 "$IMAGE"

echo ""
echo "== 3/4: verify the simulator actually loads (not just that Docker works) =="
docker run --rm --platform linux/amd64 "$IMAGE" bash -c '
  set -e
  pip install -q "kaggle-environments>=1.14.10"
  python3 -c "
from kaggle_environments import make
env = make(\"cabt\", debug=False)
print(\"OK: cabt engine loaded (libcg.so resolved correctly)\")
"
'

echo ""
echo "== 4/4: initialize the champion snapshot for protocol-v2 eval =="
# `[ -d .git ]` breaks in a git worktree (.git is a FILE there, pointing at
# the real gitdir, not a directory) — use git itself to ask, not a path guess.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ./eval/set_champion.sh HEAD
else
  echo "SKIP: not a git checkout, can't pin a champion commit — run"
  echo "      ./eval/set_champion.sh <commit> manually once you have one."
fi

chmod +x ./*.sh ./eval/*.sh 2>/dev/null || true

echo ""
echo "Setup complete. Try:"
echo "  ./eval/run_batch_docker.sh --games 10 --opponent random   # smoke test"
echo "  ./eval/run_train_eval.sh                                   # frozen 50-game protocol"
echo "  ./package_submission.sh                                    # build submission.tar.gz"
echo ""
echo "Note: this repo's knowledge/ directory is a git submodule (the PTCG"
echo "strategy brain, its own repo). If knowledge/ looks empty, run:"
echo "  git submodule update --init --recursive"
