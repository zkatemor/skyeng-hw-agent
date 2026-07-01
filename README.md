# solitaire-agent-autosolver

A local bot that auto-solves Klondike Solitaire at [cardgames.io/solitaire](https://cardgames.io/solitaire/) in a visible browser window.

No login required. Two independent ways to decide moves:
- **`solver` (default)** — a deterministic Python search, no API keys or LLM needed.
- **`llm`** — an LLM picks each move instead, as a point of comparison against the solver. Requires an API key.

Both share the same browser driver and board-reading logic, so their results are directly comparable.

---

## How it works

```
run.py
  │
  ├─► browser.py           reads the board (Playwright, DOM inspection)
  │
  ├─► solitaire.solver      (--mode solver) computes a full move plan up front
  │   or llm_player          (--mode llm) picks one move at a time via an LLM
  │
  └─► browser.py           plays each move back (mouse drag simulation)
```

The site's DOM reveals every card's true rank/suit even while face-down (see `doc/adr/0001-full-information-solver.md`), so the solver plans with full knowledge of the deal — much stronger than a bot that only reacts to what's currently visible. It still respects the real game rules: a card can only be moved once it's actually face-up in play.

Not every deal is solvable this way; when it isn't, the tool plays as far as it can and reports how many cards made it home instead of pretending to win.

---

## Requirements

- Python 3.12+
- [uv](https://github.com/astral-sh/uv)
- For `--mode llm` only: an OpenAI-compatible API key

## Setup

```bash
git clone <this repo>
cd solitaire-agent-autosolver

uv sync
uv run playwright install chromium
```

For `--mode llm`, also copy the environment template and fill in your key:

```bash
cp .env.example .env
```

## Usage

```bash
# Play a fresh random deal with the deterministic solver
uv run python run.py

# Play a specific numbered deal (reproducible — same number, same cards every time)
uv run python run.py --game 12345

# Let an LLM choose each move instead (requires .env)
uv run python run.py --game 12345 --mode llm

# Just read and print the board, don't play — use this to sanity-check that
# the DOM-reading logic matches what's actually on screen
uv run python run.py --game 12345 --dry-run

# Run without a visible browser window
uv run python run.py --headless
```

What happens:

1. Chromium opens and loads the game (or a specific numbered deal, if given).
2. The board is read and printed.
3. In `solver` mode: a full move plan is computed up front and played move by move, re-verifying against the real page and re-solving if a move doesn't land as expected. In `llm` mode: the LLM is asked for one move at a time, from the exact list of currently-legal moves.
4. At the end: "Solved!" or a report of how many cards made it to the foundations.

---

## Tests

```bash
uv run python -m pytest
```

Unit tests cover the solitaire rules, solver, and LLM move-parsing logic (`tests/`) — pure Python, no browser or API calls needed.

---

## Project layout

| Path | Purpose |
|---|---|
| `solitaire/cards.py` | Card/suit representation, DOM class parsing |
| `solitaire/board.py` | Board state, legal moves, move application, win check, text description |
| `solitaire/solver.py` | Full-information search over the board state space |
| `browser.py` | Playwright driver: reads the board, executes moves |
| `llm_player.py` | `--mode llm`: asks an LLM to pick from the legal-move list each turn |
| `run.py` | CLI entry point |
| `doc/adr/` | Architecture decisions and why they were made |

See `doc/adr/` for the reasoning behind the DOM-reading approach, the drag simulation, and why the solver mode needs no LLM.

---

## Known limitations

- Some deals are unsolvable even with full information; the tool reports partial progress rather than a false win.
- The site's own `autoComplete` feature can finish an obviously-won game ahead of the solver's plan — `solver` mode's re-verify/re-solve loop handles this gracefully (it just re-solves from the more-advanced real state), but it shows up as a "did not land as expected" line that isn't actually an error.
- Drag timings are conservative starting points and may need tuning on slower machines.
- `llm` mode has no transposition table, so it can loop between the same couple of states; `MAX_LLM_MOVES` and a repeated-state check bound this, but it means `llm` mode isn't expected to match the solver's win rate — that gap is the point of having both modes.
