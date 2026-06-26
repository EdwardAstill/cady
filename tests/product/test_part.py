from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cady.geometry import Mesh3D
from cady.product import Material, Part, ProductError
from cady.vec import Vec3


def _triangle(offset: float = 0.0) -> Mesh3D:
    return Mesh3D(
        (
            Vec3(offset, 0.0, 0.0),
            Vec3(offset + 1.0, 0.0, 0.0),
            Vec3(offset, 1.0, 0.0),
        ),
        ((0, 1, 2),),
    )


class MeshableBody:
    def __init__(self, mesh: Mesh3D) -> None:
        self.mesh = mesh

    def to_mesh(self, *, tolerance: float) -> Mesh3D:
        assert tolerance == 1e-3
        return self.mesh


def test_material_and_part_are_immutable_values() -> None:
    material = Material("steel", density=7850.0, color=(0.4, 0.4, 0.42))
    part = Part("plate").with_material(material).with_body(_triangle())

    assert part.material == material
    assert len(part.bodies) == 1

    with pytest.raises(FrozenInstanceError):
        part.name = "changed"  # type: ignore[misc]


def test_part_with_body_returns_new_part_and_merges_meshes() -> None:
    original = Part("bracket")
    updated = original.with_body(MeshableBody(_triangle())).with_body(_triangle(2.0))

    assert original.bodies == ()

    mesh = updated.to_mesh(tolerance=1e-3)
    assert len(mesh.vertices) == 6
    assert mesh.faces == ((0, 1, 2), (3, 4, 5))


def test_part_rejects_non_meshable_bodies() -> None:
    with pytest.raises(ProductError):
        Part("bad").with_body(object())


def test_empty_part_meshes_to_empty_mesh() -> None:
    mesh = Part("empty").to_mesh(tolerance=1e-3)

    assert mesh.vertices == ()
    assert mesh.faces == ()
