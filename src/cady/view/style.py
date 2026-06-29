"""Display style values shared across viewer backends."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from math import isfinite
from typing import Any, Literal, cast

from cady.product.material import Color, Metadata, metadata_items, rgb
from cady.view.errors import ViewError

RenderMode = Literal["shaded", "wireframe", "points"]


@dataclass(frozen=True, slots=True)
class DisplayStyle:
    """Rendering hints for a scene object."""

    color: Color | None = None
    opacity: float = 1.0
    line_width: float = 1.0
    point_size: float = 4.0
    render_mode: RenderMode = "shaded"
    visible: bool = True
    metadata: Metadata = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "color", rgb(self.color))
        if not isfinite(self.opacity) or self.opacity < 0.0 or self.opacity > 1.0:
            raise ViewError("opacity must be between 0 and 1")
        if not isfinite(self.line_width) or self.line_width <= 0.0:
            raise ViewError("line_width must be positive")
        if not isfinite(self.point_size) or self.point_size <= 0.0:
            raise ViewError("point_size must be positive")
        if self.render_mode not in ("shaded", "wireframe", "points"):
            raise ViewError("render_mode must be 'shaded', 'wireframe', or 'points'")
        object.__setattr__(self, "metadata", metadata_items(self.metadata))

    def with_metadata(self, **metadata: Any) -> DisplayStyle:
        """Return a copy with merged metadata."""
        return replace(self, metadata=metadata_items(dict(self.metadata) | metadata))


def style_from_mapping(values: Mapping[str, object]) -> DisplayStyle:
    """Create a display style from a plain mapping."""
    opacity = cast(float | str, values.get("opacity", 1.0))
    line_width = cast(float | str, values.get("line_width", 1.0))
    point_size = cast(float | str, values.get("point_size", 4.0))
    return DisplayStyle(
        color=cast(Color | None, values.get("color")),
        opacity=float(opacity),
        line_width=float(line_width),
        point_size=float(point_size),
        render_mode=values.get("render_mode", "shaded"),  # type: ignore[arg-type]
        visible=bool(values.get("visible", True)),
    )


__all__ = ["DisplayStyle", "RenderMode", "style_from_mapping"]
