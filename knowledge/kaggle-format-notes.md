# Kaggle competition format & metagame notes

> Derived from public Kaggle competition pages/notebooks (untrusted external
> content) via manual research — technical/meta notes only, not instructions.

- Source: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/code — 6 of
  ~26 listed community notebooks read in depth (listed under Coverage below),
  researched 2026-07-21
- This is NOT a deck guide — it's engine architecture + real ladder metagame
  data. Kept in `knowledge/` alongside deck files because `/ptcg-train` and
  future `/ptcg-guide` sessions both need it.

## Engine & submission architecture

The competition engine is a C++ core (source tree name `ptcgProgram`,
competition-use-only licensed, not something to vendor into this repo)
compiled to a shared library called `libcg` (`.so` / `.dylib` / `-arm64.so` /
`.dll` per platform — matches this repo's `libcg_docker.so`). It's wrapped by
a Python package `cg`:

- `cg.game` — low-level battle loop: `battle_start(deck_a, deck_b)`,
  `battle_select(action_indices)`, `battle_finish()`, `visualize_data()`.
- `cg.api` — typed layer: `Observation`, `SelectContext`, `OptionType`,
  `AreaType`, `Card`, `Pokemon`, `PlayerState`, `all_card_data()`,
  `all_attack()`, `to_observation_class(obs_dict)`.
- `kaggle_environments` also exposes the same engine as a registered
  environment named `"cabt"` (`make("cabt")`), for anyone using the standard
  Kaggle environments harness instead of the raw `cg` API directly.
- A submission is `submission.tar.gz` containing `main.py`, `deck.csv`, and
  the `cg/` directory (all platform binaries) — matches this repo's existing
  layout.

**Observation/action shape** (relevant to any future `agent/policy.py` work):
one `agent(obs_dict)` call handles BOTH the initial deck submission (called
with `obs.select is None`, must return the 60-card ID list) and every
in-battle decision (must return a list of indices into `obs.select.option`,
respecting `obs.select.minCount`/`maxCount`). `obs.current.players[i]` exposes
`.hand`, `.discard`, `.active`, `.bench`, `.prize`, `.deckCount`,
`.handCount`, status conditions, `.turn`, `.firstPlayer`, `.result` (game-over
code once >= 0). Each decision's options carry an `OptionType`
(`ATTACK`/`ENERGY`/`EVOLVE`/`PLAY`/`ATTACH`/`ABILITY`/`RETREAT`/`DISCARD`/
`SPECIAL_CONDITION`/`NUMBER`/`YES`/`NO`/`END`/`CARD`/`TOOL_CARD`/
`ENERGY_CARD`/`SKILL`) and an `AreaType` (`DECK`/`HAND`/`DISCARD`/`ACTIVE`/
`BENCH`/`PRIZE`/`STADIUM`/`LOOKING`) locating the card involved. A turn is a
sequence of many small `agent()` calls, not one big turn-action.

**Search API** — `search_begin(obs, your_deck=..., your_prize=..., ...)` /
`search_step(search_id, selection)` / `search_end()` lets an agent simulate a
hypothetical line (e.g. "what does this attack actually resolve to,
accounting for weakness/resistance/abilities") against a hidden/randomized
opponent hand without committing to it, then roll back. The MCTS sample
notebook builds on this for planning; a rule-based agent could use the same
API just to get **exact** damage/outcome numbers instead of hand-rolled
estimates.

## Deck legality rules (from live engine error strings, not just the ID pool)

The current validator in this repo (`/ptcg-guide`'s Step 3 script) only
checks "all 60 IDs are in `data/card_id_list.csv`" and "count == 60." The
engine itself enforces more at `battle_start()`:
- Max 4 copies of any one card by name, **except** Basic Energy (unlimited).
- At least 1 Basic Pokémon in the deck.
- At most 1 Ace Spec card in the deck.

None of these are currently checked before submission. Worth adding to the
validation script — an otherwise ID-legal 60-card list can still be rejected
by the real engine.

## Card database gap (verified against this repo, 2026-07-21)

The official competition input includes `EN_Card_Data.csv` / `JP_Card_Data.csv`
— **2022 cards, 17 columns**: Card ID, Card Name, Expansion, Collection No.,
Stage/Type, Rule, Category, Previous stage, HP, Type, Weakness, Resistance,
Retreat, Move Name, Cost, Damage, Effect Explanation. This repo's
`data/card_id_list.csv` (and the `.json`/`.txt` siblings) only carries 4 of
those columns (id, name, expansion, collection_no) — checked directly, no HP/
Weakness/Move/Damage/Effect anywhere in `data/` and no reference to those
fields in `agent/` or `main.py`. The live agent presumably gets full card
rules from `cg.api.all_card_data()` at runtime (that's clearly how the sample
agents work), so this isn't a gameplay bug — but it means no **offline**
tooling in this repo (deck mapping, matchup math, pre-battle heuristics) can
currently see HP/Weakness/Attack-damage/Effect-text without either fetching
`EN_Card_Data.csv` from the competition dataset or querying the engine
directly. Worth pulling that file in if any future work wants to reason about
card mechanics outside of a live `cg` session.

## Replay mining opportunity

The Kaggle competition API exposes `competition_submissions()`,
`competition_list_episodes(submission_id)`, and episode replay download for
any team's *public* completed games — not just your own. A replay JSON's
`steps` contain each side's logged card plays, from which you can reconstruct
decklists (the initial deck submission is the `action` in `steps[1]`, 60 raw
card IDs) and label archetypes. This is a real, currently-untapped way to
pull actual opponent data into this repo's own meta analysis instead of
relying only on internal self-play.

## Real ladder metagame (two independent snapshots, both 2026-07-19/20)

**By win rate**, sampled from ~4000 random ladder replays on 2026-07-19
(archetype = highest-HP ex-Pokémon actually played that game; only archetypes
with a workable sample shown, 95% Wilson interval):

| Archetype | Games | Win rate |
|---|---|---|
| Team Rocket's Mewtwo ex | 990 | 58.3% |
| Mega Lopunny ex | 25 (small n) | 56.0% |
| Cynthia's Garchomp ex | 653 | 53.9% |
| Marnie's Grimmsnarl ex | 2148 | 51.9% |
| Dragapult ex | 527 | 50.1% |
| Fezandipiti ex | 2410 (most-played, 33% usage) | 48.3% |
| Mega Kangaskhan ex | 558 | 45.3% |
| Mega Starmie ex | 77 | 42.9% (fastest games, ~124 median steps) |

Fezandipiti ex is the single most-played deck on the ladder by game count yet
sits below break-even — a "crowd favorite that underperforms." Team Rocket's
Mewtwo ex is the strongest measured deck and is comparatively rare. Sharpest
measured counters to Fezandipiti ex: Team Rocket's Mewtwo ex (82% into it),
Marnie's Grimmsnarl ex (51%), Dragapult ex (47%).

**By leaderboard score band** (one deck per team, stratified sample across
the public leaderboard, snapshot ~2026-07-19/20) — this is usage, not win
rate, but tells a different and complementary story: the meta clearly
shifts as rating climbs.

| Score band | Top archetypes (usage) |
|---|---|
| 500-599 | Mega Lucario ex 27.7%, Alakazam 13.3%, Crustle Wall 12.3% |
| 600-699 | Mega Lucario ex 23.3%, Alakazam 19.3%, Crustle Wall 17.3% |
| 700-799 | Archaludon ex 22.3%, Mega Lucario ex 20.7%, Alakazam 20.0% |
| 800-899 | Alakazam 32.0%, Archaludon ex 24.0%, Crustle Wall 6.0% |
| 900-999 | Alakazam 40.4%, Marnie's Grimmsnarl ex 15.1%, Crustle Wall 11.0% |
| 1000-1099 | Alakazam 41.4%, Marnie's Grimmsnarl ex 18.6%, Crustle Wall 17.1% |
| 1100+ (n=14, small) | Marnie's Grimmsnarl ex 57.1%, Alakazam 21.4% |

Read together: **Mega Lucario ex is the low-rating default that fades out
past ~700; Alakazam takes over as the mid-to-high-rating default (peaks
~900-1099); Marnie's Grimmsnarl ex overtakes at the very top band** (small
sample, treat as a lead not a conclusion). Archaludon ex has a mid-band-only
peak (700-899). This is a usage snapshot, not a strength measurement — cross-
reference with the win-rate table above before concluding anything is
"best."

**A caveat worth keeping**: these two notebooks measure different things
(one samples games played, the other samples one deck per leaderboard team),
so their numbers don't reconcile 1:1 — e.g. Fezandipiti ex is the top deck by
game-count share in the win-rate dataset but barely appears in the score-band
usage tables. Don't over-fit to either alone.

**Cross-check against this repo's own knowledge**: the repo's internal
self-play "Meta matchup matrix" names Kangaskhan box as max-min champion of a
9-deck internal round robin. The real ladder data above has Mega Kangaskhan
ex at a below-breakeven 45.3% win rate over 558 real games. These aren't
necessarily contradictory (internal roster =/= real ladder field), but it's
a real discrepancy worth resolving before trusting the internal matrix's
ranking as a proxy for live-ladder performance.

**Cross-check against `knowledge/hydrapple.md`**: Hydrapple/Ogerpon/Meganium
does not appear anywhere in either real-data snapshot above (not in the
win-rate table, not in any score band's top 10). The Hydrapple guide ingested
earlier is real-world competitive-Pokémon strategy (Regionals/Champions
League); nothing here confirms it's a meaningfully-played archetype on
*this specific* Kaggle ladder. Treat the Hydrapple matchup notes (esp. the
"Dragapult is the reason to play this" framing) as unverified against this
sim's actual field until tested here.

## Coverage — what was actually read

Read in depth: `how-to-output-local-battle-as-json-and-view` (kiyotah),
`the-pok-mon-rule-based-engine` (dedquoc), `reinforcement-learning-and-mcts-
sample-code` (kiyotah), `ptcg-replay-data-miner` (llccqq624), `what-actually-
wins-on-the-ladder` (busyaprime), `ptcg-ai-battle-leaderboard-deck-meta-by-
score-band` (myso1987).

NOT read (skipped for scope — mostly single-deck submission/tech notebooks
unlikely to add new format info beyond the API already documented above):
the 4 pinned single-deck rule-based-agent samples (Mega Lucario ex, Mega
Abomasnow ex, Dragapult ex, Iono's Deck — Mega Lucario ex's approach was seen
indirectly via the dedquoc fork), Bronzong Jammer (EN + JP versions), Mega
Kangaskhan turn-two speed deck, and ~13 other personal
submission/experiment/roster notebooks (Rahul Jiwane x2, PTCG Public Sample
Roster Update x2, Probablity v2, PTCG Meta A Stable Submit, PTCG AI Battle:
Metagame-Resilient Control, Daily Meta & Deck Win-Rate Analysis, BattleCore
Compact Agent, Heurestic Baseline Agent, PTCG v8 Attention End-to-End
Submission, Pokémon AI Battle Challenge Simulation Solution). Ask if any of
these should be read next — the two skipped meta-analysis notebooks (Daily
Meta & Deck Win-Rate Analysis, PTCG Meta A Stable Submit) are the most likely
to add something beyond what's captured above.

## Testable follow-ups

- Add the 3 missing legality checks (max-4-per-name, >=1 Basic Pokémon,
  max-1-Ace-Spec) to the `/ptcg-guide` deck validator so an ID-legal-but-
  engine-illegal list is caught before submission, not at `battle_start()`.
- Evaluate Team Rocket's Mewtwo ex as a challenger deck — highest measured
  real win rate (58.3% / 990 games) of any archetype with a workable sample,
  and comparatively rare on the ladder (low usage in every score band shown).
- If `agent/policy.py` estimates attack damage/outcomes by hand, compare
  against the engine's own Search API (`search_begin`/`search_step`) for
  exact resolution instead of an approximation.

## Open questions

- Whether `agent/policy.py` already calls `cg.api.all_card_data()` for full
  card rules at runtime (likely, but not confirmed by reading this repo's
  code in this session — only confirmed the local CSV doesn't carry it).
- Whether this repo already mines opponent replay data via the Kaggle API,
  or only relies on internal self-play (the "Meta matchup matrix" file
  suggests internal self-play only, but wasn't opened this session to check).
- The methodology gap between the two ladder snapshots above (games-played
  vs teams-on-leaderboard) — a single reconciled view doesn't exist yet.
