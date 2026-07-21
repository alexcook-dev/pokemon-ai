#!/usr/bin/env python3
"""8-round Swiss tournament, best-of-3 matches, among all user-provided decks.

Every seat is piloted by our own live policy (main.agent) -- "practice
against yourself" -- only the decklists differ. Swiss pairing: each round,
sort by current match-win standings, pair adjacent players, skip a pairing
that's already been played if a fresh one is available, otherwise allow a
forced rematch (unavoidable with a small field). Repeats the full 8-round
tournament 5 times with independent seeds and reports per-run + aggregate
standings.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kaggle_environments import make  # noqa: E402
from main import agent as pilot  # noqa: E402

DECKS = {
    "alakazam-elgyem": "deck_user-alakazam-elgyem.csv",
    "grimmsnarl-munkidori": "deck_user-grimmsnarl-munkidori.csv",
    "kangaskhan-crustle": "deck_user-kangaskhan-crustle.csv",
    "kangaskhan-clefairy": "deck_user-kangaskhan-clefairy.csv",
}


def load_deck(path: str) -> list[int]:
    ids = [int(l.strip()) for l in (ROOT / path).read_text().splitlines() if l.strip()]
    assert len(ids) == 60, f"{path}: {len(ids)} cards"
    return ids


DECK_LISTS = {name: load_deck(path) for name, path in DECKS.items()}


def play_game(deck_a: list[int], deck_b: list[int], seed: int) -> str:
    random.seed(seed)
    try:
        env = make("cabt", debug=False, configuration={"decks": [deck_a, deck_b]})
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


def play_match(p1: str, p2: str, seed_base: int) -> tuple[str | None, str]:
    """Best-of-3. Returns (winner_name_or_None, score_str). Alternates seat each game."""
    wins1 = wins2 = 0
    game_num = 0
    while wins1 < 2 and wins2 < 2 and game_num < 3:
        seed = seed_base + game_num
        if game_num % 2 == 0:
            res = play_game(DECK_LISTS[p1], DECK_LISTS[p2], seed)
        else:
            res = play_game(DECK_LISTS[p2], DECK_LISTS[p1], seed)
            res = {"win": "loss", "loss": "win"}.get(res, res)
        if res == "win":
            wins1 += 1
        elif res == "loss":
            wins2 += 1
        # draws/crashes: game still counted as played, no match-win increment
        game_num += 1
    score = f"{wins1}-{wins2}"
    if wins1 > wins2:
        return p1, score
    if wins2 > wins1:
        return p2, score
    return None, score


def swiss_pairings(standings: dict[str, int], played_pairs: set[frozenset], rng: random.Random) -> list[tuple[str, str | None]]:
    groups: dict[int, list[str]] = {}
    for p, s in standings.items():
        groups.setdefault(s, []).append(p)
    ordered: list[str] = []
    for score in sorted(groups.keys(), reverse=True):
        bucket = groups[score]
        rng.shuffle(bucket)
        ordered.extend(bucket)

    unpaired = ordered[:]
    pairs: list[tuple[str, str | None]] = []
    while unpaired:
        p1 = unpaired.pop(0)
        opp = None
        for cand in unpaired:
            if frozenset((p1, cand)) not in played_pairs:
                opp = cand
                break
        if opp is None and unpaired:
            opp = unpaired[0]  # forced rematch, unavoidable with this few players
        if opp is not None:
            unpaired.remove(opp)
            pairs.append((p1, opp))
        else:
            pairs.append((p1, None))  # bye (shouldn't occur with an even player count)
    return pairs


def run_tournament(run_idx: int, tournament_seed: int) -> dict[str, int]:
    print(f"\n{'='*60}\nTOURNAMENT RUN {run_idx} (seed base {tournament_seed})\n{'='*60}")
    standings = {name: 0 for name in DECKS}
    match_record: dict[str, list[str]] = {name: [] for name in DECKS}
    played_pairs: set[frozenset] = set()
    seed_counter = tournament_seed

    for rnd in range(1, 9):
        rng = random.Random(tournament_seed * 1000 + rnd)
        pairs = swiss_pairings(standings, played_pairs, rng)
        print(f"\n-- Round {rnd} --")
        for p1, p2 in pairs:
            if p2 is None:
                standings[p1] += 1
                match_record[p1].append("BYE")
                print(f"  {p1}: BYE")
                continue
            played_pairs.add(frozenset((p1, p2)))
            winner, score = play_match(p1, p2, seed_counter)
            seed_counter += 10
            if winner:
                standings[winner] += 1
                loser = p2 if winner == p1 else p1
                match_record[winner].append(f"W {score} vs {loser}")
                match_record[loser].append(f"L {score} vs {winner}")
                print(f"  {p1} vs {p2}: {winner} wins {score}")
            else:
                match_record[p1].append(f"D {score} vs {p2}")
                match_record[p2].append(f"D {score} vs {p1}")
                print(f"  {p1} vs {p2}: draw {score}")

    print(f"\n-- Final standings, run {run_idx} --")
    for name, wins in sorted(standings.items(), key=lambda kv: -kv[1]):
        print(f"  {name}: {wins}/8 match wins   [{', '.join(match_record[name])}]")
    return standings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-idx", type=int, default=None, help="Run only this single tournament (1-5)")
    ap.add_argument("--out", type=Path, default=None, help="Write this run's standings JSON here")
    ap.add_argument("--aggregate", nargs="*", type=Path, default=None, help="Read these JSON files and print the aggregate summary")
    args = ap.parse_args()

    if args.aggregate is not None:
        all_results = [json.loads(p.read_text()) for p in args.aggregate]
        print(f"\n{'='*60}\nAGGREGATE ACROSS {len(all_results)} TOURNAMENTS\n{'='*60}")
        totals = {name: 0 for name in DECKS}
        for result in all_results:
            for name, wins in result.items():
                totals[name] += wins
        n = len(all_results)
        for name, total in sorted(totals.items(), key=lambda kv: -kv[1]):
            avg = total / n
            print(f"  {name}: {total}/{n*8} total match wins across {n} runs (avg {avg:.1f}/8 per tournament)")
        return 0

    if args.run_idx is not None:
        result = run_tournament(args.run_idx, tournament_seed=args.run_idx * 7919)
        if args.out:
            args.out.write_text(json.dumps(result))
        return 0

    all_results: list[dict[str, int]] = []
    for i in range(1, 6):
        result = run_tournament(i, tournament_seed=i * 7919)
        all_results.append(result)

    print(f"\n{'='*60}\nAGGREGATE ACROSS 5 TOURNAMENTS\n{'='*60}")
    totals = {name: 0 for name in DECKS}
    for result in all_results:
        for name, wins in result.items():
            totals[name] += wins
    for name, total in sorted(totals.items(), key=lambda kv: -kv[1]):
        avg = total / 5
        print(f"  {name}: {total}/40 total match wins across 5 runs (avg {avg:.1f}/8 per tournament)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
