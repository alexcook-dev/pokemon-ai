"""
Human-style decision policy for cabt Pokémon TCG (Dragapult primary).

Think like a player, not a weight table:

  1. READ the situation (prizes, board, hand pressure, energy status)
  1.5 PLAN a combo order for this turn, once, reused across every
      decision in the turn (tiers 2+3 — see below)
  2. SET a turn goal (setup / develop / attack / disrupt)
  3. WALK the normal human action checklist among *legal* options only
  4. When the game asks a sub-question (which card? yes/no?), answer
     with the same goal in mind

``choose_actions(obs) -> list[int]`` returns indices into select["option"].
Deck selection (select is None) is handled by main.py.

On any error: random legal sample (never crash).

Combo-sequencing architecture (added 2026-07-20): the base scorer above is
a stateless per-option greedy scorer — it has no lookahead and no memory
across the several `choose_actions` calls that make up one turn, so it
cannot represent "play these two cards together, in this order" or
"invest now for a payoff two turns from now." Four additive layers close
that gap, each independently inspectable/removable:

  Tier 1 (knowledge)  — `_BASE_CARD_VALUE` / `_synergy_bonus`: hand-authored
                         card values and pairwise synergy terms (e.g. Boss's
                         Orders before Unfair Stamp).
  Tier 2 (memory)     — `_TURN_PLAN_CACHE` / `_get_turn_plan`: persists a
                         plan across calls within one turn. Keyed by
                         (seat, turn, hand contents) so it is safe when the
                         same policy instance pilots both seats in self-play
                         / tournament runs — a plan can never leak across
                         seats, and any hand change mid-turn (a draw, a
                         search) invalidates the cached plan automatically.
  Tier 3 (search)     — `_search_best_order`: a bounded (<=4 cards, <=24
                         permutations) combinatorial search over PLAY ORDER
                         this turn, using tier 1's values/synergy terms.
                         This is NOT multi-turn game-tree search — the
                         compiled cabt engine gives no forward-simulation
                         hook to build that against — it is single-turn
                         ordering search, which is exactly the gap the
                         stateless scorer cannot cover on its own.
  Tier 4 (learned)    — `agent/learned_scorer.py`: an additive scoring
                         adjustment from a trained model. OFF by default
                         (no weights file ships, and it requires
                         PTCG_USE_LEARNED_SCORER=1 even if one exists) —
                         see `eval/train_value_model.py` to train and
                         validate one via protocol v2 before ever trusting it.

All four are purely additive on top of the existing, 94%-vs-random-tested
base scoring (`_think_score_base` / `_human_play_card_base`) — nothing here
changes behavior for decks/situations that never trigger it.
"""

from __future__ import annotations

import itertools
import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Optional helpers
try:
    from agent import deck_knowledge as _deck_mod  # type: ignore
except Exception:  # pragma: no cover
    _deck_mod = None

try:
    from agent.learned_scorer import learned_score_adjustment as _learned_score_adjustment  # type: ignore
except Exception:  # pragma: no cover
    _learned_score_adjustment = None

# ---------------------------------------------------------------------------
# Enums (cabt ints)
# ---------------------------------------------------------------------------
SELECT_MAIN = 0
SELECT_CARD = 1
SELECT_YES_NO = 9
SELECT_COUNT = 8
SELECT_ATTACK = 6
SELECT_EVOLVE = 7

CTX_MAIN = 0
CTX_SETUP_ACTIVE = 1
CTX_SETUP_BENCH = 2
CTX_SWITCH = 3
CTX_TO_ACTIVE = 4
CTX_TO_BENCH = 5
CTX_TO_FIELD = 6
CTX_TO_HAND = 7
CTX_DISCARD = 8
CTX_DAMAGE = 15
CTX_DAMAGE_COUNTER = 13
CTX_HEAL = 17
CTX_IS_FIRST = 41
CTX_MULLIGAN = 42
CTX_ACTIVATE = 43
CTX_FIRST_EFFECT = 44
CTX_COIN_HEAD = 46
CTX_DRAW_COUNT = 38

OPT_NUMBER = 0
OPT_YES = 1
OPT_NO = 2
OPT_CARD = 3
OPT_PLAY = 7
OPT_ATTACH = 8
OPT_EVOLVE = 9
OPT_ABILITY = 10
OPT_DISCARD = 11
OPT_RETREAT = 12
OPT_ATTACK = 13
OPT_END = 14
OPT_SKILL = 15

AREA_HAND = 2
AREA_ACTIVE = 4
AREA_BENCH = 5

# Dragapult-line card IDs (competition pool)
ID_DREEPY = 119
ID_DRAKLOAK = 120
ID_DRAGAPULT = 121
ID_DUSKULL = 131
ID_DUSCLOPS = 132
ID_DUSKNOIR = 133
ID_BUDEW = 235
ID_MUNKIDORI = 112
ID_CRISPIN = 1198
ID_LILLIE = 1227
ID_BOSS = 1182
ID_ULTRA_BALL = 1121
ID_POFFIN = 1086
ID_POKE_PAD = 1152
ID_HAMMER = 1120
ID_UNFAIR_STAMP = 1080
ID_PRIME_CATCHER = 1088  # ACE SPEC — draw + gust; combo-order matters (tier 1/3)
ID_FEZANDIPITI = 140  # Fezandipiti ex — ability "Flip the Script"

LINE_DRAGAPULT = (ID_DREEPY, ID_DRAKLOAK, ID_DRAGAPULT)
LINE_DUSK = (ID_DUSKULL, ID_DUSCLOPS, ID_DUSKNOIR)
BASICS_PRIORITY = (ID_DREEPY, ID_DUSKULL, ID_BUDEW, ID_MUNKIDORI, 1071, 140)
ATTACKERS = frozenset({ID_DRAGAPULT, ID_DUSKNOIR, 1071, 140, ID_MUNKIDORI, ID_DRAKLOAK})
EVOS = frozenset({ID_DRAKLOAK, ID_DRAGAPULT, ID_DUSCLOPS, ID_DUSKNOIR})
SEARCH_IDS = frozenset({ID_ULTRA_BALL, ID_POFFIN, ID_POKE_PAD, 1122, 1097, 1094})
ENERGY_IDS = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 19, 20})

# --- Tier 1 (knowledge) + Tier 3 (search) shared vocabulary ---------------
# Cards whose relative ORDER within a turn can matter. Deliberately Items
# only, not Supporters (Crispin, Lillie's Determination): only one
# Supporter is legal per turn (sit["supporter_played"]), so there is no
# same-turn "order" between two Supporters to search over — including them
# here (an earlier draft did) just added a spurious, always-the-same-way
# Crispin-over-Lillie nudge on top of scoring that already handles that
# tradeoff on its own. Root-caused 2026-07-20: regressed the frozen eval
# 94% -> 82-84% on identical seed=0 games; removing them recovers it.
# Extend with new ITEM-type combo pieces as /ptcg-guide ingests hints.
COMBO_CANDIDATES = frozenset({ID_BOSS, ID_UNFAIR_STAMP, ID_PRIME_CATCHER})

# Hand-authored per-card value used only to rank ORDER among COMBO_CANDIDATES
# present in hand this turn — not a replacement for _human_play_card_base's
# own (already-tested) absolute scoring.
_BASE_CARD_VALUE = {
    ID_BOSS: 90.0,
    ID_UNFAIR_STAMP: 60.0,
    ID_PRIME_CATCHER: 85.0,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def choose_actions(obs: dict) -> list[int]:
    """Human-style choice among legal options. Never raises."""
    try:
        select = obs.get("select") if isinstance(obs, dict) else None
        if select is None:
            return []

        options = select.get("option") or []
        max_count = int(select.get("maxCount") or 0)
        min_count = int(select.get("minCount") or 0)
        n = len(options)
        if max_count <= 0 or n == 0:
            return []

        max_count = min(max_count, n)
        min_count = max(0, min(min_count, max_count))
        select_type = int(select.get("type") or 0)
        context = int(select.get("context") or 0)

        # 1) Read the board the way a human glances at it
        sit = _read_situation(obs)

        # 2) Score each legal option under that plan
        scored: List[Tuple[float, int]] = []
        for i, opt in enumerate(options):
            if not isinstance(opt, dict):
                opt = {"type": opt}
            scored.append((_think_score(obs, sit, select_type, context, i, opt), i))

        scored.sort(key=lambda t: (-t[0], t[1]))

        k = _how_many_to_pick(select_type, context, min_count, max_count, scored, sit)
        chosen = [idx for _, idx in scored[:k]]

        if len(chosen) < min_count:
            for _, idx in scored[len(chosen) :]:
                if idx not in chosen:
                    chosen.append(idx)
                if len(chosen) >= min_count:
                    break

        return chosen
    except Exception:
        return _random_fallback(obs)


def score_option(obs: dict, option_index: int, option_dict: dict) -> float:
    """Public scorer (used by debug tools)."""
    try:
        select = (obs or {}).get("select") or {}
        sit = _read_situation(obs)
        return _think_score(
            obs,
            sit,
            int(select.get("type") or 0),
            int(select.get("context") or 0),
            option_index,
            option_dict if isinstance(option_dict, dict) else {"type": option_dict},
        )
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# 1) READ — human situation assessment
# ---------------------------------------------------------------------------
def _read_situation(obs: dict) -> Dict[str, Any]:
    """Glance at the board the way a player does before acting."""
    current = (obs or {}).get("current") or {}
    yi = int(current.get("yourIndex") or 0)
    players = current.get("players") or []
    me = players[yi] if yi < len(players) and isinstance(players[yi], dict) else {}
    opp = players[1 - yi] if len(players) > 1 and isinstance(players[1 - yi], dict) else {}

    my_active = _first_mon(me.get("active"))
    opp_active = _first_mon(opp.get("active"))
    my_bench = [m for m in (me.get("bench") or []) if m]
    opp_bench = [m for m in (opp.get("bench") or []) if m]
    hand = me.get("hand")
    hand_ids = _ids_from_cards(hand) if hand else []

    my_active_id = _cid(my_active)
    my_prize = _prize_count(me)
    opp_prize = _prize_count(opp)

    # What would a human call this turn's *job*?
    has_attacker = my_active_id in ATTACKERS or any(_cid(m) in ATTACKERS for m in my_bench)
    needs_setup = len(my_bench) < 1 or my_active is None
    needs_evolution = _board_wants_evolution(me)
    energy_on_active = bool(my_active and (my_active.get("energies") or my_active.get("energyCards")))
    energy_attached_this_turn = bool(current.get("energyAttached"))
    supporter_played = bool(current.get("supporterPlayed"))
    stadium_played = bool(current.get("stadiumPlayed"))

    if needs_setup:
        goal = "setup"  # establish board
    elif needs_evolution or not has_attacker:
        goal = "develop"  # evolve / search / energy
    elif energy_on_active or energy_attached_this_turn:
        goal = "attack"  # try to take prizes
    else:
        goal = "develop"

    # Late game: more aggressive
    if my_prize is not None and my_prize <= 2:
        if goal == "develop":
            goal = "attack"

    turn = current.get("turn")
    turn_plan = _get_turn_plan(yi, turn, hand_ids)
    ko_last_turn = _detect_ko_last_turn(yi, turn, opp_prize)

    deck_n = int(me.get("deckCount") or 0)

    return {
        "turn": turn,
        "turn_plan": turn_plan,
        "ko_last_turn": ko_last_turn,
        "deck_n": deck_n,
        "goal": goal,
        "me": me,
        "opp": opp,
        "my_active": my_active,
        "my_active_id": my_active_id,
        "opp_active": opp_active,
        "my_bench": my_bench,
        "opp_bench": opp_bench,
        "hand_ids": hand_ids,
        "hand_n": len(hand_ids) if hand is not None else int(me.get("handCount") or 0),
        "my_prize": my_prize,
        "opp_prize": opp_prize,
        "energy_on_active": energy_on_active,
        "energy_attached": energy_attached_this_turn,
        "supporter_played": supporter_played,
        "stadium_played": stadium_played,
        "active_weak": _active_is_weak(me, my_active),
        "opp_has_bench": len(opp_bench) > 0,
    }


def _board_wants_evolution(me: dict) -> bool:
    """True if we have pre-evos in play that still need the next stage."""
    ids = []
    for m in [_first_mon(me.get("active"))] + list(me.get("bench") or []):
        c = _cid(m)
        if c is not None:
            ids.append(c)
    if ID_DREEPY in ids and ID_DRAKLOAK not in ids and ID_DRAGAPULT not in ids:
        return True
    if ID_DRAKLOAK in ids and ID_DRAGAPULT not in ids:
        return True
    if ID_DUSKULL in ids and ID_DUSCLOPS not in ids and ID_DUSKNOIR not in ids:
        return True
    if ID_DUSCLOPS in ids and ID_DUSKNOIR not in ids:
        return True
    return False


# ---------------------------------------------------------------------------
# 1.5) PLAN — turn-scoped combo-order search (tiers 2 & 3)
# ---------------------------------------------------------------------------
# Tier 2: cache a plan across the several choose_actions() calls that make
# up one turn. Keyed by (seat, turn, hand contents) — never by anything
# tied to a specific obs/select dict, since those are rebuilt fresh by the
# engine every call. The hand-contents component makes this self-healing:
# a draw or search mid-turn changes hand_ids, which misses the cache and
# forces a fresh plan, rather than executing a plan built for a hand that
# no longer exists. Bounded size: this is a coherence aid, not a source of
# truth, so a full clear on overflow is fine (worst case = extra recompute).
_TURN_PLAN_CACHE: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
_TURN_PLAN_CACHE_MAX = 16


def _get_turn_plan(yi: int, turn: Any, hand_ids: List[int]) -> Dict[str, Any]:
    key = (yi, turn, tuple(sorted(hand_ids)))
    cached = _TURN_PLAN_CACHE.get(key)
    if cached is not None:
        return cached
    if len(_TURN_PLAN_CACHE) > _TURN_PLAN_CACHE_MAX:
        _TURN_PLAN_CACHE.clear()
    plan = _compute_turn_plan(hand_ids)
    _TURN_PLAN_CACHE[key] = plan
    return plan


def _synergy_bonus(order: Tuple[int, ...]) -> float:
    """Tier 1's pairwise combo knowledge, expressed as search terms so
    tier 3 can weigh them in context instead of only matching a literal
    hard-coded pattern. Small and explicit on purpose — extend alongside
    COMBO_CANDIDATES as new combos are documented in knowledge/*.md.
    """
    bonus = 0.0
    if ID_BOSS in order and ID_UNFAIR_STAMP in order:
        # Gust the answer into range, THEN lock it out — Boss before Stamp.
        # Wrong order (bonus stays negative) locks before a target is even
        # in range, which is close to wasted.
        if order.index(ID_BOSS) < order.index(ID_UNFAIR_STAMP):
            bonus += 40.0
        else:
            bonus -= 15.0
    if ID_PRIME_CATCHER in order and len(order) > 1 and order.index(ID_PRIME_CATCHER) == 0:
        # Its draw is worth more the earlier it happens — more of the turn
        # left to act on whatever it finds.
        bonus += 15.0
    return bonus


def _search_best_order(candidates: List[int]) -> Tuple[int, ...]:
    """Tier 3: enumerate every ordering of the (small) combo-capable hand
    this turn, score each by base value + synergy terms, keep the best.

    Bounded to <=4 cards (<=24 permutations) so this stays cheap. This is
    deliberately NOT multi-turn game-tree search / MCTS — the compiled
    cabt engine (libcg.so) exposes no fork/rollout hook to build a forward
    model against, so true search over the opponent's responses isn't
    implementable against it in this timeframe. What this covers is the
    real gap: single-turn ordering among the cards already in hand, which
    the stateless per-option scorer above has no way to represent at all.
    """
    if not candidates:
        return ()
    pool = candidates[:4]
    best_order: Tuple[int, ...] = tuple(pool)
    best_score = float("-inf")
    for perm in itertools.permutations(pool):
        score = sum(_BASE_CARD_VALUE.get(c, 50.0) for c in perm) + _synergy_bonus(perm)
        if score > best_score:
            best_score, best_order = score, perm
    return best_order


def _compute_turn_plan(hand_ids: List[int]) -> Dict[str, Any]:
    candidates = [c for c in hand_ids if c in COMBO_CANDIDATES]
    order = _search_best_order(candidates) if len(candidates) >= 2 else tuple(candidates)
    # rank: earlier in the chosen order -> larger bonus for that card id
    rank = {cid: (len(order) - i) for i, cid in enumerate(order)}
    return {"order": order, "rank": rank}


# ---------------------------------------------------------------------------
# CROSS-TURN memory: "was one of my Pokemon KO'd during the opponent's last
# turn" — a second, distinct kind of state from the tier-2 turn-plan cache
# above (that one deliberately resets every turn; this one deliberately
# persists ACROSS turns). Needed for Fezandipiti ex's real ability text
# (verified against the engine binary, not memory): "Once during your turn,
# if any of your Pokemon were Knocked Out during your opponent's last turn,
# you may draw 3 cards." Same seat-isolation requirement as tier 2 — keyed
# by yi so self-play/tournament runs (one policy instance, two seats) can
# never cross-contaminate.
_LAST_TURN_SNAPSHOT: Dict[int, Tuple[Any, int]] = {}  # yi -> (turn, opp_prize) at that turn's start


def _detect_ko_last_turn(yi: int, turn: Any, opp_prize: Optional[int]) -> bool:
    """True iff opp_prize dropped since the start of THIS seat's previous
    turn — opp_prize only decreases when the opponent takes a prize, which
    only happens when they KO one of ours, which can only happen on their
    (intervening) turn. Snapshots once per turn change, not every call.

    Bug fixed 2026-07-21 (pre-merge adversarial review, empirically
    reproduced): this is keyed by seat (correctly — verified no cross-seat
    leakage), but a bare `turn != prev[0]` check has no notion of GAME
    boundaries. `eval/run_batch.py`'s `--games N` loop (and self-play/
    tournament eval generally) reuses this same module across many games in
    one process; turn numbers reset each game, so a same-numbered turn in a
    NEW game could silently compare against the PREVIOUS game's stale
    opp_prize baseline. Turn numbers only ever increase within one real
    game, so a same-or-lower turn number for this seat is proof this is a
    fresh game reusing the slot — treat it as a hard reset, not a same-game
    turn change.
    """
    if opp_prize is None:
        return False
    prev = _LAST_TURN_SNAPSHOT.get(yi)
    is_new_game = prev is None or (
        isinstance(turn, (int, float))
        and isinstance(prev[0], (int, float))
        and turn <= prev[0]
    )
    if is_new_game:
        _LAST_TURN_SNAPSHOT[yi] = (turn, opp_prize)
        return False
    result = False
    if turn != prev[0]:
        result = opp_prize < prev[1]
        _LAST_TURN_SNAPSHOT[yi] = (turn, opp_prize)
    return result


def _find_mon_by_option(sit: Dict[str, Any], opt: dict, cid: Optional[int]) -> Optional[dict]:
    """Match a CTX_SWITCH/CTX_TO_ACTIVE option back to the actual board mon
    it refers to, so target-selection can see that mon's real HP/energy —
    the option itself only carries identifiers (serial/cardId), not state.
    Tries serial first (exact — distinguishes duplicate copies), falls back
    to first-matching card_id.
    """
    pool = list(sit.get("opp_bench") or []) + list(sit.get("my_bench") or [])
    if sit.get("opp_active"):
        pool.append(sit["opp_active"])
    if sit.get("my_active"):
        pool.append(sit["my_active"])
    serial = opt.get("serial")
    if serial is not None:
        for m in pool:
            if isinstance(m, dict) and m.get("serial") == serial:
                return m
    if cid is not None:
        for m in pool:
            if isinstance(m, dict) and _cid(m) == cid:
                return m
    return None


def _fez_flip_the_script_live(sit: Dict[str, Any]) -> bool:
    """True iff Fezandipiti ex is in play for us AND its ability's real
    trigger condition (verified from the engine binary) is currently met:
    a Pokemon of ours was KO'd during the opponent's last turn.
    """
    if not sit.get("ko_last_turn"):
        return False
    if sit.get("my_active_id") == ID_FEZANDIPITI:
        return True
    return any(_cid(m) == ID_FEZANDIPITI for m in (sit.get("my_bench") or []))


def _opponent_target_bonus(mon: Optional[dict], cid: Optional[int]) -> float:
    """Scoring bonus for choosing an OPPONENT's Pokemon (Boss's Orders /
    gust / snipe targets) — the tactic being "lock a Pokemon they don't
    want active into the active spot so they have to burn cards/tempo to
    get out of it," not just "hit the biggest attacker."

    Real retreat cost is NOT available: checked obs.py's parsing and two
    real logged debug dumps (eval/debug_*.json) — no retreatCost field
    anywhere. Uses defensible proxies instead of exact data:
      - low remaining HP -> a follow-up KO is likely reachable
      - no energy attached -> forced active AND can't attack back, which
        buys a free turn regardless of what its retreat cost actually is
      - "ex" in the printed name -> real-world proxy for "probably has a
        non-trivial retreat cost and is the Pokemon they least want stuck
        active" (ex/mega Pokemon are overwhelmingly retreat-cost 2+ in the
        actual game). An approximation, not measured data — replace with
        real retreat costs if a future engine version exposes them.
    """
    bonus = 0.0
    if isinstance(mon, dict):
        try:
            hp, max_hp = mon.get("hp"), mon.get("maxHp")
            if hp is not None and max_hp:
                frac = float(hp) / float(max_hp)
                bonus += (1.0 - frac) * 30.0
        except (TypeError, ValueError):
            pass
        has_energy = bool(mon.get("energies") or mon.get("energyCards"))
        if not has_energy:
            bonus += 25.0
    name = _card_name(cid)
    if name.endswith(" ex"):
        bonus += 15.0
    return bonus


# ---------------------------------------------------------------------------
# 2–3) THINK + CHECKLIST — score legal options like a player scanning choices
# ---------------------------------------------------------------------------
def _think_score(
    obs: dict,
    sit: Dict[str, Any],
    select_type: int,
    context: int,
    option_index: int,
    opt: dict,
) -> float:
    """Adds tier 4 (learned adjustment, off by default) on top of the
    existing, tested base scorer. Pure no-op unless a weights file exists
    AND PTCG_USE_LEARNED_SCORER=1 is set — see agent/learned_scorer.py.
    """
    base = _think_score_base(obs, sit, select_type, context, option_index, opt)
    if _learned_score_adjustment is None:
        return base
    try:
        cid = _option_card_id(obs, opt)
        opt_type = int(opt.get("type") if opt.get("type") is not None else -1)
        return base + _learned_score_adjustment(sit, cid, opt_type)
    except Exception:
        return base


def _think_score_base(
    obs: dict,
    sit: Dict[str, Any],
    select_type: int,
    context: int,
    option_index: int,
    opt: dict,
) -> float:
    opt_type = int(opt.get("type") if opt.get("type") is not None else -1)

    # YES/NO questions a judge would ask you
    if select_type == SELECT_YES_NO or opt_type in (OPT_YES, OPT_NO):
        return _human_yes_no(context, opt_type)

    # Setup: "What do I put as Active / Bench?"
    if context in (CTX_SETUP_ACTIVE, CTX_SETUP_BENCH, CTX_TO_FIELD, CTX_TO_BENCH):
        return _human_place_basic(opt, context, option_index)

    # Main turn menu: human checklist order
    if select_type == SELECT_MAIN or context == CTX_MAIN:
        return _human_main_checklist(obs, sit, opt, opt_type)

    # Attack choice among multiple attacks: the engine only lists affordable
    # attacks, and bigger attacks list later — prefer the last affordable one
    if select_type == SELECT_ATTACK or context == 35:
        return 50.0 + 1.0 * option_index

    # Evolve picker
    if select_type == SELECT_EVOLVE or context == 37:
        return 80.0 + _evo_bonus(_option_card_id(obs, opt)) - 0.01 * option_index

    # Count questions (draw N, place N counters)
    if select_type == SELECT_COUNT or opt_type == OPT_NUMBER:
        try:
            n = float(opt.get("number") or 0)
        except (TypeError, ValueError):
            n = 0.0
        return 10.0 + n

    # Card pickers (search, discard, targets…)
    return _human_card_pick(obs, sit, context, opt, option_index)


def _human_main_checklist(obs: dict, sit: Dict[str, Any], opt: dict, opt_type: int) -> float:
    """
    Human turn order (among what the engine allows):

      evolve → attach energy → ability → setup plays →
      supporter → items → attack → end
      (retreat only if Active is doomed)
    """
    goal = sit["goal"]
    can_attack = _options_include(obs, OPT_ATTACK)
    energy_done = sit["energy_attached"]

    # --- Attack: if I can take a swing and board is ready, I do it ---
    if opt_type == OPT_ATTACK:
        # Humans don't skip a legal attack once energy is on / goal is attack
        if goal == "attack" or energy_done or sit["energy_on_active"]:
            return 200.0
        # Early: still OK to attack if literally nothing else
        return 90.0

    # --- Attach energy: "fuel the Active first" ---
    if opt_type == OPT_ATTACH:
        if energy_done:
            return 5.0
        score = 150.0  # very high — enables attack
        if opt.get("inPlayArea") == AREA_ACTIVE:
            score += 20.0
            if sit["my_active_id"] in ATTACKERS or sit["my_active_id"] in (ID_DREEPY, ID_DRAKLOAK, ID_DUSKULL, ID_DUSCLOPS):
                score += 15.0
        elif opt.get("inPlayArea") == AREA_BENCH:
            # Softer penalty: the second Dragapult powers up on the bench
            # while the active trades — full -40 starved the backup attacker
            score -= 15.0
        return score

    # --- Evolve: "build the line" ---
    if opt_type == OPT_EVOLVE:
        score = 140.0
        if opt.get("inPlayArea") == AREA_ACTIVE:
            score += 10.0
        # Prefer Dragapult/Dusk evolutions
        # (cardId on evolve option may be evo piece or in-play target depending on engine)
        score += _evo_bonus(_option_card_id(obs, opt))
        # If attack is ready this turn, mild preference to attack after evolve
        if can_attack and energy_done:
            score -= 15.0
        return score

    # --- Ability: free value before attack ---
    if opt_type == OPT_ABILITY:
        score = 120.0
        if _option_card_id(obs, opt) == ID_FEZANDIPITI and _fez_flip_the_script_live(sit):
            # Flip the Script: draw 3, once per turn, only live when a
            # Pokemon of ours was KO'd during the opponent's last turn —
            # a strong tempo swing worth taking ahead of most else.
            score = 180.0
        if can_attack and energy_done:
            score -= 20.0
        return score

    # --- Play card from hand ---
    if opt_type == OPT_PLAY:
        return _human_play_card(obs, sit, opt, can_attack, energy_done)

    # --- Retreat: only if Active is dying ---
    if opt_type == OPT_RETREAT:
        return 70.0 if sit["active_weak"] else 2.0

    # --- End turn ---
    if opt_type == OPT_END:
        if can_attack:
            return 1.0  # never pass a free attack
        return 15.0

    if opt_type == OPT_DISCARD:
        return 4.0

    if opt_type == OPT_SKILL:
        return 1.0

    return 10.0


def _human_play_card(
    obs: dict,
    sit: Dict[str, Any],
    opt: dict,
    can_attack: bool,
    energy_done: bool,
) -> float:
    """Adds tiers 2+3 (turn-plan ordering bonus) on top of the existing,
    tested base scorer. `sit["turn_plan"]["rank"]` is empty unless >=2
    COMBO_CANDIDATES are in hand, so this is a no-op for the vast majority
    of decisions — decks/hands with no combo-capable cards see identical
    scores to before this change.
    """
    cid = _resolve_play_card_id(obs, opt)
    base = _human_play_card_base(obs, sit, opt, can_attack, energy_done)
    rank = sit.get("turn_plan", {}).get("rank", {})
    return base + rank.get(cid, 0) * 3.0


def _human_play_card_base(
    obs: dict,
    sit: Dict[str, Any],
    opt: dict,
    can_attack: bool,
    energy_done: bool,
) -> float:
    """When looking at hand: what would I click?"""
    cid = _resolve_play_card_id(obs, opt)
    name = _card_name(cid).lower()
    role = _role(cid)

    # Already used supporter/stadium this turn
    if sit["supporter_played"] and (
        role in ("supporter", "draw_supporter", "boss", "gust_supporter")
        or cid in (ID_LILLIE, ID_CRISPIN, ID_BOSS, 1231)
    ):
        return 3.0
    if sit["stadium_played"] and role == "stadium":
        return 3.0

    # If I can attack now, stop fishing for more setup
    if can_attack and energy_done:
        # Still allow Boss if gust pays
        if cid == ID_BOSS and sit["opp_has_bench"]:
            return 110.0
        # Unfair Stamp's real value: play it in the SAME window as the KO,
        # to deny the opponent's response — this is the "right after"
        # branch that was missing before (bug fix, 2026-07-20: the first
        # cut of this rule lived AFTER this early-return and so never fired
        # here, only pre-attack, where it wastes tempo — regressed the
        # frozen eval 94% -> 84%; moving it here was the actual fix).
        if cid == ID_UNFAIR_STAMP:
            if _fez_flip_the_script_live(sit):
                # Sequence Stamp BEFORE Flip the Script (score above its
                # 180): resolve our own hand-shrinking effect before
                # drawing 3 more, so the extra draws aren't complicated by
                # a disruption effect landing on top of a just-grown hand.
                return 190.0
            if sit["opp_has_bench"]:
                return 105.0
        # Prime Catcher: fine to fire in the ready-to-attack window too
        # (draw 2 rarely costs the turn), but attacking still wins ties.
        if cid == ID_PRIME_CATCHER:
            return 60.0
        return 25.0

    # --- Supporter thinking ---
    if cid == ID_CRISPIN:
        # "I need energies on the board for Dragapult"
        return 135.0 if not energy_done else 100.0
    if cid == ID_LILLIE or role in ("draw_supporter", "supporter"):
        return 110.0 if sit["hand_n"] <= 4 else 95.0
    if cid == ID_BOSS or role in ("boss", "gust_supporter"):
        return 140.0 if sit["opp_has_bench"] else 20.0

    # --- Tier 1: Prime Catcher's development-phase value (draw 2 helps hit
    # missing pieces regardless of combo timing). Unfair Stamp otherwise has
    # NO general branch here — pre-attack, it falls through to the generic
    # catch-all below (~45), matching its pre-fix behavior: locking the
    # opponent's hand before we're even threatening a KO wastes tempo. The
    # one exception is the same "before Fez" sequencing as the ready-to-
    # attack branch above — Flip the Script's ability score (180) isn't
    # gated on attack-readiness, so this needs to fire here too or the
    # sequencing bug just reappears in the not-yet-attacking case.
    if cid == ID_UNFAIR_STAMP and _fez_flip_the_script_live(sit):
        return 190.0
    if cid == ID_PRIME_CATCHER:
        return 100.0 if sit["goal"] in ("setup", "develop") else 70.0

    # --- Search thinking: "am I missing pieces?" ---
    if cid in SEARCH_IDS or role == "search":
        # Deck thinning: every search (found or discarded-as-cost) removes
        # a card from the remaining deck, improving the odds of every
        # future draw hitting something useful — not just this turn's
        # pick. That value is bigger the more deck is left to thin, so
        # scale a small bonus with deck_n rather than a flat add (capped;
        # deck_n=50 -> +15, deck_n=10 -> +3, deck_n=0 -> +0).
        thinning_bonus = min(15.0, sit.get("deck_n", 0) * 0.3)
        if sit["goal"] in ("setup", "develop"):
            return 130.0 + thinning_bonus
        return 80.0 + thinning_bonus

    # --- Basics to bench ---
    if cid in BASICS_PRIORITY or role in ("basic", "support_pokemon"):
        bench_n = len(sit["my_bench"])
        if bench_n < 2:
            return 115.0 + _basic_priority_bonus(cid)
        if bench_n < 4:
            return 85.0 + _basic_priority_bonus(cid)
        return 30.0

    # --- Evolution cards in hand (play as evolve is separate; some are play) ---
    if cid in EVOS or role == "evolution":
        return 100.0

    # --- Attackers ---
    if cid in ATTACKERS or role == "attacker":
        return 105.0

    # --- Disruption items (hammers) after board exists ---
    if cid == ID_HAMMER or "hammer" in name:
        return 70.0 if sit["goal"] != "setup" else 40.0

    # --- Stadium ---
    if role == "stadium" or "tower" in name or "watchtower" in name:
        return 60.0

    # --- Tool ---
    if role == "tool" or "balloon" in name or "fan" in name:
        return 65.0

    return 45.0


def _want_to_go_first() -> bool:
    """Seat choice from deck identity (human competitive habit).

    - Evolution-line main attackers (Dragapult, etc.): go **first**.
      You need turns to evolve; first seat gives more setup tempo.
    - Basics that can attack / use impact ability on their first turn
      (e.g. Ogerpon, Meowth ex, many ex Basics): go **second** so your
      first turn can attack (first player skips attack on turn 1).
    """
    # Deck signals evolution-line primary
    evo_line_ids = frozenset(LINE_DRAGAPULT + LINE_DUSK + (ID_DRAKLOAK, ID_DRAGAPULT))
    basic_attacker_names = (
        "ogerpon",
        "meowth ex",
        "miraidon",
        "raging bolt",
        "iron hands",
        "pidgeot",  # often stage but ability-centric; still often 2nd
    )

    deck_ids = []
    if _deck_mod is not None:
        try:
            deck_ids = list(getattr(_deck_mod, "DECK", []) or [])
        except Exception:
            deck_ids = []

    evo_count = sum(1 for i in deck_ids if i in evo_line_ids)
    # Dreepy/Drakloak/Dragapult heavy → first
    if evo_count >= 6 or (ID_DREEPY in deck_ids and ID_DRAGAPULT in deck_ids):
        return True

    # Name-based: teal mask / basic ex attackers without long evo line
    basic_attack_pressure = 0
    for i in set(deck_ids):
        n = _card_name(i).lower()
        if any(b in n for b in basic_attacker_names):
            basic_attack_pressure += deck_ids.count(i)
        if "mega lucario" in n or "dragapult" in n or "drakloak" in n or "dreepy" in n:
            return True  # evolution / mega evo lines → first

    if basic_attack_pressure >= 3 and evo_count < 4:
        return False  # go second

    # Default for this project primary (Dragapult): first
    return True


def _human_yes_no(context: int, opt_type: int) -> float:
    # Seat choice: evolution decks first; ready-to-attack basics second
    if context == CTX_IS_FIRST:
        want_first = _want_to_go_first()
        if want_first:
            return 80.0 if opt_type == OPT_YES else 20.0
        return 80.0 if opt_type == OPT_NO else 20.0
    # Mulligan if offered (no basic)
    if context == CTX_MULLIGAN:
        return 80.0 if opt_type == OPT_YES else 20.0
    # Optional effects: usually take them
    if context in (CTX_ACTIVATE, CTX_FIRST_EFFECT):
        return 70.0 if opt_type == OPT_YES else 30.0
    if context == CTX_COIN_HEAD:
        return 55.0 if opt_type == OPT_YES else 45.0
    return 50.0 if opt_type == OPT_YES else 50.0


def _human_place_basic(opt: dict, context: int, option_index: int) -> float:
    cid = opt.get("cardId")
    try:
        cid_i = int(cid) if cid is not None else None
    except (TypeError, ValueError):
        cid_i = None
    score = 40.0 + _basic_priority_bonus(cid_i)
    if context == CTX_SETUP_ACTIVE:
        # Prefer Dreepy as Active for Dragapult path
        if cid_i == ID_DREEPY:
            score += 30.0
        elif cid_i in ATTACKERS:
            score += 20.0
        elif cid_i == ID_DUSKULL:
            score += 10.0
    return score - 0.01 * option_index


def _human_card_pick(
    obs: dict,
    sit: Dict[str, Any],
    context: int,
    opt: dict,
    option_index: int,
) -> float:
    cid = _option_card_id(obs, opt)
    role = _role(cid)

    # Searching deck / recovering to hand
    if context == CTX_TO_HAND:
        if cid in (ID_DRAGAPULT, ID_DRAKLOAK, ID_DREEPY):
            return 100.0
        if cid in (ID_DUSKNOIR, ID_DUSCLOPS, ID_DUSKULL):
            return 90.0
        if cid in ENERGY_IDS or role in ("energy", "energy_basic", "energy_special"):
            return 85.0
        if cid in (ID_CRISPIN, ID_LILLIE, ID_BOSS) or role in ("supporter", "draw_supporter", "boss"):
            return 80.0
        if cid in SEARCH_IDS or role == "search":
            return 70.0
        if cid in BASICS_PRIORITY or role in ("basic",):
            return 75.0 + _basic_priority_bonus(cid)
        return 40.0 - 0.01 * option_index

    # Discard cost (Ultra Ball etc.): dump junk, keep engine
    if context in (CTX_DISCARD, 29):
        if cid in ENERGY_IDS and cid not in (19,):  # keep special if any
            return 75.0
        if role in ("stadium", "tool"):
            return 60.0
        if cid in SEARCH_IDS:
            return 15.0
        if cid in (ID_DRAGAPULT, ID_DRAKLOAK, ID_DREEPY, ID_DUSKNOIR):
            return 5.0
        if cid in (ID_CRISPIN, ID_LILLIE, ID_BOSS):
            return 12.0
        if role in ("basic",) and cid not in BASICS_PRIORITY[:2]:
            return 55.0
        return 40.0 - 0.01 * option_index

    # Damage targets: hit opponent, prefer Active
    if context in (CTX_DAMAGE, CTX_DAMAGE_COUNTER, 14):
        pi = opt.get("playerIndex")
        yi = _your_index(obs)
        if pi is not None and yi is not None and int(pi) != int(yi):
            return 80.0 + (15.0 if opt.get("area") == AREA_ACTIVE else 0.0)
        return 10.0

    # Heal: self, prefer damaged
    if context in (CTX_HEAL, 16):
        pi = opt.get("playerIndex")
        yi = _your_index(obs)
        if pi is not None and yi is not None and int(pi) == int(yi):
            return 70.0
        return 15.0

    # Switch into Active. Two distinct decisions were sharing this one
    # branch with no playerIndex check (bug, 2026-07-20): choosing where
    # WE retreat/promote to (should prefer our own attackers) is a
    # different question from choosing which of the OPPONENT's Pokemon a
    # gust effect (Boss's Orders etc.) drags into their active spot
    # (should prefer denial — a Pokemon they don't want stuck there —
    # not anything from OUR OWN priority list, which doesn't even apply
    # to their card IDs).
    if context in (CTX_SWITCH, CTX_TO_ACTIVE):
        pi = opt.get("playerIndex")
        yi = _your_index(obs)
        if pi is not None and yi is not None and int(pi) != int(yi):
            mon = _find_mon_by_option(sit, opt, cid)
            return 50.0 + _opponent_target_bonus(mon, cid)
        return 50.0 + _basic_priority_bonus(cid) + (20.0 if cid in ATTACKERS else 0.0)

    # Default card
    return 35.0 + _basic_priority_bonus(cid) - 0.01 * option_index


# ---------------------------------------------------------------------------
# How many picks (human: optional bench = 1–2, search = take the good one)
# ---------------------------------------------------------------------------
def _how_many_to_pick(
    select_type: int,
    context: int,
    min_count: int,
    max_count: int,
    scored: Sequence[Tuple[float, int]],
    sit: Dict[str, Any],
) -> int:
    if max_count <= 1:
        return max_count

    # Setup bench: put 1–2, not always fill
    if context == CTX_SETUP_BENCH and min_count == 0:
        good = sum(1 for s, _ in scored if s >= 50.0)
        target = min(2, max_count, max(1, good) if good else 1)
        return max(min_count, target)

    # Optional search: take 1 good card
    if min_count == 0 and context == CTX_TO_HAND and max_count >= 1:
        return 1

    if min_count == 0 and context == 12:  # NOT_MOVE
        return 0

    return max_count


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _options_include(obs: dict, opt_type: int) -> bool:
    for o in ((obs.get("select") or {}).get("option") or []):
        if isinstance(o, dict) and int(o.get("type", -1)) == opt_type:
            return True
    return False


def _basic_priority_bonus(card_id: Optional[int]) -> float:
    if card_id is None:
        return 0.0
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return 0.0
    if cid in BASICS_PRIORITY:
        return 20.0 - 2.0 * BASICS_PRIORITY.index(cid)
    if _deck_mod is not None:
        fn = getattr(_deck_mod, "setup_priority_basics", None)
        if callable(fn):
            try:
                prefs = list(fn())
                if cid in prefs:
                    return 15.0 - 1.0 * prefs.index(cid)
            except Exception:
                pass
    return 0.0


def _evo_bonus(card_id: Optional[int]) -> float:
    if card_id is None:
        return 0.0
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return 0.0
    if cid == ID_DRAGAPULT:
        return 25.0
    if cid == ID_DRAKLOAK:
        return 20.0
    if cid == ID_DUSKNOIR:
        return 18.0
    if cid == ID_DUSCLOPS:
        return 12.0
    if cid in EVOS:
        return 10.0
    return 0.0


def _role(card_id: Optional[int]) -> str:
    if card_id is None:
        return "unknown"
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return "unknown"
    if _deck_mod is not None:
        fn = getattr(_deck_mod, "role", None)
        if callable(fn):
            try:
                return str(fn(cid)).lower()
            except Exception:
                pass
    if cid in SEARCH_IDS:
        return "search"
    if cid in (ID_LILLIE, ID_CRISPIN, 1231):
        return "supporter"
    if cid == ID_BOSS:
        return "boss"
    if cid in ENERGY_IDS:
        return "energy"
    if cid in ATTACKERS:
        return "attacker"
    if cid in EVOS:
        return "evolution"
    if cid in BASICS_PRIORITY:
        return "basic"
    return "unknown"


def _card_name(card_id: Optional[int]) -> str:
    if card_id is None:
        return ""
    if _deck_mod is not None:
        fn = getattr(_deck_mod, "card_name", None)
        if callable(fn):
            try:
                return str(fn(int(card_id)))
            except Exception:
                pass
    return str(card_id)


def _cid(mon: Any) -> Optional[int]:
    if not isinstance(mon, dict):
        return None
    v = mon.get("id", mon.get("cardId"))
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _first_mon(active_list: Any) -> Optional[dict]:
    if not active_list:
        return None
    for m in active_list:
        if isinstance(m, dict):
            return m
    return None


def _ids_from_cards(cards: Any) -> List[int]:
    out: List[int] = []
    if not cards:
        return out
    for c in cards:
        if isinstance(c, dict):
            i = c.get("id", c.get("cardId"))
            try:
                if i is not None:
                    out.append(int(i))
            except (TypeError, ValueError):
                pass
    return out


def _prize_count(player: dict) -> Optional[int]:
    prizes = player.get("prize")
    if prizes is None:
        return None
    try:
        return len(prizes)
    except TypeError:
        return None


def _active_is_weak(me: dict, active: Optional[dict]) -> bool:
    if not active:
        return False
    try:
        hp, max_hp = active.get("hp"), active.get("maxHp")
        if hp is not None and max_hp and float(hp) <= 0.3 * float(max_hp):
            return True
    except (TypeError, ValueError):
        pass
    return bool(
        me.get("poisoned")
        or me.get("burned")
        or me.get("asleep")
        or me.get("paralyzed")
        or me.get("confused")
    )


def _your_index(obs: dict) -> Optional[int]:
    current = (obs or {}).get("current") or {}
    yi = current.get("yourIndex")
    try:
        return int(yi) if yi is not None else 0
    except (TypeError, ValueError):
        return 0


def _resolve_play_card_id(obs: dict, option_dict: dict) -> Optional[int]:
    if option_dict.get("cardId") is not None:
        try:
            return int(option_dict["cardId"])
        except (TypeError, ValueError):
            pass
    hand_index = option_dict.get("index")
    if hand_index is None:
        return None
    current = (obs or {}).get("current") or {}
    players = current.get("players") or []
    yi = _your_index(obs) or 0
    try:
        me = players[int(yi)]
        hand = me.get("hand") or []
        card = hand[int(hand_index)]
    except (IndexError, TypeError, ValueError, AttributeError):
        return None
    return _cid(card) if isinstance(card, dict) else None


def _option_card_id(obs: dict, option_dict: dict) -> Optional[int]:
    if option_dict.get("cardId") is not None:
        try:
            return int(option_dict["cardId"])
        except (TypeError, ValueError):
            pass
    return _resolve_play_card_id(obs, option_dict)


def _random_fallback(obs: Any) -> list[int]:
    try:
        select = obs.get("select") if isinstance(obs, dict) else None
        if not select:
            return []
        options = select.get("option") or []
        max_count = int(select.get("maxCount") or 0)
        n = len(options)
        if max_count <= 0 or n == 0:
            return []
        k = min(max_count, n)
        return random.sample(list(range(n)), k)
    except Exception:
        return []
