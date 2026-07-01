"""Playwright driver: reads Klondike board state from cardgames.io/solitaire
and executes moves via mouse drag simulation.

Cards are flat siblings positioned with absolute top/left (see doc/adr/0003),
so pile membership is inferred geometrically from each card's screen position
relative to the 13 `.cell` pile elements — see doc/adr/0002.
"""
from __future__ import annotations

from typing import Optional

from playwright.async_api import Browser, Page, Playwright, async_playwright

from solitaire.board import Board
from solitaire.cards import Card
from solitaire.moves import Move

URL = "https://cardgames.io/solitaire/"

_READ_BOARD_JS = r"""
() => {
    const cellKind = (el) => {
        if (el.classList.contains('tableau')) return 'tableau';
        if (el.classList.contains('stock')) return 'stock';
        if (el.classList.contains('waste')) return 'waste';
        if (el.classList.contains('foundation')) return 'foundation';
        return 'other';
    };
    const suitRe = /\b([cdhs])\b/;
    const cells = [...document.querySelectorAll('.cell')].map(el => {
        const r = el.getBoundingClientRect();
        const kind = cellKind(el);
        const suitMatch = kind === 'foundation' ? el.className.match(suitRe) : null;
        return {
            kind,
            suit: suitMatch ? suitMatch[1] : null,
            x: r.x + r.width / 2,
            y: r.y + r.height / 2,
        };
    }).filter(c => c.kind !== 'other');

    const cardRe = /\b([cdhs])(\d{1,2})\b/;
    const cards = [...document.querySelectorAll('.card')].map(el => {
        const r = el.getBoundingClientRect();
        const m = el.className.match(cardRe);
        return {
            suit: m ? m[1] : null,
            rank: m ? parseInt(m[2], 10) : null,
            faceUp: el.classList.contains('up'),
            x: r.x + r.width / 2,
            y: r.y + r.height / 2,
            top: r.y,
            z: parseInt(el.style.zIndex || '0', 10),
        };
    }).filter(c => c.suit !== null);

    return { cells, cards };
}
"""


def _parse_board(raw: dict, draw_count: int) -> Board:
    cells = raw["cells"]
    cards = raw["cards"]

    tableau_cells = sorted((c for c in cells if c["kind"] == "tableau"), key=lambda c: c["x"])
    stock_cell = next(c for c in cells if c["kind"] == "stock")
    waste_cell = next(c for c in cells if c["kind"] == "waste")
    foundation_cells = {c["suit"]: c for c in cells if c["kind"] == "foundation"}

    tableau_y = tableau_cells[0]["y"]
    top_row_y = stock_cell["y"]

    tableau_slots: list[list[tuple]] = [[] for _ in tableau_cells]
    stock_slots: list[tuple] = []
    waste_slots: list[tuple] = []
    foundations = {s: 0 for s in "cdhs"}

    for c in cards:
        card = Card(suit=c["suit"], rank=c["rank"])
        in_tableau_row = abs(c["y"] - tableau_y) < abs(c["y"] - top_row_y)
        if in_tableau_row:
            nearest = min(range(len(tableau_cells)), key=lambda i: abs(tableau_cells[i]["x"] - c["x"]))
            tableau_slots[nearest].append((card, c["faceUp"], c["y"], c["z"]))
            continue

        candidates = [("stock", abs(c["x"] - stock_cell["x"])), ("waste", abs(c["x"] - waste_cell["x"]))]
        candidates += [(f"foundation:{suit}", abs(c["x"] - cell["x"])) for suit, cell in foundation_cells.items()]
        best_kind = min(candidates, key=lambda pair: pair[1])[0]

        if best_kind == "stock":
            stock_slots.append((card, c["z"]))
        elif best_kind == "waste":
            waste_slots.append((card, c["z"]))
        else:
            suit = best_kind.split(":", 1)[1]
            foundations[suit] = max(foundations[suit], card.rank)

    tableau = []
    for slots in tableau_slots:
        slots.sort(key=lambda t: t[2])  # y ascending: buried -> accessible
        tableau.append([(card, up) for card, up, _y, _z in slots])

    stock_slots.sort(key=lambda t: t[1])  # z ascending: bottom -> next-to-draw
    waste_slots.sort(key=lambda t: t[1])
    stock = [card for card, _z in stock_slots]
    waste = [card for card, _z in waste_slots]

    return Board(tableau=tableau, foundations=foundations, stock=stock, waste=waste, draw_count=draw_count)


class SolitaireBrowser:
    def __init__(self, headless: bool = False, draw_count: int = 1) -> None:
        self._headless = headless
        self._draw_count = draw_count
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    async def start(self, game_number: Optional[int] = None) -> None:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self._headless)
        self._page = await self._browser.new_page()
        await self._page.goto(URL, wait_until="networkidle")
        await self._page.wait_for_timeout(2500)
        await self._dismiss_cookie_banner()
        if game_number is not None:
            await self._start_numbered_game(game_number)
        await self._page.wait_for_timeout(2500)
        # The numbered-game dialog (and sometimes the cookie banner) can leave the
        # page scrolled so the stock/waste/foundation row sits above the viewport
        # (negative y) — every coordinate we compute is relative to the viewport,
        # so an off-screen board means every click there hits nothing.
        await self._page.evaluate("window.scrollTo(0, 0)")
        await self._page.wait_for_timeout(300)

    async def _dismiss_cookie_banner(self) -> None:
        try:
            await self._page.click("#onetrust-reject-all-handler", timeout=3000)
            await self._page.wait_for_timeout(300)
        except Exception:
            pass  # banner didn't appear (e.g. already dismissed for this profile)

    async def _start_numbered_game(self, number: int) -> None:
        page = self._page
        await page.click("#game-nr a")
        await page.wait_for_timeout(300)
        await page.fill("#start-game-nr", str(number))
        await page.click("#start-numbered-game")
        await page.wait_for_timeout(2500)

    async def read_board(self) -> Board:
        raw = await self._page.evaluate(_READ_BOARD_JS)
        return _parse_board(raw, draw_count=self._draw_count)

    async def execute_move(self, move: Move, board_before: Board) -> None:
        page = self._page
        raw = await page.evaluate(_READ_BOARD_JS)
        cells = raw["cells"]
        cards = raw["cards"]

        if move.kind in ("draw", "recycle"):
            stock_cell = next(c for c in cells if c["kind"] == "stock")
            await page.mouse.click(stock_cell["x"], stock_cell["y"])
            await page.wait_for_timeout(500)
            return

        if move.kind == "tableau_to_foundation":
            src_card = board_before.tableau[move.src][-1][0]
            target = next(c for c in cells if c["kind"] == "foundation" and c["suit"] == src_card.suit)
        elif move.kind == "waste_to_foundation":
            src_card = board_before.waste[-1]
            target = next(c for c in cells if c["kind"] == "foundation" and c["suit"] == src_card.suit)
        elif move.kind == "tableau_to_tableau":
            src_card = board_before.tableau[move.src][-move.count][0]
            target = self._column_drop_point(board_before, move.dst, cells)
        elif move.kind == "waste_to_tableau":
            src_card = board_before.waste[-1]
            target = self._column_drop_point(board_before, move.dst, cells)
        else:
            raise ValueError(f"unknown move kind {move.kind!r}")

        source = next(c for c in cards if c["suit"] == src_card.suit and c["rank"] == src_card.rank)
        # Click near the exposed top strip, not the card's center: tableau cards
        # cascade with only ~24px revealed out of ~94px height, so a card that has
        # others stacked on top of it (e.g. the base of a multi-card run) has its
        # center covered by the card below it — clicking there grabs the WRONG card.
        source_y = source["top"] + 10
        await self._drag(source["x"], source_y, target["x"], target["y"])

    def _column_drop_point(self, board: Board, col_idx: int, cells: list[dict]) -> dict:
        tableau_cells = sorted((c for c in cells if c["kind"] == "tableau"), key=lambda c: c["x"])
        cell = tableau_cells[col_idx]
        column = board.tableau[col_idx]
        if not column:
            return {"x": cell["x"], "y": cell["y"]}
        return {"x": cell["x"], "y": cell["y"] + 24 * len(column)}

    async def _drag(self, sx: float, sy: float, tx: float, ty: float) -> None:
        page = self._page
        await page.mouse.move(sx, sy)
        await page.wait_for_timeout(150)
        await page.mouse.down()
        await page.wait_for_timeout(150)
        await page.mouse.move(sx + 4, sy - 4, steps=3)
        await page.wait_for_timeout(100)
        await page.mouse.move(tx, ty, steps=20)
        await page.wait_for_timeout(200)
        await page.mouse.up()
        await page.wait_for_timeout(700)

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
