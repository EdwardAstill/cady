from __future__ import annotations

from collections import Counter
from math import isclose

import numpy as np
import pytest

from cady import GeometryError
from cady.geometry3d import Mesh3D
from cady.numeric.mesh3d import ArrayMesh3
from cady.ops import close_planar_cap
from cady.vec import Vec3


def _cube_vertices() -> tuple[Vec3, ...]:
    return (
        Vec3(0.0, 0.0, 0.0),
        Vec3(1.0, 0.0, 0.0),
        Vec3(1.0, 1.0, 0.0),
        Vec3(0.0, 1.0, 0.0),
        Vec3(0.0, 0.0, 1.0),
        Vec3(1.0, 0.0, 1.0),
        Vec3(1.0, 1.0, 1.0),
        Vec3(0.0, 1.0, 1.0),
    )


def _cube_faces() -> tuple[tuple[int, int, int], ...]:
    return (
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    )


def _cube_mesh() -> Mesh3D:
    return Mesh3D(_cube_vertices(), _cube_faces())


def _cube_minus_top() -> Mesh3D:
    """Cube with the top (+Z) face removed: faces containing all-z=1 vertices."""
    vertices = _cube_vertices()
    faces = tuple(f for f in _cube_faces() if not all(isclose(vertices[i].z, 1.0) for i in f))
    return Mesh3D(vertices, faces)


def _edge_occurrence_counts(mesh: Mesh3D) -> Counter[tuple[int, int]]:
    """Return Counter mapping each edge (min,max) to its occurrence count."""
    counts: Counter[tuple[int, int]] = Counter()
    for face in mesh.faces:
        indices = [face[0], face[1], face[2]]
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
            counts[(min(start, end), max(start, end))] += 1
    return counts


def _all_edges_manifold(mesh: Mesh3D) -> bool:
    """True when every edge appears in exactly two faces."""
    return set(_edge_occurrence_counts(mesh).values()) == {2}


# ── close_planar ──────────────────────────────────────────────────────────


def test_close_planar_caps_box_with_missing_face() -> None:
    mesh = _cube_minus_top()
    result = mesh.close_planar(
        plane_origin=(0.0, 0.0, 1.0),
        plane_normal=(0.0, 0.0, 1.0),
        tolerance=1e-6,
    )

    assert isinstance(result, Mesh3D)
    assert result is not mesh
    # Should have same vertices, one extra face
    assert len(result.vertices) == len(mesh.vertices)
    assert len(result.faces) == len(mesh.faces) + 2  # quad → 2 tris
    # All edges should now be manifold (count=2)
    assert _all_edges_manifold(result)


def test_close_planar_is_noop_when_mesh_is_already_closed() -> None:
    mesh = _cube_mesh()
    result = mesh.close_planar(
        plane_origin=(0.0, 0.0, 1.0),
        plane_normal=(0.0, 0.0, 1.0),
        tolerance=1e-6,
    )
    assert result.faces == mesh.faces


def test_close_planar_is_noop_when_plane_does_not_intersect_boundary() -> None:
    mesh = _cube_minus_top()
    result = mesh.close_planar(
        plane_origin=(0.0, 0.0, 0.0),
        plane_normal=(0.0, 0.0, 1.0),
        tolerance=1e-6,
    )
    # Bottom plane does not intersect the open top boundary
    assert len(result.faces) == len(mesh.faces)


def test_close_planar_rejects_negative_tolerance() -> None:
    mesh = _cube_minus_top()
    with pytest.raises(ValueError, match="tolerance"):
        mesh.close_planar((0, 0, 1), (0, 0, 1), tolerance=0.0)


# ── close_boundary ────────────────────────────────────────────────────────


def test_close_boundary_fills_open_ends_of_extrusion() -> None:
    """A box missing the top face should be closed by close_boundary."""
    mesh = _cube_minus_top()
    result = mesh.close_boundary(tolerance=1e-6)

    assert isinstance(result, Mesh3D)
    assert result is not mesh
    assert len(result.faces) == len(mesh.faces) + 2  # quad → 2 tris
    assert _all_edges_manifold(result)


def test_close_boundary_is_noop_when_already_closed() -> None:
    mesh = _cube_mesh()
    result = mesh.close_boundary(tolerance=1e-6)
    assert len(result.faces) == len(mesh.faces)


def test_close_boundary_raises_for_non_planar_boundary() -> None:
    # A cube missing the top face, but with one top vertex displaced
    # so the 4-vertex boundary loop is non-planar
    vertices = (
        Vec3(0.0, 0.0, 0.0),
        Vec3(1.0, 0.0, 0.0),
        Vec3(1.0, 1.0, 0.0),
        Vec3(0.0, 1.0, 0.0),
        Vec3(0.0, 0.0, 1.0),
        Vec3(1.0, 0.0, 1.0),
        Vec3(1.0, 1.0, 0.7),  # displaced downward — breaks planarity
        Vec3(0.0, 1.0, 1.0),
    )
    faces: tuple[tuple[int, int, int], ...] = (
        (0, 2, 1),
        (0, 3, 2),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    )

    mesh = Mesh3D(vertices, faces)
    with pytest.raises(ValueError, match="non-planar"):
        mesh.close_boundary(tolerance=1e-6)


def test_close_boundary_fills_multiple_holes() -> None:
    """A box missing top AND bottom faces should get both closed."""
    vertices = _cube_vertices()
    faces = tuple(
        f
        for f in _cube_faces()
        if not (
            all(isclose(vertices[i].z, 1.0) for i in f)
            or all(isclose(vertices[i].z, 0.0) for i in f)
        )
    )
    mesh = Mesh3D(vertices, faces)
    result = mesh.close_boundary(tolerance=1e-6)

    # 4 cap triangles (2 per missing quad face)
    assert len(result.faces) == len(mesh.faces) + 4
    assert _all_edges_manifold(result)


def test_mesh_boundary_returns_single_closed_polyline3() -> None:
    mesh = _cube_minus_top()

    boundary = mesh.boundary

    assert boundary.vertices.shape == (5, 3)
    np.testing.assert_allclose(boundary.vertices[0], boundary.vertices[-1])
    assert {tuple(point) for point in boundary.vertices[:-1]} == {
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 1.0),
        (1.0, 1.0, 1.0),
        (0.0, 1.0, 1.0),
    }


def test_mesh_boundary_raises_when_mesh_is_closed() -> None:
    with pytest.raises(GeometryError, match="closed"):
        _ = _cube_mesh().boundary


def test_mesh_boundary_raises_for_multiple_boundary_loops() -> None:
    vertices = _cube_vertices()
    faces = tuple(
        f
        for f in _cube_faces()
        if not (
            all(isclose(vertices[i].z, 1.0) for i in f)
            or all(isclose(vertices[i].z, 0.0) for i in f)
        )
    )
    mesh = Mesh3D(vertices, faces)

    with pytest.raises(GeometryError, match="2 boundary loops"):
        _ = mesh.boundary


def test_mesh_boundary_loops_returns_multiple_closed_polyline3_values() -> None:
    vertices = _cube_vertices()
    faces = tuple(
        f
        for f in _cube_faces()
        if not (
            all(isclose(vertices[i].z, 1.0) for i in f)
            or all(isclose(vertices[i].z, 0.0) for i in f)
        )
    )
    mesh = Mesh3D(vertices, faces)

    loops = mesh.boundary_loops

    assert len(loops) == 2
    assert [loop.vertices.shape for loop in loops] == [(5, 3), (5, 3)]
    for loop in loops:
        np.testing.assert_allclose(loop.vertices[0], loop.vertices[-1])


def test_mesh_boundary_loops_raises_for_non_manifold_edges() -> None:
    mesh = Mesh3D(
        (
            Vec3(0.0, 0.0, 0.0),
            Vec3(1.0, 0.0, 0.0),
            Vec3(0.0, 1.0, 0.0),
            Vec3(0.0, -1.0, 0.0),
            Vec3(0.0, 0.0, 1.0),
        ),
        ((0, 1, 2), (1, 0, 3), (0, 1, 4)),
    )

    with pytest.raises(GeometryError, match="non-manifold"):
        _ = mesh.boundary_loops


# ── close_holes stub ──────────────────────────────────────────────────────


def test_close_holes_raises_not_implemented() -> None:
    mesh = _cube_minus_top()
    with pytest.raises(NotImplementedError, match="close_holes"):
        mesh.close_holes(tolerance=1e-3)


def test_close_holes_accepts_max_hole_edges() -> None:
    mesh = _cube_minus_top()
    with pytest.raises(NotImplementedError, match="close_holes"):
        mesh.close_holes(tolerance=1e-3, max_hole_edges=100)


# ── ops-level close_planar_cap ────────────────────────────────────────────


def test_ops_close_planar_cap_on_cut_mesh() -> None:
    """Cut a cube in half without capping, then cap the open boundary."""
    from cady.ops import cut_mesh_by_plane

    cube = ArrayMesh3(
        np.array(
            [[float(v.x), float(v.y), float(v.z)] for v in _cube_vertices()],
            dtype=np.float64,
        ),
        np.array(_cube_faces(), dtype=np.int64),
    )

    # Cut without cap
    cut = cut_mesh_by_plane(
        cube,
        plane_origin=(0.0, 0.0, 0.5),
        plane_normal=(0.0, 0.0, 1.0),
        keep="negative",
        cap=False,
        tolerance=1e-9,
    )

    # Verify it's open
    boundary_before = sum(1 for _, c in _array_boundary_counts(cut).items() if c == 1)
    assert boundary_before > 0

    # Cap it
    capped = close_planar_cap(
        cut, plane_origin=(0.0, 0.0, 0.5), plane_normal=(0.0, 0.0, 1.0), tolerance=1e-9
    )

    # Should now be watertight
    assert len(capped.faces) > len(cut.faces)
    assert set(_array_boundary_counts(capped).values()) == {2}


# ── close_planar snap_tolerance ─────────────────────────────────────────


def _cube_minus_top_displaced() -> Mesh3D:
    """Cube missing top face, with top vertices slightly off Z=1."""
    vertices = (
        Vec3(0.0, 0.0, 0.0),
        Vec3(1.0, 0.0, 0.0),
        Vec3(1.0, 1.0, 0.0),
        Vec3(0.0, 1.0, 0.0),
        Vec3(0.0, 0.0, 0.98),  # displaced
        Vec3(1.0, 0.0, 0.99),
        Vec3(1.0, 1.0, 0.97),
        Vec3(0.0, 1.0, 1.02),
    )
    faces = tuple(
        f for f in _cube_faces() if not all(isclose(vertices[i].z, 1.0, abs_tol=0.05) for i in f)
    )
    return Mesh3D(vertices, faces)


def test_close_planar_snap_projects_nearby_boundary() -> None:
    """Boundary vertices ~2 mm off-plane get projected and capped."""
    mesh = _cube_minus_top_displaced()
    result = mesh.close_planar(
        plane_origin=(0.0, 0.0, 1.0),
        plane_normal=(0.0, 0.0, 1.0),
        tolerance=1e-6,
        snap_tolerance=0.05,
    )
    # projected copies were appended — more vertices than original
    assert len(result.vertices) > len(mesh.vertices)
    # cap faces were added
    assert len(result.faces) > len(mesh.faces)
    # original vertices are still there
    for original in mesh.vertices:
        assert original in result.vertices


def test_close_planar_snap_creates_gaps_for_close_boundary() -> None:
    """After a snap-cap, close_boundary can run without error on the gaps."""
    mesh = _cube_minus_top_displaced()
    snapped = mesh.close_planar(
        plane_origin=(0.0, 0.0, 1.0),
        plane_normal=(0.0, 0.0, 1.0),
        tolerance=1e-6,
        snap_tolerance=0.05,
    )
    # Snap-cap creates gaps — not manifold yet
    assert not _all_edges_manifold(snapped)
    # The gaps are thin strips between the original boundary and the projected
    # cap boundary.  close_boundary fills both loops, so it adds faces.
    result = snapped.close_boundary(tolerance=0.03)
    assert len(result.faces) > len(snapped.faces)


def test_close_planar_snap_noop_when_all_on_plane() -> None:
    """snap_tolerance does not change behavior when boundary is already planar."""
    mesh = _cube_minus_top()
    result = mesh.close_planar(
        plane_origin=(0.0, 0.0, 1.0),
        plane_normal=(0.0, 0.0, 1.0),
        tolerance=1e-6,
        snap_tolerance=0.1,
    )
    # Same vertices (no projected copies needed)
    assert len(result.vertices) == len(mesh.vertices)
    assert len(result.faces) == len(mesh.faces) + 2  # quad → 2 tris
    assert _all_edges_manifold(result)


def test_close_planar_snap_rejects_negative() -> None:
    mesh = _cube_minus_top()
    with pytest.raises(ValueError, match="snap_tolerance"):
        mesh.close_planar((0, 0, 1), (0, 0, 1), tolerance=1e-3, snap_tolerance=0.0)
    with pytest.raises(ValueError, match="snap_tolerance"):
        mesh.close_planar((0, 0, 1), (0, 0, 1), tolerance=1e-3, snap_tolerance=-1.0)


def _array_boundary_counts(mesh: ArrayMesh3) -> Counter[tuple[int, int]]:
    counts: Counter[tuple[int, int]] = Counter()
    for face in mesh.faces:
        indices = [int(face[0]), int(face[1]), int(face[2])]
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
            counts[(min(start, end), max(start, end))] += 1
    return counts
