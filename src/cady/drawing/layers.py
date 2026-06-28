"""Layer definitions for 2D drawing entities."""

from __future__ import annotations

from dataclasses import dataclass

SUPPORTED_LINETYPES = {"CONTINUOUS", "HIDDEN", "CENTER"}


def normalise_linetype(linetype: str) -> str:
    """Validate and canonicalise a DXF-style linetype name."""
    value = linetype.upper()
    if value not in SUPPORTED_LINETYPES:
        raise ValueError(f"unsupported linetype: {linetype}")
    return value


@dataclass(frozen=True, slots=True)
class Layer:
    """Named drawing layer with colour and linetype metadata."""

    name: str
    color: int = 7
    linetype: str = "CONTINUOUS"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("layer name must be non-empty")
        if isinstance(self.color, bool):
            raise TypeError("layer color must be an integer")
        if self.color < 1 or self.color > 255:
            raise ValueError("layer color must be between 1 and 255")
        object.__setattr__(self, "linetype", normalise_linetype(self.linetype))
