# src/cady/write/step/ids.py
from __future__ import annotations


class IdAllocator:
    """Sequential entity ID counter and registry for a STEP DATA section."""

    def __init__(self) -> None:
        self._n = 0
        self._lines: list[str] = []

    def add(self, definition: str) -> int:
        self._n += 1
        self._lines.append(f"#{self._n}={definition};")
        return self._n

    def render_data(self) -> str:
        return "\n".join(self._lines)
