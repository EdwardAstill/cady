from __future__ import annotations

import pytest

from cady import GeometryError, Mesh3D, Wireframe3D
from cady.numeric.mesh3d import ArrayMesh3
from cady.numeric.transform import Transform3
from cady.vec import Vec3

# -- Construction ----------------------------------------------------------


def test_wireframe_construction() -> None:
    wf = Wireframe3D(
        (Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(1, 1, 0), Vec3(0, 1, 0)),
        ((0, 1), (1, 2), (2, 3), (3, 0)),
    )
    assert len(wf.vertices) == 4
    assert len(wf.edges) == 4
    assert tuple(wf.vertices[0].tuple()) == (0.0, 0.0, 0.0)


def test_wireframe_construction_rejects_negative_indices() -> None:
    with pytest.raises(ValueError, match="negative"):
        Wireframe3D((Vec3(0, 0, 0),), ((-1, 0),))


def test_wireframe_construction_rejects_out_of_range_edges() -> None:
    with pytest.raises(ValueError, match="outside"):
        Wireframe3D((Vec3(0, 0, 0),), ((0, 1),))


def test_wireframe_empty() -> None:
    wf = Wireframe3D((), ())
    assert len(wf.vertices) == 0
    assert len(wf.edges) == 0


def test_wireframe_empty_rejects_edges_without_vertices() -> None:
    with pytest.raises(ValueError, match="empty"):
        Wireframe3D((), ((0, 1),))


# -- Transforms ------------------------------------------------------------


def test_wireframe_transformed() -> None:
    wf = Wireframe3D(
        (Vec3(0, 0, 0), Vec3(1, 0, 0)),
        ((0, 1),),
    )
    moved = wf.transformed(Transform3.translation(0, 0, 5))
    assert tuple(moved.vertices[0].tuple()) == (0.0, 0.0, 5.0)
    assert tuple(moved.vertices[1].tuple()) == (1.0, 0.0, 5.0)
    assert moved.edges == ((0, 1),)


def test_wireframe_mirror() -> None:
    wf = Wireframe3D(
        (Vec3(0, 1, 0), Vec3(1, 1, 0)),
        ((0, 1),),
    )
    mirrored = wf.mirror((0, 0, 0), (0, 1, 0))
    assert tuple(mirrored.vertices[0].tuple()) == (0.0, -1.0, 0.0)
    assert tuple(mirrored.vertices[1].tuple()) == (1.0, -1.0, 0.0)
    assert mirrored.edges == ((0, 1),)


def test_wireframe_bounds() -> None:
    wf = Wireframe3D(
        (Vec3(0, 0, -1), Vec3(2, 3, 5)),
        ((0, 1),),
    )
    lower, upper = wf.bounds()
    assert tuple(lower.tuple()) == (0.0, 0.0, -1.0)
    assert tuple(upper.tuple()) == (2.0, 3.0, 5.0)

    with pytest.raises(ValueError, match="empty"):
        Wireframe3D((), ()).bounds()


def test_wireframe_to_array() -> None:
    wf = Wireframe3D(
        (Vec3(0, 0, 0), Vec3(1, 0, 0)),
        ((0, 1),),
    )
    arr = wf.to_array(tolerance=1e-3)
    assert isinstance(arr, ArrayMesh3)
    assert arr.vertices.shape == (2, 3)
    assert arr.edges.shape == (1, 2)
    assert arr.faces.shape == (0, 3)


# -- close_planar ----------------------------------------------------------


def test_wireframe_close_planar_square() -> None:
    wf = Wireframe3D(
        (Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(1, 1, 0), Vec3(0, 1, 0)),
        ((0, 1), (1, 2), (2, 3), (3, 0)),
    )
    mesh = wf.close_planar((0, 0, 0), (0, 0, 1), tolerance=1e-3)
    assert len(mesh.faces) == 2  # two triangles
    assert len(mesh.vertices) == 4
    assert mesh.edges == wf.edges  # original edges preserved


def test_wireframe_close_planar_no_edges_on_plane() -> None:
    wf = Wireframe3D(
        (Vec3(0, 0, 0), Vec3(1, 0, 0)),
        ((0, 1),),
    )
    with pytest.raises(GeometryError, match="no edges lie"):
        wf.close_planar((0, 0, 5), (0, 0, 1), tolerance=1e-3)


def test_wireframe_close_planar_partial() -> None:
    # Square on z=0 plus some off-plane edges
    wf = Wireframe3D(
        (
            Vec3(0, 0, 0),  # 0
            Vec3(1, 0, 0),  # 1
            Vec3(1, 1, 0),  # 2
            Vec3(0, 1, 0),  # 3
            Vec3(0, 0, 5),  # 4 - off plane
            Vec3(0, 1, 5),  # 5 - off plane
        ),
        ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5)),
    )
    mesh = wf.close_planar((0, 0, 0), (0, 0, 1), tolerance=1e-3)
    # Only the on-plane square gets capped
    assert len(mesh.faces) == 2
    assert len(mesh.vertices) == 6


def test_wireframe_close_planar_multiple_loops() -> None:
    # Two separate squares on the same plane
    wf = Wireframe3D(
        (
            Vec3(0, 0, 0),
            Vec3(0.5, 0, 0),
            Vec3(0.5, 0.5, 0),
            Vec3(0, 0.5, 0),
            Vec3(2, 0, 0),
            Vec3(3, 0, 0),
            Vec3(3, 1, 0),
            Vec3(2, 1, 0),
        ),
        ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4)),
    )
    mesh = wf.close_planar((0, 0, 0), (0, 0, 1), tolerance=1e-3)
    assert len(mesh.faces) == 4  # 2 per loop


def test_close_planar_rejects_open_chain() -> None:
    """An open edge chain on the plane must not be capped as a closed loop."""
    wf = Wireframe3D(
        (
            Vec3(0, 0, 0),
            Vec3(1, 0, 0),
            Vec3(2, 0, 0),
            Vec3(3, 0, 0),
        ),
        ((0, 1), (1, 2), (2, 3)),
    )
    with pytest.raises(GeometryError, match="no closed planar edge loops"):
        wf.close_planar((0, 0, 0), (0, 0, 1), tolerance=1e-3)


# -- triangulate_loops -----------------------------------------------------


def test_wireframe_triangulate_loops_square() -> None:
    wf = Wireframe3D(
        (Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(1, 1, 0), Vec3(0, 1, 0)),
        ((0, 1), (1, 2), (2, 3), (3, 0)),
    )
    mesh = wf.triangulate_loops(tolerance=1e-3)
    assert len(mesh.faces) == 2
    assert len(mesh.vertices) == 4


def test_wireframe_triangulate_loops_no_cycles() -> None:
    wf = Wireframe3D(
        (Vec3(0, 0, 0), Vec3(1, 0, 0)),
        ((0, 1),),
    )
    with pytest.raises(GeometryError, match="no closed edge loops"):
        wf.triangulate_loops(tolerance=1e-3)


def test_wireframe_triangulate_loops_non_planar() -> None:
    # Non-planar quad (one vertex displaced)
    wf = Wireframe3D(
        (Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(1, 1, 1), Vec3(0, 1, 0)),
        ((0, 1), (1, 2), (2, 3), (3, 0)),
    )
    with pytest.raises(GeometryError, match="non-planar"):
        wf.triangulate_loops(tolerance=1e-3)


def test_triangulate_loops_multiple_disjoint_cycles() -> None:
    wf = Wireframe3D(
        (
            Vec3(0, 0, 0),
            Vec3(1, 0, 0),
            Vec3(1, 1, 0),
            Vec3(0, 1, 0),
            Vec3(2, 0, 0),
            Vec3(3, 0, 0),
            Vec3(3, 1, 0),
            Vec3(2, 1, 0),
        ),
        ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4)),
    )
    mesh = wf.triangulate_loops(tolerance=1e-3)
    assert len(mesh.faces) == 4


def test_triangulate_loops_two_connected_squares() -> None:
    """Two squares joined by a bridge edge — both cycles must be found."""
    # Square A: 0-1-6-5, Square B: 2-3-4-7, bridge: 6-2
    wf = Wireframe3D(
        (
            Vec3(0, 0, 0),  # 0
            Vec3(1, 0, 0),  # 1
            Vec3(2, 0, 0),  # 2
            Vec3(3, 0, 0),  # 3
            Vec3(3, 1, 0),  # 4
            Vec3(0, 1, 0),  # 5
            Vec3(1, 1, 0),  # 6
            Vec3(2, 1, 0),  # 7
        ),
        (
            (0, 1),
            (1, 6),
            (6, 5),
            (5, 0),  # square A
            (6, 2),  # bridge
            (2, 3),
            (3, 4),
            (4, 7),
            (7, 2),  # square B
        ),
    )
    mesh = wf.triangulate_loops(tolerance=1e-3)
    assert len(mesh.faces) == 4  # 2 triangles per square


# -- close_to_plane --------------------------------------------------------


def test_close_to_plane_creates_wall_faces() -> None:
    """A square 1 unit above the plane produces 8 wall triangles (4 quads)."""
    wf = Wireframe3D(
        (Vec3(0, 1, 0), Vec3(1, 1, 0), Vec3(1, 2, 0), Vec3(0, 2, 0)),
        ((0, 1), (1, 2), (2, 3), (3, 0)),
    )
    mesh = wf.close_to_plane((0, 0, 0), (0, 1, 0), tolerance=1e-3, max_distance=3.0)
    assert isinstance(mesh, Mesh3D)
    # 4 original + 4 projected = 8 vertices
    assert len(mesh.vertices) == 8
    # 4 edges × 2 triangles = 8 wall faces
    assert len(mesh.faces) == 8
    # Original edges preserved
    assert mesh.edges == wf.edges


def test_close_to_plane_dedup_shared_vertices() -> None:
    """Two edges sharing a vertex share one projected vertex."""
    wf = Wireframe3D(
        (Vec3(0, 1, 0), Vec3(1, 1, 0), Vec3(2, 1, 0)),
        ((0, 1), (1, 2)),
    )
    mesh = wf.close_to_plane((0, 0, 0), (0, 1, 0), tolerance=1e-3, max_distance=2.0)
    # 3 original + 3 projected (vertex 1 shared) = 6
    assert len(mesh.vertices) == 6
    # 2 edges × 2 triangles = 4 wall faces
    assert len(mesh.faces) == 4


def test_close_to_plane_skips_far_edges() -> None:
    """Edges beyond max_distance are ignored."""
    wf = Wireframe3D(
        (
            Vec3(0, 1, 0),  # near
            Vec3(1, 1, 0),  # near
            Vec3(0, 10, 0),  # far
            Vec3(1, 10, 0),  # far
        ),
        ((0, 1), (2, 3)),
    )
    mesh = wf.close_to_plane((0, 0, 0), (0, 1, 0), tolerance=1e-3, max_distance=2.0)
    # Only the near edge (0,1) gets wall faces
    # 4 original + 2 projected = 6 vertices
    assert len(mesh.vertices) == 6
    assert len(mesh.faces) == 2


def test_close_to_plane_rejects_negative_params() -> None:
    wf = Wireframe3D(
        (Vec3(0, 0, 0), Vec3(1, 0, 0)),
        ((0, 1),),
    )
    with pytest.raises(ValueError, match="tolerance must be positive"):
        wf.close_to_plane((0, 0, 0), (0, 0, 1), tolerance=0, max_distance=1.0)
    with pytest.raises(ValueError, match="max_distance must be positive"):
        wf.close_to_plane((0, 0, 0), (0, 0, 1), tolerance=1e-3, max_distance=0.0)


def test_close_to_plane_empty_noop() -> None:
    wf = Wireframe3D((), ())
    with pytest.raises(GeometryError, match="no edges found"):
        wf.close_to_plane((0, 0, 0), (0, 0, 1), tolerance=1e-3, max_distance=1.0)


def test_close_to_plane_all_far_raises() -> None:
    """When all edges are beyond max_distance, GeometryError is raised."""
    wf = Wireframe3D(
        (Vec3(0, 10, 0), Vec3(1, 10, 0)),
        ((0, 1),),
    )
    with pytest.raises(GeometryError, match="no edges found"):
        wf.close_to_plane((0, 0, 0), (0, 1, 0), tolerance=1e-3, max_distance=1.0)
