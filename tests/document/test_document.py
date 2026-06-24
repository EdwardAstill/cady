from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass

import pytest

from cady.document import Document
from cady.product import Assembly, Part
from cady.view import Scene


@dataclass(frozen=True, slots=True)
class NamedDrawing:
    name: str


def test_document_registry_stores_named_contents_immutably() -> None:
    drawing = NamedDrawing("front")
    part = Part("plate")
    assembly = Assembly("assy").add(part)
    scene = Scene.from_assembly(assembly)

    document = (
        Document("job", units="mm")
        .add_drawing(drawing)
        .add_part(part)
        .add_assembly(assembly)
        .add_scene(scene, name="main")
        .with_metadata(author="cady")
    )

    assert document.names("drawing") == ("front",)
    assert document.names("part") == ("plate",)
    assert document.get("assembly", "assy") is assembly
    assert document.get("scene", "main") is scene
    assert dict(document.metadata) == {"author": "cady"}

    with pytest.raises(FrozenInstanceError):
        document.units = "m"  # type: ignore[misc]


def test_document_add_methods_return_new_documents_and_reject_duplicates() -> None:
    part = Part("plate")
    original = Document("job")
    updated = original.add_part(part)

    assert original.parts == ()
    assert updated.names("part") == ("plate",)

    with pytest.raises(ValueError):
        updated.add_part(part)
    with pytest.raises(ValueError):
        original.add_drawing(object())
    with pytest.raises(KeyError):
        original.get("part", "missing")
