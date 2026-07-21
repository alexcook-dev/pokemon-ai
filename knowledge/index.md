# PTCG deck knowledge base

Strategy knowledge extracted from deck guides by `/ptcg-guide`. Consumed by
`/ptcg-train` when forming experiment hypotheses, and by humans deciding what
to submit to the ladder.

One file per archetype. POLICY HINTS sections contain testable hypotheses —
each falsifiable by the frozen eval (`./eval/run_train_eval.sh`).

## Decks

- [Dragapult / Dusknoir](dragapult-dusknoir.md) — spread damage with Phantom Dive, Dusknoir picks off damaged targets; wins the prize race through multi-KO turns (deck: `deck.csv` = "Neddy Kosek - Pult / Noir - NAIC 26", also saved as `deck_neddy-kosek-pult-noir-naic26.csv`, currently active) — updated 2026-07-20
- [Hydrapple](hydrapple.md) — Syrup Storm counts all in-play Grass Energy (doubled by Meganium) for cheap big OHKOs, notably on Dragapult ex (decks: `deck_hydrapple.csv` = Matricardi Campinas, `deck_grant-walworth-hydrapple-naic2026.csv` = "Grant Walworth - Hydrapple - NAIC 2026") — updated 2026-07-20
- [Tournament gauntlet 2026-07-20](tournament-gauntlet-jul20.md) — 5× Swiss Bo3 vs 7 meta decks: Dragapult avg 6.2/8, winless vs Alakazam; Alakazam-b won 3 of 5 tournaments
- [Meta matchup matrix](meta-matchup-matrix.md) — full 9-deck round-robin (~700 games, real energies): Kangaskhan box is max-min champion 42%/54%; no >50%-vs-all deck exists; supersedes the gauntlet standings
