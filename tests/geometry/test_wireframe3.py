from __future__ import annotations

import pytest

from cady import GeometryError, Polyline3, Wireframe3
from cady.operations.transforms import Transform3

# -- Construction ----------------------------------------------------------


def test_wireframe_construction() -> None:
    wf = Wireframe3(
        ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)),
        ((0, 1), (1, 2), (2, 3), (3, 0)),
    )
    assert len(wf.vertices) == 4
    assert len(wf.edges) == 4
    assert tuple(wf.vertices[0]) == (0.0, 0.0, 0.0)


def test_wireframe_construction_rejects_negative_indices() -> None:
    with pytest.raises(ValueError, match="negative"):
        Wireframe3(((0, 0, 0),), ((-1, 0),))


def test_wireframe_construction_rejects_out_of_range_edges() -> None:
    with pytest.raises(ValueError, match="outside"):
        Wireframe3(((0, 0, 0),), ((0, 1),))


def test_wireframe_empty() -> None:
    wf = Wireframe3((), ())
    assert len(wf.vertices) == 0
    assert len(wf.edges) == 0


def test_wireframe_empty_rejects_edges_without_vertices() -> None:
    with pytest.raises(ValueError, match="empty"):
        Wireframe3((), ((0, 1),))


def test_wireframe_from_polylines_dedupes_shared_vertices_and_edges() -> None:
    wf = Wireframe3.from_polylines(
        (
            Polyline3(((0, 0, 0), (1, 0, 0), (1, 1, 0))),
            Polyline3(((1, 1, 0), (1, 0, 0), (0, 0, 0))),
            Polyline3(((1, 1, 0), (0, 1, 0))),
        )
    )

    assert wf.vertices == (
        (0, 0, 0),
        (1, 0, 0),
        (1, 1, 0),
        (0, 1, 0),
    )
    assert wf.edges == ((0, 1), (1, 2), (2, 3))


def test_wireframe_from_polylines_closes_closed_polylines() -> None:
    wf = Wireframe3.from_polylines(
        (
            Polyline3(
                (
                    (0, 0, 0),
                    (1, 0, 0),
                    (0, 1, 0),
                ),
                closed=True,
            ),
        )
    )

    assert wf.vertices == (
        (0, 0, 0),
        (1, 0, 0),
        (0, 1, 0),
    )
    assert wf.edges == ((0, 1), (1, 2), (2, 0))


# -- Transforms ------------------------------------------------------------


def test_wireframe_transformed() -> None:
    wf = Wireframe3(
        ((0, 0, 0), (1, 0, 0)),
        ((0, 1),),
    )
    moved = wf.transformed(Transform3(wf.vertices).translate(0, 0, 5))
    assert tuple(moved.vertices[0]) == (0.0, 0.0, 5.0)
    assert tuple(moved.vertices[1]) == (1.0, 0.0, 5.0)
    assert moved.edges == ((0, 1),)


def test_wireframe_mirror() -> None:
    wf = Wireframe3(
        ((0, 1, 0), (1, 1, 0)),
        ((0, 1),),
    )
    mirrored = wf.mirror((0, 0, 0), (0, 1, 0))
    assert tuple(mirrored.vertices[0]) == (0.0, -1.0, 0.0)
    assert tuple(mirrored.vertices[1]) == (1.0, -1.0, 0.0)
    assert mirrored.edges == ((0, 1),)


def test_wireframe_bounds() -> None:
    wf = Wireframe3(
        ((0, 0, -1), (2, 3, 5)),
        ((0, 1),),
    )
    lower, upper = wf.bounds()
    assert tuple(lower) == (0.0, 0.0, -1.0)
    assert tuple(upper) == (2.0, 3.0, 5.0)

    with pytest.raises(ValueError, match="empty"):
        Wireframe3((), ()).bounds()


def test_wireframe_to_array() -> None:
    wf = Wireframe3(
        ((0, 0, 0), (1, 0, 0)),
        ((0, 1),),
    )
    arr = wf.to_array(tolerance=1e-3)
    vertices, faces, edges = arr
    assert vertices.shape == (2, 3)
    assert edges.shape == (1, 2)
    assert faces.shape == (0, 3)


def test_wireframe_to_mesh_splits_crossings_and_uses_triangles_as_faces() -> None:
    wf = Wireframe3(
        (
            (0, 0, 0),
            (2, 2, 0),
            (0, 2, 0),
            (2, 0, 0),
        ),
        ((0, 1), (1, 2), (2, 3), (3, 0)),
    )

    triangulated = wf.triangulate(tolerance=1e-6)
    mesh = wf.to_mesh(tolerance=1e-6)

    assert isinstance(triangulated, Wireframe3)
    assert len(mesh.vertices) == 5
    assert len(mesh.faces) == 2
    assert all(len(face) == 3 for face in mesh.faces)
    assert triangulated.vertices == mesh.vertices
    assert triangulated.edges == mesh.edges
    assert mesh.edges == ((0, 3), (0, 4), (1, 2), (1, 4), (2, 4), (3, 4))


def test_wireframe_to_mesh_lofts_open_section_curves() -> None:
    wf = Wireframe3(
        (
            (0, 0, 0),
            (0, 1, 1),
            (0, 2, 2),
            (0, 3, 3),
            (2, 0, 0),
            (2, 1, 1),
            (2, 2, 2),
            (2, 3, 3),
        ),
        ((0, 1), (1, 2), (2, 3), (4, 5), (5, 6), (6, 7)),
    )

    mesh = wf.to_mesh(tolerance=1e-6)
    triangulated = wf.triangulate(tolerance=1e-6)

    assert isinstance(triangulated, Wireframe3)
    assert len(mesh.vertices) == 8
    assert len(mesh.faces) == 6
    assert len(triangulated.edges) == 13
    assert len(mesh.edges) == 13
    assert triangulated.vertices == mesh.vertices
    assert triangulated.edges == mesh.edges
    assert all(len(face) == 3 for face in mesh.faces)


def test_wireframe_remove_dangling_edges_prunes_branches_and_compacts() -> None:
    wf = Wireframe3(
        (
            (10, 0, 0),
            (10, 1, 0),
            (0, 0, 0),
            (1, 0, 0),
            (1, 1, 0),
            (0, 1, 0),
            (2, 1, 0),
            (3, 1, 0),
            (99, 99, 99),
        ),
        ((2, 3), (3, 4), (4, 5), (5, 2), (4, 6), (6, 7), (0, 1)),
    )

    pruned = wf.remove_dangling_edges()

    assert pruned.vertices == wf.vertices[2:6]
    assert pruned.edges == ((0, 1), (1, 2), (2, 3), (3, 0))
    assert wf.edges == ((2, 3), (3, 4), (4, 5), (5, 2), (4, 6), (6, 7), (0, 1))


def test_wireframe_remove_dangling_edges_returns_empty_for_open_chain() -> None:
    wf = Wireframe3(
        ((0, 0, 0), (1, 0, 0), (2, 0, 0)),
        ((0, 1), (1, 2)),
    )

    assert wf.remove_dangling_edges() == Wireframe3((), ())


def test_wireframe_split_crossing_edges_adds_shared_crossing_vertex() -> None:
    wf = Wireframe3(
        (
            (0, 0, 0),
            (2, 2, 0),
            (0, 2, 0),
            (2, 0, 0),
        ),
        ((0, 1), (2, 3)),
    )

    split = wf.split_crossing_edges(tolerance=1e-6)

    assert split.vertices[:4] == wf.vertices
    assert split.vertices[4] == pytest.approx((1.0, 1.0, 0.0))
    assert split.edges == ((0, 4), (4, 1), (2, 4), (4, 3))


def test_wireframe_split_crossing_edges_splits_t_junction() -> None:
    wf = Wireframe3(
        (
            (0, 0, 0),
            (2, 0, 0),
            (1, 0, 0),
            (1, 1, 0),
        ),
        ((0, 1), (2, 3)),
    )

    split = wf.split_crossing_edges(tolerance=1e-6)

    assert split.vertices == wf.vertices
    assert split.edges == ((0, 2), (2, 1), (2, 3))


def test_wireframe_split_crossing_edges_ignores_skew_edges() -> None:
    wf = Wireframe3(
        (
            (0, 0, 0),
            (2, 0, 0),
            (1, -1, 1),
            (1, 1, 1),
        ),
        ((0, 1), (2, 3)),
    )

    assert wf.split_crossing_edges(tolerance=1e-6) == wf


def test_wireframe_split_crossing_edges_splits_collinear_overlap_endpoints() -> None:
    wf = Wireframe3(
        (
            (0, 0, 0),
            (3, 0, 0),
            (1, 0, 0),
            (2, 0, 0),
        ),
        ((0, 1), (2, 3)),
    )

    split = wf.split_crossing_edges(tolerance=1e-6)

    assert split.vertices == wf.vertices
    assert split.edges == ((0, 2), (2, 3), (3, 1))


def test_wireframe_does_not_expose_mesh_closing_methods() -> None:
    assert not hasattr(Wireframe3, "close_planar")
    assert not hasattr(Wireframe3, "close_to_plane")


# -- triangulate_loops -----------------------------------------------------


def test_wireframe_triangulate_returns_loop_triangulation() -> None:
    wf = Wireframe3(
        ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)),
        ((0, 1), (1, 2), (2, 3), (3, 0)),
    )

    triangulated = wf.triangulate(tolerance=1e-3)

    assert isinstance(triangulated, Wireframe3)
    assert triangulated == wf.triangulate_loops(tolerance=1e-3)
    assert len(triangulated.edges) == 5


def test_wireframe_triangulate_loops_square() -> None:
    wf = Wireframe3(
        ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)),
        ((0, 1), (1, 2), (2, 3), (3, 0)),
    )
    triangulated = wf.triangulate_loops(tolerance=1e-3)
    mesh = wf.to_mesh(tolerance=1e-3)
    assert len(mesh.faces) == 2
    assert len(triangulated.vertices) == 4
    assert len(triangulated.edges) == 5


def test_wireframe_triangulate_loops_prunes_dangling_branches() -> None:
    wf = Wireframe3(
        (
            (0, 0, 0),
            (1, 0, 0),
            (1, 1, 0),
            (0, 1, 0),
            (2, 1, 0),
            (3, 1, 0),
        ),
        ((0, 1), (1, 2), (2, 3), (3, 0), (2, 4), (4, 5)),
    )

    triangulated = wf.triangulate_loops(tolerance=1e-3)
    mesh = wf.to_mesh(tolerance=1e-3)

    assert len(mesh.faces) == 2
    assert len(mesh.vertices) == 4
    assert triangulated.edges == ((0, 1), (0, 2), (0, 3), (1, 2), (2, 3))


def test_wireframe_triangulate_loops_no_cycles() -> None:
    wf = Wireframe3(
        ((0, 0, 0), (1, 0, 0)),
        ((0, 1),),
    )
    with pytest.raises(GeometryError, match="no closed edge loops"):
        wf.triangulate_loops(tolerance=1e-3)


def test_wireframe_triangulate_loops_non_planar() -> None:
    # Non-planar quad (one vertex displaced)
    wf = Wireframe3(
        ((0, 0, 0), (1, 0, 0), (1, 1, 1), (0, 1, 0)),
        ((0, 1), (1, 2), (2, 3), (3, 0)),
    )
    with pytest.raises(GeometryError, match="non-planar"):
        wf.triangulate_loops(tolerance=1e-3)


def test_triangulate_loops_multiple_disjoint_cycles() -> None:
    wf = Wireframe3(
        (
            (0, 0, 0),
            (1, 0, 0),
            (1, 1, 0),
            (0, 1, 0),
            (2, 0, 0),
            (3, 0, 0),
            (3, 1, 0),
            (2, 1, 0),
        ),
        ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4)),
    )
    triangulated = wf.triangulate_loops(tolerance=1e-3)
    mesh = wf.to_mesh(tolerance=1e-3)
    assert isinstance(triangulated, Wireframe3)
    assert len(mesh.faces) == 4


def test_triangulate_loops_two_connected_squares() -> None:
    """Two squares joined by a bridge edge — both cycles must be found."""
    # Square A: 0-1-6-5, Square B: 2-3-4-7, bridge: 6-2
    wf = Wireframe3(
        (
            (0, 0, 0),  # 0
            (1, 0, 0),  # 1
            (2, 0, 0),  # 2
            (3, 0, 0),  # 3
            (3, 1, 0),  # 4
            (0, 1, 0),  # 5
            (1, 1, 0),  # 6
            (2, 1, 0),  # 7
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
    triangulated = wf.triangulate_loops(tolerance=1e-3)
    mesh = wf.to_mesh(tolerance=1e-3)
    assert isinstance(triangulated, Wireframe3)
    assert len(mesh.faces) == 4  # 2 triangles per square
