# ADR-0005: Add an independent LLM mode alongside the solver, for comparison

**Status:** Accepted
**Date:** 2026-07

## Context

The deterministic solver (ADR-0001, ADR-0002) is the primary way this project plays solitaire, and needs no LLM. Separately, the owner wanted a second, independent way to play — an LLM choosing each move — specifically so the two approaches' results (win rate, move count, reliability) could be compared against each other, not because solitaire itself has any decision uncertainty that requires a model.

## Decision

Add `run.py --mode llm` as a fully separate move-selection path, sharing everything else with the solver mode:

- `Board.describe()` (used by both the CLI's board printout and the solver's stdout) is also what's sent to the LLM — the exact same text representation, not a screenshot. The LLM never needs to *read* the board visually; the DOM-derived state (ADR-0001, ADR-0003) is already exact.
- The LLM picks from the **exact list of currently-legal moves** (`board.legal_moves()`), returned as a numbered list; it responds with just an index. It cannot propose an illegal move — there's no parsing of free-form move text to get wrong.
- One chat completion per turn. No agent framework, no tool-calling loop, no MCP server (ADR-0002 still applies) — the model has nothing to *do* except pick a number, so there's nothing for a multi-tool agent loop to add.
- Unlike solver mode, there's no upfront plan to verify move-by-move: `_play_llm` re-reads the real board after every single move and feeds that fresh state into the next turn, so it can't drift from reality the way a stale plan could (see the resolve-loop in `_play_solver`, which exists precisely to handle that risk for the solver's longer-lived plans).
- Bounded by `MAX_LLM_MOVES` and a same-state-repeated-3-times stuck check, since without a transposition table the model can loop between two states indefinitely.

## Consequences

- `--mode llm` requires `OPENAI_API_KEY` (`.env`, see `.env.example`); `--mode solver` (the default) still needs nothing.
- This reintroduces network calls, cost, and non-determinism, but only for this one opt-in mode — the default path (ADR-0002's reasoning) is untouched.
- Because the LLM only sees exact game state and a pre-validated move list, any losses/inefficiency it produces are genuinely about move *quality*, not misreading the board or hallucinating illegal moves — making it a fair comparison against the solver rather than a stacked deck against the LLM.
