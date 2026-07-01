"""Klondike board state: legal moves, move application, win/progress checks.

Foundation-to-tableau moves are intentionally not modeled — they rarely help
under thoughtful play and would multiply the branching factor of the search
for little benefit (see doc/adr/0001).
"""
from __future__ import annotations

from dataclasses import dataclass

from .cards import Card, SUITS
from .moves import Move

TableauCard = tuple[Card, bool]  # (card, face_up)


@dataclass
class Board:
    tableau: list[list[TableauCard]]  # 7 columns; index 0 = buried, -1 = accessible
    foundations: dict[str, int]  # suit -> highest rank placed, 0 = empty
    stock: list[Card]  # -1 = next to draw
    waste: list[Card]  # -1 = top / playable
    draw_count: int = 1

    def is_won(self) -> bool:
        return all(rank == 13 for rank in self.foundations.values())

    def describe(self) -> str:
        lines = [f"Foundations: {self.foundations}"]
        top_waste = self.waste[-1] if self.waste else "-"
        lines.append(f"Stock: {len(self.stock)}   Waste: {len(self.waste)} (top: {top_waste})")
        for i, col in enumerate(self.tableau):
            cards = " ".join(str(c) if up else "[?]" for c, up in col)
            lines.append(f"  T{i}: {cards}")
        return "\n".join(lines)

    def progress(self) -> int:
        """Best-effort ranking used when no full solution is found in budget."""
        home = sum(self.foundations.values())
        face_up = sum(1 for col in self.tableau for _card, up in col if up)
        return home * 2 + face_up

    def key(self) -> tuple:
        return (
            tuple(tuple((c.suit, c.rank, up) for c, up in col) for col in self.tableau),
            tuple(self.foundations[s] for s in SUITS),
            tuple((c.suit, c.rank) for c in self.stock),
            tuple((c.suit, c.rank) for c in self.waste),
        )

    def _run_starts(self, col_idx: int) -> list[int]:
        """Start indices of every draggable run in a column, closest-to-top first.

        A run is a maximal face-up suffix in alternating-color, descending order.
        """
        col = self.tableau[col_idx]
        if not col:
            return []
        starts = [len(col) - 1]
        for i in range(len(col) - 2, -1, -1):
            card, up = col[i]
            next_card, next_up = col[i + 1]
            if not up or not next_up:
                break
            if card.is_red == next_card.is_red:
                break
            if card.rank != next_card.rank + 1:
                break
            starts.append(i)
        return starts

    def _fits_tableau(self, card: Card, target: list[TableauCard]) -> bool:
        if not target:
            return card.rank == 13
        top_card, top_up = target[-1]
        return top_up and (top_card.is_red != card.is_red) and top_card.rank == card.rank + 1

    def legal_moves(self) -> list[Move]:
        moves: list[Move] = []

        for i, col in enumerate(self.tableau):
            if not col:
                continue
            top_card, top_up = col[-1]
            if not top_up:
                continue
            if self.foundations[top_card.suit] == top_card.rank - 1:
                moves.append(Move("tableau_to_foundation", src=i, dst=None, count=1))
            for start in self._run_starts(i):
                run_card = col[start][0]
                count = len(col) - start
                for j, target in enumerate(self.tableau):
                    if j == i:
                        continue
                    if self._fits_tableau(run_card, target):
                        moves.append(Move("tableau_to_tableau", src=i, dst=j, count=count))

        if self.waste:
            top = self.waste[-1]
            if self.foundations[top.suit] == top.rank - 1:
                moves.append(Move("waste_to_foundation", src=None, dst=None, count=1))
            for j, target in enumerate(self.tableau):
                if self._fits_tableau(top, target):
                    moves.append(Move("waste_to_tableau", src=None, dst=j, count=1))

        if self.stock:
            moves.append(Move("draw", src=None, dst=None, count=min(self.draw_count, len(self.stock))))
        elif self.waste:
            moves.append(Move("recycle", src=None, dst=None, count=0))

        return moves

    def apply(self, move: Move) -> "Board":
        tableau = [list(col) for col in self.tableau]
        foundations = dict(self.foundations)
        stock = list(self.stock)
        waste = list(self.waste)

        if move.kind == "tableau_to_foundation":
            card, _up = tableau[move.src].pop()
            foundations[card.suit] = card.rank
            self._reveal(tableau, move.src)
        elif move.kind == "tableau_to_tableau":
            run = tableau[move.src][-move.count:]
            del tableau[move.src][-move.count:]
            tableau[move.dst].extend(run)
            self._reveal(tableau, move.src)
        elif move.kind == "waste_to_foundation":
            card = waste.pop()
            foundations[card.suit] = card.rank
        elif move.kind == "waste_to_tableau":
            card = waste.pop()
            tableau[move.dst].append((card, True))
        elif move.kind == "draw":
            for _ in range(move.count):
                waste.append(stock.pop())
        elif move.kind == "recycle":
            stock = list(reversed(waste))
            waste = []
        else:
            raise ValueError(f"unknown move kind {move.kind!r}")

        return Board(tableau=tableau, foundations=foundations, stock=stock, waste=waste, draw_count=self.draw_count)

    @staticmethod
    def _reveal(tableau: list[list[TableauCard]], col_idx: int) -> None:
        col = tableau[col_idx]
        if col and not col[-1][1]:
            card, _up = col[-1]
            col[-1] = (card, True)
