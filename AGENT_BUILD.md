# Multi-agent build plan

Challenge: Pokémon TCG AI Training Agent under incomplete information (hidden opponent hand),
cabt simulator, legal options only. Heuristics first; search/RL later.

## File ownership

| Owner agent | Files | Deliverable |
|-------------|-------|-------------|
| obs-layer | `agent/obs.py`, `agent/options.py` | Parse observation + typed options |
| deck-knowledge | `agent/deck_knowledge.py` | Roles for our deck.csv IDs |
| policy | `agent/policy.py` | Score options + choose indices |
| eval-harness | `eval/run_batch.py`, `eval/run_batch_docker.sh` | N-game win-rate loop |
| **train** (`/ptcg-train`) | edits `agent/policy.py` via keep/discard | Higher win rate; see `program.md` |
| integrator | `main.py`, wire imports | Single agent entry for Kaggle |

**Orchestrators:** call the train agent via `/ptcg-train` or `agents/CALL_TRAIN.md`. Do not edit policy in parallel.

## Agent contract

```python
def agent(obs: dict) -> list[int]:
    if obs.get("select") is None:
        return DECK  # 60 ints
    return choose_actions(obs)  # indices, len == maxCount
```

## Eval

Docker only on Mac. Beat random ≥70% / 50 games is v1 gate.
