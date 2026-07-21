"""Tier 4 (learned): an optional additive scoring adjustment on top of the
hand-tuned heuristic policy in agent/policy.py.

OFF BY DEFAULT, on two independent gates:
  1. `agent/learned_weights.json` must exist (produced by
     eval/train_value_model.py — NOT run as part of shipping this file;
     the live/default policy is unaffected until someone explicitly
     trains AND validates weights via protocol v2's champion-vs-challenger
     gate, per program.md's Approach C: "real risk of not converging,
     could crowd out the safe working loop").
  2. Env var PTCG_USE_LEARNED_SCORER=1 must be set, even if a weights
     file exists — so a stray trained file sitting on disk can never
     silently change behavior.

Deliberately tiny: a hand-rolled linear/logistic model over a small
hand-authored feature vector. No numpy/sklearn dependency, matching
program.md's idea-menu note for tier E ("no heavy deps for Kaggle").
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    _WEIGHTS_PATH = Path(__file__).resolve().parent / "learned_weights.json"
except NameError:
    _WEIGHTS_PATH = Path.cwd() / "agent" / "learned_weights.json"
_weights_cache: Optional[Dict[str, float]] = None
_weights_loaded = False


def _load_weights() -> Optional[Dict[str, float]]:
    global _weights_cache, _weights_loaded
    if _weights_loaded:
        return _weights_cache
    _weights_loaded = True
    try:
        if _WEIGHTS_PATH.exists():
            data = json.loads(_WEIGHTS_PATH.read_text())
            if isinstance(data, dict) and isinstance(data.get("weights"), dict):
                _weights_cache = {str(k): float(v) for k, v in data["weights"].items()}
    except Exception:
        _weights_cache = None
    return _weights_cache


def extract_features(sit: Dict[str, Any], cid: Optional[int], opt_type: int) -> Dict[str, float]:
    """Small, hand-authored feature set — deliberately not exhaustive.
    If retrained, extend this alongside eval/train_value_model.py (both
    must agree on the feature set, or trained weights become meaningless).
    """
    return {
        "bias": 1.0,
        "hand_n": float(sit.get("hand_n") or 0),
        "my_prize": float(sit.get("my_prize") if sit.get("my_prize") is not None else 6),
        "opp_prize": float(sit.get("opp_prize") if sit.get("opp_prize") is not None else 6),
        "opp_has_bench": 1.0 if sit.get("opp_has_bench") else 0.0,
        "energy_on_active": 1.0 if sit.get("energy_on_active") else 0.0,
        "active_weak": 1.0 if sit.get("active_weak") else 0.0,
        "opt_type": float(opt_type),
    }


def learned_score_adjustment(sit: Dict[str, Any], cid: Optional[int], opt_type: int) -> float:
    """Returns 0.0 (pure no-op) unless both gates above are satisfied."""
    if os.environ.get("PTCG_USE_LEARNED_SCORER") != "1":
        return 0.0
    weights = _load_weights()
    if not weights:
        return 0.0
    try:
        features = extract_features(sit, cid, opt_type)
        return sum(weights.get(k, 0.0) * v for k, v in features.items())
    except Exception:
        return 0.0
