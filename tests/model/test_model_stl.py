from __future__ import annotations

import struct

import pytest

from cady import Model, SceneError, circle, prism, rectangle
from cady.domain import StlMesh


def test_part_add_delegates_to_stl_mesh() -> None:
    part = Model("demo", created_at="2026-05-08T00:00:00Z").part("box")
    assert part.add(prism((0, 0, 0), (1, 1, 1))) is part
    mesh = part.to_stl_mesh(tolerance=1e-3)
    assert isinstance(mesh, StlMesh)
    assert len(mesh.triangles) == 12


def test_part_rejects_2d_shapes() -> None:
    part = Model("demo", created_at="2026-05-08T00:00:00Z").part("bad")
    with pytest.raises(SceneError):
        part.add(circle((0, 0), 1))  # type: ignore[arg-type]


def test_model_write_stl_combines_parts(tmp_path) -> None:
    path = tmp_path / "model.stl"
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    model.part("box").add(prism((0, 0, 0), (1, 1, 1)))
    model.part("plate").add(rectangle((0, 0), (1, 1)).extrude("+z", 0.1))

    assert model.write_stl(path, tolerance=1e-3) is model

    data = path.read_bytes()
    assert struct.unpack("<I", data[80:84])[0] > 12
