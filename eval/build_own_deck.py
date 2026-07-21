#!/usr/bin/env python3
"""Build my own designed deck: "Boltpon Basics Rush".

Thesis: every attacker is a Basic Pokemon (no evolution lines at all), which
removes the entire class of evolve-timing/sequencing decisions our heuristic
policy is weakest at (it has never had to pilot a deck with zero Stage-1/
Stage-2 pieces). Two 4-of ex attackers carry the offense (Raging Bolt ex /
Teal Mask Ogerpon ex — the real-world "Bolt/Ogerpon" pairing, and the same
Ogerpon core that anchored the tournament-winning Kangaskhan box), Iron
Leaves ex is a flex third attacker, Meowth ex smooths draws. Trainer line
leans on Night Stretcher (every discarded attacker is fully recoverable in
an all-basic shell) and Prime Catcher (ACE SPEC gust+draw) since there's no
evolution engine to support instead.

All names verified present in data/card_id_list.csv AND in the cabt engine's
own string table (grepped from libcg_docker.so) before inclusion — nothing
here is from memory alone.
"""
from __future__ import annotations

import csv
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SPEC = [
    # Pokemon (13) — all Basic, zero evolution lines
    (4, "Raging Bolt ex", "TEF", "123"),
    (4, "Teal Mask Ogerpon ex", "TWM", "25"),
    (3, "Meowth ex", "POR", "62"),
    (2, "Iron Leaves ex", "TEF", "25"),
    # Trainers (29)
    (4, "Lillie's Determination", "MEG", "119"),
    (3, "Crispin", "SCR", "133"),
    (2, "Dawn", "PFL", "87"),
    (3, "Boss's Orders", "MEG", "114"),
    (4, "Ultra Ball", "MEG", "131"),
    (4, "Poké Pad", "POR", "81"),
    (2, "Energy Switch", "MEG", "115"),
    (3, "Night Stretcher", "ASC", "196"),
    (2, "Air Balloon", "ASC", "181"),
    (1, "Unfair Stamp", "TWM", "165"),
    (1, "Prime Catcher", "TEF", "157"),  # ACE SPEC — 1 max, satisfied
    # Energy (18): weighted 9 Lightning / 6 Grass / 3 Psychic to match the
    # 4/4/2-ish attacker split (Bolt=L, Ogerpon=G, Leaves=P)
    (9, "Lightning Energy", "MEE", "4"),
    (6, "Grass Energy", "MEE", "1"),
    (3, "Psychic Energy", "MEE", "5"),
]

MEE_TO_SVE = {"1": "Basic {G} Energy", "2": "Basic {R} Energy", "3": "Basic {W} Energy",
              "4": "Basic {L} Energy", "5": "Basic {P} Energy", "6": "Basic {F} Energy",
              "7": "Basic {D} Energy", "8": "Basic {M} Energy"}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().replace("’", "'").strip()


def main() -> int:
    by_exact, by_name = {}, {}
    for r in csv.DictReader(open(ROOT / "data" / "card_id_list.csv", encoding="utf-8")):
        key = (norm(r["name"]), r["expansion"].strip(), r["collection_no"].strip())
        by_exact[key] = r["card_id"]
        by_name.setdefault(norm(r["name"]), []).append((r["card_id"], r["expansion"], r["collection_no"]))

    ids, report, prize_liability = [], [], 0
    for count, name, exp, no in SPEC:
        if name.endswith("Energy") and exp == "MEE":
            sve = MEE_TO_SVE[no]
            hits = by_name[norm(sve)]
            ids += [hits[0][0]] * count
            report.append(f"  {count}x {name} MEE {no} -> {sve} (id {hits[0][0]})")
            continue
        key = (norm(name), exp, no)
        if key in by_exact:
            cid = by_exact[key]
            ids += [cid] * count
            report.append(f"  {count}x {name} {exp} {no} -> EXACT (id {cid})")
        else:
            hits = by_name.get(norm(name), [])
            assert hits, f"NOT FOUND ANYWHERE: {name} {exp} {no}"
            cid, hexp, hno = hits[0]
            ids += [cid] * count
            report.append(f"  {count}x {name} {exp} {no} -> REPRINT {hexp} {hno} (id {cid})")
        if name.endswith(" ex"):
            prize_liability += count

    assert len(ids) == 60, f"got {len(ids)} cards"
    pool = {row["card_id"] for row in csv.DictReader(open(ROOT / "data" / "card_id_list.csv", encoding="utf-8"))}
    illegal = [c for c in ids if c not in pool]
    assert not illegal, f"illegal ids: {illegal}"

    out = ROOT / "deck_boltpon-basics-rush.csv"
    out.write_text("\n".join(ids) + "\n")
    print(f"=== boltpon-basics-rush -> {out.name} (60/60 legal) ===")
    print("\n".join(report))
    print(f"\nex-count (2-prize liability): {prize_liability}/13 Pokemon")
    print(f"non-ex Pokemon (1-prize): {13 - prize_liability}")
    print(f"card counts: {dict(sorted(Counter(ids).items(), key=lambda kv: -int(kv[1]) if False else kv[0]))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
