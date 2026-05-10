from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, cast

from cad.errors import SceneError
from cad.geom.base import Shape2D, Shape3D
from cad.geom.vec import Vec2
from cad.scene.dxf import DxfDrawing, Layer
from cad.scene.stl import StlMesh


def _parse_created_at(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, str):
        normalised = value.removesuffix("Z") + "+00:00" if value.endswith("Z") else value
        value = datetime.fromisoformat(normalised)
    if value.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class ModelMetadata:
    units: str = "m"
    author: str | None = None
    source: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.units != "m":
            raise ValueError("units must be 'm' in Stage 2")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))

    def to_dict(self) -> dict[str, str | None]:
        return {
            "units": self.units,
            "author": self.author,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class ModelLayer:
    name: str
    _layer: Layer

    def add(self, shape: Shape2D) -> ModelLayer:
        self._layer.add(shape)
        return self


@dataclass(slots=True)
class Drawing2D:
    name: str
    _drawing: DxfDrawing = field(default_factory=DxfDrawing)
    _layers: dict[str, ModelLayer] = field(default_factory=dict[str, ModelLayer])

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("drawing name cannot be empty")

    def layer(self, name: str, color: int = 7) -> ModelLayer:
        existing = self._layers.get(name)
        if existing is not None:
            return existing
        layer = self._drawing.layer(name, color)
        wrapped = ModelLayer(name, layer)
        self._layers[name] = wrapped
        return wrapped

    def add_text(
        self,
        text: str,
        at: Vec2 | tuple[float, float],
        height: float,
        layer: str = "0",
    ) -> Drawing2D:
        self._drawing.add_text(text, at, height, layer)
        return self

    def to_dxf_drawing(self) -> DxfDrawing:
        return self._drawing

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "layers": [
                {
                    "name": layer.name,
                    "color": layer.color,
                    "linetype": layer.linetype,
                    "entities": len(layer.entities),
                }
                for layer in self._drawing.layers.values()
            ],
        }


@dataclass(slots=True)
class Part:
    name: str
    solids: list[Shape3D] = field(default_factory=list[Shape3D])

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("part name cannot be empty")

    def add(self, *solids: Shape3D) -> Part:
        for solid in solids:
            if not isinstance(cast(object, solid), Shape3D):
                raise SceneError("Part accepts Shape3D values only")
            self.solids.append(solid)
        return self

    def to_stl_mesh(self, *, tolerance: float = 1e-3) -> StlMesh:
        return StlMesh(tolerance=tolerance).add(*self.solids)

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "solids": len(self.solids)}


@dataclass(slots=True)
class Assembly:
    name: str
    part_names: list[str] = field(default_factory=list[str])

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("assembly name cannot be empty")

    def add(self, *parts: Part | str) -> Assembly:
        for part in parts:
            name = part.name if isinstance(part, Part) else part
            if not name:
                raise ValueError("part reference cannot be empty")
            if name not in self.part_names:
                self.part_names.append(name)
        return self

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "parts": list(self.part_names)}


class Model:
    def __init__(
        self,
        name: str,
        *,
        units: str = "m",
        author: str | None = None,
        source: str | None = None,
        created_at: datetime | str | None = None,
    ) -> None:
        if not name:
            raise ValueError("model name cannot be empty")
        self.name = name
        self.metadata = ModelMetadata(
            units=units,
            author=author,
            source=source,
            created_at=_parse_created_at(created_at),
        )
        self._drawings: dict[str, Drawing2D] = {}
        self._parts: dict[str, Part] = {}
        self._assemblies: dict[str, Assembly] = {}

    def drawing(self, name: str) -> Drawing2D:
        drawing = self._drawings.get(name)
        if drawing is None:
            drawing = Drawing2D(name)
            self._drawings[name] = drawing
        return drawing

    def part(self, name: str) -> Part:
        part = self._parts.get(name)
        if part is None:
            part = Part(name)
            self._parts[name] = part
        return part

    def assembly(self, name: str) -> Assembly:
        assembly = self._assemblies.get(name)
        if assembly is None:
            assembly = Assembly(name)
            self._assemblies[name] = assembly
        return assembly

    def write_dxf(self, path: str | Path) -> Model:
        drawing = DxfDrawing()
        for source in self._drawings.values():
            dxf = source.to_dxf_drawing()
            for layer in dxf.layers.values():
                target = drawing.layer(layer.name, layer.color)
                for entity in layer.entities:
                    target.add(entity)
            for text in dxf.texts:
                drawing.add_text(text.text, text.at, text.height, text.layer)
        drawing.write(path)
        return self

    def write_stl(self, path: str | Path, *, ascii: bool = False, tolerance: float = 1e-3) -> Model:
        mesh = StlMesh(tolerance=tolerance)
        for part in self._parts.values():
            mesh.add(*part.solids)
        mesh.write(path, ascii=ascii)
        return self

    def write_step(self, path: str | Path) -> NoReturn:
        raise NotImplementedError("STEP export is reserved for Stage 5")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "metadata": self.metadata.to_dict(),
            "drawings": [drawing.to_dict() for drawing in self._drawings.values()],
            "parts": [part.to_dict() for part in self._parts.values()],
            "assemblies": [assembly.to_dict() for assembly in self._assemblies.values()],
        }
