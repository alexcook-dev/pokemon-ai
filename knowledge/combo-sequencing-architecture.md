# Combo-sequencing architecture (tiers 1-4), 2026-07-20

Implements the fix for a named limitation: `agent/policy.py`'s base scorer
(`_think_score_base` / `_human_play_card_base`) is a stateless per-option
greedy scorer with no lookahead and no memory across the several
`choose_actions` calls in one turn, so it cannot represent "play these two
cards together, in this order" (e.g. Boss's Orders then Unfair Stamp) or
"invest now for a payoff later" (e.g. Ogerpon's Teal Dance). Four additive
layers close that gap without touching the tested base scorer:

- **Tier 1 (knowledge):** `_BASE_CARD_VALUE` + `_synergy_bonus` — hand-authored
  per-card values and pairwise synergy terms (Boss before Stamp: +40; wrong
  order: -15). Also gave Unfair Stamp and Prime Catcher explicit base scores
  in `_human_play_card_base` — previously both fell through to the ~45
  generic catch-all.
- **Tier 2 (memory):** `_TURN_PLAN_CACHE` / `_get_turn_plan` — persists a plan
  across calls within one turn. Keyed by `(seat, turn, sorted hand ids)`, so
  it is safe when the same policy instance pilots both seats in self-play /
  tournament runs (unit-tested: seat 0 and seat 1's plans never leak into
  each other even with the same turn number) and self-healing (a draw/search
  mid-turn changes hand_ids, which misses the cache and forces a fresh plan).
- **Tier 3 (search):** `_search_best_order` — bounded (<=4 cards, <=24
  permutations) search over PLAY ORDER this turn using tier 1's values.
  Explicitly NOT multi-turn game-tree search — the compiled `libcg.so`
  engine gives no fork/rollout hook to build that against.
- **Tier 4 (learned):** `agent/learned_scorer.py` + `eval/train_value_model.py`
  — an additive scoring adjustment from a trained model. Complete, runnable
  infrastructure, but OFF by default on two independent gates (no weights
  file ships; `PTCG_USE_LEARNED_SCORER=1` required even if one exists) and
  NOT trained/validated as part of this change — matches program.md's
  Approach C scoping (real risk of not converging, validate via protocol v2
  before ever trusting it for a submission).

## COMBO_CANDIDATES scope — Items only, not Supporters

Only ONE Supporter is legal per turn (`sit["supporter_played"]`), so there is
no same-turn "order" between two Supporters (e.g. Crispin vs Lillie's
Determination) to search over. An early draft included them anyway; see
the debugging story below for what that cost.

## Debugging story — a false alarm, then a real (small) question, resolved

**Step 1 — alarm:** first cut scored 84% vs random (frozen protocol, seed 0),
down from the 94% recorded at commit `1020794`. Looked like a serious
regression.

**Step 2 — wrong diagnosis, first fix:** found and fixed a real placement
bug (Unfair Stamp's bonus lived *after* the `can_attack and energy_done`
early-return, so it only ever fired pre-attack — wasting tempo — never in
the intended post-KO lock window). Re-tested: 82%, not recovered.

**Step 3 — second real fix:** removed Crispin/Lillie from
`COMBO_CANDIDATES` (the flawed Supporter-ordering inclusion above).
Re-tested: 84%, still not back to 94%.

**Step 4 — reverify the baseline itself:** `git stash`ed all changes and
re-ran the *unmodified* code on the same seed. Result: **84%, identical
42-8 record** — the unmodified code no longer reproduces 94% either. Root
cause: 94% was recorded before the later "use energy" `deck.csv` swap
(Hand Trimmer -> 4th Psychic Energy, see `deck-substitution-rule.md`),
which itself cost ~10pp and was already flagged in
`dragapult-dusknoir.md` ("the next `/ptcg-train` run starts with a fresh
50-game baseline") — that fresh baseline never actually got run before
this session moved into deck-brewing and tournament work. **The
combo-sequencing code was never the source of the apparent regression.**

**Step 5 — the real question, answered cleanly:** vs-random at ~84-86% is
close enough to saturated that single-seed noise (~±10pp at n=50, p≈0.85)
can't distinguish a small real effect from sampling variance (seed 0:
exact match, 84% both; seed 500: baseline 86% vs new code 76% — a gap
inside the noise band). Resolved with the sharper instrument built for
exactly this: **champion-vs-challenger (protocol v2)**, champion pinned to
commit `0674f51` (pre-change code, confirmed identical `deck.csv` to the
current one — the one variable isolated). Result: **25-25, exact 50%,
0 crashes.** The new architecture is statistically indistinguishable from
the old code on this deck — expected, since the only real behavior change
(Boss-before-Stamp ordering) needs both cards in hand simultaneously, and
Unfair Stamp is a 1-of in a 60-card deck. Prime Catcher (the other
combo-capable card) has 0 copies in this deck, so tier 1-3 is close to a
true no-op here; it should matter more on decks running heavier combo-card
counts (Hydrapple's documented H4 Boss+Stamp hint is the next place to
look — both copies of Boss AND Stamp are denser there).

## Lesson for future sessions

Before diagnosing ANY win-rate change, reverify the OLD code still
reproduces the recorded baseline number on the current deck/environment.
A deck change (or any other drift) can silently invalidate an old
baseline; don't assume a recorded number is still real without checking.
Champion-vs-challenger resolves noise that vs-random cannot once win rate
is this close to saturated — reach for it first, not last.

## Next steps (not done here)

- Test Hydrapple's H4 hint (denser Boss+Stamp count) through this same
  machinery — better chance of a measurable effect than on Dragapult.
- Extend `COMBO_CANDIDATES` as new combo-shaped POLICY HINTS get ingested
  by `/ptcg-guide`.
- If tier 4 is ever trained (`eval/train_value_model.py`), validate via
  champion-vs-challenger before considering it for a real submission —
  same bar this architecture change itself was just held to.
