# Dragapult / Dusknoir — strategy knowledge

- Source: seeded from DECK_MAPPING.md + established Grok-session decisions, ingested 2026-07-20
- Guide author/level: internal baseline (no external guide ingested yet — replace/extend when one is posted)

## Decklist (mapped to competition IDs)

See `DECK_MAPPING.md` for the full 60-card mapping with reprint substitutions.
Live as `deck.csv`. Notable: Special Red Card was not in the pool →
substituted Hand Trimmer (1087) for hand disruption.

## Archetype & win condition

Evolution-line deck: Dreepy → Drakloak → Dragapult ex as the primary attacker,
with a Duskull → Dusclops → Dusknoir secondary line. Wins by spreading damage
(Phantom Dive) and converting spread into multi-KO turns, trading its 2-prize
attacker efficiently against the opponent's board.

## Game plan by phase

- Setup (turns 1-2): bench Dreepy (multiple), get Duskull down, dig with
  Poffin/Ultra Ball/Poké Pad for evolution pieces.
- Build: evolve into Drakloak (draw engine) ASAP; attach energy on curve
  (Psychic consistency); time supporters around what the hand needs.
- Attack: Phantom Dive for board spread; use Dusknoir line to finish damaged
  targets; keep a second Dragapult building behind the active.

## Opening priorities

- **Go FIRST** — evolution deck needs the extra evolution turn (established
  rule in `policy.py::_want_to_go_first`: evolution-line decks go first;
  ready-to-attack basic decks go second, since first player can't attack T1).
- Mulligan logic: accept mulligan when offered with no basic (CTX_MULLIGAN → YES).

## Key decision rules

- WHEN seat choice offered AND deck is evolution-line → choose first.
- WHEN optional effect offered (activate / first-effect contexts) → usually take it (70/30 prior).
- WHEN opponent's key threat is within KO range AND gust (Boss's Orders) in hand → weigh Boss heavily (exp1 raised this weight; kept — win rate improved).

## Matchups

(none documented yet — populate from real guides via /ptcg-guide)

## Tech cards & why

- Hand Trimmer (1087): hand disruption, substitute for out-of-pool Special Red Card.
- Munkidori (112): damage-counter movement synergizes with Phantom Dive spread.
- Unfair Stamp (1080): post-KO hand disruption swing turn.

## POLICY HINTS (testable hypotheses for /ptcg-train)

- H1: exp1 (higher attack/attach/evolve/boss weights) already KEPT — direction
  validated; further weight increases may have diminishing or negative returns.
- H2: Prize-aware attacker choice (prefer single-prize attackers when the
  prize trade favors it) — from program.md target style #5; untested.
- H3: Spread-then-execute sequencing (score Phantom Dive higher when it sets
  up a Dusknoir pick-off next turn) — untested.

## Open questions

- No external guide for this archetype ingested yet — matchup table empty.
- Second deck list from the original session was never pasted (DECK_MAPPING.md
  notes "Only 1 of 2 lists was pasted").
