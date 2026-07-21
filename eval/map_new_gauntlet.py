#!/usr/bin/env python3
"""Map the 3 user-provided opponent decklists to competition card IDs.

Same mapping rule as map_gauntlet_decks.py (2026-07-20 standing rule):
  1. exact (name, expansion, collection_no) match
  2. same-name reprint (any printing in pool)
  3. MISSING -> fill slot with +1 basic energy of the deck's primary type
"""
from __future__ import annotations

import csv
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MEE_TO_SVE = {"1": "Basic {G} Energy", "2": "Basic {R} Energy", "3": "Basic {W} Energy",
              "4": "Basic {L} Energy", "5": "Basic {P} Energy", "6": "Basic {F} Energy",
              "7": "Basic {D} Energy", "8": "Basic {M} Energy"}

DECKS = {
    "user-alakazam-elgyem": {
        "primary_energy": "Basic {P} Energy",
        "cards": [
            (4, "Abra", "MEG", "54"), (4, "Kadabra", "MEG", "55"), (3, "Alakazam", "MEG", "56"),
            (3, "Dunsparce", "JTG", "120"), (3, "Dudunsparce", "TEF", "129"),
            (1, "Dedenne", "SSP", "87"), (1, "Elgyem", "BLK", "40"), (1, "Genesect", "SFA", "40"),
            (1, "Fezandipiti ex", "ASC", "142"), (1, "Shaymin", "DRI", "10"),
            (4, "Dawn", "PFL", "87"), (3, "Hilda", "WHT", "84"), (2, "Boss's Orders", "MEG", "114"),
            (1, "Lana's Aid", "TWM", "155"), (4, "Buddy-Buddy Poffin", "TEF", "144"),
            (4, "Poké Pad", "POR", "81"), (3, "Rare Candy", "MEG", "125"),
            (2, "Enhanced Hammer", "TWM", "148"), (1, "Sacred Ash", "DRI", "168"),
            (1, "Night Stretcher", "ASC", "196"), (1, "Lucky Helmet", "TWM", "158"),
            (1, "Handheld Fan", "TWM", "150"), (1, "Air Balloon", "ASC", "181"),
            (4, "Nighttime Mine", "ASC", "197"),
            (4, "Telepathic Psychic Energy", "POR", "88"), (1, "Psychic Energy", "MEE", "5"),
            (1, "Enriching Energy", "SSP", "191"),
        ],
    },
    "user-grimmsnarl-munkidori": {
        "primary_energy": "Basic {D} Energy",
        "cards": [
            (4, "Munkidori", "TWM", "95"), (3, "Marnie's Impidimp", "DRI", "134"),
            (2, "Marnie's Morgrem", "DRI", "135"), (3, "Marnie's Grimmsnarl ex", "DRI", "136"),
            (2, "Snorunt", "ASC", "46"), (2, "Froslass", "TWM", "53"),
            (1, "Budew", "ASC", "16"), (1, "Tatsugiri", "TWM", "131"), (1, "Yveltal", "MEG", "88"),
            (4, "Lillie's Determination", "MEG", "119"), (4, "Team Rocket's Petrel", "DRI", "176"),
            (3, "Boss's Orders", "MEG", "114"), (1, "Iris's Fighting Spirit", "JTG", "149"),
            (4, "Poké Pad", "POR", "81"), (3, "Buddy-Buddy Poffin", "TEF", "144"),
            (3, "Night Stretcher", "ASC", "196"), (2, "Rare Candy", "MEG", "125"),
            (1, "Energy Switch", "MEG", "115"), (1, "Special Red Card", "CRI", "82"),
            (1, "Secret Box", "TWM", "163"), (1, "Air Balloon", "ASC", "181"),
            (4, "Spikemuth Gym", "DRI", "169"),
            (9, "Darkness Energy", "MEE", "7"),
        ],
    },
    "user-kangaskhan-crustle": {
        "primary_energy": "Basic {G} Energy",
        "cards": [
            (4, "Mega Kangaskhan ex", "MEG", "104"), (3, "Dwebble", "DRI", "11"),
            (3, "Crustle", "DRI", "12"),
            (4, "Lillie's Determination", "MEG", "119"), (4, "Boss's Orders", "MEG", "114"),
            (4, "Team Rocket's Petrel", "DRI", "176"), (2, "Hilda", "WHT", "84"),
            (2, "Eri", "TEF", "146"), (1, "Xerosic's Machinations", "SFA", "64"),
            (1, "Pokémon Center Lady", "MEG", "123"), (1, "Bianca's Devotion", "TEF", "142"),
            (1, "Lisia's Appeal", "SSP", "179"), (4, "Jumbo Ice Cream", "PFL", "91"),
            (3, "Pokégear 3.0", "SVI", "186"), (2, "Buddy-Buddy Poffin", "TEF", "144"),
            (1, "Ultra Ball", "MEG", "131"), (1, "Switch", "MEG", "130"),
            (1, "Hand Trimmer", "TEF", "150"), (1, "Hero's Cape", "TEF", "152"),
            (1, "Handheld Fan", "TWM", "150"), (1, "Team Rocket's Factory", "DRI", "173"),
            (1, "Community Center", "TWM", "146"), (1, "Festival Grounds", "TWM", "149"),
            (4, "Spiky Energy", "JTG", "159"), (4, "Growing Grass Energy", "POR", "86"),
            (4, "Mist Energy", "TEF", "161"), (1, "Grass Energy", "MEE", "1"),
        ],
    },
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().replace("’", "'").strip()


def main() -> int:
    by_exact, by_name, by_setno = {}, {}, {}
    for r in csv.DictReader(open(ROOT / "data" / "card_id_list.csv", encoding="utf-8")):
        key = (norm(r["name"]), r["expansion"].strip(), r["collection_no"].strip())
        by_exact[key] = r["card_id"]
        by_name.setdefault(norm(r["name"]), []).append((r["card_id"], r["expansion"], r["collection_no"]))
        by_setno[(r["expansion"].strip(), r["collection_no"].strip())] = (r["card_id"], r["name"])

    pool = {row["card_id"] for row in csv.DictReader(open(ROOT / "data" / "card_id_list.csv", encoding="utf-8"))}

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
            setno_hit = by_setno.get((exp, no))
            if setno_hit:
                cid, cat_name = setno_hit
                ids += [cid] * count
                report.append(f"  {count}x {name} {exp} {no} -> NAME-VARIANT '{cat_name}' (id {cid})")
                continue
            missing_n += count
            report.append(f"  {count}x {name} {exp} {no} -> MISSING (energy-fill)")
        if missing_n:
            fill = by_name[norm(spec["primary_energy"])][0][0]
            ids += [fill] * missing_n
            report.append(f"  +{missing_n}x {spec['primary_energy']} (id {fill}) filling missing slots")
        if len(ids) != 60:
            print(f"!!! {slug}: got {len(ids)} cards, need 60")
        legal = set(ids)
        illegal = legal - pool
        if illegal:
            print(f"!!! {slug}: illegal ids {illegal}")
        out = ROOT / f"deck_{slug}.csv"
        out.write_text("\n".join(ids) + "\n")
        print(f"\n=== {slug} -> {out.name} ({len(ids)}/60, {missing_n} energy-filled) ===")
        print("\n".join(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
