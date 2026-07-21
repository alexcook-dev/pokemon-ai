# PTCG deck knowledge base

Strategy knowledge extracted from deck guides by `/ptcg-guide`. Consumed by
`/ptcg-train` when forming experiment hypotheses, and by humans deciding what
to submit to the ladder.

One file per archetype. POLICY HINTS sections contain testable hypotheses —
each falsifiable by the frozen eval (`./eval/run_train_eval.sh`).

## Decks

- [Dragapult / Dusknoir](dragapult-dusknoir.md) — spread damage with Phantom Dive, Dusknoir picks off damaged targets; wins the prize race through multi-KO turns (deck: `deck.csv` = "Neddy Kosek - Pult / Noir - NAIC 26", also saved as `deck_neddy-kosek-pult-noir-naic26.csv`, currently active) — updated 2026-07-20
- [Hydrapple](hydrapple.md) — Syrup Storm counts all in-play Grass Energy (doubled by Meganium) for cheap big OHKOs, notably on Dragapult ex (decks: `deck_hydrapple.csv` = Matricardi Campinas, `deck_grant-walworth-hydrapple-naic2026.csv` = "Grant Walworth - Hydrapple - NAIC 2026") — updated 2026-07-20
