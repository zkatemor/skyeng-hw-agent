"""LLM-driven move selection: an independent alternative to solitaire.solver,
used with `run.py --mode llm`, to compare against the deterministic solver.

One API call per turn — the model picks from the exact list of legal moves (it
can't propose an illegal one) given the board as plain text. There's no agent
framework or tool-calling loop here, unlike the old Skyeng project: the model
has nothing to *do* except choose an index, so a single chat completion per
turn is enough. See doc/adr/0005.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI

from solitaire.board import Board
from solitaire.moves import Move

load_dotenv(Path(__file__).parent / ".env")

_SYSTEM_PROMPT = """\
You are playing Klondike Solitaire. You will be shown the current board, your
recent move history, and a numbered list of legal moves. Pick the move that
makes the most progress toward winning: prefer moves that get cards to the
foundations or reveal face-down cards.

Check your recent move history before answering. If your last move moved a
run from column A to column B, do NOT immediately move it back from B to A —
that undoes your own progress and creates an infinite loop. If undoing the
last move is the only option that looks appealing, prefer drawing from the
stock or making a different move entirely instead.

Respond with ONLY a JSON object: {"index": N} where N is the number of your
chosen move from the list. No other text.
"""

_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
    return _client


def _format_moves(moves: list[Move]) -> str:
    return "\n".join(f"{i}: {move}" for i, move in enumerate(moves))


def _parse_index(content: str, num_moves: int) -> Optional[int]:
    try:
        data = json.loads(content)
        index = int(data["index"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
    return index if 0 <= index < num_moves else None


def _format_history(history: list[Move]) -> str:
    if not history:
        return "(none yet — this is your first move)"
    return "\n".join(f"- {move}" for move in history)


async def choose_move(
    board: Board,
    legal_moves: list[Move],
    history: Optional[list[Move]] = None,
    model: Optional[str] = None,
) -> Move:
    """Ask the LLM to pick one of the given legal moves.

    `history` is the last few moves actually made (most recent last) — without
    it the model has no way to notice it's undoing its own previous move and
    will happily ping-pong between two columns forever.

    Falls back to the first legal move if the response can't be parsed after
    a few retries — an occasional malformed response shouldn't stall the game.
    """
    if len(legal_moves) == 1:
        return legal_moves[0]

    client = _get_client()
    model = model or os.getenv("MODEL", "gpt-4o-mini")
    user_prompt = (
        f"{board.describe()}\n\n"
        f"Your recent moves (oldest to most recent):\n{_format_history(history or [])}\n\n"
        f"Legal moves:\n{_format_moves(legal_moves)}"
    )

    for _attempt in range(3):
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
        index = _parse_index(content, len(legal_moves))
        if index is not None:
            return legal_moves[index]

    return legal_moves[0]
