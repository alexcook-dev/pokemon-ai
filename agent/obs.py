"""
Observation helpers for the cabt (Pokémon TCG) Kaggle agent.

Usage:
    from agent.obs import load_card_catalog, parse_observation, get_card_id

    catalog = load_card_catalog()           # id -> name
    parsed = parse_observation(obs)        # dataclass summary of board + select
    if parsed.select is None:
        # deck-selection phase
        ...
    else:
        # use parsed.me / parsed.opp / parsed flags for policy
        card_id = get_card_id(parsed.me.active)

No third-party deps; works offline with data/card_id_list.csv.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Default catalog next to the project root: <repo>/data/card_id_list.csv
_DEFAULT_CATALOG = Path(__file__).resolve().parent.parent / "data" / "card_id_list.csv"

# Module-level cache so repeated loads are cheap.
_CATALOG_CACHE: Optional[Dict[int, str]] = None
_CATALOG_PATH: Optional[Path] = None


def load_card_catalog(path: Optional[Union[str, Path]] = None) -> Dict[int, str]:
    """Load card_id -> name mapping from CSV.

    CSV columns: card_id,name,expansion,collection_no
    Results are cached per path.
    """
    global _CATALOG_CACHE, _CATALOG_PATH
    catalog_path = Path(path) if path is not None else _DEFAULT_CATALOG
    if _CATALOG_CACHE is not None and _CATALOG_PATH == catalog_path:
        return _CATALOG_CACHE

    mapping: Dict[int, str] = {}
    if catalog_path.exists():
        with catalog_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    cid = int(row["card_id"])
                except (KeyError, TypeError, ValueError):
                    continue
                name = (row.get("name") or "").strip()
                mapping[cid] = name
    _CATALOG_CACHE = mapping
    _CATALOG_PATH = catalog_path
    return mapping


def get_card_id(obj: Any) -> Optional[int]:
    """Safely extract a card id from a card/pokemon dict (or nested wrappers).

    Accepts:
      - int
      - dict with "id" or "cardId"
      - list/tuple of length 1 containing one of the above
      - dict with nested "card" / "pokemon" fields
    Returns None if missing/unknown.
    """
    if obj is None:
        return None
    if isinstance(obj, bool):
        return None
    if isinstance(obj, int):
        return obj
    if isinstance(obj, (list, tuple)):
        if not obj:
            return None
        # active is often a 0-or-1 length list
        return get_card_id(obj[0])
    if isinstance(obj, dict):
        for key in ("id", "cardId", "card_id"):
            if key in obj and obj[key] is not None:
                try:
                    return int(obj[key])
                except (TypeError, ValueError):
                    pass
        for nest in ("card", "pokemon", "data"):
            if nest in obj and obj[nest] is not None:
                nested = get_card_id(obj[nest])
                if nested is not None:
                    return nested
    return None


def get_card_name(
    obj: Any,
    catalog: Optional[Dict[int, str]] = None,
) -> Optional[str]:
    """Name from the object itself, else catalog lookup by id."""
    if isinstance(obj, dict):
        name = obj.get("name")
        if isinstance(name, str) and name:
            return name
    cid = get_card_id(obj)
    if cid is None:
        return None
    if catalog is None:
        catalog = load_card_catalog()
    return catalog.get(cid)


def _first_or_none(seq: Any) -> Any:
    if not seq:
        return None
    if isinstance(seq, (list, tuple)):
        return seq[0] if seq else None
    return seq


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


@dataclass
class PokemonSummary:
    """Lightweight view of a Pokémon in play (active/bench)."""

    raw: Any
    card_id: Optional[int] = None
    serial: Optional[int] = None
    name: Optional[str] = None
    hp: Optional[int] = None
    max_hp: Optional[int] = None
    appear_this_turn: bool = False
    energies: List[Any] = field(default_factory=list)
    energy_cards: List[Any] = field(default_factory=list)
    tools: List[Any] = field(default_factory=list)
    pre_evolution: List[Any] = field(default_factory=list)

    @property
    def energy_count(self) -> int:
        return len(self.energies) if self.energies is not None else 0


@dataclass
class PlayerSummary:
    """Per-player board summary used by policy."""

    index: int
    active: Optional[PokemonSummary]
    bench: List[PokemonSummary]
    hand: Optional[List[Any]]  # None when hidden (opponent)
    hand_count: int
    discard: List[Any]
    prize: List[Any]
    prize_count: int
    deck_count: int
    bench_max: int = 5
    poisoned: bool = False
    burned: bool = False
    asleep: bool = False
    paralyzed: bool = False
    confused: bool = False
    raw: Any = None

    @property
    def has_active(self) -> bool:
        return self.active is not None

    @property
    def bench_count(self) -> int:
        return len(self.bench)


@dataclass
class ParsedObservation:
    """Parsed cabt observation for agent decision-making."""

    raw: dict
    select: Optional[dict]
    select_type: Optional[int]
    select_context: Optional[int]
    min_count: int
    max_count: int
    your_index: Optional[int]
    me: Optional[PlayerSummary]
    opp: Optional[PlayerSummary]
    energy_attached: bool
    supporter_played: bool
    stadium_played: bool
    retreated: bool
    turn: int
    turn_action_count: int = 0
    first_player: int = -1
    result: int = -1
    stadium: List[Any] = field(default_factory=list)
    looking: Optional[List[Any]] = None
    logs: List[Any] = field(default_factory=list)
    current: Optional[dict] = None
    remain_damage_counter: int = 0
    remain_energy_cost: int = 0
    context_card: Any = None
    effect: Any = None
    select_deck: Optional[List[Any]] = None

    @property
    def is_deck_select(self) -> bool:
        """True during the initial deck-selection phase (select is None)."""
        return self.select is None


def _summarize_pokemon(raw: Any, catalog: Optional[Dict[int, str]] = None) -> Optional[PokemonSummary]:
    if raw is None:
        return None
    if isinstance(raw, list):
        if not raw:
            return None
        raw = raw[0]
        if raw is None:
            return None
    if not isinstance(raw, dict):
        # Face-down / unknown; still record something if we got an int id
        cid = get_card_id(raw)
        return PokemonSummary(raw=raw, card_id=cid)

    cid = get_card_id(raw)
    name = raw.get("name") if isinstance(raw.get("name"), str) else None
    if name is None and catalog is not None and cid is not None:
        name = catalog.get(cid)

    return PokemonSummary(
        raw=raw,
        card_id=cid,
        serial=raw.get("serial"),
        name=name,
        hp=raw.get("hp"),
        max_hp=raw.get("maxHp"),
        appear_this_turn=bool(raw.get("appearThisTurn", False)),
        energies=_as_list(raw.get("energies")),
        energy_cards=_as_list(raw.get("energyCards")),
        tools=_as_list(raw.get("tools")),
        pre_evolution=_as_list(raw.get("preEvolution")),
    )


def _summarize_player(
    player: Any,
    index: int,
    catalog: Optional[Dict[int, str]] = None,
) -> PlayerSummary:
    if not isinstance(player, dict):
        return PlayerSummary(
            index=index,
            active=None,
            bench=[],
            hand=None,
            hand_count=0,
            discard=[],
            prize=[],
            prize_count=0,
            deck_count=0,
            raw=player,
        )

    active_list = player.get("active") or []
    active = _summarize_pokemon(_first_or_none(active_list), catalog)

    bench_raw = player.get("bench") or []
    bench: List[PokemonSummary] = []
    for p in bench_raw:
        s = _summarize_pokemon(p, catalog)
        if s is not None:
            bench.append(s)

    hand = player.get("hand")  # may be None for opponent
    if hand is not None and not isinstance(hand, list):
        hand = list(hand)

    prize = _as_list(player.get("prize"))
    hand_count = player.get("handCount")
    if hand_count is None:
        hand_count = len(hand) if hand is not None else 0

    return PlayerSummary(
        index=index,
        active=active,
        bench=bench,
        hand=hand,
        hand_count=int(hand_count),
        discard=_as_list(player.get("discard")),
        prize=prize,
        prize_count=len(prize),
        deck_count=int(player.get("deckCount") or 0),
        bench_max=int(player.get("benchMax") or 5),
        poisoned=bool(player.get("poisoned", False)),
        burned=bool(player.get("burned", False)),
        asleep=bool(player.get("asleep", False)),
        paralyzed=bool(player.get("paralyzed", False)),
        confused=bool(player.get("confused", False)),
        raw=player,
    )


def get_your_index(obs: dict) -> Optional[int]:
    """Return current["yourIndex"] from a raw observation, or None."""
    if not isinstance(obs, dict):
        return None
    current = obs.get("current")
    if not isinstance(current, dict):
        return None
    yi = current.get("yourIndex")
    if yi is None:
        return None
    try:
        return int(yi)
    except (TypeError, ValueError):
        return None


def parse_observation(
    obs: dict,
    catalog: Optional[Dict[int, str]] = None,
) -> ParsedObservation:
    """Parse a raw cabt observation dict into a structured summary.

    When select is None, this is the deck-selection phase (current may also be None).
    """
    if not isinstance(obs, dict):
        raise TypeError(f"obs must be a dict, got {type(obs)!r}")

    select = obs.get("select")
    current = obs.get("current")
    logs = obs.get("logs") or []

    select_type = None
    select_context = None
    min_count = 0
    max_count = 0
    remain_damage_counter = 0
    remain_energy_cost = 0
    context_card = None
    effect = None
    select_deck = None

    if isinstance(select, dict):
        select_type = select.get("type")
        select_context = select.get("context")
        min_count = int(select.get("minCount") or 0)
        max_count = int(select.get("maxCount") or 0)
        remain_damage_counter = int(select.get("remainDamageCounter") or 0)
        remain_energy_cost = int(select.get("remainEnergyCost") or 0)
        context_card = select.get("contextCard")
        effect = select.get("effect")
        select_deck = select.get("deck")

    your_index: Optional[int] = None
    energy_attached = False
    supporter_played = False
    stadium_played = False
    retreated = False
    turn = 0
    turn_action_count = 0
    first_player = -1
    result = -1
    stadium: List[Any] = []
    looking = None
    me: Optional[PlayerSummary] = None
    opp: Optional[PlayerSummary] = None

    if isinstance(current, dict):
        your_index = current.get("yourIndex")
        if your_index is not None:
            try:
                your_index = int(your_index)
            except (TypeError, ValueError):
                your_index = None
        energy_attached = bool(current.get("energyAttached", False))
        supporter_played = bool(current.get("supporterPlayed", False))
        stadium_played = bool(current.get("stadiumPlayed", False))
        retreated = bool(current.get("retreated", False))
        turn = int(current.get("turn") or 0)
        turn_action_count = int(current.get("turnActionCount") or 0)
        first_player = int(current.get("firstPlayer") if current.get("firstPlayer") is not None else -1)
        result = int(current.get("result") if current.get("result") is not None else -1)
        stadium = _as_list(current.get("stadium"))
        looking = current.get("looking")

        players = current.get("players") or []
        if your_index is not None and isinstance(players, list) and len(players) >= 2:
            me = _summarize_player(players[your_index], your_index, catalog)
            opp_idx = 1 - your_index
            opp = _summarize_player(players[opp_idx], opp_idx, catalog)
        elif isinstance(players, list):
            # Fallback: index 0 = me, 1 = opp when yourIndex missing
            if len(players) >= 1:
                me = _summarize_player(players[0], 0, catalog)
            if len(players) >= 2:
                opp = _summarize_player(players[1], 1, catalog)

    return ParsedObservation(
        raw=obs,
        select=select if isinstance(select, dict) else None,
        select_type=select_type if select_type is None or isinstance(select_type, int) else int(select_type),
        select_context=select_context
        if select_context is None or isinstance(select_context, int)
        else int(select_context),
        min_count=min_count,
        max_count=max_count,
        your_index=your_index,
        me=me,
        opp=opp,
        energy_attached=energy_attached,
        supporter_played=supporter_played,
        stadium_played=stadium_played,
        retreated=retreated,
        turn=turn,
        turn_action_count=turn_action_count,
        first_player=first_player,
        result=result,
        stadium=stadium,
        looking=looking,
        logs=list(logs) if logs else [],
        current=current if isinstance(current, dict) else None,
        remain_damage_counter=remain_damage_counter,
        remain_energy_cost=remain_energy_cost,
        context_card=context_card,
        effect=effect,
        select_deck=select_deck,
    )


def describe_player(player: Optional[PlayerSummary], label: str = "player") -> str:
    """Short one-line summary for logging."""
    if player is None:
        return f"{label}=?"
    act = player.active
    if act is None:
        act_s = "none"
    else:
        act_s = f"{act.name or act.card_id} hp={act.hp}/{act.max_hp} e={act.energy_count}"
    return (
        f"{label}[p{player.index}] active={act_s} "
        f"bench={player.bench_count} hand={player.hand_count} "
        f"prize={player.prize_count} deck={player.deck_count}"
    )


if __name__ == "__main__":
    # Fake MAIN select with PLAY / END, plus a minimal board state.
    fake_obs = {
        "logs": [],
        "select": {
            "type": 0,  # MAIN
            "context": 0,  # MAIN
            "minCount": 1,
            "maxCount": 1,
            "remainDamageCounter": 0,
            "remainEnergyCost": 0,
            "option": [
                {"type": 7, "index": 0},  # PLAY hand[0]
                {"type": 7, "index": 2},  # PLAY hand[2]
                {"type": 14},  # END
            ],
            "deck": None,
            "contextCard": None,
            "effect": None,
        },
        "current": {
            "turn": 3,
            "turnActionCount": 1,
            "yourIndex": 0,
            "firstPlayer": 0,
            "supporterPlayed": False,
            "stadiumPlayed": False,
            "energyAttached": False,
            "retreated": False,
            "result": -1,
            "stadium": [],
            "looking": None,
            "players": [
                {
                    "active": [
                        {
                            "id": 331,
                            "serial": 1,
                            "hp": 70,
                            "maxHp": 70,
                            "appearThisTurn": False,
                            "energies": [5],
                            "energyCards": [{"id": 5, "serial": 10, "playerIndex": 0}],
                            "tools": [],
                            "preEvolution": [],
                        }
                    ],
                    "bench": [],
                    "benchMax": 5,
                    "deckCount": 47,
                    "discard": [],
                    "prize": [None, None, None, None, None, None],
                    "handCount": 5,
                    "hand": [
                        {"id": 5, "serial": 11, "playerIndex": 0},
                        {"id": 554, "serial": 12, "playerIndex": 0},
                        {"id": 585, "serial": 13, "playerIndex": 0},
                    ],
                    "poisoned": False,
                    "burned": False,
                    "asleep": False,
                    "paralyzed": False,
                    "confused": False,
                },
                {
                    "active": [
                        {
                            "id": 408,
                            "serial": 50,
                            "hp": 90,
                            "maxHp": 120,
                            "appearThisTurn": False,
                            "energies": [],
                            "energyCards": [],
                            "tools": [],
                            "preEvolution": [],
                        }
                    ],
                    "bench": [],
                    "benchMax": 5,
                    "deckCount": 48,
                    "discard": [],
                    "prize": [None, None, None, None, None, None],
                    "handCount": 6,
                    "hand": None,
                    "poisoned": False,
                    "burned": False,
                    "asleep": False,
                    "paralyzed": False,
                    "confused": False,
                },
            ],
        },
    }

    catalog = load_card_catalog()
    print(f"catalog entries: {len(catalog)}")
    parsed = parse_observation(fake_obs, catalog=catalog)
    print(
        f"turn={parsed.turn} your_index={parsed.your_index} "
        f"select_type={parsed.select_type} min/max={parsed.min_count}/{parsed.max_count}"
    )
    print(
        f"flags: energy_attached={parsed.energy_attached} "
        f"supporter={parsed.supporter_played} stadium={parsed.stadium_played} "
        f"retreated={parsed.retreated}"
    )
    print(describe_player(parsed.me, "me"))
    print(describe_player(parsed.opp, "opp"))
    if parsed.me and parsed.me.active:
        print(
            "active id/name:",
            get_card_id(parsed.me.active.raw),
            get_card_name(parsed.me.active.raw, catalog),
        )
    print("options raw:", parsed.select and parsed.select.get("option"))
