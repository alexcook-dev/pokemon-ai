"""Deck-specific knowledge derived from deck.csv + card catalog.

Roles are inferred from card names so any competition-legal deck.csv works.
"""

from __future__ import annotations

import csv
import os
import re
from collections import Counter
from enum import Enum
from typing import Dict, List, Optional, Set

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_HERE)
_DECK_CSV = os.path.join(_PROJECT_ROOT, "deck.csv")
_CATALOG_CSV = os.path.join(_PROJECT_ROOT, "data", "card_id_list.csv")


class CardRole(str, Enum):
    BASIC = "BASIC"
    EVOLUTION = "EVOLUTION"
    ATTACKER = "ATTACKER"
    SUPPORT_POKEMON = "SUPPORT_POKEMON"
    SEARCH_ITEM = "SEARCH_ITEM"
    DRAW_SUPPORTER = "DRAW_SUPPORTER"
    GUST_SUPPORTER = "GUST_SUPPORTER"
    ENERGY_BASIC = "ENERGY_BASIC"
    ENERGY_SPECIAL = "ENERGY_SPECIAL"
    STADIUM = "STADIUM"
    TOOL = "TOOL"
    OTHER = "OTHER"


BASIC = CardRole.BASIC.value
EVOLUTION = CardRole.EVOLUTION.value
ATTACKER = CardRole.ATTACKER.value
SUPPORT_POKEMON = CardRole.SUPPORT_POKEMON.value
SEARCH_ITEM = CardRole.SEARCH_ITEM.value
DRAW_SUPPORTER = CardRole.DRAW_SUPPORTER.value
GUST_SUPPORTER = CardRole.GUST_SUPPORTER.value
ENERGY_BASIC = CardRole.ENERGY_BASIC.value
ENERGY_SPECIAL = CardRole.ENERGY_SPECIAL.value
STADIUM = CardRole.STADIUM.value
TOOL = CardRole.TOOL.value
OTHER = CardRole.OTHER.value


def _load_deck_ids(path: str = _DECK_CSV) -> List[int]:
    ids: List[int] = []
    with open(path, newline="", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                ids.append(int(line))
    return ids


def _load_catalog(path: str = _CATALOG_CSV) -> Dict[int, str]:
    names: Dict[int, str] = {}
    if not os.path.isfile(path):
        return names
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                cid = int(row["card_id"])
            except (KeyError, TypeError, ValueError):
                continue
            names[cid] = (row.get("name") or "").strip()
    return names


DECK: List[int] = _load_deck_ids()
_UNIQUE_IDS: Set[int] = set(DECK)
_ALL_NAMES: Dict[int, str] = _load_catalog()
CARD_NAMES: Dict[int, str] = {i: _ALL_NAMES.get(i, f"#{i}") for i in _UNIQUE_IDS}


def card_name(card_id: int) -> str:
    return CARD_NAMES.get(card_id) or _ALL_NAMES.get(card_id) or f"#{card_id}"


def _infer_role(card_id: int, name: str) -> str:
    n = name.lower().replace("’", "'")

    # Energy
    if re.search(r"basic\s*\{[grwlpfdm]\}\s*energy", n) or n.startswith("basic {") and "energy" in n:
        return ENERGY_BASIC
    if "energy" in n:
        return ENERGY_SPECIAL

    # Trainers by name
    if "boss" in n and "order" in n:
        return GUST_SUPPORTER
    if any(x in n for x in ("prime catcher", "counter catcher")):
        return GUST_SUPPORTER
    if any(
        x in n
        for x in (
            "ultra ball",
            "poké pad",
            "poke pad",
            "buddy-buddy",
            "poffin",
            "pokégear",
            "pokegear",
            "night stretcher",
            "rare candy",
            "mega signal",
            "nest ball",
            "level ball",
            "quick ball",
            "energy search",
            "earthen vessel",
        )
    ):
        return SEARCH_ITEM
    if any(
        x in n
        for x in (
            "determination",
            "naveen",
            "research",
            "professor",
            "iono",
            "arven",
            "crispin",
            "lacey",
            "carmine",
            "premium power",
            "iris",
            "kieran",
        )
    ):
        return DRAW_SUPPORTER
    if any(
        x in n
        for x in (
            "gravity mountain",
            "area zero",
            "battle cage",
            "jamming tower",
            "stadium",
            "artazon",
            "beach",
            "town",
        )
    ) or n.endswith(" mountain") or n.endswith(" tower") or n.endswith(" grounds"):
        # rough stadium heuristics
        if "ball" not in n and "energy" not in n:
            # known stadiums
            if any(x in n for x in ("gravity", "area zero", "battle cage", "jamming", "lively", "festival", "forest", "beach", "city", "tower", "mountain", "cage", "underdepths")):
                return STADIUM

    if any(x in n for x in ("air balloon", "cape", "belt", "helmet", "band", "tool", "balloon")):
        return TOOL

    # Pokemon
    if any(
        x in n
        for x in (
            "lucario",
            "charizard",
            "gardevoir",
            "dragapult",
            "ogerpon",
            "ursaluna",
            "clefairy",
            "dhelmise",
            "flutter mane",
            "hawlucha",
            "kangaskhan",
            "latias",
            "meowth ex",
        )
    ):
        if any(x in n for x in ("riolu", "charmander", "ralts", "dreepy", "kirlia")):
            return BASIC
        return ATTACKER

    if any(x in n for x in ("riolu", "charmander", "ralts", "dreepy", "shuppet", "poltchageist", "dunsparce", "fan rotom")):
        return BASIC

    if any(x in n for x in ("kirlia", "banette", "sinistcha", "dudunsparce", "charmeleon", "drakloak")):
        return EVOLUTION

    if "ex" in n or "mega " in n:
        return ATTACKER

    # Default pokemon-ish
    if name and not any(x in n for x in ("ball", "pad", "switch", "order", "energy", "rod", "hammer")):
        return SUPPORT_POKEMON

    return OTHER


CARD_ROLES: Dict[int, str] = {
    cid: _infer_role(cid, card_name(cid)) for cid in _UNIQUE_IDS
}

# Manual overrides for known stadiums / tools / etc.
_OVERRIDES = {
    1252: STADIUM,  # Gravity Mountain
    1250: STADIUM,  # Area Zero Underdepths
    1264: STADIUM,  # Battle Cage
    1246: STADIUM,  # Jamming Tower
    1256: STADIUM,  # Team Rocket's Watchtower
    1261: STADIUM,  # Forest of Vitality
    1174: TOOL,  # Air Balloon
    1161: TOOL,  # Handheld Fan
    1142: SEARCH_ITEM,  # Fighting Gong
    1079: SEARCH_ITEM,  # Rare Candy
    1145: SEARCH_ITEM,  # Mega Signal
    1088: GUST_SUPPORTER,  # Prime Catcher
    1120: SEARCH_ITEM,  # Crushing Hammer (item disruption)
    1080: SEARCH_ITEM,  # Unfair Stamp
    1087: SEARCH_ITEM,  # Hand Trimmer
    119: BASIC,  # Dreepy
    120: EVOLUTION,  # Drakloak
    121: ATTACKER,  # Dragapult ex
    131: BASIC,  # Duskull
    132: EVOLUTION,  # Dusclops
    133: ATTACKER,  # Dusknoir
    235: BASIC,  # Budew
    112: SUPPORT_POKEMON,  # Munkidori
    1198: DRAW_SUPPORTER,  # Crispin
    1231: DRAW_SUPPORTER,  # Dawn
    20: ENERGY_SPECIAL,  # Rock Fighting Energy
    6: ENERGY_BASIC,
    5: ENERGY_BASIC,
    2: ENERGY_BASIC,
    7: ENERGY_BASIC,
    1: ENERGY_BASIC,
}
for _cid, _role in _OVERRIDES.items():
    if _cid in CARD_ROLES:
        CARD_ROLES[_cid] = _role

DECK_BASICS: Set[int] = {
    cid
    for cid, r in CARD_ROLES.items()
    if r in (BASIC, ATTACKER, SUPPORT_POKEMON)
    and "ex" not in card_name(cid).lower()
    or (r == BASIC)
}
# Basics that are also attackers (ex basics)
for cid, r in CARD_ROLES.items():
    n = card_name(cid).lower()
    if r == ATTACKER and not any(x in n for x in ("mega lucario", "mega charizard", "mega gardevoir", "stage")):
        # treat basic-stage attackers as basics for setup
        if "mega " not in n or "riolu" in n:
            pass
    if r in (BASIC, SUPPORT_POKEMON):
        DECK_BASICS.add(cid)
    # Riolu, Fan Rotom, Hawlucha without mega
    if any(x in n for x in ("riolu", "fan rotom", "hawlucha")) and "mega" not in n:
        DECK_BASICS.add(cid)
        CARD_ROLES[cid] = BASIC if "hawlucha" not in n else ATTACKER

DECK_EVOLUTIONS: Set[int] = {cid for cid, r in CARD_ROLES.items() if r == EVOLUTION}
# Mega evolutions
for cid, r in CARD_ROLES.items():
    if "mega " in card_name(cid).lower() and "ex" in card_name(cid).lower():
        DECK_EVOLUTIONS.add(cid)
        if CARD_ROLES.get(cid) == ATTACKER:
            pass  # keep attacker primary
        else:
            CARD_ROLES[cid] = EVOLUTION

_ENERGY_IDS = {cid for cid, r in CARD_ROLES.items() if r in (ENERGY_BASIC, ENERGY_SPECIAL)}
_SEARCH_IDS = {cid for cid, r in CARD_ROLES.items() if r == SEARCH_ITEM}
_GUST_IDS = {cid for cid, r in CARD_ROLES.items() if r == GUST_SUPPORTER}


def role(card_id: int) -> str:
    return CARD_ROLES.get(card_id, OTHER)


def is_basic_pokemon(card_id: int) -> bool:
    if card_id in DECK_BASICS:
        return True
    r = role(card_id)
    if r in (ENERGY_BASIC, ENERGY_SPECIAL, SEARCH_ITEM, DRAW_SUPPORTER, GUST_SUPPORTER, STADIUM, TOOL, EVOLUTION):
        return False
    n = card_name(card_id).lower()
    if "mega " in n:
        return False
    return r in (BASIC, SUPPORT_POKEMON) or card_id in DECK_BASICS


def is_energy(card_id: int) -> bool:
    return role(card_id) in (ENERGY_BASIC, ENERGY_SPECIAL) or card_id in _ENERGY_IDS


def is_search(card_id: int) -> bool:
    return role(card_id) == SEARCH_ITEM or card_id in _SEARCH_IDS


def is_gust(card_id: int) -> bool:
    return role(card_id) == GUST_SUPPORTER or card_id in _GUST_IDS


def is_draw_supporter(card_id: int) -> bool:
    return role(card_id) == DRAW_SUPPORTER


def preferred_attackers() -> List[int]:
    """Attack priority among our deck Pokémon IDs."""
    scored = []
    for cid in _UNIQUE_IDS:
        n = card_name(cid).lower()
        r = role(cid)
        score = 0
        if "mega lucario" in n:
            score = 100
        elif "lucario" in n:
            score = 90
        elif "ursaluna" in n:
            score = 80
        elif "hawlucha" in n and "mega" not in n:
            score = 70
        elif r == ATTACKER:
            score = 60
        elif r == EVOLUTION:
            score = 40
        if score:
            scored.append((score, cid))
    scored.sort(reverse=True)
    return [c for _, c in scored]


def setup_priority_basics() -> List[int]:
    """Basics to put Active/Bench first."""
    order = []
    # Prefer Riolu for Lucario line
    for cid in _UNIQUE_IDS:
        n = card_name(cid).lower()
        if "riolu" in n:
            order.append(cid)
    for cid in preferred_attackers():
        if is_basic_pokemon(cid) and cid not in order:
            order.append(cid)
    for cid in sorted(DECK_BASICS):
        if cid not in order:
            order.append(cid)
    return order


def summarize_deck() -> str:
    counts = Counter(DECK)
    lines = [f"Deck: {len(DECK)} cards, {len(_UNIQUE_IDS)} unique IDs", "Composition (count × id name [role]):"]
    for cid, c in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"  {c}× {cid} {card_name(cid)} [{role(cid)}]")
    return "\n".join(lines)


# Self-check on import
assert len(DECK) == 60, f"deck.csv must have 60 cards, got {len(DECK)}"
assert _UNIQUE_IDS <= set(CARD_ROLES.keys()) or all(cid in CARD_ROLES for cid in _UNIQUE_IDS)
