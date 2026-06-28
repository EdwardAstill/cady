from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from cady.errors import ReadError
from cady.geometry import Mesh3
from cady.operations.transforms import Transform3


def test_mesh_triangles_bounds_and_transform() -> None:
    mesh = Mesh3(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
    )

    assert mesh.triangles == (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),)
    assert mesh.bounds() == ((0.0, 0.0, 0.0), (1.0, 1.0, 0.0))

    moved = mesh.transformed(Transform3.translation(0.0, 0.0, 2.0))
    assert moved.bounds() == ((0.0, 0.0, 2.0), (1.0, 1.0, 2.0))


def test_mesh_mirror_reflects_about_plane_and_reverses_face_winding() -> None:
    mesh = Mesh3(
        ((1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (1.0, 0.0, 1.0)),
        ((0, 1, 2),),
        ((0, 1),),
    )

    mirrored = mesh.mirror((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))

    assert [point for point in mirrored.vertices] == [
        (-1.0, 0.0, 0.0),
        (-1.0, 1.0, 0.0),
        (-1.0, 0.0, 1.0),
    ]
    assert mirrored.faces == ((0, 2, 1),)
    assert mirrored.edges == mesh.edges


def test_mesh_to_array_requires_explicit_positive_tolerance() -> None:
    mesh = Mesh3(((0.0, 0.0, 0.0),), ())

    with pytest.raises(ValueError, match="tolerance"):
        mesh.to_array(tolerance=0.0)


def test_mesh_to_array_and_merged_offsets_faces() -> None:
    first = Mesh3(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
    )
    second = Mesh3(
        ((0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (0.0, 1.0, 1.0)),
        ((0, 1, 2),),
    )

    merged = Mesh3.merged((first, second))
    vertices, faces, _edges = merged.to_array(tolerance=1e-3)

    assert vertices.shape == (6, 3)
    np.testing.assert_array_equal(faces, [[0, 1, 2], [3, 4, 5]])


def test_mesh_edges_round_trip_through_array_transform_and_merge() -> None:
    mesh = Mesh3(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        (),
        ((0, 1),),
    )

    _vertices, _faces, edges = mesh.to_array(tolerance=1e-3)
    moved = mesh.transformed(Transform3.translation(0.0, 0.0, 2.0))
    merged = Mesh3.merged((mesh, moved))

    np.testing.assert_array_equal(edges, [[0, 1]])
    assert moved.edges == ((0, 1),)
    assert merged.edges == ((0, 1), (2, 3))


def test_dxf_read_wireframe_converts_polyline_wires_to_wireframe(tmp_path: Path) -> None:
    from cady.files import dxf

    path = tmp_path / "wire.dxf"
    path.write_text(
        "\n".join(
            [
                "0",
                "SECTION",
                "2",
                "ENTITIES",
                "0",
                "POLYLINE",
                "8",
                "WATERLINES",
                "66",
                "1",
                "0",
                "VERTEX",
                "10",
                "0",
                "20",
                "0",
                "30",
                "1",
                "0",
                "VERTEX",
                "10",
                "2",
                "20",
                "0",
                "30",
                "3",
                "0",
                "VERTEX",
                "10",
                "4",
                "20",
                "1",
                "30",
                "5",
                "0",
                "SEQEND",
                "0",
                "ENDSEC",
                "0",
                "EOF",
            ]
        )
        + "\n",
        encoding="ascii",
    )

    wf = dxf.read_wireframe(path)

    assert [point for point in wf.vertices] == [
        (0.0, 0.0, 1.0),
        (2.0, 0.0, 3.0),
        (4.0, 1.0, 5.0),
    ]
    assert wf.edges == ((0, 1), (1, 2))


def test_dxf_read_mesh_rejects_polyline_mesh_conversion_kwargs(tmp_path: Path) -> None:
    from cady.files import dxf

    path = tmp_path / "wire_mesh.dxf"
    path.write_text(
        "\n".join(
            [
                "0",
                "SECTION",
                "2",
                "ENTITIES",
                "0",
                "POLYLINE",
                "8",
                "WATERLINES",
                "66",
                "1",
                "0",
                "VERTEX",
                "10",
                "0",
                "20",
                "1",
                "30",
                "0",
                "0",
                "VERTEX",
                "10",
                "2",
                "20",
                "1",
                "30",
                "0",
                "0",
                "SEQEND",
                "0",
                "ENDSEC",
                "0",
                "EOF",
            ]
        )
        + "\n",
        encoding="ascii",
    )

    with pytest.raises(ReadError, match="no longer converts DXF line geometry"):
        dxf.read_mesh(
            path,
            mirror_origin=(0.0, 0.0, 0.0),
            mirror_normal=(1.0, 0.0, 0.0),
        )

    with pytest.raises(ReadError, match="DXF contained no supported mesh geometry"):
        dxf.read_mesh(path)


def test_dxf_read_mesh_no_longer_lofts_section_wires_to_faces(tmp_path: Path) -> None:
    from cady.files import dxf

    path = tmp_path / "section_mesh.dxf"
    path.write_text(
        "\n".join(
            [
                "0",
                "SECTION",
                "2",
                "ENTITIES",
                *_section_polyline_dxf(x=0.0),
                *_section_polyline_dxf(x=2.0),
                "0",
                "ENDSEC",
                "0",
                "EOF",
            ]
        )
        + "\n",
        encoding="ascii",
    )

    with pytest.raises(ReadError, match="no longer converts DXF line geometry"):
        dxf.read_mesh(
            path,
            mirror_origin=(0.0, 0.0, 0.0),
            mirror_normal=(1.0, 0.0, 0.0),
        )

    with pytest.raises(ReadError, match="DXF contained no supported mesh geometry"):
        dxf.read_mesh(path)

    curves = dxf.read_curves(path)
    assert len(curves) == 2
    assert all(curve.layer == "SECTIONS" for curve in curves)
    assert [curve.constant_x for curve in curves] == [True, True]


def test_dxf_curves_preserve_source_wires_separately_from_mesh(
    tmp_path: Path,
) -> None:
    from cady.files import dxf

    path = tmp_path / "section_mesh_with_guide.dxf"
    path.write_text(
        "\n".join(
            [
                "0",
                "SECTION",
                "2",
                "ENTITIES",
                *_section_polyline_dxf(x=0.0),
                *_section_polyline_dxf(x=2.0),
                *_guide_polyline_dxf(),
                "0",
                "ENDSEC",
                "0",
                "EOF",
            ]
        )
        + "\n",
        encoding="ascii",
    )

    with pytest.raises(ReadError, match="DXF contained no supported mesh geometry"):
        dxf.read_mesh(path)

    curves = dxf.read_curves(path)
    assert [curve.layer for curve in curves] == ["SECTIONS", "SECTIONS", "GUIDES"]
    assert [curve.source_index for curve in curves] == [0, 1, 2]
    assert curves[2].constant_x is False
    assert curves[2].constant_y is True
    assert curves[2].constant_z is True

    wireframe = dxf.read_wireframe(path)
    assert len(wireframe.vertices) == 10
    assert len(wireframe.edges) == 7


def _section_polyline_dxf(*, x: float) -> list[str]:
    lines = [
        "0",
        "POLYLINE",
        "8",
        "SECTIONS",
        "66",
        "1",
    ]
    for y, z in ((0.0, 0.0), (0.5, 1.0), (1.0, 2.0), (1.5, 3.0)):
        lines.extend(
            [
                "0",
                "VERTEX",
                "10",
                str(x),
                "20",
                str(y),
                "30",
                str(z),
            ]
        )
    lines.extend(["0", "SEQEND"])
    return lines


def _guide_polyline_dxf() -> list[str]:
    return [
        "0",
        "POLYLINE",
        "8",
        "GUIDES",
        "66",
        "1",
        "0",
        "VERTEX",
        "10",
        "0",
        "20",
        "0",
        "30",
        "4",
        "0",
        "VERTEX",
        "10",
        "3",
        "20",
        "0",
        "30",
        "4",
        "0",
        "SEQEND",
    ]


def test_mesh_rejects_out_of_range_faces() -> None:
    with pytest.raises(ValueError, match="outside"):
        Mesh3(((0.0, 0.0, 0.0),), ((0, 1, 2),))


def test_mesh_rejects_out_of_range_edges() -> None:
    with pytest.raises(ValueError, match="outside"):
        Mesh3(((0.0, 0.0, 0.0),), (), ((0, 1),))


def test_mesh_to_wireframe() -> None:
    from cady.geometry import Wireframe3

    mesh = Mesh3(
        ((0, 0, 0), (1, 0, 0), (0, 1, 0)),
        ((0, 1, 2),),
    )
    wf = mesh.to_wireframe()
    assert isinstance(wf, Wireframe3)
    assert len(wf.vertices) == 3
    assert len(wf.edges) == 3
    assert (0, 1) in wf.edges
    assert (1, 2) in wf.edges
    assert (0, 2) in wf.edges


def test_mesh_to_wireframe_empty_faces() -> None:
    from cady.geometry import Wireframe3

    mesh = Mesh3(((0, 0, 0), (1, 0, 0)), ())
    wf = mesh.to_wireframe()
    assert isinstance(wf, Wireframe3)
    assert len(wf.vertices) == 2
    assert len(wf.edges) == 0


def test_mesh_from_dxf_removed() -> None:
    assert not hasattr(Mesh3, "from_dxf")
