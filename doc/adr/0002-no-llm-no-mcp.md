# ADR-0002: Plain Python + Playwright by default, no MCP layer

**Status:** Accepted (revised — see ADR-0005 for the later addition of an optional LLM mode)
**Date:** 2026-07

## Context

The previous version of this project (a homework-filling agent) used the OpenAI Agents SDK with an MCP browser-tool server, because an LLM had to *decide* which answer was correct for each exercise — genuine uncertainty that needed a model in the loop.

Solitaire has no such uncertainty: once the deal is known (ADR-0001), the correct move is a deterministic function of the board state. There is nothing for an LLM to decide. (An LLM-driven mode was added later purely as an independent point of comparison — see ADR-0005 — but the default, and the thing the solver was actually designed around, remains this deterministic search.)

## Decision

Drop the MCP/tool-calling-agent stack entirely, and make the default move-selection path a plain Python program with no LLM in the loop:

```
run.py → solitaire.solver.solve(board) → list[Move] → browser.py executes each Move via Playwright
```

`solitaire/` has zero browser dependencies and is unit-tested directly (`tests/`). `browser.py` is a thin Playwright wrapper with no decision-making of its own — it only reads state and executes the moves it's told to.

## Consequences

- The default mode (`run.py` with no `--mode` flag) needs no API keys, no `.env`, no LLM proxy — it runs fully offline except for the one game website.
- Moves are reproducible: the same deal always produces the same plan (see `tests/test_solver.py::test_deterministic_across_runs`), unlike an LLM agent whose tool-call choices can vary run to run.
- MCP specifically is never coming back in this project regardless of mode: there's no multi-tool tool-calling loop to justify it, even in `--mode llm` (ADR-0005) — that mode is one plain chat completion per turn, not an agent with tools.
