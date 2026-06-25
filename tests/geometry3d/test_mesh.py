from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from cady.geometry3d import Mesh3D
from cady.numeric.mesh3d import ArrayMesh3
from cady.numeric.transform import Transform3
from cady.vec import Vec3


def test_mesh_from_array_triangles_bounds_and_transform() -> None:
    array = ArrayMesh3(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        [[0, 1, 2]],
    )

    mesh = Mesh3D.from_array(array)
    assert mesh.triangles == ((Vec3(0.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0)),)
    assert mesh.bounds() == (Vec3(0.0, 0.0, 0.0), Vec3(1.0, 1.0, 0.0))

    moved = mesh.transformed(Transform3.translation(0.0, 0.0, 2.0))
    assert moved.bounds() == (Vec3(0.0, 0.0, 2.0), Vec3(1.0, 1.0, 2.0))


def test_mesh_mirror_reflects_about_plane_and_reverses_face_winding() -> None:
    mesh = Mesh3D(
        (Vec3(1.0, 0.0, 0.0), Vec3(1.0, 1.0, 0.0), Vec3(1.0, 0.0, 1.0)),
        ((0, 1, 2),),
        ((0, 1),),
    )

    mirrored = mesh.mirror((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))

    assert [point.tuple() for point in mirrored.vertices] == [
        (-1.0, 0.0, 0.0),
        (-1.0, 1.0, 0.0),
        (-1.0, 0.0, 1.0),
    ]
    assert mirrored.faces == ((0, 2, 1),)
    assert mirrored.edges == mesh.edges


def test_mesh_to_array_requires_explicit_positive_tolerance() -> None:
    mesh = Mesh3D((Vec3(0.0, 0.0, 0.0),), ())

    with pytest.raises(ValueError, match="tolerance"):
        mesh.to_array(tolerance=0.0)


def test_mesh_to_array_and_merged_offsets_faces() -> None:
    first = Mesh3D(
        (Vec3(0.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0), Vec3(0.0, 1.0, 0.0)),
        ((0, 1, 2),),
    )
    second = Mesh3D(
        (Vec3(0.0, 0.0, 1.0), Vec3(1.0, 0.0, 1.0), Vec3(0.0, 1.0, 1.0)),
        ((0, 1, 2),),
    )

    merged = Mesh3D.merged((first, second))
    array = merged.to_array(tolerance=1e-3)

    assert array.vertices.shape == (6, 3)
    np.testing.assert_array_equal(array.faces, [[0, 1, 2], [3, 4, 5]])


def test_mesh_edges_round_trip_through_array_transform_and_merge() -> None:
    mesh = Mesh3D(
        (Vec3(0.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0)),
        (),
        ((0, 1),),
    )

    array = mesh.to_array(tolerance=1e-3)
    from_array = Mesh3D.from_array(array)
    moved = mesh.transformed(Transform3.translation(0.0, 0.0, 2.0))
    merged = Mesh3D.merged((mesh, moved))

    np.testing.assert_array_equal(array.edges, [[0, 1]])
    assert from_array.edges == ((0, 1),)
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

    assert [point.tuple() for point in wf.vertices] == [
        (0.0, 0.0, 1.0),
        (2.0, 0.0, 3.0),
        (4.0, 1.0, 5.0),
    ]
    assert wf.edges == ((0, 1), (1, 2))


def test_mesh_rejects_out_of_range_faces() -> None:
    with pytest.raises(ValueError, match="outside"):
        Mesh3D((Vec3(0.0, 0.0, 0.0),), ((0, 1, 2),))


def test_mesh_rejects_out_of_range_edges() -> None:
    with pytest.raises(ValueError, match="outside"):
        Mesh3D((Vec3(0.0, 0.0, 0.0),), (), ((0, 1),))


def test_mesh_to_wireframe() -> None:
    from cady.geometry3d import Wireframe3D

    mesh = Mesh3D(
        (Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(0, 1, 0)),
        ((0, 1, 2),),
    )
    wf = mesh.to_wireframe()
    assert isinstance(wf, Wireframe3D)
    assert len(wf.vertices) == 3
    assert len(wf.edges) == 3
    assert (0, 1) in wf.edges
    assert (1, 2) in wf.edges
    assert (0, 2) in wf.edges


def test_mesh_to_wireframe_empty_faces() -> None:
    from cady.geometry3d import Wireframe3D

    mesh = Mesh3D((Vec3(0, 0, 0), Vec3(1, 0, 0)), ())
    wf = mesh.to_wireframe()
    assert isinstance(wf, Wireframe3D)
    assert len(wf.vertices) == 2
    assert len(wf.edges) == 0


def test_mesh_from_dxf_removed() -> None:
    assert not hasattr(Mesh3D, "from_dxf")
