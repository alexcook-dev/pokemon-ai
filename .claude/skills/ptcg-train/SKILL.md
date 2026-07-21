---
name: ptcg-train
description: >
  Autonomous PTCG (Pokémon TCG / cabt) policy trainer. Runs a Karpathy-style
  autoresearch keep/discard loop: edit agent/policy.py, batch-eval win rate vs
  random, keep only real improvements. Use when asked to train the Pokémon
  agent, improve win rate, run autoresearch, ptcg-train, self-train the TCG
  bot, overnight experiments, or when another agent should "call the train
  agent". Slash: /ptcg-train.
---

# /ptcg-train — PTCG train agent

You are a **specialist train agent**. Another agent or the human called you to
improve the cabt battle policy. Do not redesign the Kaggle competition. Optimize
**win rate** under the frozen eval protocol.

## Step 0 — Resolve project root

```bash
if [ -f main.py ] && [ -d agent ]; then
  PTCG_ROOT="$(pwd)"
else
  PTCG_ROOT=""
  for d in /Users/alexcook/conductor/workspaces/pokemon-ai/*/; do
    if [ -f "$d/main.py" ] && [ -d "$d/agent" ]; then PTCG_ROOT="${d%/}"; break; fi
  done
  if [ -z "$PTCG_ROOT" ] && [ -f "$HOME/Projects/ptcg-ai-battle/main.py" ]; then
    PTCG_ROOT="$HOME/Projects/ptcg-ai-battle"
    echo "WARNING: legacy checkout — no knowledge/ base here; guide-derived hints will NOT be found"
  fi
fi
[ -z "$PTCG_ROOT" ] && { echo "BLOCKED: cannot find pokemon-ai (main.py + agent/)"; exit 1; }
cd "$PTCG_ROOT"
echo "PTCG_ROOT=$PTCG_ROOT"
```

Then **Read** and obey:

1. `program.md` (full train-agent contract — source of truth)
2. `eval/README.md`
3. Current `agent/policy.py` (and `main.py` if needed)

If `program.md` is missing, stop with `BLOCKED` and tell the caller to restore it.

## Step 1 — Parse invocation mode

From the user/caller message:

| Signal | Mode |
|--------|------|
| setup / baseline only | `setup` |
| one experiment / try this | `once` |
| N experiments / "help train" (default) | `n=5` unless N specified |
| overnight / forever / loop | `forever` |
| explicit hypothesis text | use as first experiment idea |

Default when ambiguous: **`n=5`** then emit TRAIN REPORT (orchestrator-safe).

## Step 2 — Execute program.md

Follow `program.md` exactly:

1. Branch `autoresearch/<date-or-tag>` if not already on one  
2. Baseline eval if no baseline row in `results.tsv`  
3. Experiment loop per mode  
4. Mutable: mainly `agent/policy.py`  
5. Frozen: `eval/run_*`, `deck.csv`  
6. Eval: `./eval/run_train_eval.sh > run.log 2>&1`  
7. Keep if higher `win_rate` and `crash_rate == 0`  
8. Else `git reset --hard` to last keep  
9. Log `results.tsv` (untracked)

### Standard eval

```bash
./eval/run_train_eval.sh > run.log 2>&1
grep -E '^(win_rate|crash_rate|games|wins|losses|avg_steps):' run.log
```

v1 gate: ≥70% over 50 games vs random, seed 0.

## Step 3 — Hand back to caller

Always end with:

```
PTCG-TRAIN REPORT
branch: ...
experiments: ...
best_win_rate: ...
best_commit: ...
baseline_win_rate: ...
kept: ... discarded: ... crashes: ...
v1_gate_70pct: PASS|FAIL
next_ideas: ...
STATUS: DONE | DONE_WITH_CONCERNS | BLOCKED
```

If `forever` was interrupted, still print the best-so-far report.

## Rules

- Never invent illegal moves; only rank legal options.  
- Never edit the eval harness to "win".  
- Never stop mid-loop to ask permission (except true BLOCKED: missing Docker, missing project).  
- Prefer small heuristic diffs over rewrites.  
- On Mac, always use Docker eval scripts (libcg is Linux-only).  
- Do not commit `results.tsv`, `run.log`, or large `eval/results_*.jsonl` unless asked.

## How orchestrators should call you

Examples the parent agent can say:

- `Invoke /ptcg-train mode=n=5`  
- `Call the train agent: improve policy vs random for 5 experiments`  
- `Read program.md and run ptcg-train forever`  

Parent agents must **not** edit `agent/policy.py` in parallel while this skill runs.
