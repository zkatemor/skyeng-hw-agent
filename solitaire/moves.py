"""Move representation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# kind is one of:
#   tableau_to_foundation, tableau_to_tableau, waste_to_foundation,
#   waste_to_tableau, draw, recycle


@dataclass(frozen=True)
class Move:
    kind: str
    src: Optional[int]
    dst: Optional[int]
    count: int

    def __str__(self) -> str:
        if self.kind == "tableau_to_foundation":
            return f"tableau[{self.src}] -> foundation"
        if self.kind == "tableau_to_tableau":
            return f"tableau[{self.src}] (x{self.count}) -> tableau[{self.dst}]"
        if self.kind == "waste_to_foundation":
            return "waste -> foundation"
        if self.kind == "waste_to_tableau":
            return f"waste -> tableau[{self.dst}]"
        if self.kind == "draw":
            return f"draw {self.count}"
        if self.kind == "recycle":
            return "recycle stock"
        return self.kind
