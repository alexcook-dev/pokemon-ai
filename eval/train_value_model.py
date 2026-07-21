#!/usr/bin/env python3
"""Tier 4 (learned) training: log self-play decisions + outcomes, fit a
tiny logistic regression, write agent/learned_weights.json.

This is the "path out" for tier 4 — complete, runnable code — but it is
NOT run as part of shipping tiers 1-3. Training produces an UNVALIDATED
model; agent/learned_scorer.py stays a no-op until PTCG_USE_LEARNED_SCORER=1
is set explicitly, and any weights this script produces should be tested
via protocol v2 (champion-vs-challenger, program.md) before being trusted
for a real submission — same keep/discard discipline as every heuristic
experiment in results.tsv.

Honest limitation: the label is crude outcome-weighted imitation ("was
this option the kind a WINNING game picked"), not proper credit
assignment — an option played in an otherwise-losing game gets label 0
even if it was locally correct, and vice versa. Good enough as a first
pass / to prove the plumbing; a real credit-assignment signal (e.g.
value-of-state deltas) is future work.

Usage (inside Linux docker):
  python eval/train_value_model.py --games 200 --seed 0 \
      --out agent/learned_weights.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kaggle_environments import make  # noqa: E402

from agent.learned_scorer import extract_features  # noqa: E402
from agent.policy import _option_card_id, _read_situation, choose_actions  # noqa: E402
from main import DECK  # noqa: E402

_LOGGED: List[Dict[str, Any]] = []
_CURRENT_GAME = [0]


def _logging_agent(obs: dict) -> list:
    """Play with the real (untouched) policy so logged games stay at full
    strength; log every option's features + whether it was chosen, tagged
    with the current game id so labels can be filled in once that game's
    outcome is known.
    """
    select = obs.get("select") if isinstance(obs, dict) else None
    chosen = choose_actions(obs)
    if select is not None:
        try:
            sit = _read_situation(obs)
            options = select.get("option") or []
            chosen_set = set(chosen)
            for i, opt in enumerate(options):
                if not isinstance(opt, dict):
                    opt = {"type": opt}
                cid = _option_card_id(obs, opt)
                opt_type = int(opt.get("type") if opt.get("type") is not None else -1)
                _LOGGED.append({
                    "features": extract_features(sit, cid, opt_type),
                    "chosen": i in chosen_set,
                    "game": _CURRENT_GAME[0],
                })
        except Exception:
            pass  # logging must never break the underlying game
    return chosen


def _sigmoid(x: float) -> float:
    if x < -60:
        return 0.0
    if x > 60:
        return 1.0
    return 1.0 / (1.0 + math.exp(-x))


def _train_logistic(rows: List[Dict[str, Any]], epochs: int, lr: float) -> Dict[str, float]:
    """Pure-Python logistic regression — no numpy/sklearn, so this script
    has zero extra dependencies beyond what the eval Docker image already
    installs for kaggle-environments."""
    keys = sorted({k for r in rows for k in r["features"]})
    w = {k: 0.0 for k in keys}
    n = max(1, len(rows))
    for _ in range(epochs):
        grad = {k: 0.0 for k in keys}
        for r in rows:
            x = r["features"]
            z = sum(w[k] * x.get(k, 0.0) for k in keys)
            err = _sigmoid(z) - r["label"]
            for k in keys:
                grad[k] += err * x.get(k, 0.0)
        for k in keys:
            w[k] -= lr * grad[k] / n
    return w


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--lr", type=float, default=0.05)
    ap.add_argument("--out", type=Path, default=ROOT / "agent" / "learned_weights.json")
    args = ap.parse_args(argv)

    deck = list(DECK)
    outcomes: Dict[int, int] = {}  # game_id -> +1 win / -1 loss / 0 draw|crash (seat0's view)

    for g in range(args.games):
        _CURRENT_GAME[0] = g
        random.seed(args.seed + g)
        try:
            env = make("cabt", debug=False, configuration={"decks": [deck, deck]})
            steps = env.run([_logging_agent, _logging_agent])
            last = steps[-1] if steps else None
            r0 = last[0].get("reward") if last and len(last) > 0 else None
            outcomes[g] = 1 if r0 == 1 else (-1 if r0 == -1 else 0)
        except Exception as exc:  # noqa: BLE001 — per-game isolation
            print(f"  game {g}: crash {type(exc).__name__}: {exc}")
            outcomes[g] = 0
        if (g + 1) % 20 == 0:
            print(f"  {g + 1}/{args.games} games, {len(_LOGGED)} decisions logged so far")

    rows = []
    for r in _LOGGED:
        outcome = outcomes.get(r["game"], 0)
        if outcome == 0:
            continue  # no clean win/loss label (draw or crash) — skip
        label = 1.0 if (r["chosen"] and outcome == 1) else 0.0
        rows.append({"features": r["features"], "label": label})

    if not rows:
        print("No labeled rows collected (all draws/crashes?) — nothing to train.")
        return 1

    weights = _train_logistic(rows, epochs=args.epochs, lr=args.lr)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "weights": weights,
        "trained_on_games": args.games,
        "labeled_rows": len(rows),
        "note": "tier-4 experimental (outcome-weighted imitation) — "
                "validate via protocol v2 before trusting for a submission",
    }, indent=2))
    print(f"\nWrote {args.out} ({len(rows)} labeled rows, {len(weights)} features)")
    print("Does NOT activate automatically. Test with:")
    print("  PTCG_USE_LEARNED_SCORER=1 ./eval/run_batch_docker.sh --games 50 --opponent snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
