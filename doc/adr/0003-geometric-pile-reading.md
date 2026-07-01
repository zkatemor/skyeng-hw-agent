# ADR-0003: Infer pile membership from card position, not DOM nesting

**Status:** Accepted
**Date:** 2026-07

## Context

Every `.card` element on cardgames.io/solitaire is a flat sibling under `#play-page`, positioned with absolute `top`/`left` — cards are **not** nested inside their pile's container element. So `read_board()` cannot tell which pile a card belongs to by walking up the DOM tree; it has to infer it from where the card is drawn.

The board has 13 pile "cells" (`.stock.cell`, `.waste.cell`, 7× `.tableau.cell`, 4× `.foundation.cell`), each a distinct element with its own fixed on-screen position, arranged in two rows: stock/waste/foundations on top, tableau columns below.

## Decision

`browser.py::_parse_board` reads the bounding rect of every `.cell` and every `.card`, then buckets each card in two steps:

1. **Row**: compare the card's `y` to the tableau row's `y` vs. the top row's `y` — whichever is closer wins. This is safe even for a tall tableau column, because there is no third row to confuse it with.
2. **Column within the row**: nearest pile cell by `x` distance only (not full 2D distance) — a card can be cascaded far down its own tableau column, but its `x` never drifts from that column's `x`.

Within a tableau column, cards are then sorted by `y` ascending (buried → accessible). Within stock/waste, cards are sorted by their CSS `z-index` (bottom of stack → top/next-to-act), since those piles keep every card visually stacked at the same `x, y`.

Each card's true suit/rank comes straight from parsing its class name (`card h11` → hearts, jack) — see ADR-0001.

## Consequences

- Reading the board is a single `page.evaluate()` round-trip plus cheap Python-side geometry — no need to reverse-engineer the site's internal state object.
- This is brittle to a layout change (e.g. cell reordering or a redesign that overlaps rows) — if `read_board()` ever misclassifies a pile, `run.py --dry-run` (prints the parsed board without playing) is the tool to catch it before trusting it to drive real moves.
