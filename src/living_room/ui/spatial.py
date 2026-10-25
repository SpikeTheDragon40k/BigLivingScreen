"""Pure spatial (TV-style) focus navigation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable, Iterable


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


def _gap(a0: float, a1: float, b0: float, b1: float) -> float:
    """Distance between two 1-D intervals (0 if they overlap)."""
    if b1 < a0:
        return a0 - b1
    if b0 > a1:
        return b0 - a1
    return 0.0


def find_next(current: Rect, candidates: Iterable[tuple[Hashable, Rect]], direction: str):
    """Return the key of the best candidate in `direction` (up/down/left/right), or None."""
    best_key, best_score = None, None
    for key, r in candidates:
        if direction == "right":
            if r.cx <= current.cx + 1 or r.x < current.x + 1:
                continue
            primary = max(0.0, r.x - current.right)
            ortho = _gap(current.y, current.bottom, r.y, r.bottom)
            centre = abs(r.cy - current.cy)
        elif direction == "left":
            if r.cx >= current.cx - 1 or r.right > current.right - 1:
                continue
            primary = max(0.0, current.x - r.right)
            ortho = _gap(current.y, current.bottom, r.y, r.bottom)
            centre = abs(r.cy - current.cy)
        elif direction == "down":
            if r.cy <= current.cy + 1 or r.y < current.y + 1:
                continue
            primary = max(0.0, r.y - current.bottom)
            ortho = _gap(current.x, current.right, r.x, r.right)
            centre = abs(r.cx - current.cx)
        elif direction == "up":
            if r.cy >= current.cy - 1 or r.bottom > current.bottom - 1:
                continue
            primary = max(0.0, current.y - r.bottom)
            ortho = _gap(current.x, current.right, r.x, r.right)
            centre = abs(r.cx - current.cx)
        else:
            return None
        # Weighted distance as used by Android TV focus search: the gap along
        # the travel axis dominates; aligned candidates (ortho == 0) win ties.
        score = 13 * primary * primary + centre * centre + (0 if ortho == 0 else 1)
        if best_score is None or score < best_score:
            best_key, best_score = key, score
    return best_key
