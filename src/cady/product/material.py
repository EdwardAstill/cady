from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Any

Metadata = tuple[tuple[str, Any], ...]
Color = tuple[float, float, float]


def metadata_items(value: Mapping[str, Any] | Metadata | None) -> Metadata:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    return tuple(sorted((str(key), item) for key, item in value.items()))


def rgb(value: object | None, *, name: str = "color") -> Color | None:
    if value is None:
        return None
    try:
        raw = tuple(float(component) for component in value)  # type: ignore[reportUnknownVariableType]
    except TypeError as exc:
        raise ValueError(f"{name} must be an RGB triple") from exc
    if len(raw) != 3 or any(not isfinite(component) for component in raw):
        raise ValueError(f"{name} must be a finite RGB triple")
    if any(component < 0.0 or component > 1.0 for component in raw):
        raise ValueError(f"{name} components must be between 0 and 1")
    return raw


@dataclass(frozen=True, slots=True)
class Material:
    name: str
    density: float | None = None
    color: Color | None = None
    metadata: Metadata = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("material name cannot be empty")
        if self.density is not None and (not isfinite(self.density) or self.density <= 0.0):
            raise ValueError("density must be a positive finite value")
        object.__setattr__(self, "color", rgb(self.color))
        object.__setattr__(self, "metadata", metadata_items(self.metadata))

    def with_metadata(self, **metadata: Any) -> Material:
        return Material(
            self.name,
            density=self.density,
            color=self.color,
            metadata=metadata_items(dict(self.metadata) | metadata),
        )


__all__ = ["Color", "Material", "Metadata", "metadata_items", "rgb"]
