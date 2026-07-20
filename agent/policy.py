"""
Heuristic decision policy for the cabt Pokémon TCG agent (v1).

``choose_actions(obs) -> list[int]`` returns indices into ``obs["select"]["option"]``.
Deck selection (``select is None``) is handled by ``main.py``; this module returns [].

Scoring weights (higher = preferred)
------------------------------------
MAIN option types (SelectType.MAIN = 0):

| OptionType | base weight | notes |
|------------|------------:|-------|
| ATTACK (13)|       100.0 | Prefer ending the turn with an attack |
| ATTACH (8) |        85.0 | High while energy not yet attached this turn; else low |
| PLAY (7)   |   40–90.0   | Search/setup items & supporters high; stadiums medium; Boss if opp bench |
| EVOLVE (9) |        75.0 | Build board |
| ABILITY (10)|       70.0 | Use free abilities before attacking |
| RETREAT (12)|   15–65.0  | Low by default; higher if active is weak/low HP/statused |
| END (14)   |         5.0 | Last resort when nothing better |
| DISCARD (11)|        8.0 | Avoid unless forced |
| SKILL (15) |         1.0 | Passive / rare ordering |

CARD / YES_NO / other select types:
- Prefer preferred basics (Dunsparce / Shuppet / Poltchageist style) and attackers.
- YES over NO for ACTIVATE / FIRST_EFFECT / MULLIGAN contexts.
- Damage targets: prefer opponent active/bench; heal/remove damage: prefer our damaged.
- COUNT: prefer larger useful numbers (draw) or max when placing damage.

Setup:
- SETUP_ACTIVE: best preferred basic among options.
- SETUP_BENCH (minCount often 0): place 1–2 good basics, not always maxCount.

On any error: random legal sample of size maxCount (or [] if maxCount <= 0).
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Optional helper modules (duck-type fallbacks if missing / incomplete)
# ---------------------------------------------------------------------------
try:
    from agent import obs as _obs_mod  # type: ignore
except Exception:  # pragma: no cover
    _obs_mod = None

try:
    from agent import options as _options_mod  # type: ignore
except Exception:  # pragma: no cover
    _options_mod = None

try:
    from agent import deck_knowledge as _deck_mod  # type: ignore
except Exception:  # pragma: no cover
    _deck_mod = None

# ---------------------------------------------------------------------------
# cabt enums (ints) — keep local so policy works without the env package
# ---------------------------------------------------------------------------
# SelectType
SELECT_MAIN = 0
SELECT_CARD = 1
SELECT_ATTACHED_CARD = 2
SELECT_CARD_OR_ATTACHED = 3
SELECT_ENERGY = 4
SELECT_SKILL = 5
SELECT_ATTACK = 6
SELECT_EVOLVE = 7
SELECT_COUNT = 8
SELECT_YES_NO = 9
SELECT_SPECIAL_CONDITION = 10

# SelectContext
CTX_MAIN = 0
CTX_SETUP_ACTIVE = 1
CTX_SETUP_BENCH = 2
CTX_SWITCH = 3
CTX_TO_ACTIVE = 4
CTX_TO_BENCH = 5
CTX_TO_FIELD = 6
CTX_TO_HAND = 7
CTX_DISCARD = 8
CTX_TO_DECK = 9
CTX_TO_DECK_BOTTOM = 10
CTX_TO_PRIZE = 11
CTX_NOT_MOVE = 12
CTX_DAMAGE_COUNTER = 13
CTX_DAMAGE_COUNTER_ANY = 14
CTX_DAMAGE = 15
CTX_REMOVE_DAMAGE_COUNTER = 16
CTX_HEAL = 17
CTX_EVOLVES_FROM = 18
CTX_EVOLVES_TO = 19
CTX_DEVOLVE = 20
CTX_ATTACH_FROM = 21
CTX_ATTACH_TO = 22
CTX_DETACH_FROM = 23
CTX_LOOK = 24
CTX_EFFECT_TARGET = 25
CTX_DISCARD_ENERGY_CARD = 26
CTX_DISCARD_TOOL_CARD = 27
CTX_SWITCH_ENERGY_CARD = 28
CTX_DISCARD_CARD_OR_ATTACHED = 29
CTX_DISCARD_ENERGY = 30
CTX_TO_HAND_ENERGY = 31
CTX_TO_DECK_ENERGY = 32
CTX_SWITCH_ENERGY = 33
CTX_SKILL_ORDER = 34
CTX_ATTACK = 35
CTX_DISABLE_ATTACK = 36
CTX_EVOLVE = 37
CTX_DRAW_COUNT = 38
CTX_DAMAGE_COUNTER_COUNT = 39
CTX_REMOVE_DAMAGE_COUNTER_COUNT = 40
CTX_IS_FIRST = 41
CTX_MULLIGAN = 42
CTX_ACTIVATE = 43
CTX_FIRST_EFFECT = 44
CTX_MORE_DEVOLVE = 45
CTX_COIN_HEAD = 46
CTX_AFFECT_SPECIAL_CONDITION = 47
CTX_RECOVER_SPECIAL_CONDITION = 48

# OptionType
OPT_NUMBER = 0
OPT_YES = 1
OPT_NO = 2
OPT_CARD = 3
OPT_TOOL_CARD = 4
OPT_ENERGY_CARD = 5
OPT_ENERGY = 6
OPT_PLAY = 7
OPT_ATTACH = 8
OPT_EVOLVE = 9
OPT_ABILITY = 10
OPT_DISCARD = 11
OPT_RETREAT = 12
OPT_ATTACK = 13
OPT_END = 14
OPT_SKILL = 15
OPT_SPECIAL_CONDITION = 16

# AreaType
AREA_HAND = 2
AREA_ACTIVE = 4
AREA_BENCH = 5

# ---------------------------------------------------------------------------
# MAIN base weights (documented in module docstring)
# ---------------------------------------------------------------------------
# MAIN priority (tuned after smoke eval: premature retreat + never attacking hurt winrate)
W_ATTACK_READY = 130.0  # attack legal — take it after setup pieces this turn
W_ATTACK = 100.0
W_ATTACH = 105.0  # energy first often enables attack
W_ATTACH_ALREADY = 8.0
W_EVOLVE = 95.0
W_ABILITY = 80.0
W_PLAY_SEARCH = 82.0
W_PLAY_SUPPORTER = 74.0
W_PLAY_BOSS = 90.0
W_PLAY_STADIUM = 50.0
W_PLAY_TOOL = 55.0
W_PLAY_BASIC = 70.0
W_PLAY_DEFAULT = 40.0
W_RETREAT = 3.0  # must stay BELOW END unless active is in real trouble
W_RETREAT_WEAK = 55.0
W_END = 12.0
W_DISCARD = 6.0
W_SKILL = 1.0
W_UNKNOWN = 15.0

# Prefer these basics during setup / benching (cardId)
# Dragapult primary deck priorities (deck.csv)
PREFERRED_BASICS_DEFAULT = (
    119,  # Dreepy — Dragapult line
    131,  # Duskull — Dusknoir line
    235,  # Budew
    112,  # Munkidori
    1071,  # Meowth ex
    140,  # Fezandipiti ex
)

# Evolutions we want ASAP
_EVOLVE_PRIORITY = frozenset({
    120,  # Drakloak
    121,  # Dragapult ex
    132,  # Dusclops
    133,  # Dusknoir
})

# cardId role fallbacks when deck_knowledge is unavailable
_SEARCH_ITEMS = frozenset({1121, 1086, 1152, 1122, 1097, 1128, 1120, 1094})  # + hammer, bug set
_SUPPORTERS = frozenset({1227, 1239, 1182, 1191, 1198, 1231})  # + Crispin, Dawn
# NOTE: deck_knowledge.role() is preferred; these are fallbacks only.
_BOSS_ORDERS = frozenset({1182, 1088})
_STADIUMS = frozenset({1264, 1256, 1246, 1261, 1252})
_TOOLS = frozenset({1174, 1161})
_ENERGY_IDS = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9, 19, 20})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def choose_actions(obs: dict) -> list[int]:
    """Choose legal option indices for the current select prompt.

    Returns a list of length ``maxCount`` in most cases (or between
    ``minCount`` and ``maxCount`` for optional multi-picks like setup bench).
    Never raises: falls back to a random legal sample on error.
    """
    try:
        select = obs.get("select") if isinstance(obs, dict) else None
        if select is None:
            # Deck phase is handled in main.py
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

        scored: List[Tuple[float, int]] = []
        for i, opt in enumerate(options):
            if not isinstance(opt, dict):
                opt = {"type": opt}
            s = score_option(obs, i, opt)
            scored.append((s, i))

        # Stable tie-break: higher score, then lower index
        scored.sort(key=lambda t: (-t[0], t[1]))

        k = _desired_pick_count(
            select_type=select_type,
            context=context,
            min_count=min_count,
            max_count=max_count,
            scored=scored,
        )
        chosen = [idx for _, idx in scored[:k]]

        # Satisfy minCount with next-best if we undershot
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
    """Return a heuristic score for one option (higher is better)."""
    try:
        select = (obs or {}).get("select") or {}
        select_type = int(select.get("type") or 0)
        context = int(select.get("context") or 0)
        opt_type = int(option_dict.get("type") if option_dict.get("type") is not None else -1)

        if select_type == SELECT_MAIN or context == CTX_MAIN:
            return _score_main(obs, option_dict, opt_type)

        if select_type == SELECT_YES_NO or opt_type in (OPT_YES, OPT_NO):
            return _score_yes_no(context, opt_type)

        if select_type == SELECT_COUNT or opt_type == OPT_NUMBER:
            return _score_number(context, option_dict)

        if select_type == SELECT_ATTACK or context in (CTX_ATTACK, CTX_DISABLE_ATTACK):
            # Prefer first attack; slight preference for lower attackId as proxy for main attack
            attack_id = option_dict.get("attackId")
            base = 50.0
            if attack_id is not None:
                base += max(0.0, 10.0 - float(attack_id) * 0.01)
            if context == CTX_DISABLE_ATTACK:
                # Prefer disabling stronger-looking attacks (higher id noise); keep flat
                base = 40.0
            return base - 0.01 * option_index

        if select_type == SELECT_EVOLVE or context == CTX_EVOLVE:
            return W_EVOLVE - 0.01 * option_index

        # CARD / attached / energy / skill / special-condition style picks
        return _score_cardish(obs, option_dict, opt_type, context, option_index)
    except Exception:
        return W_UNKNOWN - 0.01 * option_index


# ---------------------------------------------------------------------------
# MAIN scoring
# ---------------------------------------------------------------------------
def _main_has_type(obs: dict, opt_type: int) -> bool:
    select = (obs or {}).get("select") or {}
    for o in select.get("option") or []:
        if isinstance(o, dict) and int(o.get("type", -1)) == opt_type:
            return True
    return False


def _score_main(obs: dict, option_dict: dict, opt_type: int) -> float:
    current = (obs or {}).get("current") or {}
    energy_attached = bool(current.get("energyAttached"))
    supporter_played = bool(current.get("supporterPlayed"))
    stadium_played = bool(current.get("stadiumPlayed"))
    can_attack = _main_has_type(obs, OPT_ATTACK)

    if opt_type == OPT_ATTACK:
        # If we already attached (or attack is legal), prefer finishing with attack
        return W_ATTACK_READY if energy_attached or can_attack else W_ATTACK

    if opt_type == OPT_ATTACH:
        score = W_ATTACH_ALREADY if energy_attached else W_ATTACH
        in_play_area = option_dict.get("inPlayArea")
        if in_play_area == AREA_ACTIVE:
            score += 15.0
            # Prefer powering known attackers
            score += _attacker_active_bonus(_active_card_id(obs))
        elif in_play_area == AREA_BENCH:
            # Almost never attach to bench before active is fueled
            score -= 25.0
        return score

    if opt_type == OPT_EVOLVE:
        # Dragapult line: evolve early and often (Drakloak enables engine)
        base = W_EVOLVE + 10.0
        if option_dict.get("inPlayArea") == AREA_ACTIVE:
            base += 8.0
        # Prefer evolving into priority stages when cardId resolvable
        evo_id = option_dict.get("cardId")
        try:
            if evo_id is not None and int(evo_id) in _EVOLVE_PRIORITY:
                base += 15.0
        except (TypeError, ValueError):
            pass
        # Only defer evolve if attack is ready AND we already have Dragapult-level board
        if can_attack and energy_attached:
            base -= 10.0  # mild: still OK to evolve mid-turn before attack sometimes
        return base

    if opt_type == OPT_ABILITY:
        # Abilities before attack usually OK; slight penalty if attack ready after attach
        base = W_ABILITY
        if can_attack and energy_attached:
            base -= 15.0
        return base

    if opt_type == OPT_PLAY:
        score = _score_play(obs, option_dict, supporter_played, stadium_played)
        # Once attack is available after attaching, stop chaining more plays
        if can_attack and energy_attached:
            score -= 40.0
        return score

    if opt_type == OPT_RETREAT:
        return _score_retreat(obs)

    if opt_type == OPT_END:
        # Prefer END over pointless retreat; if attack available never prefer end
        if can_attack:
            return 1.0
        return W_END

    if opt_type == OPT_DISCARD:
        return W_DISCARD

    if opt_type == OPT_SKILL:
        return W_SKILL

    return W_UNKNOWN


def _score_play(
    obs: dict,
    option_dict: dict,
    supporter_played: bool = False,
    stadium_played: bool = False,
) -> float:
    card_id = _resolve_play_card_id(obs, option_dict)
    role = _card_role(card_id)

    if role in ("boss", "gust", "gust_supporter"):
        if supporter_played:
            return 5.0
        if _opponent_has_bench(obs):
            return W_PLAY_BOSS
        return W_PLAY_DEFAULT - 15.0

    if role in ("search", "search_item"):
        return W_PLAY_SEARCH

    if role in ("supporter", "draw_supporter", "draw"):
        if supporter_played:
            return 5.0
        # Crispin (energy acceleration) is critical for multi-type Dragapult
        if card_id == 1198:
            return W_PLAY_SUPPORTER + 12.0
        return W_PLAY_SUPPORTER

    if role == "stadium":
        if stadium_played:
            return 5.0
        return W_PLAY_STADIUM

    if role == "tool":
        return W_PLAY_TOOL

    if role in ("basic", "attacker", "support_pokemon"):
        me = _my_player(obs)
        bench = (me or {}).get("bench") or []
        bench_n = sum(1 for p in bench if p is not None)
        bonus = 8.0 if bench_n < 2 else (3.0 if bench_n < 4 else -10.0)
        pref = _preferred_basic_bonus(card_id)
        return W_PLAY_BASIC + bonus + pref

    if role in ("energy", "energy_basic", "energy_special"):
        return 20.0

    if role == "evolution":
        return W_PLAY_DEFAULT + 8.0

    return W_PLAY_DEFAULT


def _score_retreat(obs: dict) -> float:
    me = _my_player(obs)
    if not me:
        return W_RETREAT

    active_list = me.get("active") or []
    active = None
    for p in active_list:
        if p is not None:
            active = p
            break
    if not active:
        return W_RETREAT

    weak = False
    try:
        hp = active.get("hp")
        max_hp = active.get("maxHp")
        if hp is not None and max_hp:
            if float(hp) <= 0.35 * float(max_hp):
                weak = True
        if me.get("poisoned") or me.get("burned") or me.get("asleep") or me.get("paralyzed") or me.get("confused"):
            weak = True
    except Exception:
        pass

    return W_RETREAT_WEAK if weak else W_RETREAT


# ---------------------------------------------------------------------------
# Non-MAIN scoring
# ---------------------------------------------------------------------------
def _score_yes_no(context: int, opt_type: int) -> float:
    prefer_yes = context in (
        CTX_ACTIVATE,
        CTX_FIRST_EFFECT,
        CTX_MULLIGAN,  # redraw if offered (often no basic — engine only offers when legal)
        CTX_MORE_DEVOLVE,
    )
    # Going first skips attack on turn 1 — prefer second (NO on IS_FIRST).
    if context == CTX_IS_FIRST:
        prefer_yes = False
    # Coin: slight heads preference is fine
    if context == CTX_COIN_HEAD:
        prefer_yes = True

    if opt_type == OPT_YES:
        return 60.0 if prefer_yes else 30.0
    if opt_type == OPT_NO:
        return 30.0 if prefer_yes else 60.0
    return W_UNKNOWN


def _score_number(context: int, option_dict: dict) -> float:
    number = option_dict.get("number")
    try:
        n = float(number) if number is not None else 0.0
    except (TypeError, ValueError):
        n = 0.0

    if context == CTX_DRAW_COUNT:
        return 10.0 + n  # draw more
    if context in (CTX_DAMAGE_COUNTER_COUNT, CTX_REMOVE_DAMAGE_COUNTER_COUNT):
        return 10.0 + n  # place/remove more
    return 10.0 + n


def _score_cardish(
    obs: dict,
    option_dict: dict,
    opt_type: int,
    context: int,
    option_index: int,
) -> float:
    card_id = _option_card_id(obs, option_dict)
    score = 30.0 + _preferred_basic_bonus(card_id)

    # Setup / field placement
    if context in (CTX_SETUP_ACTIVE, CTX_SETUP_BENCH, CTX_TO_FIELD, CTX_TO_BENCH):
        score = 40.0 + _preferred_basic_bonus(card_id) * 3.0
        if context == CTX_SETUP_ACTIVE:
            # Prefer engine basics that can attack / enable lines
            score += _attacker_active_bonus(card_id)
        return score - 0.01 * option_index

    if context in (CTX_SWITCH, CTX_TO_ACTIVE):
        # Prefer healthy / preferred attackers to active
        score = 40.0 + _attacker_active_bonus(card_id) + _preferred_basic_bonus(card_id)
        hp_bonus = _hp_fraction_bonus(option_dict, obs, prefer_high=True)
        return score + hp_bonus - 0.01 * option_index

    if context in (CTX_DAMAGE, CTX_DAMAGE_COUNTER, CTX_DAMAGE_COUNTER_ANY):
        # Prefer opponent's Pokémon; prefer active for knockouts
        player_index = option_dict.get("playerIndex")
        my_idx = _your_index(obs)
        if player_index is not None and my_idx is not None and int(player_index) != int(my_idx):
            score = 70.0
            if option_dict.get("area") == AREA_ACTIVE:
                score += 15.0
        else:
            score = 10.0  # avoid damaging self unless only option
        return score - 0.01 * option_index

    if context in (CTX_HEAL, CTX_REMOVE_DAMAGE_COUNTER):
        player_index = option_dict.get("playerIndex")
        my_idx = _your_index(obs)
        if player_index is not None and my_idx is not None and int(player_index) == int(my_idx):
            score = 60.0 + _hp_fraction_bonus(option_dict, obs, prefer_high=False)
        else:
            score = 15.0
        return score - 0.01 * option_index

    if context in (CTX_DISCARD, CTX_DISCARD_CARD_OR_ATTACHED, CTX_TO_DECK, CTX_TO_DECK_BOTTOM, CTX_TO_PRIZE):
        # Prefer discarding low-value; keep attackers, search, key supporters
        role = _card_role(card_id)
        if role == "energy":
            # Keep special energy (Telepath); discard plain basic first
            score = 40.0 if card_id in (19,) else 70.0
        elif role in ("search",):
            score = 12.0
        elif role in ("supporter", "boss"):
            score = 18.0
        elif role in ("attacker",):
            score = 8.0
        elif role in ("basic",):
            score = 45.0 - _preferred_basic_bonus(card_id)
        elif role == "evolution":
            score = 25.0
        elif role == "stadium":
            score = 50.0
        elif role == "tool":
            score = 48.0
        else:
            score = 42.0
        return score - 0.01 * option_index

    if context in (CTX_ATTACH_FROM, CTX_ATTACH_TO):
        # Attach energy/tools to Active preferentially
        if option_dict.get("area") == AREA_ACTIVE or option_dict.get("inPlayArea") == AREA_ACTIVE:
            score = 70.0
        elif option_dict.get("area") == AREA_BENCH:
            score = 40.0
        else:
            score = 50.0 + _preferred_basic_bonus(card_id)
        return score - 0.01 * option_index

    if context in (CTX_EVOLVES_FROM, CTX_EVOLVES_TO, CTX_DEVOLVE):
        return 50.0 + _preferred_basic_bonus(card_id) - 0.01 * option_index

    if context == CTX_TO_HAND:
        # Deck search / recovery: prioritize attackers, evolutions, energy, draw
        role = _card_role(card_id)
        if role == "attacker":
            score = 95.0
        elif role == "evolution":
            score = 88.0
        elif role == "energy":
            score = 84.0
        elif role in ("supporter", "boss"):
            score = 80.0
        elif role == "search":
            score = 70.0
        elif role in ("basic",):
            score = 75.0 + _preferred_basic_bonus(card_id)
        else:
            score = 45.0
        return score - 0.01 * option_index

    if context in (
        CTX_DISCARD_ENERGY,
        CTX_DISCARD_ENERGY_CARD,
        CTX_TO_HAND_ENERGY,
        CTX_TO_DECK_ENERGY,
        CTX_SWITCH_ENERGY,
        CTX_SWITCH_ENERGY_CARD,
        CTX_DISCARD_TOOL_CARD,
    ):
        # Prefer operating on opponent when playerIndex present; else first option
        player_index = option_dict.get("playerIndex")
        my_idx = _your_index(obs)
        if (
            context in (CTX_DISCARD_ENERGY, CTX_DISCARD_ENERGY_CARD, CTX_DISCARD_TOOL_CARD)
            and player_index is not None
            and my_idx is not None
            and int(player_index) != int(my_idx)
        ):
            score = 70.0
        else:
            score = 40.0
        return score - 0.01 * option_index

    if opt_type == OPT_CARD:
        return 40.0 + _preferred_basic_bonus(card_id) - 0.01 * option_index

    return W_UNKNOWN - 0.01 * option_index


# ---------------------------------------------------------------------------
# How many options to pick
# ---------------------------------------------------------------------------
def _desired_pick_count(
    select_type: int,
    context: int,
    min_count: int,
    max_count: int,
    scored: Sequence[Tuple[float, int]],
) -> int:
    """Choose k in [min_count, max_count]."""
    if max_count <= 1:
        return max_count

    # Optional setup bench: prefer 1–2 good basics, not always fill
    if context == CTX_SETUP_BENCH and min_count == 0:
        good = sum(1 for s, _ in scored if s >= 45.0)
        target = min(2, max_count, max(1, good) if good else 1)
        return max(min_count, min(max_count, target))

    # Optional multi-card contexts: still take max when forced value is unclear
    # but for pure optional (min 0) discard-to-deck style, take fewer low-score
    if min_count == 0 and context in (CTX_NOT_MOVE,):
        return 0

    # Optional TO_HAND / search: always take 1 good card if max allows
    if min_count == 0 and context == CTX_TO_HAND and max_count >= 1:
        good = sum(1 for s, _ in scored if s >= 70.0)
        return 1 if good or max_count >= 1 else 0

    return max_count


# ---------------------------------------------------------------------------
# Card / board helpers (graceful without obs/deck modules)
# ---------------------------------------------------------------------------
def _preferred_ids() -> Tuple[int, ...]:
    if _deck_mod is not None:
        for attr in ("PREFERRED_BASICS", "preferred_basics", "SETUP_BASICS", "DECK_BASICS"):
            val = getattr(_deck_mod, attr, None)
            if val:
                try:
                    return tuple(int(x) for x in val)
                except Exception:
                    pass
        for fn_name in ("setup_priority_basics", "preferred_basic_ids", "preferred_attackers"):
            fn = getattr(_deck_mod, fn_name, None)
            if callable(fn):
                try:
                    return tuple(int(x) for x in fn())
                except Exception:
                    pass
    return PREFERRED_BASICS_DEFAULT


def _preferred_basic_bonus(card_id: Optional[int]) -> float:
    if card_id is None:
        return 0.0
    prefs = _preferred_ids()
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return 0.0
    if cid in prefs:
        # Earlier in list = higher bonus
        return 12.0 - 0.5 * prefs.index(cid)
    return 0.0


def _attacker_active_bonus(card_id: Optional[int]) -> float:
    """Mild preference for known attacker-ish actives during setup/switch."""
    if card_id is None:
        return 0.0
    # Prefer real attackers as Active; engine pieces for setup lines
    strong = {121, 133, 140, 1071, 112, 678, 96, 150}  # Dragapult, Dusknoir, …
    engine = {119, 131, 235, 120, 132, 677}  # Dreepy, Duskull, Drakloak, …
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return 0.0
    if cid in strong:
        return 12.0
    if cid in engine:
        return 4.0
    return 0.0


def _active_card_id(obs: dict) -> Optional[int]:
    me = _my_player(obs)
    if not me:
        return None
    for p in me.get("active") or []:
        if isinstance(p, dict):
            cid = p.get("id", p.get("cardId"))
            try:
                return int(cid) if cid is not None else None
            except (TypeError, ValueError):
                return None
    return None


def _normalize_role(r: str) -> str:
    """Map deck_knowledge roles (SEARCH_ITEM, …) onto policy buckets."""
    r = (r or "unknown").strip().lower()
    aliases = {
        "search_item": "search",
        "draw_supporter": "supporter",
        "gust_supporter": "boss",
        "gust": "boss",
        "energy_basic": "energy",
        "energy_special": "energy",
        "support_pokemon": "basic",
        "attacker": "attacker",
        "basic": "basic",
        "evolution": "evolution",
        "stadium": "stadium",
        "tool": "tool",
        "other": "unknown",
    }
    return aliases.get(r, r)


def _card_role(card_id: Optional[int]) -> str:
    if card_id is None:
        return "unknown"
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return "unknown"

    if _deck_mod is not None:
        for fn_name in ("role", "role_for", "card_role", "get_role"):
            fn = getattr(_deck_mod, fn_name, None)
            if callable(fn):
                try:
                    r = fn(cid)
                    if r:
                        return _normalize_role(str(r))
                except Exception:
                    pass
        # CARD_ROLES dict
        roles = getattr(_deck_mod, "CARD_ROLES", None)
        if isinstance(roles, dict) and cid in roles:
            return _normalize_role(str(roles[cid]))

    if cid in _BOSS_ORDERS:
        return "boss"
    if cid in _SEARCH_ITEMS:
        return "search"
    if cid in _SUPPORTERS:
        return "supporter"
    if cid in _STADIUMS:
        return "stadium"
    if cid in _TOOLS:
        return "tool"
    if cid in _ENERGY_IDS or cid <= 19:
        return "energy"
    if cid in (332, 272, 44, 56):  # Dhelmise, Clefairy, Ursaluna, Flutter
        return "attacker"
    if cid in _preferred_ids() or cid in PREFERRED_BASICS_DEFAULT:
        return "basic"
    if cid in (273, 66, 94):  # Banette, Dudunsparce, Sinistcha
        return "evolution"
    return "unknown"


def _resolve_play_card_id(obs: dict, option_dict: dict) -> Optional[int]:
    """PLAY options reference a hand index; resolve to cardId when possible."""
    if option_dict.get("cardId") is not None:
        try:
            return int(option_dict["cardId"])
        except (TypeError, ValueError):
            pass

    hand_index = option_dict.get("index")
    if hand_index is None:
        return None

    me = _my_player(obs)
    if not me:
        return None
    hand = me.get("hand")
    if not hand:
        return None
    try:
        card = hand[int(hand_index)]
    except (IndexError, TypeError, ValueError):
        return None
    if card is None:
        return None
    if isinstance(card, dict):
        cid = card.get("id", card.get("cardId"))
        try:
            return int(cid) if cid is not None else None
        except (TypeError, ValueError):
            return None
    return None


def _option_card_id(obs: dict, option_dict: dict) -> Optional[int]:
    if option_dict.get("cardId") is not None:
        try:
            return int(option_dict["cardId"])
        except (TypeError, ValueError):
            pass

    # Try resolving from area + index via board
    area = option_dict.get("area")
    index = option_dict.get("index")
    player_index = option_dict.get("playerIndex")
    if area is None or index is None:
        # PLAY-style
        return _resolve_play_card_id(obs, option_dict)

    current = (obs or {}).get("current") or {}
    players = current.get("players") or []
    if player_index is None:
        player_index = current.get("yourIndex", 0)
    try:
        player = players[int(player_index)]
    except (IndexError, TypeError, ValueError):
        return None
    if not isinstance(player, dict):
        return None

    try:
        idx = int(index)
    except (TypeError, ValueError):
        return None

    card = None
    if area == AREA_HAND:
        hand = player.get("hand") or []
        if 0 <= idx < len(hand):
            card = hand[idx]
    elif area == AREA_ACTIVE:
        active = player.get("active") or []
        if 0 <= idx < len(active):
            card = active[idx]
    elif area == AREA_BENCH:
        bench = player.get("bench") or []
        if 0 <= idx < len(bench):
            card = bench[idx]
    elif area == 3:  # DISCARD
        discard = player.get("discard") or []
        if 0 <= idx < len(discard):
            card = discard[idx]

    if isinstance(card, dict):
        cid = card.get("id", card.get("cardId"))
        try:
            return int(cid) if cid is not None else None
        except (TypeError, ValueError):
            return None
    return None


def _your_index(obs: dict) -> Optional[int]:
    current = (obs or {}).get("current") or {}
    yi = current.get("yourIndex")
    if yi is not None:
        try:
            return int(yi)
        except (TypeError, ValueError):
            pass
    if _obs_mod is not None:
        fn = getattr(_obs_mod, "your_index", None) or getattr(_obs_mod, "get_your_index", None)
        if callable(fn):
            try:
                return int(fn(obs))
            except Exception:
                pass
    return 0


def _my_player(obs: dict) -> Optional[dict]:
    current = (obs or {}).get("current") or {}
    players = current.get("players") or []
    yi = _your_index(obs)
    if yi is None:
        return None
    try:
        p = players[int(yi)]
        return p if isinstance(p, dict) else None
    except (IndexError, TypeError, ValueError):
        return None


def _opponent_player(obs: dict) -> Optional[dict]:
    current = (obs or {}).get("current") or {}
    players = current.get("players") or []
    yi = _your_index(obs)
    if yi is None:
        return None
    oi = 1 - int(yi)
    try:
        p = players[oi]
        return p if isinstance(p, dict) else None
    except (IndexError, TypeError, ValueError):
        return None


def _opponent_has_bench(obs: dict) -> bool:
    opp = _opponent_player(obs)
    if not opp:
        return False
    bench = opp.get("bench") or []
    return any(p is not None for p in bench)


def _hp_fraction_bonus(option_dict: dict, obs: dict, prefer_high: bool) -> float:
    """Bonus from HP fraction of referenced in-play Pokémon if resolvable."""
    try:
        area = option_dict.get("area")
        index = option_dict.get("index")
        player_index = option_dict.get("playerIndex")
        if area is None or index is None:
            return 0.0
        current = (obs or {}).get("current") or {}
        players = current.get("players") or []
        if player_index is None:
            player_index = current.get("yourIndex", 0)
        player = players[int(player_index)]
        if area == AREA_ACTIVE:
            mon = (player.get("active") or [])[int(index)]
        elif area == AREA_BENCH:
            mon = (player.get("bench") or [])[int(index)]
        else:
            return 0.0
        if not isinstance(mon, dict):
            return 0.0
        hp, max_hp = mon.get("hp"), mon.get("maxHp")
        if hp is None or not max_hp:
            return 0.0
        frac = float(hp) / float(max_hp)
        return 10.0 * frac if prefer_high else 10.0 * (1.0 - frac)
    except Exception:
        return 0.0


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
