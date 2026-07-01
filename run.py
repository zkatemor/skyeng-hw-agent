"""CLI entry point: solves a Klondike deal on cardgames.io/solitaire and plays it.

Two independent move-selection modes (--mode solver | llm), sharing the same
browser driver and Board model, so their results are directly comparable —
see doc/adr/0005.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from browser import SolitaireBrowser
from solitaire.board import Board
from solitaire.moves import Move

# Loaded here (not just inside llm_player) so --mode llm's upfront API-key
# check below sees it before llm_player is ever imported.
load_dotenv(Path(__file__).parent / ".env")
from solitaire.solver import solve

MAX_RESOLVES = 5
MAX_LLM_MOVES = 300


async def _play_solver(browser: SolitaireBrowser, board: Board) -> Board:
    """Play a solved plan, verifying each move against the real DOM. A move that
    doesn't land as expected is retried once (timing glitch); if it still
    doesn't match, the true board is re-read and re-solved from scratch. Bounded
    by MAX_RESOLVES so a persistently broken move can't loop forever."""
    result = solve(board)
    plan = result.moves
    outcome = "WIN" if result.won else "best effort"
    print(f"\nSolver: {outcome} — {result.cards_home}/52 home, {len(plan)} moves planned.")

    current = board
    resolves = 0
    i = 0
    while i < len(plan):
        move = plan[i]
        print(f"[{i + 1}/{len(plan)}] {move}")
        expected = current.apply(move)

        await browser.execute_move(move, current)
        actual = await browser.read_board()
        if actual.key() != expected.key():
            print("  did not land as expected — retrying once")
            await browser.execute_move(move, current)
            actual = await browser.read_board()

        if actual.key() == expected.key():
            current = expected
            i += 1
            continue

        resolves += 1
        if resolves > MAX_RESOLVES:
            print(f"\nGiving up after {resolves} re-solves — stuck at {sum(actual.foundations.values())}/52 cards home.")
            return actual

        print(f"  still off — re-reading the board and re-solving ({resolves}/{MAX_RESOLVES})")
        current = actual
        result = solve(current)
        plan = result.moves
        i = 0
        outcome = "WIN" if result.won else "best effort"
        print(f"  new plan: {outcome} — {result.cards_home}/52 home, {len(plan)} moves.")

    return current


LLM_HISTORY_LENGTH = 6


async def _play_llm(browser: SolitaireBrowser, board: Board) -> Board:
    """Play turn by turn, asking an LLM to pick the next move from the exact
    legal-move list each time. No plan to invalidate — every turn re-reads the
    real board, so there's nothing to verify against an "expected" state.

    Without a transposition table, the model can revisit a state it's already
    seen — e.g. ping-ponging a run between two columns (A->B, B->A, A->B, ...).
    That's a period-2 cycle, so checking only for N *consecutive* identical
    states misses it; instead every state seen this game is tracked, and play
    stops the instant any state repeats at all.
    """
    from llm_player import choose_move  # imported lazily: only needed for this mode

    seen = {board.key()}
    history: list[Move] = []
    current = board
    moves_made = 0

    while moves_made < MAX_LLM_MOVES:
        if current.is_won():
            break

        legal = current.legal_moves()
        if not legal:
            print("\nNo legal moves — stuck.")
            break

        move = await choose_move(current, legal, history=history[-LLM_HISTORY_LENGTH:])
        moves_made += 1
        print(f"[{moves_made}] LLM chooses: {move}")

        await browser.execute_move(move, current)
        current = await browser.read_board()
        history.append(move)

        if current.key() in seen:
            print("\nLLM revisited a state it's already seen (cycling) — stopping.")
            break
        seen.add(current.key())

    return current


async def _run(game: Optional[int], dry_run: bool, headless: bool, mode: str) -> None:
    if mode == "llm" and not os.getenv("OPENAI_API_KEY"):
        print("ERROR: --mode llm requires OPENAI_API_KEY (copy .env.example to .env and fill it in).")
        return

    browser = SolitaireBrowser(headless=headless)
    await browser.start(game_number=game)
    try:
        board = await browser.read_board()
        print(board.describe())
        if dry_run:
            return

        if mode == "llm":
            await _play_llm(browser, board)
        else:
            await _play_solver(browser, board)

        final = await browser.read_board()
        if final.is_won():
            print("\nSolved!")
        else:
            print(f"\nStopped: {sum(final.foundations.values())}/52 cards home.")
    finally:
        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-solve Klondike Solitaire on cardgames.io")
    parser.add_argument("--game", type=int, default=None, help="Numbered game to play, for reproducible testing")
    parser.add_argument("--dry-run", action="store_true", help="Only read and print the board, don't play")
    parser.add_argument("--headless", action="store_true", help="Run Chromium headless")
    parser.add_argument(
        "--mode",
        choices=["solver", "llm"],
        default="solver",
        help="'solver' (default): deterministic Python search. 'llm': an LLM picks each move — requires .env.",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.game, args.dry_run, args.headless, args.mode))


if __name__ == "__main__":
    main()
