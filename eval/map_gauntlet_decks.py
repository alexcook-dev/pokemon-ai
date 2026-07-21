#!/usr/bin/env python3
"""Map the 7 tournament-gauntlet decklists to competition card IDs.

Mapping order per card (user standing rule 2026-07-20):
  1. exact (name, expansion, collection_no) match
  2. same-name reprint (any printing in pool)
  3. MISSING -> fill slot with +1 basic energy of the deck's primary type
     (never a stand-in trainer)

Writes deck_t<N>-<slug>.csv and prints a full mapping report.
"""
from __future__ import annotations

import csv
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# MEE basic-energy prints map to SVE basics (established: MEE 1->SVE 1, etc.)
MEE_TO_SVE = {"1": "Basic {G} Energy", "2": "Basic {R} Energy", "3": "Basic {W} Energy",
              "4": "Basic {L} Energy", "5": "Basic {P} Energy", "6": "Basic {F} Energy",
              "7": "Basic {D} Energy", "8": "Basic {M} Energy"}

DECKS = {
    "t1-mega-lopunny-dudunsparce": {
        "primary_energy": "Basic {P} Energy",  # colorless attackers; Psychic per Abra/Psyduck... see note
        "cards": [
            (3, "Buneary", "PFL", "83"), (3, "Mega Lopunny ex", "PFL", "84"),
            (2, "Dunsparce", "TEF", "128"), (2, "Dunsparce", "JTG", "120"),
            (3, "Dudunsparce", "TEF", "129"), (1, "Dudunsparce ex", "JTG", "121"),
            (1, "Fan Rotom", "SCR", "118"), (1, "Psyduck", "ASC", "39"), (1, "Abra", "TWM", "80"),
            (4, "Lillie's Determination", "MEG", "119"), (4, "Hilda", "WHT", "84"),
            (4, "Wally's Compassion", "MEG", "132"), (3, "Boss's Orders", "MEG", "114"),
            (4, "Pokégear 3.0", "SVI", "186"), (4, "Ultra Ball", "MEG", "131"),
            (4, "Poké Pad", "POR", "81"), (3, "Buddy-Buddy Poffin", "TEF", "144"),
            (2, "Air Balloon", "ASC", "181"), (3, "Battle Cage", "PFL", "85"),
            (4, "Mist Energy", "TEF", "161"), (3, "Spiky Energy", "JTG", "159"),
            (1, "Enriching Energy", "SSP", "191"),
        ],
    },
    "t2-mega-lucario": {
        "primary_energy": "Basic {F} Energy",
        "cards": [
            (3, "Riolu", "MEG", "76"), (3, "Mega Lucario ex", "MEG", "77"),
            (2, "Makuhita", "MEG", "72"), (2, "Hariyama", "MEG", "73"),
            (2, "Solrock", "MEG", "75"), (2, "Lunatone", "MEG", "74"), (1, "Meowth ex", "POR", "62"),
            (4, "Lillie's Determination", "MEG", "119"), (2, "Carmine", "TWM", "145"),
            (2, "Boss's Orders", "MEG", "114"), (2, "Judge", "POR", "76"),
            (1, "Tarragon", "POR", "85"), (1, "Black Belt's Training", "JTG", "143"),
            (1, "Team Rocket's Petrel", "DRI", "176"), (1, "Wally's Compassion", "MEG", "132"),
            (4, "Fighting Gong", "MEG", "116"), (4, "Premium Power Pro", "MEG", "124"),
            (3, "Poké Pad", "POR", "81"), (3, "Ultra Ball", "MEG", "131"),
            (1, "Mega Signal", "MEG", "121"), (1, "Switch", "MEG", "130"),
            (1, "Secret Box", "TWM", "163"), (1, "Air Balloon", "ASC", "181"),
            (2, "Gravity Mountain", "SSP", "177"),
            (9, "Fighting Energy", "MEE", "6"), (2, "Rocky Fighting Energy", "POR", "87"),
        ],
    },
    "t3-mega-kangaskhan-box": {
        "primary_energy": "Basic {G} Energy",
        "cards": [
            (4, "Meowth ex", "POR", "62"), (4, "Mega Kangaskhan ex", "MEG", "104"),
            (3, "Teal Mask Ogerpon ex", "TWM", "25"), (2, "Latias ex", "SSP", "76"),
            (2, "Raging Bolt ex", "TEF", "123"), (1, "Wellspring Mask Ogerpon ex", "TWM", "64"),
            (1, "Chien-Pao", "SSP", "56"), (1, "Iron Leaves ex", "TEF", "25"),
            (1, "Lillie's Clefairy ex", "JTG", "56"), (1, "Fezandipiti ex", "ASC", "142"),
            (4, "Crispin", "SCR", "133"), (2, "Boss's Orders", "MEG", "114"),
            (1, "Cyrano", "SSP", "170"), (1, "Lillie's Determination", "MEG", "119"),
            (1, "Ciphermaniac's Codebreaking", "TEF", "145"), (4, "Ultra Ball", "MEG", "131"),
            (4, "Energy Switch", "MEG", "115"), (2, "Glass Trumpet", "SCR", "135"),
            (1, "Unfair Stamp", "TWM", "165"), (1, "Night Stretcher", "ASC", "196"),
            (3, "Area Zero Underdepths", "SCR", "131"),
            (8, "Grass Energy", "MEE", "1"), (3, "Lightning Energy", "MEE", "4"),
            (3, "Fighting Energy", "MEE", "6"), (1, "Psychic Energy", "MEE", "5"),
            (1, "Water Energy", "MEE", "3"),
        ],
    },
    "t4-team-rockets-mewtwo": {
        "primary_energy": "Basic {G} Energy",
        "cards": [
            (4, "Team Rocket's Tarountula", "DRI", "19"), (4, "Team Rocket's Spidops", "DRI", "20"),
            (2, "Team Rocket's Mewtwo ex", "DRI", "81"), (2, "Team Rocket's Articuno", "DRI", "51"),
            (1, "Team Rocket's Wobbuffet", "DRI", "82"), (1, "Team Rocket's Kangaskhan ex", "ASC", "162"),
            (1, "Team Rocket's Mimikyu", "DRI", "87"), (1, "Lillie's Clefairy ex", "JTG", "56"),
            (4, "Team Rocket's Giovanni", "DRI", "174"), (4, "Lillie's Determination", "MEG", "119"),
            (3, "Team Rocket's Proton", "DRI", "177"), (3, "Team Rocket's Ariana", "DRI", "171"),
            (4, "Team Rocket's Transceiver", "DRI", "178"), (4, "Ultra Ball", "MEG", "131"),
            (1, "Bug Catching Set", "TWM", "143"), (1, "Night Stretcher", "ASC", "196"),
            (1, "Sacred Ash", "DRI", "168"), (1, "Energy Switch", "MEG", "115"),
            (1, "Secret Box", "TWM", "163"), (2, "Lucky Helmet", "TWM", "158"),
            (2, "Handheld Fan", "TWM", "150"), (2, "Team Rocket's Factory", "DRI", "173"),
            (6, "Grass Energy", "MEE", "1"), (4, "Team Rocket's Energy", "DRI", "182"),
            (1, "Psychic Energy", "MEE", "5"),
        ],
    },
    "t5-rillaboom-dipplin": {
        "primary_energy": "Basic {G} Energy",
        "cards": [
            (4, "Grookey", "TWM", "14"), (4, "Thwackey", "TWM", "15"), (1, "Rillaboom", "TWM", "16"),
            (3, "Applin", "TWM", "17"), (1, "Applin", "TWM", "126"), (4, "Dipplin", "TWM", "18"),
            (1, "Goldeen", "TWM", "44"), (1, "Seaking", "PRE", "21"),
            (1, "Rellor", "TEF", "23"), (1, "Rabsca", "TEF", "24"), (1, "Shaymin", "DRI", "10"),
            (4, "Lillie's Determination", "MEG", "119"), (2, "Boss's Orders", "MEG", "114"),
            (2, "Kieran", "TWM", "154"), (1, "Dawn", "PFL", "87"), (1, "Lana's Aid", "TWM", "155"),
            (1, "Black Belt's Training", "JTG", "143"), (4, "Poké Pad", "POR", "81"),
            (4, "Buddy-Buddy Poffin", "TEF", "144"), (3, "Bug Catching Set", "TWM", "143"),
            (1, "Secret Box", "TWM", "163"), (1, "Switch", "MEG", "130"),
            (1, "Night Stretcher", "ASC", "196"), (1, "Tool Scrapper", "ASC", "212"),
            (2, "Brave Bangle", "WHT", "80"), (1, "Air Balloon", "ASC", "181"),
            (4, "Festival Grounds", "TWM", "149"),
            (4, "Grass Energy", "MEE", "1"), (1, "Growing Grass Energy", "POR", "86"),
        ],
    },
    "t6-alakazam-a": {
        "primary_energy": "Basic {P} Energy",
        "cards": [
            (4, "Abra", "MEG", "54"), (4, "Kadabra", "MEG", "55"), (3, "Alakazam", "MEG", "56"),
            (3, "Dunsparce", "JTG", "120"), (3, "Dudunsparce", "TEF", "129"),
            (1, "Fezandipiti ex", "ASC", "142"), (1, "Genesect", "SFA", "40"),
            (1, "Shaymin", "DRI", "10"), (1, "Dedenne", "SSP", "87"),
            (4, "Dawn", "PFL", "87"), (4, "Hilda", "WHT", "84"), (3, "Boss's Orders", "MEG", "114"),
            (1, "Lana's Aid", "TWM", "155"), (4, "Buddy-Buddy Poffin", "TEF", "144"),
            (4, "Poké Pad", "POR", "81"), (3, "Rare Candy", "MEG", "125"),
            (2, "Enhanced Hammer", "TWM", "148"), (1, "Sacred Ash", "DRI", "168"),
            (1, "Night Stretcher", "ASC", "196"), (2, "Handheld Fan", "TWM", "150"),
            (1, "Lucky Helmet", "TWM", "158"), (3, "Battle Cage", "PFL", "85"),
            (4, "Telepathic Psychic Energy", "POR", "88"), (1, "Enriching Energy", "SSP", "191"),
            (1, "Psychic Energy", "MEE", "5"),
        ],
    },
}
# deck 7 is byte-identical to deck 6 (two entrants, same archetype)
DECKS["t7-alakazam-b"] = {"primary_energy": "Basic {P} Energy",
                          "cards": list(DECKS["t6-alakazam-a"]["cards"])}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().replace("’", "'").strip()


def main() -> int:
    by_exact = {}
    by_name = {}
    for r in csv.DictReader(open(ROOT / "data" / "card_id_list.csv", encoding="utf-8")):
        key = (norm(r["name"]), r["expansion"].strip(), r["collection_no"].strip())
        by_exact[key] = r["card_id"]
        by_name.setdefault(norm(r["name"]), []).append((r["card_id"], r["expansion"], r["collection_no"]))

    grand_missing = {}
    for slug, spec in DECKS.items():
        ids, report, missing_n = [], [], 0
        for count, name, exp, no in spec["cards"]:
            if name.endswith("Energy") and exp == "MEE":
                sve = MEE_TO_SVE.get(no)
                hits = by_name.get(norm(sve), []) if sve else []
                if hits:
                    ids += [hits[0][0]] * count
                    report.append(f"  {count}x {name} MEE {no} -> {sve} (id {hits[0][0]})")
                    continue
            key = (norm(name), exp, no)
            if key in by_exact:
                ids += [by_exact[key]] * count
                report.append(f"  {count}x {name} {exp} {no} -> EXACT (id {by_exact[key]})")
                continue
            hits = by_name.get(norm(name), [])
            if hits:
                cid, hexp, hno = hits[0]
                ids += [cid] * count
                report.append(f"  {count}x {name} {exp} {no} -> REPRINT {hexp} {hno} (id {cid})")
                continue
            missing_n += count
            report.append(f"  {count}x {name} {exp} {no} -> MISSING (energy-fill)")
        if missing_n:
            fill = by_name[norm(spec["primary_energy"])][0][0]
            ids += [fill] * missing_n
            report.append(f"  +{missing_n}x {spec['primary_energy']} (id {fill}) filling missing slots")
            grand_missing[slug] = missing_n
        assert len(ids) == 60, f"{slug}: {len(ids)} cards"
        legal = {r for r in ids}
        pool = {row["card_id"] for row in csv.DictReader(open(ROOT / "data" / "card_id_list.csv", encoding="utf-8"))}
        assert legal <= pool, f"{slug}: illegal ids {legal - pool}"
        out = ROOT / f"deck_{slug}.csv"
        out.write_text("\n".join(ids) + "\n")
        print(f"\n=== {slug} -> {out.name} (60/60 legal, {missing_n} energy-filled) ===")
        print("\n".join(report))
    print("\n=== SUMMARY: energy-filled slots per deck ===")
    for slug, n in grand_missing.items():
        print(f"  {slug}: {n}")
    if not grand_missing:
        print("  none — every card mapped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
