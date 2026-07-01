from solitaire.board import Board
from solitaire.cards import Card
from solitaire.moves import Move

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


def test_tableau_to_foundation_when_rank_matches():
    board = empty_board(tableau=[[(C("h", 1), True)]] + [[] for _ in range(6)])
    moves = board.legal_moves()
    assert Move("tableau_to_foundation", src=0, dst=None, count=1) in moves


def test_tableau_to_foundation_blocked_when_face_down():
    board = empty_board(tableau=[[(C("h", 1), False)]] + [[] for _ in range(6)])
    moves = board.legal_moves()
    assert not any(m.kind == "tableau_to_foundation" for m in moves)


def test_run_detection_alternating_colors():
    col = [(C("s", 7), True), (C("h", 6), True), (C("c", 5), True)]
    board = empty_board(tableau=[col] + [[] for _ in range(6)])
    assert board._run_starts(0) == [2, 1, 0]


def test_run_breaks_on_same_color():
    col = [(C("s", 7), True), (C("c", 6), True)]  # both black — not a valid run together
    board = empty_board(tableau=[col] + [[] for _ in range(6)])
    assert board._run_starts(0) == [1]


def test_run_breaks_on_face_down_card():
    col = [(C("h", 6), False), (C("c", 5), True)]
    board = empty_board(tableau=[col] + [[] for _ in range(6)])
    assert board._run_starts(0) == [1]


def test_multi_card_run_move_is_generated_and_moves_together():
    # A valid 3-card run (7♠ 6♥ 5♣) should be draggable as ONE move onto an 8♥.
    run_col = [(C("s", 7), True), (C("h", 6), True), (C("c", 5), True)]
    target_col = [(C("h", 8), True)]
    board = empty_board(tableau=[run_col, target_col] + [[] for _ in range(5)])
    moves = board.legal_moves()
    run_moves = [m for m in moves if m.kind == "tableau_to_tableau" and m.dst == 1]
    assert run_moves == [Move("tableau_to_tableau", src=0, dst=1, count=3)]

    new_board = board.apply(run_moves[0])
    assert new_board.tableau[0] == []
    assert new_board.tableau[1] == target_col + run_col


def test_tableau_to_tableau_fit_and_apply():
    col0 = [(C("s", 7), True)]
    col1 = [(C("h", 6), True)]
    board = empty_board(tableau=[col0, col1] + [[] for _ in range(5)])
    move = Move("tableau_to_tableau", src=1, dst=0, count=1)
    assert move in board.legal_moves()
    new_board = board.apply(move)
    assert new_board.tableau[1] == []
    assert new_board.tableau[0] == [(C("s", 7), True), (C("h", 6), True)]


def test_only_king_fits_empty_column():
    col_source = [(C("h", 6), True)]
    board = empty_board(tableau=[col_source] + [[] for _ in range(6)])
    moves = board.legal_moves()
    assert not any(m.kind == "tableau_to_tableau" and m.dst == 1 for m in moves)

    col_king = [(C("h", 13), True)]
    board2 = empty_board(tableau=[col_king] + [[] for _ in range(6)])
    moves2 = board2.legal_moves()
    assert any(m.kind == "tableau_to_tableau" and m.dst == 1 for m in moves2)


def test_reveal_flips_newly_exposed_card():
    col = [(C("d", 2), False), (C("h", 6), True)]
    board = empty_board(tableau=[col] + [[] for _ in range(6)], foundations={"c": 0, "d": 0, "h": 5, "s": 0})
    move = Move("tableau_to_foundation", src=0, dst=None, count=1)
    new_board = board.apply(move)
    assert new_board.tableau[0] == [(C("d", 2), True)]


def test_waste_to_foundation_and_tableau():
    board = empty_board(waste=[C("d", 5)], foundations={"c": 0, "d": 4, "h": 0, "s": 0})
    moves = board.legal_moves()
    assert Move("waste_to_foundation", src=None, dst=None, count=1) in moves

    board2 = empty_board(waste=[C("d", 5)], tableau=[[(C("s", 6), True)]] + [[] for _ in range(6)])
    moves2 = board2.legal_moves()
    assert Move("waste_to_tableau", src=None, dst=0, count=1) in moves2


def test_draw_and_recycle():
    board = empty_board(stock=[C("c", 1), C("c", 2)], draw_count=1)
    moves = board.legal_moves()
    assert Move("draw", src=None, dst=None, count=1) in moves

    empty_stock_board = empty_board(waste=[C("s", 9)])
    moves2 = empty_stock_board.legal_moves()
    recycle_move = next(m for m in moves2 if m.kind == "recycle")
    recycled = empty_stock_board.apply(recycle_move)
    assert recycled.stock == [C("s", 9)]
    assert recycled.waste == []


def test_is_won():
    board = empty_board(foundations={"c": 13, "d": 13, "h": 13, "s": 13})
    assert board.is_won()
    board2 = empty_board(foundations={"c": 13, "d": 13, "h": 12, "s": 13})
    assert not board2.is_won()


def test_describe_shows_hidden_cards_as_unknown():
    board = empty_board(tableau=[[(C("h", 5), False), (C("s", 2), True)]] + [[] for _ in range(6)])
    text = board.describe()
    assert "[?]" in text
    assert "2♠" in text
    assert "5♥" not in text  # face-down card's identity isn't shown


def test_key_is_stable_and_distinguishes_states():
    board_a = empty_board(waste=[C("c", 1)])
    board_b = empty_board(waste=[C("c", 1)])
    board_c = empty_board(waste=[C("c", 2)])
    assert board_a.key() == board_b.key()
    assert board_a.key() != board_c.key()
