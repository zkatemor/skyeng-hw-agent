"""Full-information ("thoughtful") Klondike solver.

Every card's identity is known from the start (see doc/adr/0001), so this is a
perfect-information search rather than a heuristic guess: weighted A* over the
board-state graph, with a transposition table to prune repeated states and a
node/time budget. Plain unweighted DFS was tried first and technically found
wins, but wandered through hundreds of pointless draw/shuffle detours before
stumbling onto one (1000+ moves for a 52-card deal); A* biases expansion
toward states that are both close (few moves so far) and promising (few cards
left to home), which keeps plans close to how a person would actually play.
If no full win is found in budget, the best partial-progress sequence seen is
returned instead of failing outright — an honestly-reported "stuck" result,
not a bug.
"""
from __future__ import annotations

import heapq
import itertools
import time
from dataclasses import dataclass

from .board import Board
from .moves import Move


@dataclass
class SolveResult:
    moves: list[Move]
    won: bool
    cards_home: int


def _heuristic(board: Board) -> int:
    """Estimated moves remaining. Weighted (not admissible) on purpose — this
    is a fast, good-enough guide, not a shortest-path guarantee. The x4 weight
    on cards-home was tuned empirically: x1-x3 frequently timed out on real
    deals without finding a win at all; x4 reliably converges in a few seconds."""
    cards_home = sum(board.foundations.values())
    face_down = sum(1 for col in board.tableau for _card, up in col if not up)
    return 4 * (52 - cards_home) + face_down


def solve(board: Board, node_budget: int = 200_000, time_budget: float = 15.0) -> SolveResult:
    deadline = time.monotonic() + time_budget
    counter = itertools.count()

    visited: set[tuple] = {board.key()}
    # heap entries: (f_score, tie_breaker, board, path). f = moves-so-far + heuristic.
    heap: list[tuple[int, int, Board, list[Move]]] = [(_heuristic(board), next(counter), board, [])]

    best_score = board.progress()
    best_moves: list[Move] = []
    best_board = board

    nodes = 0
    while heap and nodes < node_budget and time.monotonic() < deadline:
        _f, _tie, current, path = heapq.heappop(heap)
        nodes += 1

        if current.is_won():
            return SolveResult(moves=path, won=True, cards_home=52)

        score = current.progress()
        if score > best_score:
            best_score, best_moves, best_board = score, path, current

        for move in current.legal_moves():
            nxt = current.apply(move)
            key = nxt.key()
            if key in visited:
                continue
            visited.add(key)
            g = len(path) + 1
            f = g + _heuristic(nxt)
            heapq.heappush(heap, (f, next(counter), nxt, path + [move]))

    return SolveResult(moves=best_moves, won=False, cards_home=sum(best_board.foundations.values()))
