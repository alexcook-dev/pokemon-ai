# PTCG AI Battle Challenge (Simulation)

Local workspace for [Kaggle Pokémon TCG AI Battle](https://www.kaggle.com/competitions/pokemon-tcg-ai-battle).

## New machine? Start here

```bash
git clone https://github.com/alexcook-dev/pokemon-ai.git
cd pokemon-ai
./setup.sh
```

`setup.sh` checks Docker is installed and running, pulls the eval base
image, boots a real container to prove the `cabt` simulator engine
actually loads (not just that Docker works), and pins the champion
snapshot for protocol-v2 eval. See [Why Docker](#why-docker-everywhere)
for what it isn't doing and why.

## Status

- [x] Accepted competition rules
- [x] Local self-play game finishes (Docker)
- [x] Heuristic policy + batch eval harness
- [x] Train agent (`/ptcg-train`) for keep/discard self-improvement
- [x] Guide-reader agent (`/ptcg-guide`) feeding a strategy knowledge base
- [x] Champion-vs-challenger eval (protocol v2, `program.md`)
- [x] Combo-sequencing policy architecture (tiers 1-4, see `knowledge/`)
- [x] Package + upload a smoke-test submission on Kaggle
- [ ] Strategy Writeup track ($240k prize competition — deliberately
      deferred until Simulation results settle, see `knowledge/`)

## The knowledge/ brain (separate repo — see note)

`knowledge/` is the strategy knowledge base `/ptcg-guide` writes and
`/ptcg-train` reads. It's being split into its own repo so it's portable
across machines independent of this agent codebase — if you're reading
this after that split landed, `knowledge/` is a git submodule and
`git clone --recurse-submodules` (or `git submodule update --init` after
a plain clone) is required for it to be populated. Check for a
`.gitmodules` file at the repo root to know which state you're in.

## Files

| File | Role |
|------|------|
| `main.py` | Agent entrypoint (`agent(obs) -> list[int]`) |
| `agent/` | Policy (`policy.py`), obs parsing, options, deck knowledge, learned-scorer hook |
| `deck.csv` | Live 60 card IDs (currently "Neddy Kosek - Pult / Noir - NAIC 26") |
| `deck_*.csv` | Named/candidate decks — Hydrapple builds, the tournament-gauntlet field, brewed decks (see `knowledge/`) |
| `knowledge/` | **Submodule** — the strategy brain (see above) |
| `data/` | Official competition card ID catalog (csv/json/txt; the 131MB PDF is gitignored, see `knowledge/`) |
| `eval/` | Batch win-rate harness, tournament runner, head-to-head matrix runner, tier-4 trainer (all Docker on Mac) |
| `program.md` | **Train-agent contract** (source of truth for self-train, incl. protocol v2) |
| `agents/CALL_TRAIN.md` | How orchestrators call the train agent |
| `package_submission.sh` | Build `submission.tar.gz` (`main.py` + `deck.csv` + `agent/`) |
| `setup.sh` | Fresh-machine bootstrap (this file's first section) |
| `play_human.py` / `play_human_docker.sh` | Interactive human-vs-AI mode (built, currently unused — see `knowledge/`) |

## Why Docker everywhere

`kaggle-environments` ships the `cabt` engine's `libcg.so` as **Linux
x86_64 only**; native macOS load fails. Every `*_docker.sh` script
installs `kaggle-environments` fresh inside its own ephemeral container,
so there's no binary to hand-copy between machines — `setup.sh` just
proves that install-and-load path actually works before you hit it
mid-eval. Kaggle's own eval runs on Linux too, so this matches production.

## Commands

```bash
# One self-play game
./run_docker.sh

# Batch eval vs random (smoke)
./eval/run_batch_docker.sh --games 10 --opponent random

# Frozen train protocol (50 games, seed 0) — used by ptcg-train
./eval/run_train_eval.sh

# Champion-vs-challenger (protocol v2 — sharper than vs-random once win
# rate saturates; see program.md)
./eval/set_champion.sh <commit>
./eval/run_batch_docker.sh --games 50 --opponent snapshot

# Deck-vs-deck matchup matrix
./eval/run_h2h.py --candidates deck_a.csv --opponents deck_b.csv,deck_c.csv --games 20

# Swiss tournament gauntlet (8-deck field, Bo3)
./eval/run_tournament_docker.sh --tournaments 5

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

## Call the guide-reader agent

Paste a deck guide or decklist and say "read this guide", or:

```text
/ptcg-guide <url, or paste the guide/decklist>
```

Ingests strategy into `knowledge/` (the brain submodule), maps decklists
to legal competition card IDs, and queues POLICY HINTS for `/ptcg-train`.

Skills are installed at:

- Project: `.claude/skills/{ptcg-train,ptcg-guide}/` and `.grok/skills/{ptcg-train,ptcg-guide}/`
- User: `~/.claude/skills/{ptcg-train,ptcg-guide}/` and `~/.grok/skills/{ptcg-train,ptcg-guide}/`

## Agent contract

1. If `obs["select"] is None` → return deck (60 ints).
2. Else → return indices into `obs["select"]["option"]` (length `maxCount`).

API docs: https://matsuoinstitute.github.io/cabt/

## Eval gate

v1: beat random **≥70%** over 50 games (`./eval/run_train_eval.sh`). Once
win rate saturates near this ceiling, protocol v2 (champion-vs-challenger,
above) is the real gate — see `program.md`.
