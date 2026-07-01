from solitaire.board import Board
from solitaire.cards import Card
from solitaire.moves import Move
from llm_player import _format_history, _format_moves, _parse_index

C = Card


def test_format_moves_numbers_each_move():
    moves = [
        Move("draw", src=None, dst=None, count=1),
        Move("tableau_to_foundation", src=2, dst=None, count=1),
    ]
    text = _format_moves(moves)
    assert "0: draw 1" in text
    assert "1: tableau[2] -> foundation" in text


def test_parse_index_valid_json():
    assert _parse_index('{"index": 2}', num_moves=5) == 2


def test_parse_index_out_of_range_rejected():
    assert _parse_index('{"index": 5}', num_moves=5) is None
    assert _parse_index('{"index": -1}', num_moves=5) is None


def test_parse_index_malformed_rejected():
    assert _parse_index("not json", num_moves=5) is None
    assert _parse_index('{"wrong_key": 1}', num_moves=5) is None


def test_format_history_empty():
    assert "first move" in _format_history([])


def test_format_history_lists_moves_in_order():
    history = [
        Move("tableau_to_tableau", src=1, dst=6, count=4),
        Move("tableau_to_tableau", src=6, dst=1, count=4),
    ]
    text = _format_history(history)
    lines = text.splitlines()
    assert "tableau[1] (x4) -> tableau[6]" in lines[0]
    assert "tableau[6] (x4) -> tableau[1]" in lines[1]
