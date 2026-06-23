from __future__ import annotations

from cady import Vec3
from cady.files import dxf


def _dxf_entities(*entities: str) -> str:
    return "\n".join(("0", "SECTION", "2", "ENTITIES", *entities, "0", "ENDSEC", "0", "EOF", ""))


def test_read_mesh_imports_polyface_triangle(tmp_path) -> None:
    path = tmp_path / "polyface.dxf"
    path.write_text(
        _dxf_entities(
            "0",
            "POLYLINE",
            "8",
            "MESH",
            "70",
            "64",
            "0",
            "VERTEX",
            "70",
            "64",
            "10",
            "0",
            "20",
            "0",
            "30",
            "0",
            "0",
            "VERTEX",
            "70",
            "64",
            "10",
            "1",
            "20",
            "0",
            "30",
            "0",
            "0",
            "VERTEX",
            "70",
            "64",
            "10",
            "0",
            "20",
            "1",
            "30",
            "0",
            "0",
            "VERTEX",
            "70",
            "128",
            "71",
            "1",
            "72",
            "2",
            "73",
            "3",
            "0",
            "SEQEND",
        ),
        encoding="ascii",
    )

    mesh = dxf.read_mesh(path)

    assert mesh.vertices == (Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0))
    assert mesh.faces == ((0, 1, 2),)


def test_read_mesh_imports_polyface_quad_with_negative_invisible_edge_index(tmp_path) -> None:
    path = tmp_path / "polyface-quad.dxf"
    path.write_text(
        _dxf_entities(
            "0",
            "POLYLINE",
            "70",
            "64",
            "0",
            "VERTEX",
            "70",
            "64",
            "10",
            "0",
            "20",
            "0",
            "30",
            "0",
            "0",
            "VERTEX",
            "70",
            "64",
            "10",
            "1",
            "20",
            "0",
            "30",
            "0",
            "0",
            "VERTEX",
            "70",
            "64",
            "10",
            "1",
            "20",
            "1",
            "30",
            "0",
            "0",
            "VERTEX",
            "70",
            "64",
            "10",
            "0",
            "20",
            "1",
            "30",
            "0",
            "0",
            "VERTEX",
            "70",
            "128",
            "71",
            "1",
            "72",
            "2",
            "73",
            "-3",
            "74",
            "4",
            "0",
            "SEQEND",
        ),
        encoding="ascii",
    )

    mesh = dxf.read_mesh(path)

    assert mesh.faces == ((0, 1, 2), (0, 2, 3))
