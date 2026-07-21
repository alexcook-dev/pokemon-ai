#!/usr/bin/env python3
"""Reproduce Kaggle's actual submission-loading mechanism and play a real game.

Our own eval scripts always `from main import agent`, a real Python import
that sets __file__ correctly and can never catch a Kaggle-harness-only bug.
Kaggle's kaggle_environments.agent.get_last_callable instead reads main.py's
raw source, compiles+execs it in a bare namespace (no __file__, no __name__),
and takes the last callable defined at module level. This script uses that
exact function against the packaged submission.tar.gz contents to prove the
agent actually loads and plays under the real harness, not just under import.
"""
from __future__ import annotations

import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

from kaggle_environments import make  # noqa: E402
from kaggle_environments.agent import get_last_callable  # noqa: E402


def load_from_tarball(tarball: Path, tmp_dir: Path):
    with tarfile.open(tarball) as tf:
        tf.extractall(tmp_dir)
    main_path = tmp_dir / "main.py"
    raw = main_path.read_text()
    return get_last_callable(raw, path=str(main_path))


def main() -> int:
    tarball = ROOT / "submission.tar.gz"
    if not tarball.exists():
        raise SystemExit(f"missing {tarball}, run ./package_submission.sh first")

    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        agent_fn = load_from_tarball(tarball, tmp_dir)
        print(f"loaded callable: {agent_fn!r}")

        deck_path = tmp_dir / "deck.csv"
        deck = [int(l.strip()) for l in deck_path.read_text().splitlines() if l.strip()]
        assert len(deck) == 60, f"deck has {len(deck)} cards"

        env = make("cabt", debug=False, configuration={"decks": [deck, deck]})
        steps = env.run([agent_fn, agent_fn])
        if not steps:
            raise SystemExit("no steps ran")
        last = steps[-1]
        statuses = [s.get("status") for s in last]
        rewards = [s.get("reward") for s in last]
        print(f"steps={len(steps)} statuses={statuses} rewards={rewards}")
        if any(str(s).upper() in ("ERROR", "INVALID", "TIMEOUT") for s in statuses):
            raise SystemExit(f"FAIL: engine reported {statuses}")
        print("PASS: agent loaded via Kaggle's exec-based harness and completed a real game")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
