#!/usr/bin/env python3
"""Head-to-head deck matrix: every candidate deck vs every opponent deck,
both seats piloted by the live policy, seats alternating per game.

Usage (inside Linux docker):
  python eval/run_h2h.py --candidates deck_a.csv,deck_b.csv \
      --opponents deck_c.csv,deck_d.csv --games 20 --seed 0 \
      --out eval/results_h2h.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kaggle_environments import make  # noqa: E402
from main import agent as pilot  # noqa: E402


def load_deck(path: Path) -> List[int]:
    ids = [int(l.strip()) for l in path.read_text().splitlines() if l.strip()]
    if len(ids) != 60:
        raise SystemExit(f"{path} has {len(ids)} cards, need 60")
    return ids


def play_game(deck0: List[int], deck1: List[int], seed: int) -> str:
    """Result for seat0: win|loss|draw|crash."""
    random.seed(seed)
    try:
        env = make("cabt", debug=False, configuration={"decks": [deck0, deck1]})
        steps = env.run([pilot, pilot])
        if not steps:
            return "draw"
        last = steps[-1]
        r0 = last[0].get("reward") if len(last) > 0 else None
        r1 = last[1].get("reward") if len(last) > 1 else None
        if r0 == 1:
            return "win"
        if r0 == -1 or r1 == 1:
            return "loss"
        return "draw"
    except Exception as exc:  # noqa: BLE001
        print(f"    CRASH: {type(exc).__name__}: {exc}", flush=True)
        return "crash"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--opponents", required=True)
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=ROOT / "eval" / "results_h2h.jsonl")
    args = ap.parse_args(argv)

    cands = [c.strip() for c in args.candidates.split(",") if c.strip()]
    opps = [o.strip() for o in args.opponents.split(",") if o.strip()]
    decks = {name: load_deck(ROOT / name) for name in set(cands + opps)}

    grid = {}
    with args.out.open("a", encoding="utf-8") as fh:
        for ci, cand in enumerate(cands):
            for oi, opp in enumerate(opps):
                if cand == opp:
                    continue
                w = l = d = cr = 0
                for g in range(args.games):
                    seed = args.seed + ci * 100_000 + oi * 10_000 + g
                    # alternate seats; result always from candidate's side
                    if g % 2 == 0:
                        res = play_game(decks[cand], decks[opp], seed)
                    else:
                        res = play_game(decks[opp], decks[cand], seed)
                        res = {"win": "loss", "loss": "win"}.get(res, res)
                    if res == "win":
                        w += 1
                    elif res == "loss":
                        l += 1
                    elif res == "draw":
                        d += 1
                    else:
                        cr += 1
                row = {"type": "h2h", "candidate": cand, "opponent": opp,
                       "wins": w, "losses": l, "draws": d, "crashes": cr,
                       "games": args.games,
                       "win_rate": w / max(1, w + l)}
                grid[(cand, opp)] = row
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                print(f"  {cand:34s} vs {opp:34s} {w}-{l}"
                      f"{' d' + str(d) if d else ''}{' CR' + str(cr) if cr else ''}"
                      f"  ({row['win_rate']:.0%})", flush=True)

    print("\n=== MATRIX (candidate win rate, draws excluded) ===")
    for cand in cands:
        total_w = sum(grid[(cand, o)]["wins"] for o in opps if (cand, o) in grid)
        total_l = sum(grid[(cand, o)]["losses"] for o in opps if (cand, o) in grid)
        cells = "  ".join(
            f"{o.split('.')[0].replace('deck_', '')[:14]}:{grid[(cand, o)]['win_rate']:.0%}"
            for o in opps if (cand, o) in grid
        )
        print(f"{cand}: overall {total_w}-{total_l} "
              f"({total_w / max(1, total_w + total_l):.0%})\n    {cells}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
