"""
Typed option parsing for cabt select["option"] lists.

Usage:
    from agent.options import parse_options, filter_by_type, describe_option
    from agent.options import OPTION_TYPE_NAMES, PLAY, END, ATTACK

    opts = parse_options(obs)                 # list[TypedOption]
    plays = filter_by_type(opts, PLAY, END)
    for o in plays:
        print(describe_option(o))

Option type ints match api.OptionType (cabt engine).
Return values from the agent are *indices into* select["option"]
(i.e. TypedOption.index), length == maxCount.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union

# ---------------------------------------------------------------------------
# OptionType enum values (api.OptionType)
# ---------------------------------------------------------------------------
NUMBER = 0
YES = 1
NO = 2
CARD = 3
TOOL_CARD = 4
ENERGY_CARD = 5
ENERGY = 6
PLAY = 7
ATTACH = 8
EVOLVE = 9
ABILITY = 10
DISCARD = 11
RETREAT = 12
ATTACK = 13
END = 14
SKILL = 15
SPECIAL_CONDITION = 16

OPTION_TYPE_NAMES: Dict[int, str] = {
    NUMBER: "NUMBER",
    YES: "YES",
    NO: "NO",
    CARD: "CARD",
    TOOL_CARD: "TOOL_CARD",
    ENERGY_CARD: "ENERGY_CARD",
    ENERGY: "ENERGY",
    PLAY: "PLAY",
    ATTACH: "ATTACH",
    EVOLVE: "EVOLVE",
    ABILITY: "ABILITY",
    DISCARD: "DISCARD",
    RETREAT: "RETREAT",
    ATTACK: "ATTACK",
    END: "END",
    SKILL: "SKILL",
    SPECIAL_CONDITION: "SPECIAL_CONDITION",
}

# AreaType names (for describe_option)
AREA_TYPE_NAMES: Dict[int, str] = {
    1: "DECK",
    2: "HAND",
    3: "DISCARD",
    4: "ACTIVE",
    5: "BENCH",
    6: "PRIZE",
    7: "STADIUM",
    8: "ENERGY",
    9: "TOOL",
    10: "PRE_EVOLUTION",
    11: "PLAYER",
    12: "LOOKING",
}

SPECIAL_CONDITION_NAMES: Dict[int, str] = {
    0: "POISON",
    1: "BURN",
    2: "SLEEP",
    3: "PARALYZE",
    4: "CONFUSE",
}


@dataclass
class TypedOption:
    """One legal choice from select["option"], with its list index.

    `index` is what the agent returns (position in the option list).
    Field meanings depend on `type` (see cabt api.OptionType docs).
    """

    index: int
    type: int
    type_name: str
    raw: dict
    # Shared / common fields
    number: Optional[int] = None
    area: Optional[int] = None
    slot_index: Optional[int] = None  # raw Option.index (hand / area slot)
    player_index: Optional[int] = None
    tool_index: Optional[int] = None
    energy_index: Optional[int] = None
    count: Optional[int] = None
    in_play_area: Optional[int] = None
    in_play_index: Optional[int] = None
    attack_id: Optional[int] = None
    card_id: Optional[int] = None
    serial: Optional[int] = None
    special_condition_type: Optional[int] = None
    # Any extra keys from the raw option not mapped above
    extras: Dict[str, Any] = field(default_factory=dict)

    @property
    def option_index(self) -> Optional[int]:
        """Alias for the raw Option.index field (area/hand slot), not list position."""
        return self.slot_index

    @property
    def is_end(self) -> bool:
        return self.type == END

    @property
    def is_play(self) -> bool:
        return self.type == PLAY

    @property
    def is_attack(self) -> bool:
        return self.type == ATTACK


_KNOWN_RAW_KEYS = frozenset(
    {
        "type",
        "number",
        "area",
        "index",
        "playerIndex",
        "toolIndex",
        "energyIndex",
        "count",
        "inPlayArea",
        "inPlayIndex",
        "attackId",
        "cardId",
        "serial",
        "specialConditionType",
    }
)


def _opt_int(raw: dict, key: str) -> Optional[int]:
    if key not in raw or raw[key] is None:
        return None
    try:
        return int(raw[key])
    except (TypeError, ValueError):
        return None


def parse_option(raw: dict, index: int) -> TypedOption:
    """Parse a single option dict into TypedOption."""
    if not isinstance(raw, dict):
        raw = {"type": -1, "_invalid": raw}

    opt_type = _opt_int(raw, "type")
    if opt_type is None:
        opt_type = -1
    type_name = OPTION_TYPE_NAMES.get(opt_type, f"UNKNOWN({opt_type})")

    extras = {k: v for k, v in raw.items() if k not in _KNOWN_RAW_KEYS}

    return TypedOption(
        index=index,
        type=opt_type,
        type_name=type_name,
        raw=raw,
        number=_opt_int(raw, "number"),
        area=_opt_int(raw, "area"),
        slot_index=_opt_int(raw, "index"),
        player_index=_opt_int(raw, "playerIndex"),
        tool_index=_opt_int(raw, "toolIndex"),
        energy_index=_opt_int(raw, "energyIndex"),
        count=_opt_int(raw, "count"),
        in_play_area=_opt_int(raw, "inPlayArea"),
        in_play_index=_opt_int(raw, "inPlayIndex"),
        attack_id=_opt_int(raw, "attackId"),
        card_id=_opt_int(raw, "cardId"),
        serial=_opt_int(raw, "serial"),
        special_condition_type=_opt_int(raw, "specialConditionType"),
        extras=extras,
    )


def parse_options(obs: Union[dict, None]) -> List[TypedOption]:
    """Parse all options from a full observation or a select dict.

    Accepts:
      - full obs with obs["select"]["option"]
      - select dict with ["option"]
      - None / missing select → empty list
    """
    if not obs:
        return []

    select = obs
    if isinstance(obs, dict) and "select" in obs:
        select = obs.get("select")

    if not isinstance(select, dict):
        return []

    options_raw = select.get("option") or []
    if not isinstance(options_raw, list):
        return []

    out: List[TypedOption] = []
    for i, raw in enumerate(options_raw):
        if isinstance(raw, dict):
            out.append(parse_option(raw, i))
        else:
            out.append(
                TypedOption(
                    index=i,
                    type=-1,
                    type_name="UNKNOWN",
                    raw={"_invalid": raw},
                )
            )
    return out


def filter_by_type(
    options: Sequence[TypedOption],
    *types: int,
) -> List[TypedOption]:
    """Return options whose type is in *types (order preserved)."""
    if not types:
        return list(options)
    wanted = set(types)
    return [o for o in options if o.type in wanted]


def filter_out_types(
    options: Sequence[TypedOption],
    *types: int,
) -> List[TypedOption]:
    """Return options whose type is not in *types."""
    if not types:
        return list(options)
    banned = set(types)
    return [o for o in options if o.type not in banned]


def _area_name(area: Optional[int]) -> str:
    if area is None:
        return "?"
    return AREA_TYPE_NAMES.get(area, str(area))


def describe_option(opt: TypedOption) -> str:
    """Short human-readable string for logging."""
    t = opt.type
    name = opt.type_name
    prefix = f"[{opt.index}] {name}"

    if t == NUMBER:
        return f"{prefix} n={opt.number}"
    if t in (YES, NO, RETREAT, END):
        return prefix
    if t == PLAY:
        return f"{prefix} hand[{opt.slot_index}]"
    if t == ATTACH:
        return (
            f"{prefix} from {_area_name(opt.area)}[{opt.slot_index}] "
            f"-> {_area_name(opt.in_play_area)}[{opt.in_play_index}]"
        )
    if t == EVOLVE:
        return (
            f"{prefix} {_area_name(opt.area)}[{opt.slot_index}] "
            f"-> {_area_name(opt.in_play_area)}[{opt.in_play_index}]"
        )
    if t == ABILITY:
        return f"{prefix} {_area_name(opt.area)}[{opt.slot_index}]"
    if t == DISCARD:
        return f"{prefix} {_area_name(opt.area)}[{opt.slot_index}]"
    if t == ATTACK:
        return f"{prefix} attackId={opt.attack_id}"
    if t == CARD:
        who = f" p{opt.player_index}" if opt.player_index is not None else ""
        return f"{prefix} {_area_name(opt.area)}[{opt.slot_index}]{who}"
    if t == TOOL_CARD:
        return (
            f"{prefix} {_area_name(opt.area)}[{opt.slot_index}] "
            f"tool[{opt.tool_index}] p{opt.player_index}"
        )
    if t in (ENERGY_CARD, ENERGY):
        return (
            f"{prefix} {_area_name(opt.area)}[{opt.slot_index}] "
            f"energy[{opt.energy_index}]"
            + (f" count={opt.count}" if opt.count is not None else "")
            + (f" p{opt.player_index}" if opt.player_index is not None else "")
        )
    if t == SKILL:
        return f"{prefix} cardId={opt.card_id} serial={opt.serial}"
    if t == SPECIAL_CONDITION:
        sc = SPECIAL_CONDITION_NAMES.get(
            opt.special_condition_type or -1,
            str(opt.special_condition_type),
        )
        return f"{prefix} {sc}"

    # Fallback: dump known non-null fields
    bits = [prefix]
    for label, val in (
        ("area", opt.area),
        ("idx", opt.slot_index),
        ("n", opt.number),
        ("atk", opt.attack_id),
        ("card", opt.card_id),
    ):
        if val is not None:
            bits.append(f"{label}={val}")
    return " ".join(bits)


def options_by_type(
    options: Sequence[TypedOption],
) -> Dict[int, List[TypedOption]]:
    """Group options by type int."""
    grouped: Dict[int, List[TypedOption]] = {}
    for o in options:
        grouped.setdefault(o.type, []).append(o)
    return grouped


if __name__ == "__main__":
    fake_obs = {
        "select": {
            "type": 0,
            "context": 0,
            "minCount": 1,
            "maxCount": 1,
            "option": [
                {"type": 7, "index": 0},
                {"type": 7, "index": 2},
                {
                    "type": 8,
                    "area": 2,
                    "index": 4,
                    "inPlayArea": 4,
                    "inPlayIndex": 0,
                },
                {"type": 13, "attackId": 42},
                {"type": 14},
            ],
        }
    }

    opts = parse_options(fake_obs)
    print(f"parsed {len(opts)} options:")
    for o in opts:
        print(" ", describe_option(o))

    plays_and_end = filter_by_type(opts, PLAY, END)
    print("PLAY/END only:")
    for o in plays_and_end:
        print(" ", o.index, o.type_name, o.slot_index)

    # Exercise obs parse when package root is on sys.path
    import sys
    from pathlib import Path

    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from agent.obs import parse_observation

    parsed = parse_observation(
        {
            **fake_obs,
            "logs": [],
            "current": {
                "turn": 1,
                "yourIndex": 0,
                "energyAttached": False,
                "supporterPlayed": False,
                "stadiumPlayed": False,
                "retreated": False,
                "players": [
                    {
                        "active": [],
                        "bench": [],
                        "hand": [{"id": 5}],
                        "handCount": 1,
                        "discard": [],
                        "prize": [],
                        "deckCount": 59,
                    },
                    {
                        "active": [],
                        "bench": [],
                        "hand": None,
                        "handCount": 7,
                        "discard": [],
                        "prize": [],
                        "deckCount": 53,
                    },
                ],
            },
        }
    )
    print(
        f"obs: turn={parsed.turn} me_hand={parsed.me.hand_count if parsed.me else None} "
        f"select max={parsed.max_count}"
    )
