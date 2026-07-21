# How to call the train agent

Use this when **you are an orchestrator** (Claude, Codex, Grok, OpenClaw, etc.)
and need the PTCG policy improved without doing the loop yourself.

## Preferred: skill invoke

```
/ptcg-train mode=n=5
```

or free-form:

```
Call /ptcg-train. Mode n=5. Do not edit agent/policy.py yourself — let the train agent own it.
```

Modes:

| Mode | When |
|------|------|
| `setup` | Branch + baseline only |
| `once` | Single experiment (optional hypothesis) |
| `n=5` | Five experiments then report (default for helpers) |
| `forever` | Overnight / unattended |

## Fallback: read program.md

If skills are unavailable:

```
Read ~/Projects/ptcg-ai-battle/program.md and execute it as the train agent.
Mode: n=5. Project root: ~/Projects/ptcg-ai-battle.
```

## Spawned-subagent prompt (copy-paste)

```
You are ptcg-train. Working directory: /Users/alexcook/Projects/ptcg-ai-battle
1. Read program.md and .claude/skills/ptcg-train/SKILL.md
2. Mode: n=5
3. Improve agent/policy.py via keep/discard on win_rate using ./eval/run_train_eval.sh
4. Do not edit eval harness or deck.csv
5. End with PTCG-TRAIN REPORT
```

## Contract

- **You own:** orchestration, deck choice, shipping to Kaggle, strategy writeups  
- **Train agent owns:** `agent/policy.py` experiments + git keep/discard on the research branch  
- **Frozen:** `eval/run_batch*.py/sh`, `eval/run_train_eval.sh`, train protocol defaults  
- **Metric:** `win_rate` up, `crash_rate` must be 0  
- **v1 gate:** ≥70% vs random / 50 games / seed 0  

## Do not

- Edit policy in parallel with the train agent  
- Change eval args mid-run to inflate scores  
- Package without `agent/` in the tarball  

## After train returns

1. Read the PTCG-TRAIN REPORT  
2. Inspect best commit on `autoresearch/*`  
3. Optionally run `./package_submission.sh` and upload to Kaggle  
