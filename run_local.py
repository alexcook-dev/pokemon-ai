"""
Run a local cabt self-play game.

On macOS the native libcg.so is Linux-only, so use Docker:
  ./run_docker.sh

If you're already on Linux x86_64:
  python3 run_local.py
"""
from pathlib import Path

from kaggle_environments import make

from main import agent, DECK


def main() -> None:
    assert len(DECK) == 60, f"Deck must be 60 cards, got {len(DECK)}"
    env = make("cabt", debug=True, configuration={"decks": [DECK, DECK]})
    # env.run agents: each agent is called with observation; first call may be deck
    steps = env.run([agent, agent])
    out = Path(__file__).resolve().parent / "result.html"
    out.write_text(env.render(mode="html"))
    print(f"Steps: {len(steps)}")
    print(f"Replay written to {out}")
    # final rewards if present
    if steps:
        last = steps[-1]
        print("Final state:", [(s.get("status"), s.get("reward")) for s in last])


if __name__ == "__main__":
    main()
