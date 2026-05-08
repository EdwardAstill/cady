from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from cad.errors import SceneError
from cad.geom.base import Shape2D
from cad.geom.vec import Vec2, promote2


@dataclass(slots=True)
class TextEntity:
    text: str
    at: Vec2
    height: float
    layer: str


@dataclass(slots=True)
class Layer:
    name: str
    color: int = 7
    linetype: str = "CONTINUOUS"
    entities: list[Shape2D] = field(default_factory=list[Shape2D])

    def add(self, shape: Shape2D) -> Layer:
        if not isinstance(cast(object, shape), Shape2D):
            raise SceneError("DxfDrawing layers accept Shape2D values only")
        self.entities.append(shape)
        return self


@dataclass(slots=True)
class DxfDrawing:
    layers: dict[str, Layer] = field(default_factory=dict[str, Layer])
    texts: list[TextEntity] = field(default_factory=list[TextEntity])

    def layer(self, name: str, color: int = 7) -> Layer:
        if not name:
            raise SceneError("layer name cannot be empty")
        existing = self.layers.get(name)
        if existing is not None:
            return existing
        layer = Layer(name, int(color))
        self.layers[name] = layer
        return layer

    def add_text(
        self,
        text: str,
        at: Vec2 | tuple[float, float],
        height: float,
        layer: str = "0",
    ) -> DxfDrawing:
        if height <= 0:
            raise SceneError("text height must be positive")
        self.layer(layer)
        self.texts.append(TextEntity(text, promote2(at), float(height), layer))
        return self

    def add_dimension(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError("DXF dimensions are reserved for Stage 3")

    def write(self, path: str | Path) -> DxfDrawing:
        from cad.write.dxf.sections import write_dxf

        write_dxf(self, Path(path))
        return self
