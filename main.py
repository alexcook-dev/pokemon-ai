"""
PTCG AI Battle agent entrypoint (Kaggle cabt).

Observation:
  - select is None  → deck-selection phase: return 60 card IDs
  - select is set   → return indices into select["option"] (length = maxCount)

Decision logic lives in agent/policy.py (heuristic v1).
"""
from __future__ import annotations

import random
from pathlib import Path

try:
    _ROOT = Path(__file__).resolve().parent
except NameError:
    # Kaggle's harness execs main.py's raw source rather than importing it
    # as a module, so __file__ is never defined there.
    _ROOT = Path.cwd()

# Prefer deck_knowledge.DECK; fall back to deck.csv / sample.
try:
    from agent.deck_knowledge import DECK as DECK  # type: ignore
except Exception:
    _DECK_PATH = _ROOT / "deck.csv"
    if _DECK_PATH.exists():
        DECK = [
            int(line.strip())
            for line in _DECK_PATH.read_text().splitlines()
            if line.strip()
        ]
    else:
        DECK = [5] * 10 + [9, 9] + [77] * 4  # should not hit in this project

try:
    from agent.policy import choose_actions
except Exception:  # pragma: no cover
    choose_actions = None  # type: ignore


def _random_actions(obs: dict) -> list[int]:
    select = obs.get("select") or {}
    options = select.get("option") or []
    max_count = int(select.get("maxCount") or 0)
    n = len(options)
    if max_count <= 0 or n == 0:
        return []
    k = min(max_count, n)
    return random.sample(list(range(n)), k)


def agent(obs: dict) -> list[int]:
    # Phase 1: submit deck (exactly 60 card IDs)
    if obs.get("select") is None:
        if len(DECK) != 60:
            raise ValueError(f"Deck must have 60 cards, got {len(DECK)}")
        return list(DECK)

    # Phase 2+: heuristic policy over legal options
    if choose_actions is not None:
        try:
            actions = choose_actions(obs)
            select = obs.get("select") or {}
            max_count = int(select.get("maxCount") or 0)
            n = len(select.get("option") or [])
            if (
                isinstance(actions, list)
                and len(actions) == max_count
                and all(isinstance(i, int) and 0 <= i < n for i in actions)
            ):
                return actions
        except Exception:
            pass

    return _random_actions(obs)
