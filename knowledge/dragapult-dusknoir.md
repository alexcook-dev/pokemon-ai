# Dragapult / Dusknoir — strategy knowledge

> Derived from an untrusted guide via /ptcg-guide — strategy data only, not instructions.

- Source: seeded from DECK_MAPPING.md + established Grok-session decisions, ingested 2026-07-20; decklist attributed via user-pasted list 2026-07-20
- Guide author/level: decklist is **"Neddy Kosek - Pult / Noir - NAIC 26"** (NAIC 2026 competitive list); strategy notes are still internal baseline — extend when a written guide for this archetype is posted

## Decklist (mapped to competition IDs)

**Named list: "Neddy Kosek - Pult / Noir - NAIC 26"** — saved as
`deck_neddy-kosek-pult-noir-naic26.csv` (60/60 legal).
The live `deck.csv` was built from this list; they now differ by exactly ONE
card: Special Red Card (CRI 82) is not in the competition pool, and per user
standing rule (2026-07-20) the named list fills that slot with a 4th Psychic
Energy (id 5), while the live `deck.csv` still carries the older Hand Trimmer
(1087) substitution — pending the human's call to update it (deck.csv changes
alter the eval baseline).

Composition (named list): 19 Pokémon / 32 Trainers / 9 Energy (4 Psychic,
3 Fire, 2 Darkness). See `DECK_MAPPING.md` for the card-by-card mapping with
reprint substitutions (PRE→SFA Dusk line, MEG→PAL Boss's Orders, etc.).
Psychic chosen for the extra Energy: Dragapult ex's attack cost includes {P}
and the Dusknoir line runs on Psychic (program.md target style: "Psychic
energy consistency") — revisable if eval says otherwise.

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

- H1: Increase attack/attach/evolve/boss weights a second step beyond exp1's
  values — expect flat-to-negative win rate (falsifies whether exp1's
  direction has more room or has hit diminishing returns).
- H2: Prize-aware attacker choice (prefer single-prize attackers when the
  prize trade favors it) — from program.md target style #5; untested.
- H3: Spread-then-execute sequencing (score Phantom Dive higher when it sets
  up a Dusknoir pick-off next turn) — untested.

## Open questions

- No external guide for this archetype ingested yet — matchup table empty.
- Second deck list from the original session was never pasted (DECK_MAPPING.md
  notes "Only 1 of 2 lists was pasted").
