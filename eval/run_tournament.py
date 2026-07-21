#!/usr/bin/env python3
"""8-player Swiss tournament for cabt decks, best-of-3, all seats piloted by
the live policy (main.agent). Human-requested gauntlet mode (2026-07-20).

Structure: 3 Swiss rounds (log2(8)), match points 3/1/0 (win/draw/loss),
Bo3 with in-match seat alternation, standings by points then game-win diff.
Run T tournaments with distinct seeds; aggregate placements.

Usage (inside Linux docker):
  python eval/run_tournament.py --tournaments 5 --seed 0 --out eval/results_tournament.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kaggle_environments import make  # noqa: E402
from main import agent as pilot  # noqa: E402  (one policy pilots every deck)

PLAYERS: List[Tuple[str, str]] = [
    ("dragapult", "deck.csv"),
    ("t1-mega-lopunny-dudunsparce", "deck_t1-mega-lopunny-dudunsparce.csv"),
    ("t2-mega-lucario", "deck_t2-mega-lucario.csv"),
    ("t3-mega-kangaskhan-box", "deck_t3-mega-kangaskhan-box.csv"),
    ("t4-team-rockets-mewtwo", "deck_t4-team-rockets-mewtwo.csv"),
    ("t5-rillaboom-dipplin", "deck_t5-rillaboom-dipplin.csv"),
    ("t6-alakazam-a", "deck_t6-alakazam-a.csv"),
    ("t7-alakazam-b", "deck_t7-alakazam-b.csv"),
]
ROUNDS = 3
MAX_GAMES_PER_MATCH = 5  # Bo3 + up to 2 draw replays


def load_deck(path: Path) -> List[int]:
    ids = [int(l.strip()) for l in path.read_text().splitlines() if l.strip()]
    if len(ids) != 60:
        raise SystemExit(f"{path} has {len(ids)} cards, need 60")
    return ids


def play_game(deck0: List[int], deck1: List[int], seed: int) -> Tuple[str, int]:
    """Return (result-for-seat0: win|loss|draw|crash, steps)."""
    random.seed(seed)
    try:
        env = make("cabt", debug=False, configuration={"decks": [deck0, deck1]})
        steps = env.run([pilot, pilot])
        if not steps:
            return "draw", 0
        last = steps[-1]
        r0 = last[0].get("reward") if len(last) > 0 else None
        r1 = last[1].get("reward") if len(last) > 1 else None
        if r0 == 1:
            return "win", len(steps)
        if r0 == -1 or r1 == 1:
            return "loss", len(steps)
        return "draw", len(steps)
    except Exception as exc:  # noqa: BLE001 — per-game isolation
        print(f"    CRASH: {type(exc).__name__}: {exc}", flush=True)
        return "crash", 0


def play_match(a: int, b: int, decks: List[List[int]], base_seed: int) -> Dict[str, Any]:
    """Bo3 between player a and player b. Seats alternate per game."""
    wins = {a: 0, b: 0}
    games = []
    for g in range(MAX_GAMES_PER_MATCH):
        # alternate: even game -> a takes seat0, odd -> b takes seat0
        s0, s1 = (a, b) if g % 2 == 0 else (b, a)
        res, steps = play_game(decks[s0], decks[s1], base_seed + g)
        if res == "win":
            wins[s0] += 1
        elif res == "loss":
            wins[s1] += 1
        # draw/crash: nobody scores; crash logged by play_game
        games.append({"seat0": PLAYERS[s0][0], "result_seat0": res, "steps": steps})
        if wins[a] == 2 or wins[b] == 2:
            break
    if wins[a] > wins[b]:
        winner: Optional[int] = a
    elif wins[b] > wins[a]:
        winner = b
    else:
        winner = None  # match draw
    return {"a": a, "b": b, "wins_a": wins[a], "wins_b": wins[b],
            "winner": winner, "games": games}


def swiss_pairings(order: List[int], points: Dict[int, int],
                   played: set, rng: random.Random) -> List[Tuple[int, int]]:
    """Pair within score groups top-down, greedily avoiding rematches."""
    ranked = sorted(order, key=lambda p: (-points[p], rng.random()))
    pairs: List[Tuple[int, int]] = []
    pool = ranked[:]
    while pool:
        p = pool.pop(0)
        opp_i = next((i for i, q in enumerate(pool) if (p, q) not in played
                      and (q, p) not in played), 0)
        q = pool.pop(opp_i)
        pairs.append((p, q))
    return pairs


def run_tournament(t_idx: int, decks: List[List[int]], seed: int,
                   fh) -> List[Tuple[int, Dict[str, Any]]]:
    rng = random.Random(seed)
    n = len(PLAYERS)
    points = {i: 0 for i in range(n)}
    gw = {i: 0 for i in range(n)}
    gl = {i: 0 for i in range(n)}
    played: set = set()

    for rnd in range(ROUNDS):
        pairs = swiss_pairings(list(range(n)), points, played, rng)
        print(f"[t{t_idx}] round {rnd + 1}: "
              + ", ".join(f"{PLAYERS[a][0]} vs {PLAYERS[b][0]}" for a, b in pairs),
              flush=True)
        for m_idx, (a, b) in enumerate(pairs):
            base_seed = seed * 100_000 + rnd * 1_000 + m_idx * 100
            match = play_match(a, b, decks, base_seed)
            played.add((a, b))
            gw[a] += match["wins_a"]; gl[a] += match["wins_b"]
            gw[b] += match["wins_b"]; gl[b] += match["wins_a"]
            if match["winner"] is None:
                points[a] += 1; points[b] += 1
            else:
                points[match["winner"]] += 3
            match.update({"type": "match", "tournament": t_idx, "round": rnd + 1,
                          "a_name": PLAYERS[a][0], "b_name": PLAYERS[b][0]})
            fh.write(json.dumps(match) + "\n"); fh.flush()
            w = "draw" if match["winner"] is None else PLAYERS[match["winner"]][0]
            print(f"    {PLAYERS[a][0]} {match['wins_a']}-{match['wins_b']} "
                  f"{PLAYERS[b][0]}  -> {w}", flush=True)

    standing = sorted(range(n), key=lambda p: (-points[p], -(gw[p] - gl[p]), rng.random()))
    result = []
    for place, p in enumerate(standing, 1):
        row = {"type": "standing", "tournament": t_idx, "place": place,
               "player": PLAYERS[p][0], "points": points[p],
               "game_wins": gw[p], "game_losses": gl[p]}
        fh.write(json.dumps(row) + "\n"); fh.flush()
        result.append((p, row))
    return result


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tournaments", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=ROOT / "eval" / "results_tournament.jsonl")
    args = ap.parse_args(argv)

    decks = [load_deck(ROOT / f) for _, f in PLAYERS]
    placements: Dict[str, List[int]] = defaultdict(list)
    pts: Dict[str, List[int]] = defaultdict(list)

    with args.out.open("a", encoding="utf-8") as fh:
        for t in range(args.tournaments):
            rows = run_tournament(t, decks, args.seed + t, fh)
            for _, row in rows:
                placements[row["player"]].append(row["place"])
                pts[row["player"]].append(row["points"])

    print("\n=== AGGREGATE over", args.tournaments, "tournaments ===")
    print(f"{'deck':32s} {'places':15s} {'avg':5s} {'pts':s}")
    for name in sorted(placements, key=lambda k: sum(placements[k]) / len(placements[k])):
        pl = placements[name]
        print(f"{name:32s} {str(pl):15s} {sum(pl) / len(pl):.1f}  {pts[name]}")
    print("---")
    drag = placements.get("dragapult", [])
    print(f"dragapult_avg_place: {sum(drag) / len(drag):.2f}")
    print(f"dragapult_places:    {drag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
