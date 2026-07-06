from __future__ import annotations

from collections import Counter
from math import isclose

import numpy as np
import pytest

from cady import GeometryError
from cady.geometry import Mesh3
from cady.operations import close_planar_cap


def _cube_vertices() -> tuple[tuple[float, float, float], ...]:
    return (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 1.0),
        (1.0, 1.0, 1.0),
        (0.0, 1.0, 1.0),
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


def _cube_mesh() -> Mesh3:
    return Mesh3(_cube_vertices(), _cube_faces())


def _cube_minus_top() -> Mesh3:
    """Cube with the top (+Z) face removed: faces containing all-z=1 vertices."""
    vertices = _cube_vertices()
    faces = tuple(f for f in _cube_faces() if not all(isclose(vertices[i][2], 1.0) for i in f))
    return Mesh3(vertices, faces)


def _edge_occurrence_counts(mesh: Mesh3) -> Counter[tuple[int, int]]:
    """Return Counter mapping each edge (min,max) to its occurrence count."""
    counts: Counter[tuple[int, int]] = Counter()
    for face in mesh.faces:
        indices = [int(index) for index in face]
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
            counts[(min(start, end), max(start, end))] += 1
    return counts


def _all_edges_manifold(mesh: Mesh3) -> bool:
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

    assert isinstance(result, Mesh3)
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


# ── close_mesh ────────────────────────────────────────────────────────────


def test_close_mesh_fills_open_ends_with_polygon_faces() -> None:
    """A box missing the top face should be closed by close_mesh."""
    mesh = _cube_minus_top()
    result = mesh.close_mesh(tolerance=1e-6)

    assert isinstance(result, Mesh3)
    assert result is not mesh
    assert len(result.faces) == len(mesh.faces) + 1
    assert len(result.faces[-1]) == 4
    assert _all_edges_manifold(result)


def test_close_mesh_is_noop_when_already_closed() -> None:
    mesh = _cube_mesh()
    result = mesh.close_mesh(tolerance=1e-6)
    assert len(result.faces) == len(mesh.faces)


def test_close_mesh_raises_for_non_planar_boundary() -> None:
    # A cube missing the top face, but with one top vertex displaced
    # so the 4-vertex boundary loop is non-planar
    vertices = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 1.0),
        (1.0, 1.0, 0.7),  # displaced downward — breaks planarity
        (0.0, 1.0, 1.0),
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

    mesh = Mesh3(vertices, faces)
    with pytest.raises(ValueError, match="non-planar"):
        mesh.close_mesh(tolerance=1e-6)


def test_close_mesh_fills_multiple_holes_with_polygon_faces() -> None:
    """A box missing top AND bottom faces should get both closed."""
    vertices = _cube_vertices()
    faces = tuple(
        f
        for f in _cube_faces()
        if not (
            all(isclose(vertices[i][2], 1.0) for i in f)
            or all(isclose(vertices[i][2], 0.0) for i in f)
        )
    )
    mesh = Mesh3(vertices, faces)
    result = mesh.close_mesh(tolerance=1e-6)

    assert len(result.faces) == len(mesh.faces) + 2
    assert all(len(face) == 4 for face in result.faces[-2:])
    assert _all_edges_manifold(result)


def test_mesh_boundary_is_bounds_and_boundary_loops_returns_topology() -> None:
    mesh = _cube_minus_top()

    assert mesh.boundary == ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))

    boundary = mesh.boundary_loops[0]

    assert boundary.shape == (5, 3)
    np.testing.assert_allclose(boundary[0], boundary[-1])
    assert {tuple(point) for point in boundary[:-1]} == {
        (0.0, 0.0, 1.0),
        (1.0, 0.0, 1.0),
        (1.0, 1.0, 1.0),
        (0.0, 1.0, 1.0),
    }


def test_closed_mesh_boundary_is_bounds() -> None:
    assert _cube_mesh().boundary == ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))


def test_mesh_boundary_is_bounds_for_multiple_boundary_loops() -> None:
    vertices = _cube_vertices()
    faces = tuple(
        f
        for f in _cube_faces()
        if not (
            all(isclose(vertices[i][2], 1.0) for i in f)
            or all(isclose(vertices[i][2], 0.0) for i in f)
        )
    )
    mesh = Mesh3(vertices, faces)

    assert mesh.boundary == ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))


def test_mesh_boundary_loops_returns_multiple_closed_polyline3_values() -> None:
    vertices = _cube_vertices()
    faces = tuple(
        f
        for f in _cube_faces()
        if not (
            all(isclose(vertices[i][2], 1.0) for i in f)
            or all(isclose(vertices[i][2], 0.0) for i in f)
        )
    )
    mesh = Mesh3(vertices, faces)

    loops = mesh.boundary_loops

    assert len(loops) == 2
    assert [loop.shape for loop in loops] == [(5, 3), (5, 3)]
    for loop in loops:
        np.testing.assert_allclose(loop[0], loop[-1])


def test_mesh_boundary_loops_raises_for_non_manifold_edges() -> None:
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, -1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        ((0, 1, 2), (1, 0, 3), (0, 1, 4)),
    )

    with pytest.raises(GeometryError, match="non-manifold"):
        _ = mesh.boundary_loops


# ── ops-level close_planar_cap ────────────────────────────────────────────


def test_ops_close_planar_cap_on_cut_mesh() -> None:
    """Cut a cube in half without capping, then cap the open boundary."""
    from cady.operations import cut_mesh_by_plane

    cube_vertices = np.array(
        [[float(v[0]), float(v[1]), float(v[2])] for v in _cube_vertices()],
        dtype=np.float64,
    )
    cube_faces = np.array(_cube_faces(), dtype=np.int64)

    # Cut without cap
    cut = cut_mesh_by_plane(
        cube_vertices,
        cube_faces,
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
        *cut,
        plane_origin=(0.0, 0.0, 0.5),
        plane_normal=(0.0, 0.0, 1.0),
        tolerance=1e-9,
    )

    # Should now be watertight
    assert len(capped[1]) > len(cut[1])
    assert set(_array_boundary_counts(capped).values()) == {2}


# ── close_planar snap_tolerance ─────────────────────────────────────────


def _cube_minus_top_displaced() -> Mesh3:
    """Cube missing top face, with top vertices slightly off Z=1."""
    vertices = (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 0.98),  # displaced
        (1.0, 0.0, 0.99),
        (1.0, 1.0, 0.97),
        (0.0, 1.0, 1.02),
    )
    faces = tuple(
        f for f in _cube_faces() if not all(isclose(vertices[i][2], 1.0, abs_tol=0.05) for i in f)
    )
    return Mesh3(vertices, faces)


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


def test_close_planar_snap_creates_gaps_for_close_mesh() -> None:
    """After a snap-cap, close_mesh can run without error on the gaps."""
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
    # cap boundary.  close_mesh fills both loops, so it adds faces.
    result = snapped.close_mesh(tolerance=0.03)
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


# ── close_to_plane ────────────────────────────────────────────────────────


def test_close_to_plane_creates_wall_faces_from_display_edges() -> None:
    mesh = Mesh3(
        (
            (0.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
            (1.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
        ),
        (),
        ((0, 1), (1, 2), (2, 3), (3, 0)),
    )

    result = mesh.close_to_plane((0, 0, 0), (0, 1, 0), tolerance=1e-3, max_distance=3.0)

    assert isinstance(result, Mesh3)
    assert len(result.vertices) == 8
    assert len(result.faces) == 8
    assert result.edges == mesh.edges


def test_close_to_plane_prunes_dangling_display_edges() -> None:
    mesh = Mesh3(
        (
            (0.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
            (1.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
            (2.0, 2.0, 0.0),
            (3.0, 2.0, 0.0),
        ),
        (),
        ((0, 1), (1, 2), (2, 3), (3, 0), (2, 4), (4, 5)),
    )

    result = mesh.close_to_plane((0, 0, 0), (0, 1, 0), tolerance=1e-3, max_distance=3.0)

    assert len(result.vertices) == 8
    assert len(result.faces) == 8
    assert result.edges == ((0, 1), (1, 2), (2, 3), (3, 0))


def test_close_to_plane_uses_boundary_edges_when_no_display_edges() -> None:
    mesh = _cube_minus_top()

    result = mesh.close_to_plane(
        plane_origin=(0.0, 0.0, 0.0),
        plane_normal=(0.0, 0.0, 1.0),
        tolerance=1e-6,
        max_distance=1.5,
    )

    assert len(result.faces) == len(mesh.faces) + 8


def test_close_to_plane_rejects_negative_params() -> None:
    mesh = Mesh3(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        (),
        ((0, 1),),
    )

    with pytest.raises(ValueError, match="tolerance must be positive"):
        mesh.close_to_plane((0, 0, 0), (0, 0, 1), tolerance=0, max_distance=1.0)
    with pytest.raises(ValueError, match="max_distance must be positive"):
        mesh.close_to_plane((0, 0, 0), (0, 0, 1), tolerance=1e-3, max_distance=0.0)


def test_close_to_plane_without_closed_edges_raises() -> None:
    mesh = Mesh3(
        ((0.0, 10.0, 0.0), (1.0, 10.0, 0.0)),
        (),
        ((0, 1),),
    )

    with pytest.raises(GeometryError, match="no edges found"):
        mesh.close_to_plane((0, 0, 0), (0, 1, 0), tolerance=1e-3, max_distance=1.0)


def _array_boundary_counts(
    mesh: tuple[np.ndarray, np.ndarray, np.ndarray],
) -> Counter[tuple[int, int]]:
    counts: Counter[tuple[int, int]] = Counter()
    for face in mesh[1]:
        indices = [int(face[0]), int(face[1]), int(face[2])]
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
            counts[(min(start, end), max(start, end))] += 1
    return counts
