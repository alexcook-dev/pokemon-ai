# Meta matchup matrix — full 9-deck round-robin, 2026-07-20

> Derived from ~700 engine games via eval/run_h2h.py — both seats piloted by the live policy (post-jul20b, 94%-vs-random commit), seats alternating. 20 games per pairing (±11pp noise at 95% CI per cell — treat single cells as indicative, row aggregates as reliable). Raw: `eval/results_h2h.jsonl` (untracked).

**Field decks use their REAL special energies** (Telepath Psychic id 19, Grow Grass 18,
Rock Fighting 20, Mist 11, Spiky 14 — the earlier gauntlet had accidentally
energy-nerfed t1/t2/t5/t6/t7; its standings are superseded by this matrix).

## Win-rate matrix (row's win % vs column, draws excluded)

|  | ala-prime | ala-stock | dragapult | hydrapple | kanga | lopunny | lucario | rillaboom | rocket |
|---|---|---|---|---|---|---|---|---|---|
| **kangaskhan** | 45 | 65 | 50 | 50 | — | 45 | 42 | 60 | 75 |
| **hydrapple** | ? | 50 | 60 | — | 50 | 50 | 60 | 40 | 55 |
| **dragapult** | 45 | 40 | — | 40 | 50 | 40 | 70 | 50 | 45 |
| **rillaboom** | 75 | 55 | 50 | 60 | 40 | 70 | 32 | — | 45 |
| **ala-stock** | 37 | — | 60 | 50 | 35 | 32 | 60 | 45 | 45 |
| **lopunny** | 75 | 68 | 60 | 50 | 55 | — | 45 | 30 | 32 |
| **lucario** | 45 | 40 | 30 | 40 | 58 | 55 | — | 68 | 58 |
| **ala-prime** | — | 63 | 55 | ? | 55 | 25 | 55 | 25 | 65 |
| **rocket-mewtwo** | 35 | 55 | 55 | 45 | 25 | 68 | 42 | 55 | — |

## Max-min ranking (worst matchup / overall)

1. **kangaskhan 42% / 54%** — only deck with no matchup below 42%; best overall
2. hydrapple 40% / 52%
3. dragapult 40% / 48% (mid-field — the gauntlet's last-place read was an artifact of the nerfed field)
4. rillaboom 32% / 53%
5. alakazam-stock 32% / 46%; lopunny 30% / 52%; lucario 30% / 49%
6. alakazam-prime 25% / 49%; rocket-mewtwo 25% / 47%

## The rock-paper-scissors chains

- Lopunny (Mist/Spiky) → beats both Alakazams (68-75%) → but loses to Rillaboom (30%) and Rocket-Mewtwo (32%)
- Rillaboom → beats Lopunny (70%) and ala-prime (75%) → loses to Lucario (32%)
- Lucario → beats Rillaboom (68%) → loses to Dragapult (30%)
- Dragapult → beats Lucario (70%) → soft to Alakazam/Lopunny/Hydrapple (40-45%)
- **No >50%-vs-all deck exists in this pool.**

## Mechanism notes (from engine strings, libcg)

- Alakazam "Powerful Hand": *"Place 2 damage counters on your opponent's Active
  Pokémon for each card in your hand"* — effect-based counters, scales with the
  deck's Kadabra "Psychic Draw" / Dudunsparce "Run Away Draw" engine.
- Mist Energy: *"Prevent all effects of attacks used by your opponent"* — the
  verified anti-effect tech; Lopunny runs 4.
- alakazam-prime experiment (t6 + 4th Rare Candy, −1 basic P): beats stock 63%
  head-to-head but inherits harder counters (25% vs Lopunny/Rillaboom) — a
  faster cannon is still a cannon.

## Nomination

**Mega Kangaskhan box (deck_t3, STOCK list) = best ladder-deck candidate** by
max-min (42% worst) and overall (54%). Dragapult (current live deck) is
defensible mid-field; a deck switch is a judgment call, not an emergency.

### kanga-mist variant — TESTED 2026-07-20, DISCARDED

−1 Water, −1 Psychic splash energy, +2 Mist Energy. Full 8-matchup row
(20 games each): prime 60 (+15), lopunny 55 (+10), lucario 50 (+8) — the
three target matchups all lifted as the Mist mechanism predicted — BUT
rillaboom 35 (−25), rocket 40 (−35), hydrapple 37 (−13), stock-ala 50 (−15),
dragapult 70 (+20). New worst-case 35% < stock's 42% → discard. Lesson:
the 1-of splash energies are load-bearing matchup coverage (likely
Chien-Pao {W} / Latias {P} attack costs), not free slots. Any future
Kangaskhan tech must cut something else.
