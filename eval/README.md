# Eval harness

Batch win-rate evaluation for the cabt agent. **Must run via Docker on macOS**
(`libcg.so` is Linux x86_64 only).

## Quick start (Docker / Mac)

```bash
# Smoke test (default): 10 games vs random
./eval/run_batch_docker.sh

# Explicit args
./eval/run_batch_docker.sh --games 10 --opponent random --seed 0 --out eval/results.jsonl

# Self-play
./eval/run_batch_docker.sh --games 10 --opponent self

# Our deck.csv agent vs deck_b.csv + random baseline
./eval/run_batch_docker.sh --games 10 --opponent deck_b
```

## v1 gate

Beat random **≥70% win rate over 50 games**:

```bash
./eval/run_batch_docker.sh --games 50 --opponent random --seed 0 --out eval/results_v1.jsonl
```

## Frozen train protocol (ptcg-train / autoresearch)

Used by the train agent. Defaults: 50 games, random opponent, seed 0.

```bash
./eval/run_train_eval.sh
# env overrides: TRAIN_GAMES TRAIN_OPPONENT TRAIN_SEED TRAIN_TAG
```

Stdout ends with a machine-parseable block:

```
---
win_rate:          0.540000
crash_rate:        0.000000
games:             50
...
```

See `../program.md` and `/ptcg-train`.

## Linux (native)

If already on Linux x86_64 with `kaggle-environments` installed:

```bash
python eval/run_batch.py --games 10 --opponent random --seed 0 --out eval/results.jsonl
```

## CLI

| Flag | Default | Description |
|------|---------|-------------|
| `--games N` | `10` | Number of games |
| `--opponent` | `random` | `random` \| `self` \| `deck_b` |
| `--seed S` | `0` | Base seed; game `i` uses `S+i` |
| `--out PATH` | `eval/results.jsonl` | Append JSONL results |

### Opponent modes

- **random** — both sides `deck.csv`; our agent vs random legal actions
- **self** — both sides `deck.csv`; our agent vs itself
- **deck_b** — player0 `deck.csv` + our agent vs player1 `deck_b.csv` + random

## Output

Each game is one JSONL line (`type: game`), then a final summary line
(`type: summary`). Fields: `result` (`win`/`loss`/`draw`/`crash`), `steps`,
`rewards`, `error`. Console prints a win-rate / crash-rate summary.
