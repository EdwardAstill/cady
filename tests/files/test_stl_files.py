from __future__ import annotations

import struct

from cady import Model, prism
from cady.domain import StlMesh
from cady.files import stl


def test_write_mesh_creates_stl_file(tmp_path) -> None:
    path = tmp_path / "mesh.stl"
    mesh = StlMesh(tolerance=1e-3).add(prism((0, 0, 0), (1, 1, 1)))

    assert stl.write_mesh(mesh, path) is mesh
    data = path.read_bytes()
    assert struct.unpack("<I", data[80:84])[0] == 12


def test_write_model_creates_stl_file(tmp_path) -> None:
    path = tmp_path / "model.stl"
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    model.part("box").add(prism((0, 0, 0), (1, 1, 1)))

    assert stl.write_model(model, path, tolerance=1e-3) is model
    data = path.read_bytes()
    assert struct.unpack("<I", data[80:84])[0] == 12
