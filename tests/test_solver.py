from solitaire.board import Board
from solitaire.cards import Card
from solitaire.solver import solve

C = Card


def empty_board(**overrides) -> Board:
    base = dict(
        tableau=[[] for _ in range(7)],
        foundations={s: 0 for s in "cdhs"},
        stock=[],
        waste=[],
        draw_count=1,
    )
    base.update(overrides)
    return Board(**base)


def test_solves_one_move_win():
    board = empty_board(foundations={"c": 13, "d": 13, "h": 12, "s": 13}, tableau=[[(C("h", 13), True)]] + [[] for _ in range(6)])
    result = solve(board)
    assert result.won
    assert result.cards_home == 52
    assert len(result.moves) == 1
    assert result.moves[0].kind == "tableau_to_foundation"


def test_solves_small_shuffle_via_tableau_moves():
    # Moving the red 2 onto the black 3 reveals the last king diamonds needs to win.
    col0 = [(C("d", 13), False), (C("h", 2), True)]
    col1 = [(C("c", 3), True)]
    board = empty_board(
        foundations={"c": 13, "d": 12, "h": 13, "s": 13},
        tableau=[col0, col1] + [[] for _ in range(5)],
    )
    result = solve(board)
    assert result.won
    assert result.cards_home == 52


def test_reports_best_effort_when_unsolvable():
    # A lone face-down card with nothing else to do: no move can ever reveal or place it.
    board = empty_board(tableau=[[(C("h", 5), False)]] + [[] for _ in range(6)])
    result = solve(board, node_budget=1000, time_budget=1.0)
    assert not result.won
    assert result.cards_home == 0
    assert result.moves == []


def test_deterministic_across_runs():
    col0 = [(C("d", 13), False), (C("h", 2), True)]
    col1 = [(C("c", 3), True)]
    board = empty_board(
        foundations={"c": 13, "d": 12, "h": 13, "s": 13},
        tableau=[col0, col1] + [[] for _ in range(5)],
    )
    result_a = solve(board)
    result_b = solve(board)
    assert result_a.moves == result_b.moves
