"""Card representation and DOM class-name parsing."""
from __future__ import annotations

import re
from dataclasses import dataclass

SUITS = ("c", "d", "h", "s")
RED_SUITS = {"d", "h"}
RANK_NAMES = {1: "A", 11: "J", 12: "Q", 13: "K"}
SUIT_SYMBOLS = {"c": "♣", "d": "♦", "h": "♥", "s": "♠"}

_CARD_CLASS_RE = re.compile(r"\b([cdhs])(\d{1,2})\b")


@dataclass(frozen=True)
class Card:
    suit: str  # one of SUITS
    rank: int  # 1 (Ace) .. 13 (King)

    @property
    def is_red(self) -> bool:
        return self.suit in RED_SUITS

    @classmethod
    def parse(cls, class_name: str) -> "Card":
        """Parse a card from a DOM class like 'card h11' or 'card d5 up'."""
        match = _CARD_CLASS_RE.search(class_name)
        if not match:
            raise ValueError(f"cannot parse card from class {class_name!r}")
        return cls(suit=match.group(1), rank=int(match.group(2)))

    def __str__(self) -> str:
        return f"{RANK_NAMES.get(self.rank, str(self.rank))}{SUIT_SYMBOLS[self.suit]}"

    def __repr__(self) -> str:
        return str(self)
