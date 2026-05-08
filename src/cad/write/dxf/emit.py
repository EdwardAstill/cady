from __future__ import annotations

from collections.abc import Iterable


def fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.8g}"
    return str(value)


def pairs(items: Iterable[tuple[int, object]]) -> list[str]:
    out: list[str] = []
    for code, value in items:
        out.append(str(code))
        out.append(fmt(value))
    return out
