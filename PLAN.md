# PTCG Agent Plan (revised)

## Challenge (host intent)
Play Pokémon TCG in **cabt** under **incomplete information** (hidden hand), with draws/coins and diverse decks. Same SDK as Kaggle. **Rule-only may not rank high** — need adaptation and eventually search/learning. Metric: **wins / skill rating**.

## Fixed assets
| File | Deck |
|------|------|
| `deck.csv` | **Primary — Dragapult / Dusknoir** (mapped) |
| `deck_b.csv` | **Sparring — Teal Mask Ogerpon grass** (mapped) |
| `data/card_id_list.csv` | Only legal Card IDs (~1259) |

Both decks validated in cabt (full games, no INVALID).

## Lessons baked into this plan
1. Never invent IDs; reprints can change strategy (PBL failed).
2. One game = smoke only; use **50-game batches**.
3. Heuristic bugs that kill win rate: retreat > end, wrong roles, go first, attach to bench, never attack.
4. Best so far: **~58% vs random / 50 games, 0 crashes** (old list). Gate still **≥70%**.
5. Lucario experiment failed = illegal deck (2-step draws) — always validate deck first.
6. Policy must be **deck-aware** (Dragapult evolution + multi-energy).

## Success gates
| Gate | Criteria |
|------|----------|
| **G0** | Deck legal in cabt (full game finishes) — **DONE** for both lists |
| **G1** | Heuristic agent, 0 crashes / 50 games |
| **G2** | **≥70% vs random** / 50 games (same primary deck) |
| **G3** | **≥55% vs deck_b** (Ogerpon) / 50 games with random opponent on B *or* agent on both |
| **G4** | Package + Kaggle validation pass |
| **G5** | Ladder >600 and rising (post-submit) |

## Architecture (keep)
```
main.py                 # Kaggle entry: deck + choose_actions
agent/obs.py            # parse board
agent/options.py        # typed options
agent/deck_knowledge.py # roles from deck.csv names
agent/policy.py         # heuristic scorer (v3+)
eval/run_batch*.sh      # Docker N-game eval
```

## Workstreams (priority)

### W1 — Primary deck = Dragapult (now)
- Ensure `deck.csv` = Dragapult map; knowledge roles for Dreepy/Drakloak/Dragapult/Dusk/Crispin energies.
- Policy priorities:
  1. Setup: Dreepy/Duskull Active/Bench
  2. Evolve Dreepy→Drakloak→Dragapult; Duskull line when useful
  3. Crispin / energy attach (P/R/D) onto attacker
  4. Attack when legal
  5. Boss / hammers when prize-positive
  6. Never healthy retreat; prefer go **second**

### W2 — Hit G2 (70% vs random)
- Iterate policy; each change → `./eval/run_batch_docker.sh --games 50 --opponent random`
- Log results in `eval/results_*.jsonl`
- Stop when G2 met

### W3 — Hit G3 (vs Ogerpon grass)
- `--opponent deck_b`
- Tune only if G2 holds (no regression)

### W4 — Ship
- `./package_submission.sh`
- Submit to Kaggle; fix validation errors from logs

### W5 — Beyond rules (later)
- cabt `search_*` on attack/Boss turns
- Self-play improvement loop
- Strategy writeup if pursuing prizes

## Explicit non-goals (for now)
- Perfect paper TCG / adding missing cards to pool
- Full RL before G2
- Optimizing sparring deck (deck_b is fixed opponent)

## Policy design principle
**Mimic human thought**, not a flat weight table:

1. **READ** situation (board, prizes, energy, hand)
2. **SET goal** for the turn (setup / develop / attack)
3. **CHECKLIST** among legal options: evolve → attach → ability → play → attack → end  
4. **ANSWER** sub-questions (search/discard/yes-no) with the same goal

## Current status (2026-07-20)
- [x] Multi-agent scaffold
- [x] Two legal mapped decks (Dragapult vs Ogerpon grass)
- [x] Human-style policy rewrite (`agent/policy.py`)
- [x] Train baseline ~**74%** vs random (Dragapult) — G2 likely PASS
- [ ] Confirm G2/G3 after human policy
- [ ] Kaggle submit
