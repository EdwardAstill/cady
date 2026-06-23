from __future__ import annotations

import pytest

from cady import FacetedMesh, Vec3
from cady.errors import ReadError
from cady.files import dxf


def _dxf_entities(*entities: str) -> str:
    return "\n".join(("0", "SECTION", "2", "ENTITIES", *entities, "0", "ENDSEC", "0", "EOF", ""))


def test_read_mesh_imports_3dface_triangle(tmp_path) -> None:
    path = tmp_path / "triangle.dxf"
    path.write_text(
        _dxf_entities(
            "0",
            "3DFACE",
            "8",
            "FACETS",
            "10",
            "0",
            "20",
            "0",
            "30",
            "0",
            "11",
            "1",
            "21",
            "0",
            "31",
            "0",
            "12",
            "0",
            "22",
            "1",
            "32",
            "0",
            "13",
            "0",
            "23",
            "1",
            "33",
            "0",
        ),
        encoding="ascii",
    )

    mesh = dxf.read_mesh(path)

    assert isinstance(mesh, FacetedMesh)
    assert mesh.vertices == (Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0))
    assert mesh.faces == ((0, 1, 2),)


def test_read_mesh_imports_3dface_quad_as_two_triangles(tmp_path) -> None:
    path = tmp_path / "quad.dxf"
    path.write_text(
        _dxf_entities(
            "0",
            "3DFACE",
            "10",
            "0",
            "20",
            "0",
            "30",
            "0",
            "11",
            "1",
            "21",
            "0",
            "31",
            "0",
            "12",
            "1",
            "22",
            "1",
            "32",
            "0",
            "13",
            "0",
            "23",
            "1",
            "33",
            "0",
        ),
        encoding="ascii",
    )

    mesh = dxf.read_mesh(path)

    assert mesh.vertices == (Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(1, 1, 0), Vec3(0, 1, 0))
    assert mesh.faces == ((0, 1, 2), (0, 2, 3))


def test_read_3d_reports_unsupported_acis_entities() -> None:
    result = dxf.parse_dxf_3d(
        _dxf_entities(
            "0",
            "3DSOLID",
            "8",
            "SOLIDS",
            "1",
            "ACIS-data",
        )
    )

    assert result.meshes == ()
    assert result.skipped[0].entity_type == "3DSOLID"
    assert result.skipped[0].layer == "SOLIDS"
    assert "ACIS" in result.skipped[0].reason


def test_read_mesh_rejects_dxf_without_supported_mesh_geometry(tmp_path) -> None:
    path = tmp_path / "empty.dxf"
    path.write_text(
        _dxf_entities(
            "0",
            "LINE",
            "10",
            "0",
            "20",
            "0",
            "11",
            "1",
            "21",
            "1",
        ),
        encoding="ascii",
    )

    with pytest.raises(ReadError, match="no supported mesh"):
        dxf.read_mesh(path)
