# Advanced sequencing & strategic principles, 2026-07-20 (user-taught)

Extends `combo-sequencing-architecture.md`. User-supplied competitive TCG
knowledge — implemented where the data/pool support it, documented as
guidance where they don't (yet).

## Implemented

**Fezandipiti ex's real ability ("Flip the Script"), verified against the
engine binary, not memory:** *"Once during your turn, if any of your
Pokemon were Knocked Out during your opponent's last turn, you may draw 3
cards. Can't use more than 1 Flip the Script Ability each turn."* A draw
effect, not a tutor (correcting an initial assumption from general
knowledge). `_detect_ko_last_turn` (cross-turn memory, seat-isolated —
distinct from tier 2's within-turn cache, which deliberately resets every
turn) tracks the trigger by watching `opp_prize` drop between our turns
(opp_prize only decreases when they take a prize, which only happens when
they KO one of ours). `_fez_flip_the_script_live(sit)` gates a 120->180
ability-score boost.

**Unfair Stamp before Fezandipiti's ability, both directions of the
"resolve KO first" sequencing:**
- `Unfair Stamp > Fez`: scores Stamp at 190 (above the ability's 180) when
  the ability is live, in both the ready-to-attack AND not-yet-attacking
  windows. General principle, not just this one pair: resolve a
  hand-shrinking effect BEFORE a hand-growing one this same turn, so the
  growing effect isn't complicated by disruption landing on top of a
  hand that just grew.
- `Iono > Fez`: **Iono is not in this competition's card pool** (checked
  `data/card_id_list.csv` directly — absent). Not implementable today.
  Recorded here so the principle is ready the moment a hand-reset-and-draw
  card like it gets ingested via `/ptcg-guide`: sequence hand-reset/shuffle
  effects BEFORE other draw effects in the same turn, so the extra draws
  survive instead of being swept back into the deck.

**Opponent-target selection (Boss's Orders / gust / snipe), a real
pre-existing gap fixed:** the `CTX_SWITCH`/`CTX_TO_ACTIVE` scoring branch
had NO `playerIndex` check at all — unlike the `CTX_DAMAGE`/`CTX_HEAL`
branches right next to it — so choosing our own retreat target and
choosing an opponent's gust target were sharing scoring logic tuned to
OUR deck's card IDs, meaningless against the opponent's different IDs.
Now branches on `playerIndex`: our own retreat keeps existing logic;
opponent targets use `_opponent_target_bonus` (denial-oriented — "lock a
Pokemon they don't want stuck active," per the user's framing, not just
"hit the biggest attacker"). **Real retreat cost is NOT available** —
checked `obs.py`'s parsing and two real logged debug dumps
(`eval/debug_main_opts.json`, `eval/debug_v2.json`) directly; no
`retreatCost` field anywhere in this obs schema. Uses defensible proxies
instead: low remaining HP (follow-up KO reachable), no energy attached
(forced active AND can't attack back — buys a free turn regardless of
actual retreat cost), and "ex" in the printed name (real-world proxy —
ex/mega Pokemon are overwhelmingly retreat-cost 2+ in the actual game;
an approximation, not measured data). Replace with real retreat costs if
a future engine version exposes them.

**Deck thinning:** every search effect (found or discarded-as-cost)
permanently removes a card from the remaining deck, improving the odds of
every FUTURE draw, not just this turn's pick — a compounding value the
scorer previously ignored entirely. `sit["deck_n"]` (from `deckCount`,
newly wired into `_read_situation`) now adds a small bonus to search
scoring, scaled by how much deck is left to thin (capped at +15, tapering
to 0 as the deck empties) rather than a flat add.

## Documented, not yet mechanized

**"Play to your outs" / anticipate the opponent / assume they hold their
best answer:** a real, correct competitive principle — make the play that
is good across the range of what the opponent might hold, not just the
play that's optimal against an empty hand. Not implemented as a mechanical
rule here: it's a *posture* that should inform many individual scoring
decisions (how much to overextend the board, when to hold up a removal
answer, whether to commit a combo piece early) rather than one clean
function, and encoding it wrong risks the same kind of subtle regression
`combo-sequencing-architecture.md` already documented once this session
(the Crispin/Lillie false start). Left as a design principle for future,
narrowly-scoped, individually-tested applications — e.g. "don't bench a
4th `ex` Pokemon when 3 already cover the turn's plan, since more `ex` on
board is more prize liability if the opponent has an unanswered snipe/gust
effect" would be one testable instance of this, not yet built.

## Validation

Champion-vs-challenger (protocol v2), deck held constant, vs the
previously-validated commit `042a33b`: **24-26 (48%), 0 crashes** — within
noise of 50% at n=50 (95% CI roughly ±14pp), consistent with these being
correctness fixes for specific, situational triggers (all of KO'd-last-turn
+ Fezandipiti-in-play + Stamp-in-hand co-occurring; a multi-target Boss's
Orders choice) rather than something that reshapes every game. Each piece
is unit-tested independently for correctness (including the seat-isolation
guarantee for the new cross-turn state, same pitfall tier 2 already hit
once). A denser test — Hydrapple runs both Boss's Orders and Unfair Stamp
at higher count than Dragapult — is the natural next place to look for a
clearer aggregate signal, per `combo-sequencing-architecture.md`'s own
"next steps."
