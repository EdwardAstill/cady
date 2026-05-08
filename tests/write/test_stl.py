from __future__ import annotations

import struct
from math import isclose

import pytest

from cad import StlMesh, WriteError, prism, rectangle, sphere
from cad.write.stl.ascii import write_ascii_stl
from cad.write.stl.binary import write_binary_stl


def test_binary_prism_invariants(tmp_path) -> None:
    path = tmp_path / "box.stl"
    StlMesh().add(prism((0, 0, 0), (2, 2, 1))).write(path)
    data = path.read_bytes()
    assert len(data) == 84 + 12 * 50
    assert struct.unpack("<I", data[80:84]) == (12,)
    for idx in range(12):
        normal = struct.unpack("<3f", data[84 + idx * 50 : 96 + idx * 50])
        assert isclose(sum(n * n for n in normal), 1.0, rel_tol=1e-6)


def test_ascii_stl_tokens(tmp_path) -> None:
    path = tmp_path / "box_ascii.stl"
    StlMesh().add(prism((0, 0, 0), (2, 2, 1))).write(path, ascii=True)
    text = path.read_text(encoding="ascii")
    assert text.startswith("solid")
    assert text.strip().endswith("endsolid")
    assert text.count("facet normal") == 12


def test_stl_dispatcher() -> None:
    mesh = StlMesh(tolerance=2e-2).add(
        rectangle((0, 0), (1, 1)).extrude("+z", 0.1), sphere((0, 0, 0), 0.5)
    )
    assert len(mesh.triangles) > 12


def test_stl_empty_writeerror(tmp_path) -> None:
    with pytest.raises(WriteError):
        write_binary_stl([], tmp_path / "empty.stl")
    with pytest.raises(WriteError):
        write_ascii_stl([], tmp_path / "empty.stl")


def test_self_intersecting_profile_writeerror() -> None:
    from cad import polyline

    bad = polyline([(0, 0), (1, 1), (0, 1), (1, 0)], closed=True)
    with pytest.raises(WriteError, match="first 3 points"):
        StlMesh().add(bad.extrude("+z", 1))
