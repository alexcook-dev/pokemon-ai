"""
Human vs AI: you pilot a deck against the trained policy, turn by turn.

  YOU  = seat 0, deck from $HUMAN_DECK (default: deck_grant-walworth-hydrapple-naic2026.csv)
  AI   = seat 1, the live agent (main.agent → agent/policy.py + deck.csv)

Each of your turns prints the board and the legal options; type the option
number (or comma-separated numbers when several picks are required).

Env vars:
  HUMAN_DECK=<csv path>   deck you pilot (60 ids, one per line)
  HUMAN_AUTO=first        no prompts — auto-pick first option(s) (smoke test)
  HUMAN_SEAT=1            play seat 1 instead (AI goes first in seat 0)

Run through Docker on Mac (libcg is Linux-only): ./play_human_docker.sh
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from kaggle_environments import make

from main import agent as ai_agent
from agent.obs import load_card_catalog, parse_observation, describe_player
from agent.options import parse_options, describe_option

ROOT = Path(__file__).resolve().parent
HUMAN_DECK_PATH = ROOT / os.environ.get(
    "HUMAN_DECK", "deck_grant-walworth-hydrapple-naic2026.csv"
)
AUTO = os.environ.get("HUMAN_AUTO", "") == "first"
HUMAN_SEAT = 1 if os.environ.get("HUMAN_SEAT", "0") == "1" else 0

CATALOG = load_card_catalog()
_turn_counter = {"n": 0}


def _load_deck(path: Path) -> list[int]:
    ids = [int(l.strip()) for l in path.read_text().splitlines() if l.strip()]
    assert len(ids) == 60, f"{path} has {len(ids)} cards, need 60"
    return ids


HUMAN_DECK = _load_deck(HUMAN_DECK_PATH)


def _render(obs: dict) -> None:
    parsed = parse_observation(obs)
    print("\n" + "=" * 62)
    _turn_counter["n"] += 1
    print(f"[decision #{_turn_counter['n']}]  (you = {HUMAN_DECK_PATH.name})")
    try:
        print(describe_player(parsed.me, "YOU"))
        print(describe_player(parsed.opp, "AI "))
    except Exception as e:  # board render must never kill the game
        print(f"(board render unavailable: {e})")
    hand = getattr(getattr(parsed, "me", None), "hand", None)
    if hand:
        names = []
        for c in hand:
            try:
                from agent.obs import get_card_id

                cid = get_card_id(c)
                names.append(CATALOG.get(cid, str(cid)))
            except Exception:
                names.append("?")
        print(f"YOUR HAND ({len(names)}): " + ", ".join(names))


def _prompt(k: int, n: int) -> list[int]:
    while True:
        raw = input(f"pick {k} option number(s) 0-{n - 1} (comma-separated): ").strip()
        try:
            picks = [int(x) for x in raw.replace(" ", "").split(",") if x != ""]
            if len(picks) == k and all(0 <= p < n for p in picks) and len(set(picks)) == k:
                return picks
        except ValueError:
            pass
        print(f"  need exactly {k} distinct numbers in 0-{n - 1}, try again")


def human_agent(obs: dict) -> list[int]:
    if obs.get("select") is None:
        print(f"[deck phase] submitting {HUMAN_DECK_PATH.name}")
        return list(HUMAN_DECK)

    select = obs["select"]
    options = select.get("option") or []
    max_count = int(select.get("maxCount") or 0)
    n = len(options)
    if max_count <= 0 or n == 0:
        return []

    _render(obs)
    opts = parse_options(obs)
    print(f"LEGAL OPTIONS (choose {max_count}):")
    for o in opts:
        try:
            print(f"  [{o.index}] {describe_option(o)}")
        except Exception:
            print(f"  [{getattr(o, 'index', '?')}] (unrenderable option)")

    if AUTO:
        picks = list(range(min(max_count, n)))
        print(f"[auto] picked {picks}")
        return picks
    if n == 1 and max_count == 1:
        print("(only one legal option — auto-picked [0])")
        return [0]
    return _prompt(min(max_count, n), n)


def main() -> None:
    seats = [human_agent, ai_agent] if HUMAN_SEAT == 0 else [ai_agent, human_agent]
    env = make(
        "cabt",
        debug=True,
        configuration={
            "decks": None,  # each agent submits its own deck in the deck phase
            "actTimeout": 100_000,  # human thinking time
            "runTimeout": 1_000_000,
        },
    )
    # cabt's configuration.decks (when set) overrides agent deck submission;
    # drop the key entirely so both agents pick their own decks.
    if env.configuration.get("decks") is None:
        try:
            del env.configuration["decks"]
        except Exception:
            pass

    steps = env.run(seats)
    out = ROOT / "result_human.html"
    out.write_text(env.render(mode="html"))
    last = steps[-1]
    you, ai = (0, 1) if HUMAN_SEAT == 0 else (1, 0)
    r_you, r_ai = last[you].get("reward"), last[ai].get("reward")
    print("\n" + "=" * 62)
    print(f"steps: {len(steps)}   replay: {out.name}")
    if r_you == 1:
        print("RESULT: YOU WIN")
    elif r_ai == 1:
        print("RESULT: AI WINS")
    else:
        print(f"RESULT: draw/incomplete (you={r_you}, ai={r_ai})")


if __name__ == "__main__":
    main()
