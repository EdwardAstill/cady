from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from cady.product.material import Metadata, metadata_items

DocumentKind = Literal["drawing", "part", "assembly", "scene"]


@dataclass(frozen=True, slots=True)
class DocumentItem:
    name: str
    value: object
    kind: DocumentKind

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("document item name cannot be empty")
        if self.value is None:
            raise ValueError("document item value cannot be None")
        if self.kind not in ("drawing", "part", "assembly", "scene"):
            raise ValueError("invalid document item kind")


@dataclass(frozen=True, slots=True)
class Document:
    name: str = "document"
    units: str = "m"
    drawings: tuple[DocumentItem, ...] = field(default_factory=tuple)
    parts: tuple[DocumentItem, ...] = field(default_factory=tuple)
    assemblies: tuple[DocumentItem, ...] = field(default_factory=tuple)
    scenes: tuple[DocumentItem, ...] = field(default_factory=tuple)
    metadata: Metadata = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("document name cannot be empty")
        if not self.units:
            raise ValueError("document units cannot be empty")
        object.__setattr__(self, "drawings", tuple(self.drawings))
        object.__setattr__(self, "parts", tuple(self.parts))
        object.__setattr__(self, "assemblies", tuple(self.assemblies))
        object.__setattr__(self, "scenes", tuple(self.scenes))
        object.__setattr__(self, "metadata", metadata_items(self.metadata))
        _reject_duplicates(self.drawings, "drawing")
        _reject_duplicates(self.parts, "part")
        _reject_duplicates(self.assemblies, "assembly")
        _reject_duplicates(self.scenes, "scene")

    def add_drawing(self, drawing: object, *, name: str | None = None) -> Document:
        return self._add("drawing", drawing, name=name)

    def add_part(self, part: object, *, name: str | None = None) -> Document:
        return self._add("part", part, name=name)

    def add_assembly(self, assembly: object, *, name: str | None = None) -> Document:
        return self._add("assembly", assembly, name=name)

    def add_scene(self, scene: object, *, name: str | None = None) -> Document:
        return self._add("scene", scene, name=name)

    def with_metadata(self, **metadata: Any) -> Document:
        return Document(
            name=self.name,
            units=self.units,
            drawings=self.drawings,
            parts=self.parts,
            assemblies=self.assemblies,
            scenes=self.scenes,
            metadata=metadata_items(dict(self.metadata) | metadata),
        )

    def get(self, kind: DocumentKind, name: str) -> object:
        for item in self._items(kind):
            if item.name == name:
                return item.value
        raise KeyError(f"no {kind} named {name!r}")

    def names(self, kind: DocumentKind) -> tuple[str, ...]:
        return tuple(item.name for item in self._items(kind))

    def _add(self, kind: DocumentKind, value: object, *, name: str | None = None) -> Document:
        item = DocumentItem(_item_name(value, name), value, kind)
        target = self._items(kind)
        if any(existing.name == item.name for existing in target):
            raise ValueError(f"duplicate {kind} name: {item.name}")
        return Document(
            name=self.name,
            units=self.units,
            drawings=(*self.drawings, item) if kind == "drawing" else self.drawings,
            parts=(*self.parts, item) if kind == "part" else self.parts,
            assemblies=(*self.assemblies, item) if kind == "assembly" else self.assemblies,
            scenes=(*self.scenes, item) if kind == "scene" else self.scenes,
            metadata=self.metadata,
        )

    def _items(self, kind: DocumentKind) -> tuple[DocumentItem, ...]:
        if kind == "drawing":
            return self.drawings
        if kind == "part":
            return self.parts
        if kind == "assembly":
            return self.assemblies
        if kind == "scene":
            return self.scenes
        raise ValueError("invalid document item kind")


def _item_name(value: object, explicit: str | None) -> str:
    if explicit is not None:
        if not explicit:
            raise ValueError("document item name cannot be empty")
        return explicit
    value_name = getattr(value, "name", None)
    if isinstance(value_name, str) and value_name:
        return value_name
    raise ValueError("document item name is required when value has no name")


def _reject_duplicates(items: Iterable[DocumentItem], kind: str) -> None:
    names = [item.name for item in items]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate {kind} names are not allowed")


def document_from_mapping(
    *,
    name: str = "document",
    units: str = "m",
    metadata: Mapping[str, Any] | Metadata | None = None,
) -> Document:
    return Document(name=name, units=units, metadata=metadata_items(metadata))


__all__ = ["Document", "DocumentItem", "DocumentKind", "document_from_mapping"]
