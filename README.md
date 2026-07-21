# PTCG AI Battle Challenge (Simulation)

Local workspace for [Kaggle Pokémon TCG AI Battle](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle).

## Step 1 status

- [x] Accepted competition rules
- [x] Local self-play game finishes (Docker on Mac)
- [x] Heuristic policy + batch eval harness
- [x] Train agent (`/ptcg-train`) for keep/discard self-improvement
- [ ] Package + upload a smoke-test submission on Kaggle

## Files

| File | Role |
|------|------|
| `main.py` | Agent entrypoint (`agent(obs) -> list[int]`) |
| `agent/` | Policy, obs, options, deck knowledge |
| `deck.csv` | Fixed 60 card IDs |
| `eval/` | Batch win-rate harness (Docker on Mac) |
| `program.md` | **Train-agent contract** (source of truth for self-train) |
| `agents/CALL_TRAIN.md` | How orchestrators call the train agent |
| `package_submission.sh` | Build `submission.tar.gz` (`main.py` + `deck.csv` + `agent/`) |

## Why Docker on Mac

`kaggle-environments` ships `libcg.so` as **Linux x86_64 only**. Native macOS load fails. Kaggle eval is Linux, so Docker matches production.

## Commands

```bash
# One self-play game (Mac)
./run_docker.sh

# Batch eval vs random (smoke)
./eval/run_batch_docker.sh --games 10 --opponent random

# Frozen train protocol (50 games, seed 0) — used by ptcg-train
./eval/run_train_eval.sh

# Package for Kaggle
./package_submission.sh
```

## Call the train agent (from another agent)

```text
/ptcg-train mode=n=5
```

or:

```text
Read program.md and execute as the train agent. Mode: n=5.
```

Details: [`agents/CALL_TRAIN.md`](agents/CALL_TRAIN.md) · contract: [`program.md`](program.md)

Skill is installed at:

- Project: `.claude/skills/ptcg-train/` and `.grok/skills/ptcg-train/`
- User: `~/.claude/skills/ptcg-train/` and `~/.grok/skills/ptcg-train/`

## Agent contract

1. If `obs["select"] is None` → return deck (60 ints).
2. Else → return indices into `obs["select"]["option"]` (length `maxCount`).

API docs: https://matsuoinstitute.github.io/cabt/

## Eval gate

v1: beat random **≥70%** over 50 games (`./eval/run_train_eval.sh`).
