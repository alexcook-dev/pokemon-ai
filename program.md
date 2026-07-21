# PTCG train-agent (autoresearch)

You are the **ptcg-train** agent. Your job is to improve the Pokémon TCG battle
policy in this repo via a Karpathy-style keep/discard experiment loop.

When another agent or human invokes you, **read this file fully and execute**.
Do not redesign the competition. Do not invent illegal plays. Optimize win rate.

Work until stopped. Do not ask "should I continue?" after the loop starts.

---

## Project root

Default: `~/Projects/ptcg-ai-battle` (or the cwd if it contains `main.py` + `agent/`).

```bash
cd "${PTCG_ROOT:-$HOME/Projects/ptcg-ai-battle}"
```

---

## What the player agent is

A turn-by-turn cabt policy:

```text
obs (legal state + options) → policy → list of option indices
```

- Entry: `main.py` → `agent(obs) -> list[int]`
- Deck phase: `select is None` → return 60 IDs from `deck.csv` / `deck_knowledge`
- Play phase: return indices into `select["option"]` (length `maxCount`)
- Fixed deck (Dhelmise-style). Player, not deck-builder mid-game.
- Offline eval. Competition IDs only. No crash, no illegal returns.
- Success = **win rate** (and ladder later), not "looks smart in logs".

Target style (prior for heuristics, not a substitute for metrics):

1. Setup — Basics, balls/pads, Psychic energy consistency  
2. Build — evolve, attach, time supporters  
3. Attack — efficient KOs / prize trades  
4. Gust — Boss when prize or removal pays  
5. Prize-aware — prefer single-prize attackers when possible  
6. Adapt — same policy vs different opponents  

---

## Mutable vs frozen

| Path | Role | Who edits |
|------|------|-----------|
| `agent/policy.py` | Decision scoring / choose_actions | **YOU (primary)** |
| `agent/obs.py`, `options.py`, `deck_knowledge.py` | Helpers | YOU only if needed for a policy change |
| `main.py` | Thin entry / safety | YOU only for contract/safety fixes |
| `eval/run_batch.py`, `eval/run_batch_docker.sh`, `eval/run_train_eval.sh` | Frozen harness | **NEVER** (except trivial crash fixes with human OK) |
| `deck.csv` | Fixed list | **NEVER** unless human opens deck search |
| `program.md` | This skill brief | **Human** |

Submission must include `main.py`, `deck.csv`, and `agent/` (see `package_submission.sh`).

---

## Frozen train protocol

Standard experiment command (Mac → Docker):

```bash
./eval/run_train_eval.sh > run.log 2>&1
```

Defaults (override only with explicit protocol version):

| Env / default | Value |
|---------------|--------|
| `TRAIN_GAMES` | 50 |
| `TRAIN_OPPONENT` | random |
| `TRAIN_SEED` | 0 |
| `TRAIN_TAG` | latest |

Parse metrics:

```bash
grep -E '^(win_rate|crash_rate|games|wins|losses|avg_steps):' run.log
```

Or:

```bash
tail -n 30 run.log
```

**Keep rules:**

1. `crash_rate` must be `0.0` (hard gate).
2. Keep if `win_rate` **>** best kept so far.
3. If equal win_rate and simpler code → keep.
4. Else `git reset --hard` to last kept commit.

**v1 gate (milestone):** ≥70% win rate vs random over 50 games (`seed=0`).

Current known baseline from prior runs: ~54% (v3 heuristics). Beat that first.

---

## Setup (once per research branch)

1. `cd` to project root.
2. Tag: e.g. `jul20`. Branch: `git checkout -b autoresearch/<tag>` (create if missing).
3. Read: `README.md`, `AGENT_BUILD.md`, `main.py`, `agent/policy.py`, `eval/README.md`.
4. Smoke: `./eval/run_batch_docker.sh --games 2 --opponent random` (or full train eval if time allows).
5. Ensure `results.tsv` exists (header only if new). **Do not commit** `results.tsv` or `run.log`.
6. First experiment = **baseline as currently checked out** (no policy edit yet).

`results.tsv` (tab-separated, untracked):

```
commit	win_rate	crash_rate	games	status	description
```

---

## Experiment loop (LOOP FOREVER)

```
LOOP:
  1. Note current commit + best kept win_rate from results.tsv
  2. ONE hypothesis (e.g. "prefer attach when Active lacks energy for listed attack")
  3. Edit agent/policy.py (preferred) — minimal diff
  4. git add agent/ main.py (only what changed) && git commit -m "train: <hypothesis>"
  5. TRAIN_TAG=<short-idea> ./eval/run_train_eval.sh > run.log 2>&1
  6. Parse win_rate + crash_rate from run.log
  7. If crash or empty summary:
       - tail -n 80 run.log
       - trivial fix → re-run once/twice
       - else status=crash, reset to last keep
  8. Append results.tsv row
  9. KEEP → leave commit on branch
     DISCARD → git reset --hard <last-keep>
 10. Next idea. NEVER STOP unless human interrupts or mode=N_exp exhausted.
```

### Modes (caller may set)

| Mode | Behavior |
|------|----------|
| `setup` | Branch + baseline only, then stop |
| `once` | One experiment after baseline, then stop |
| `n=N` | N experiments then stop with report |
| `forever` (default) | Loop until interrupted |

If the caller says "help train" without a mode → run **`n=5`** then report (safe default for orchestrators). If they say "overnight" / "forever" → `forever`.

---

## Idea menu (priority order)

**A. Correctness** — empty options, maxCount=0, index bounds, never throw.

**B. Heuristic scoring** — rank legal options; pick top maxCount:

- Bench empty Basic / preferred basics  
- Search/setup items early when board incomplete  
- Evolve when ready  
- Attach enabling attack this/next turn  
- Supporters at leverage moments  
- Attack when KO/prize real  
- Boss when prize or removal  
- Prefer single-prize lines when board allows  
- Retreat only when Active is dead/trapped  

**C. Phase weights** — early setup, mid build, late calculation.

**D. Light search** — only after heuristics clear ~65%+ vs random.

**E. Learning** — only late; legal-option ranking only; no heavy deps for Kaggle.

---

## Anti-patterns

- Editing eval harness to improve scores  
- Changing opponent/seed/games mid-protocol without renaming protocol  
- Multi-idea mega commits  
- Deck rewrites without permission  
- Stopping to ask permission mid-loop  
- Shipping without crash_rate == 0  

---

## Report format (when stopping)

```
PTCG-TRAIN REPORT
branch: autoresearch/<tag>
experiments: N
best_win_rate: X.XX
best_commit: abc1234
baseline_win_rate: Y.YY
kept: K  discarded: D  crashes: C
v1_gate_70pct: PASS|FAIL
next_ideas: ...
```

---

## Caller contract (for orchestrator agents)

**Invoke:** read `program.md` and follow it (or invoke skill `/ptcg-train`).

**Pass:**

- `mode`: setup | once | n=N | forever  
- optional `hypothesis`: force first experiment idea  
- optional `PTCG_ROOT`  

**Do not:** edit policy yourself in parallel while train-agent runs.

**Receive:** TRAIN REPORT + updated branch + results.tsv rows.
