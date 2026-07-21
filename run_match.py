"""
Head-to-head: deck.csv (player 0) vs deck_b.csv (player 1).
Both use the same agent policy (random for now).
"""
from pathlib import Path
from kaggle_environments import make
from main import agent

ROOT = Path(__file__).resolve().parent

def load_deck(path: Path) -> list[int]:
    ids = [int(line.strip()) for line in path.read_text().splitlines() if line.strip()]
    assert len(ids) == 60, f"{path} has {len(ids)} cards, need 60"
    return ids

def main() -> None:
    deck_a = load_deck(ROOT / "deck.csv")
    deck_b = load_deck(ROOT / "deck_b.csv")
    env = make("cabt", debug=True, configuration={"decks": [deck_a, deck_b]})
    steps = env.run([agent, agent])
    out = ROOT / "result.html"
    out.write_text(env.render(mode="html"))
    print(f"Steps: {len(steps)}")
    print(f"Replay: {out}")
    if steps:
        last = steps[-1]
        print("Final:", [(s.get("status"), s.get("reward")) for s in last])
        # reward: 1 win, -1 loss for each player
        r0 = last[0].get("reward")
        r1 = last[1].get("reward")
        if r0 == 1:
            print("Winner: Player 0 (deck.csv — your Dhelmise list)")
        elif r1 == 1:
            print("Winner: Player 1 (deck_b.csv — Ogerpon list)")
        else:
            print("Result: draw or incomplete")

if __name__ == "__main__":
    main()
