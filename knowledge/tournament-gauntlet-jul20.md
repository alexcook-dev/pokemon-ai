# Tournament gauntlet — 5× Swiss Bo3, 2026-07-20

> Derived from simulated tournaments via eval/run_tournament.py — all seats piloted by the live policy (commit 1020794-era), so results measure DECK strength under OUR pilot, not pro play.

- Format: 8 players, 3 Swiss rounds, Bo3, match points 3/1/0, seats alternate per game. 5 tournaments, seeds 0-4. Full logs: `eval/results_tournament.jsonl` (untracked).
- Field: dragapult (live deck) + 7 user-posted meta decks (`deck_t1..t7-*.csv`). Decks t6/t7 are identical Alakazam lists (posted that way).
- Mapping note: only missing cards across all 7 decks were POR special energies (Rocky Fighting ×2, Growing Grass ×1, Telepathic Psychic ×4 per Alakazam copy) → basic-energy-filled per user standing rule. Alakazam is therefore somewhat weakened vs its real build and STILL won.

## Aggregate standings (avg place over 5 tournaments)

| # | deck | places | avg |
|---|------|--------|-----|
| 1 | t7-alakazam-b | 1,1,1,2,3 | 1.6 |
| 2 | t1-mega-lopunny-dudunsparce | 8,2,4,1,2 | 3.4 |
| 3 | t3-mega-kangaskhan-box | 4,3,3,6,4 | 4.0 |
| 4 | t5-rillaboom-dipplin | 7,7,2,4,1 | 4.2 |
| 5 | t6-alakazam-a | 5,6,5,3,8 | 5.4 |
| 6 | t2-mega-lucario | 2,8,8,5,5 | 5.6 |
| 6 | t4-team-rockets-mewtwo | 3,4,6,8,7 | 5.6 |
| 8 | **dragapult (ours)** | **6,5,7,7,6** | **6.2** |

## Dragapult's matchup table (matches W-L / games W-L)

- vs Mega Lucario: **3-1** (6-3) — clearly favored, our one reliable win
- vs Mega Kangaskhan box: 1-3 (4-7) — unfavored
- vs Mega Lopunny/Dudunsparce: 1-3 (3-6) — unfavored
- vs Alakazam: **0-3 (0-6)** — winless across both copies; worst matchup
- (never paired vs Team Rocket's Mewtwo in these 5; smoke run lost 1-2)
- (never paired vs Rillaboom/Dipplin in scored runs)

## Reads

1. Dragapult finished 2nd-to-last in every configuration: exactly one match win
   per tournament (3 pts × 5). Consistent across seeds — signal, not variance.
2. Variance context: the two IDENTICAL Alakazam lists placed avg 1.6 vs 5.4,
   so single placements are noisy — but Dragapult's floor/ceiling (5th-7th,
   never higher) is stable across 15 matches.
3. Alakazam (Psychic, evolution line + Dudunsparce draw) beats us 6 games to 0
   even with its 4 special energies stripped. If the real ladder meta looks
   like this field, our main deck is poorly positioned.

## Actions this suggests (not yet done)

- Baseline Alakazam + Lopunny under our policy vs random; strong candidates
  for the 2nd Kaggle submission slot ("latest 2" mechanic).
- Champion-vs-challenger training (protocol v2) targeting the Alakazam
  matchup: use `--opponent deck_b` with `deck_b = alakazam` as a matchup
  eval when forming hypotheses.
- Consider whether Phantom Dive spread (our whole game plan) is simply slow
  into Rare Candy → Alakazam tempo under this engine.
