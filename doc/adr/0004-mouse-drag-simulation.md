# ADR-0004: Move cards with low-level mouse drag simulation

**Status:** Accepted
**Date:** 2026-07

## Context

Cards on cardgames.io/solitaire have `draggable="false"` — the site implements its own drag interaction via mouse/pointer events rather than the native HTML5 Drag API. Playwright's high-level `page.drag_and_drop()` dispatches `DragEvent`s, which this kind of custom drag handling ignores (the same failure mode the previous project hit with Vimbox's Angular CDK drag-and-drop).

Live testing confirmed that a raw mouse choreography does move a card: `mouse.move` to the card → `mouse.down()` → a small jiggle move (to register as a drag, not a click) → `mouse.move` to the target in several steps → `mouse.up()`.

## Decision

`browser.py::SolitaireBrowser._drag()` reuses this exact choreography. Source and target pixels are computed from the live DOM read (`execute_move`): the source is located by looking up the specific card's unique `(suit, rank)` in the current `.card` elements (every card is unique, so this is unambiguous regardless of which pile it's currently in); the target is either a foundation cell's center, a tableau cell's position (for an empty column), or just below the target column's current top card.

## Consequences

- Works without needing to reverse-engineer the site's pointer-event handlers.
- Multi-card run moves (`tableau_to_tableau` with `count > 1`) are executed as a single drag of the run's bottom-most card, relying on the site to move the whole face-up sequence together, the way a human dragging a valid run would. This has not been exhaustively verified against every possible run length — worth watching during `run.py` playthroughs.
- Timing constants (`wait_for_timeout` calls) are conservative starting points, not measured minimums; they may need tuning the same way the original Vimbox drag timings did.
