# ADR-0001: Solve with full information instead of guessing

**Status:** Accepted
**Date:** 2026-07

## Context

cardgames.io/solitaire renders every card as a DOM element like `<div class="card h11">` (or `"card h11 up"` once flipped). Inspecting the DOM shows this class carries the card's true rank and suit **even while it is face-down** — the `up` class only toggles which of two always-present child elements (`.faceup` / `.facedown`) is visible via CSS. Nothing about the identity is hidden from the page.

This means the entire 52-card deal is knowable the instant the game loads, before a single card is flipped.

## Decision

Build the solver as a perfect-information ("thoughtful solitaire") search: `solitaire/board.py` models the true identity of every card from the start, while still tracking each card's actual `face_up` flag and enforcing that only face-up cards can be moved. `solitaire/solver.py` searches this fully-known state space with a transposition table, so it can plan several moves ahead — including moves that only make sense because we know what a currently-buried card is.

This is different from (and much stronger than) a heuristic bot that only reacts to what's currently visible.

## Consequences

- The solver can find winning lines that a heuristic autoplay bot would miss, because it can plan around cards it hasn't uncovered yet.
- Some Klondike deals are provably unsolvable even with full information and "thoughtful" play; `solve()` reports its best partial progress in that case rather than pretending to win (see `solitaire/solver.py::SolveResult`).
- If the site ever stops encoding hidden-card identity in the DOM (e.g. switches to a canvas renderer), this whole approach breaks and the solver would need to fall back to reactive heuristics.
