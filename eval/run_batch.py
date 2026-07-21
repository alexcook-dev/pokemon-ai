#!/usr/bin/env python3
"""
Batch evaluation harness for the cabt agent.

Runs N games, records win/loss/draw/crash to JSONL, prints summary.
Must run on Linux x86_64 (use eval/run_batch_docker.sh on macOS).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kaggle_environments import make  # noqa: E402

from main import DECK, agent as our_agent  # noqa: E402

AgentFn = Callable[[dict], list]


def load_deck(path: Path) -> List[int]:
    ids = [int(line.strip()) for line in path.read_text().splitlines() if line.strip()]
    if len(ids) != 60:
        raise ValueError(f"{path} has {len(ids)} cards, need 60")
    return ids


def make_random_agent(deck: List[int]) -> AgentFn:
    """Random legal-action agent that submits `deck` during deck-selection."""

    def _agent(obs: dict) -> list:
        if obs.get("select") is None:
            return list(deck)
        options = obs["select"]["option"]
        max_count = obs["select"]["maxCount"]
        n = len(options)
        if max_count <= 0 or n == 0:
            return []
        k = min(max_count, n)
        return random.sample(list(range(n)), k)

    return _agent


def resolve_matchup(
    opponent: str,
    deck_a: List[int],
    deck_b: List[int],
) -> Tuple[List[int], List[int], AgentFn, AgentFn]:
    """
    Returns (deck0, deck1, agent0, agent1).

    - random: both decks = deck.csv; our agent vs random legal actions
    - self:   both decks = deck.csv; our agent vs our agent
    - deck_b: deck.csv vs deck_b.csv; our agent vs random (baseline)
    (snapshot mode is resolved in main() — it needs the loaded champion)
    """
    if opponent == "random":
        return deck_a, deck_a, our_agent, make_random_agent(deck_a)
    if opponent == "self":
        return deck_a, deck_a, our_agent, our_agent
    if opponent == "deck_b":
        return deck_a, deck_b, our_agent, make_random_agent(deck_b)
    raise ValueError(f"Unknown opponent mode: {opponent}")


def load_snapshot_agent(snapshot_dir: Path) -> Tuple[AgentFn, List[int]]:
    """Load the champion agent from a self-contained snapshot directory.

    Protocol v2 (champion-vs-challenger, human-approved 2026-07-20).
    The snapshot holds main.py + agent/ + deck.csv + data/ from the champion
    commit (populated by eval/set_champion.sh). Import it with the snapshot
    dir at sys.path[0] and a scrubbed module cache so its `agent` package
    resolves to the snapshot copy, then restore the cache so the already-
    imported challenger modules are untouched.
    """
    import importlib

    snapshot_dir = snapshot_dir.resolve()
    if not (snapshot_dir / "main.py").exists():
        raise SystemExit(
            f"snapshot missing main.py: {snapshot_dir} — run eval/set_champion.sh <commit>"
        )
    saved_modules: Dict[str, Any] = {}
    for name in list(sys.modules):
        if name == "main" or name == "agent" or name.startswith("agent."):
            saved_modules[name] = sys.modules.pop(name)
    saved_path = list(sys.path)
    sys.path.insert(0, str(snapshot_dir))
    try:
        champ_main = importlib.import_module("main")
        champ_agent: AgentFn = champ_main.agent
        champ_deck = list(champ_main.DECK)
    finally:
        sys.path[:] = saved_path
        for name in list(sys.modules):
            if name == "main" or name == "agent" or name.startswith("agent."):
                del sys.modules[name]
        sys.modules.update(saved_modules)
    if len(champ_deck) != 60:
        raise SystemExit(f"champion deck has {len(champ_deck)} cards, need 60")
    return champ_agent, champ_deck


def classify_result(steps: list) -> Tuple[str, Optional[List[Any]], int]:
    """Return (result, rewards, n_steps) from env.run output. result in win|loss|draw."""
    n_steps = len(steps) if steps else 0
    if not steps:
        return "draw", None, 0

    last = steps[-1]
    # Each step is a list of player states
    r0 = last[0].get("reward") if last and len(last) > 0 else None
    r1 = last[1].get("reward") if last and len(last) > 1 else None
    rewards: List[Any] = [r0, r1]

    status0 = last[0].get("status") if last and len(last) > 0 else None
    status1 = last[1].get("status") if last and len(last) > 1 else None
    for st in (status0, status1):
        if st and str(st).upper() in ("ERROR", "INVALID", "TIMEOUT"):
            # Treat engine-side agent failure as crash at classify time only if rewards missing
            if r0 is None and r1 is None:
                return "crash", rewards, n_steps

    if r0 == 1:
        return "win", rewards, n_steps
    if r0 == -1 or r1 == 1:
        return "loss", rewards, n_steps
    return "draw", rewards, n_steps


def run_one_game(
    game_idx: int,
    deck0: List[int],
    deck1: List[int],
    agent0: AgentFn,
    agent1: AgentFn,
    seed: int,
    opponent: str,
) -> Dict[str, Any]:
    """Play a single game; never raises — crashes recorded in the record."""
    record: Dict[str, Any] = {
        "type": "game",
        "game": game_idx,
        "opponent": opponent,
        "seed": seed,
        "result": None,
        "steps": 0,
        "rewards": None,
        "error": None,
    }
    # Per-game seed so batch is reproducible but games differ
    random.seed(seed)
    try:
        env = make(
            "cabt",
            debug=False,
            configuration={"decks": [deck0, deck1]},
        )
        steps = env.run([agent0, agent1])
        result, rewards, n_steps = classify_result(steps)
        record["result"] = result
        record["steps"] = n_steps
        record["rewards"] = rewards
        if result == "crash":
            record["error"] = "engine status ERROR/INVALID/TIMEOUT with no rewards"
    except Exception as exc:  # noqa: BLE001 — per-game isolation
        record["result"] = "crash"
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["traceback"] = traceback.format_exc(limit=5)
    return record


def summarize(records: List[Dict[str, Any]], opponent: str, seed: Optional[int]) -> Dict[str, Any]:
    n = len(records)
    wins = sum(1 for r in records if r.get("result") == "win")
    losses = sum(1 for r in records if r.get("result") == "loss")
    draws = sum(1 for r in records if r.get("result") == "draw")
    crashes = sum(1 for r in records if r.get("result") == "crash")
    finished = n - crashes
    total_steps = sum(int(r.get("steps") or 0) for r in records)
    return {
        "type": "summary",
        "games": n,
        "opponent": opponent,
        "seed": seed,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "crashes": crashes,
        "win_rate": (wins / n) if n else 0.0,
        "win_rate_excl_crashes": (wins / finished) if finished else 0.0,
        "crash_rate": (crashes / n) if n else 0.0,
        "avg_steps": (total_steps / n) if n else 0.0,
    }


def print_summary(s: Dict[str, Any]) -> None:
    n = s["games"]
    print()
    print("=== batch summary ===")
    print(f"opponent:  {s['opponent']}")
    print(f"games:     {n}")
    print(f"wins:      {s['wins']}")
    print(f"losses:    {s['losses']}")
    print(f"draws:     {s['draws']}")
    print(f"crashes:   {s['crashes']}")
    print(f"win rate:  {s['win_rate']:.1%}  ({s['wins']}/{n})")
    if s["crashes"]:
        print(f"win rate excl. crashes: {s['win_rate_excl_crashes']:.1%}")
    print(f"crash rate:{s['crash_rate']:.1%}  ({s['crashes']}/{n})")
    print(f"avg steps: {s['avg_steps']:.1f}")
    print("=====================")
    # Machine-parseable block for the ptcg-train / autoresearch loop
    print("---")
    print(f"win_rate:          {s['win_rate']:.6f}")
    print(f"win_rate_excl_crashes: {s['win_rate_excl_crashes']:.6f}")
    print(f"wins:              {s['wins']}")
    print(f"losses:            {s['losses']}")
    print(f"draws:             {s['draws']}")
    print(f"games:             {n}")
    print(f"crash_rate:        {s['crash_rate']:.6f}")
    print(f"crashes:           {s['crashes']}")
    print(f"avg_steps:         {s['avg_steps']:.2f}")
    print(f"opponent:          {s['opponent']}")
    print(f"seed:              {s['seed']}")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Batch-evaluate cabt agent win rate")
    p.add_argument("--games", type=int, default=10, help="Number of games (default 10; v1 gate uses 50)")
    p.add_argument(
        "--opponent",
        choices=("random", "self", "deck_b", "snapshot"),
        default="random",
        help="Opponent mode (default: random). snapshot = champion-vs-challenger (protocol v2)",
    )
    p.add_argument(
        "--snapshot-dir",
        type=Path,
        default=ROOT / "eval" / "champion",
        help="Champion snapshot dir for --opponent snapshot (default: eval/champion)",
    )
    p.add_argument("--seed", type=int, default=0, help="Base RNG seed (game i uses seed+i)")
    p.add_argument(
        "--out",
        type=Path,
        default=ROOT / "eval" / "results.jsonl",
        help="JSONL output path (default: eval/results.jsonl)",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    deck_path = ROOT / "deck.csv"
    deck_b_path = ROOT / "deck_b.csv"
    deck_a = load_deck(deck_path) if deck_path.exists() else list(DECK)
    if len(deck_a) != 60:
        raise SystemExit(f"Player 0 deck must have 60 cards, got {len(deck_a)}")

    if args.opponent == "deck_b":
        if not deck_b_path.exists():
            raise SystemExit(f"--opponent deck_b requires {deck_b_path}")
        deck_b = load_deck(deck_b_path)
    else:
        deck_b = list(deck_a)

    champ_note = ""
    if args.opponent == "snapshot":
        champ_agent, champ_deck = load_snapshot_agent(args.snapshot_dir)
        commit_file = args.snapshot_dir / "COMMIT"
        champ_note = commit_file.read_text().strip() if commit_file.exists() else "?"
        deck0, deck1, agent0, agent1 = deck_a, champ_deck, our_agent, champ_agent
    else:
        deck0, deck1, agent0, agent1 = resolve_matchup(args.opponent, deck_a, deck_b)

    out_path: Path = args.out
    if not out_path.is_absolute():
        out_path = Path.cwd() / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(
        f"Running {args.games} games | opponent={args.opponent}"
        + (f" (champion {champ_note}, seats alternate)" if champ_note else "")
        + f" | seed={args.seed} | out={out_path}"
    )

    records: List[Dict[str, Any]] = []
    with out_path.open("a", encoding="utf-8") as fh:
        for i in range(args.games):
            game_seed = args.seed + i
            # Snapshot mode: alternate seats so first-player advantage
            # cancels out; win/loss is always from the CHALLENGER's side.
            swap = args.opponent == "snapshot" and (i % 2 == 1)
            if swap:
                rec = run_one_game(
                    game_idx=i,
                    deck0=deck1,
                    deck1=deck0,
                    agent0=agent1,
                    agent1=agent0,
                    seed=game_seed,
                    opponent=args.opponent,
                )
                if rec["result"] == "win":
                    rec["result"] = "loss"
                elif rec["result"] == "loss":
                    rec["result"] = "win"
            else:
                rec = run_one_game(
                    game_idx=i,
                    deck0=deck0,
                    deck1=deck1,
                    agent0=agent0,
                    agent1=agent1,
                    seed=game_seed,
                    opponent=args.opponent,
                )
            if args.opponent == "snapshot":
                rec["challenger_seat"] = 1 if swap else 0
            records.append(rec)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            err = f" err={rec['error']}" if rec.get("error") else ""
            print(
                f"  game {i:03d}: {rec['result']:6s}  steps={rec['steps']}  "
                f"rewards={rec['rewards']}{err}"
            )

        summary = summarize(records, opponent=args.opponent, seed=args.seed)
        fh.write(json.dumps(summary, ensure_ascii=False) + "\n")
        fh.flush()

    print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
