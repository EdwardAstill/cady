from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from cady.errors import ReadError
from cady.geometry import Mesh3
from cady.operations import TriangulationGuide
from cady.operations.transforms import Transform3


def test_mesh_triangles_bounds_and_transform() -> None:
    mesh = Mesh3(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
    )

    assert mesh.triangles == (((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),)
    assert mesh.bounds() == ((0.0, 0.0, 0.0), (1.0, 1.0, 0.0))

    moved = mesh.transformed(Transform3(mesh.vertices).translate(0.0, 0.0, 2.0))
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


def test_mesh3_accepts_polygon_faces_and_triangulates_at_array_boundary() -> None:
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        ((0, 1, 2, 3),),
    )

    vertices, faces, _edges = mesh.to_array(tolerance=1e-9)
    wireframe = mesh.to_wireframe()
    merged = Mesh3.merged((mesh, mesh))

    assert mesh.faces == ((0, 1, 2, 3),)
    assert merged.faces == ((0, 1, 2, 3), (4, 5, 6, 7))
    assert len(mesh.triangles) == 2
    assert mesh.area == pytest.approx(1.0)
    assert vertices.shape == (4, 3)
    assert faces.shape == (2, 3)
    assert {tuple(face) for face in faces.tolist()} == {(3, 0, 1), (1, 2, 3)}
    assert wireframe.edges == ((0, 1), (0, 3), (1, 2), (2, 3))


def test_mesh_triangulate_merges_connected_coplanar_faces() -> None:
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        ((0, 1, 2), (0, 2, 3)),
    )

    triangulated = mesh.triangulate(tolerance=1e-9)

    assert triangulated.vertices == mesh.vertices
    assert set(triangulated.faces) == {(3, 0, 1), (1, 2, 3)}
    assert (0, 2) not in triangulated.edges
    assert (1, 3) in triangulated.edges


def test_mesh_merge_coplanar_faces_returns_intermediate_polygon_mesh() -> None:
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        ((0, 1, 2), (0, 2, 3)),
    )

    merged = mesh.merge_coplanar_faces(tolerance=1e-9)

    assert merged.vertices == mesh.vertices
    assert len(merged.faces) == 1
    assert set(merged.faces[0]) == {0, 1, 2, 3}
    assert (0, 2) not in merged.edges


def test_mesh_triangulate_discards_internal_vertices_after_coplanar_merge() -> None:
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
            (1.0, 1.0, 0.0),
        ),
        ((0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)),
    )

    triangulated = mesh.triangulate(tolerance=1e-9, guide="auto")

    assert not any(4 in face for face in triangulated.faces)
    assert len(triangulated.vertices) >= 4
    assert all(len(face) == 3 for face in triangulated.faces)


def test_mesh_triangulate_auto_guide_refines_from_local_shape() -> None:
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
        ),
        ((0, 1, 2, 3),),
    )

    triangulated = mesh.triangulate(tolerance=1e-6, guide="auto")

    assert len(triangulated.vertices) > len(mesh.vertices)
    assert len(triangulated.faces) > 2
    assert all(len(face) == 3 for face in triangulated.faces)


def test_mesh_triangulate_accepts_triangulation_guide() -> None:
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
        ),
        ((0, 1, 2, 3),),
    )

    triangulated = mesh.triangulate(
        tolerance=1e-6,
        guide=TriangulationGuide(max_area=0.25),
    )

    assert len(triangulated.vertices) > len(mesh.vertices)
    assert len(triangulated.faces) > 2
    assert triangulated.vertices[4] == (1.0, 1.0, 0.0)
    assert all(len(face) == 3 for face in triangulated.faces)


def test_mesh_triangulate_rejects_min_angle_violations() -> None:
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
            (4.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        ((0, 1, 2, 3),),
    )

    with pytest.raises(ValueError, match="below min_angle_degrees 20"):
        mesh.triangulate(
            tolerance=1e-9,
            guide=TriangulationGuide(min_angle_degrees=20.0),
        )


def test_mesh_triangulate_auto_can_reject_min_angle_violations() -> None:
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (4.0, 0.0, 0.0),
            (4.0, 1.0, 0.0),
        ),
        ((0, 1, 2),),
    )

    with pytest.raises(ValueError, match="below min_angle_degrees 20"):
        mesh.triangulate(
            tolerance=1e-9,
            guide="auto",
            min_angle_degrees=20.0,
        )


def test_mesh_triangulate_uses_distributed_polygon_diagonals() -> None:
    mesh = Mesh3(
        (
            (-1.65, -0.25, 0.0),
            (-1.05, -0.9, 0.0),
            (-0.2, -0.82, 0.0),
            (0.35, -1.18, 0.0),
            (1.35, -0.6, 0.0),
            (1.7, 0.18, 0.0),
            (0.85, 0.5, 0.0),
            (0.55, 1.1, 0.0),
            (-0.28, 0.68, 0.0),
            (-1.18, 0.96, 0.0),
            (-1.58, 0.35, 0.0),
        ),
        ((0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10),),
    )

    triangulated = mesh.triangulate(tolerance=1e-6)
    face_counts = {
        index: sum(index in face for face in triangulated.faces)
        for index in range(len(triangulated.vertices))
    }

    assert len(triangulated.faces) == 9
    assert max(face_counts.values()) < len(triangulated.faces)
    assert all(len(face) == 3 for face in triangulated.faces)


def test_mesh_decimate_reduces_faces_and_remaps_edges() -> None:
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
            (2.0, 1.0, 0.0),
            (0.0, 2.0, 0.0),
            (1.0, 2.0, 0.0),
            (2.0, 2.0, 0.0),
        ),
        (
            (0, 1, 4),
            (0, 4, 3),
            (1, 2, 5),
            (1, 5, 4),
            (3, 4, 7),
            (3, 7, 6),
            (4, 5, 8),
            (4, 8, 7),
        ),
        ((0, 1), (1, 2), (2, 5), (5, 8), (7, 8), (6, 7), (3, 6), (0, 3)),
    )

    decimated = mesh.decimate(4, tolerance=1e-9)

    assert len(decimated.faces) <= 4
    assert len(decimated.faces) < len(mesh.faces)
    assert len(decimated.vertices) < len(mesh.vertices)
    assert all(len(face) == 3 for face in decimated.faces)
    assert all(0 <= index < len(decimated.vertices) for face in decimated.faces for index in face)
    assert all(0 <= index < len(decimated.vertices) for edge in decimated.edges for index in edge)


def test_mesh_decimate_preserves_polygon_faces_when_no_reduction_is_needed() -> None:
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        ((0, 1, 2, 3),),
    )

    decimated = mesh.decimate(2, tolerance=1e-9)

    assert decimated.faces == mesh.faces
    assert decimated.vertices == mesh.vertices


def test_mesh_decimate_validates_target_and_tolerance() -> None:
    mesh = Mesh3(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ((0, 1, 2),),
    )

    with pytest.raises(ValueError, match="target_faces"):
        mesh.decimate(0)

    with pytest.raises(ValueError, match="tolerance"):
        mesh.decimate(1, tolerance=0.0)


def test_mesh_from_points_reconstructs_with_advancing_front() -> None:
    points = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (1.0, 1.0, 0.0),
        (2.0, 1.0, 0.0),
    )

    mesh = Mesh3.from_points(points, tolerance=1e-9)

    assert mesh.vertices == points
    assert mesh.faces == ((0, 1, 3), (3, 1, 4), (4, 1, 2), (4, 2, 5))
    assert mesh.edges == (
        (0, 1),
        (0, 3),
        (1, 2),
        (1, 3),
        (1, 4),
        (2, 4),
        (2, 5),
        (3, 4),
        (4, 5),
    )


def test_mesh_from_points_accepts_numpy_point_array() -> None:
    points = np.array(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
        dtype=np.float64,
    )

    mesh = Mesh3.from_points(points, tolerance=1e-9)

    assert mesh.vertices == ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    assert mesh.faces == ((0, 1, 2),)


def test_mesh_from_points_validates_point_count_shape_and_tolerance() -> None:
    too_few_points = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
    )
    valid_points = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    )

    with pytest.raises(ValueError, match="at least three"):
        Mesh3.from_points(too_few_points, tolerance=1e-9)

    with pytest.raises(ValueError, match="shape"):
        Mesh3.from_points(
            (
                (0.0, 0.0),
                (1.0, 0.0),
                (0.0, 1.0),
            ),
            tolerance=1e-9,
        )

    with pytest.raises(ValueError, match="tolerance"):
        Mesh3.from_points(valid_points, tolerance=0.0)


def test_mesh_from_point_cloud_old_constructor_is_not_preserved() -> None:
    assert not hasattr(Mesh3, "from_point_cloud")


def test_mesh_edges_round_trip_through_array_transform_and_merge() -> None:
    mesh = Mesh3(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        (),
        ((0, 1),),
    )

    _vertices, _faces, edges = mesh.to_array(tolerance=1e-3)
    moved = mesh.transformed(Transform3(mesh.vertices).translate(0.0, 0.0, 2.0))
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
