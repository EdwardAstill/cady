from __future__ import annotations

import numpy as np
import pytest

from cady.geometry.polyline import Polyline2, Polyline3
from cady.operations import (
    TriangulationGuide,
    triangulate2,
    triangulate3,
    triangulate_curve2,
    triangulate_curve3,
    triangulate_mesh2,
    triangulate_mesh3,
)


def test_triangulate2_returns_nodes_and_triangle_faces() -> None:
    nodes = np.array(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0],
        ],
        dtype=np.float64,
    )
    edges = np.array([(0, 1), (1, 2), (2, 3), (3, 0)], dtype=np.int64)

    out_nodes, faces = triangulate2(nodes, edges)

    np.testing.assert_allclose(out_nodes, nodes)
    assert faces.shape == (2, 3)
    assert {tuple(face) for face in faces} == {(3, 0, 1), (1, 2, 3)}


def test_triangulate3_projects_planar_edges_and_returns_original_nodes() -> None:
    nodes = np.array(
        [
            [0.0, 0.0, 2.0],
            [1.0, 0.0, 2.0],
            [1.0, 1.0, 2.0],
            [0.0, 1.0, 2.0],
        ],
        dtype=np.float64,
    )
    edges = np.array([(0, 1), (1, 2), (2, 3), (3, 0)], dtype=np.int64)

    out_nodes, faces = triangulate3(nodes, edges)

    np.testing.assert_allclose(out_nodes, nodes)
    assert faces.shape == (2, 3)
    assert {tuple(face) for face in faces} == {(3, 0, 1), (1, 2, 3)}


def test_triangulate_curve2_fills_closed_polyline() -> None:
    polyline = Polyline2(
        ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        closed=True,
    )

    mesh = triangulate_curve2(polyline, tolerance=1e-6)

    assert mesh.vertices == polyline.vertices
    assert len(mesh.faces) == 2
    assert mesh.edges


def test_triangulate_curve3_fills_planar_closed_polyline() -> None:
    polyline = Polyline3(
        (
            (0.0, 0.0, 2.0),
            (1.0, 0.0, 2.0),
            (1.0, 1.0, 2.0),
            (0.0, 1.0, 2.0),
        ),
        closed=True,
    )

    mesh = triangulate_curve3(polyline, tolerance=1e-6)

    assert mesh.vertices == polyline.vertices
    assert len(mesh.faces) == 2
    assert mesh.edges


def test_triangulate_curve3_rejects_non_planar_closed_curve() -> None:
    polyline = Polyline3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 1.0),
            (0.0, 1.0, 0.0),
        ),
        closed=True,
    )

    with pytest.raises(ValueError, match="non-planar"):
        triangulate_curve3(polyline, tolerance=1e-3)


def test_triangulate_mesh2_returns_internal_edges_and_faces() -> None:
    nodes = np.array(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0],
        ],
        dtype=np.float64,
    )
    edges = np.array([(0, 1), (1, 2), (2, 3), (3, 0)], dtype=np.int64)

    out_nodes, out_edges, faces = triangulate_mesh2(nodes, edges)

    np.testing.assert_allclose(out_nodes, nodes)
    assert faces.shape == (2, 3)
    assert out_edges.shape[1] == 2
    assert len(out_edges) > len(edges)


def test_triangulate_mesh3_returns_internal_edges_and_faces() -> None:
    nodes = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=np.float64,
    )
    edges = np.array([(0, 1), (1, 2), (2, 3), (3, 0)], dtype=np.int64)

    out_nodes, out_edges, faces = triangulate_mesh3(nodes, edges)

    np.testing.assert_allclose(out_nodes, nodes)
    assert faces.shape == (2, 3)
    assert out_edges.shape[1] == 2
    assert len(out_edges) > len(edges)


def test_triangulation_guide_refines_boundary_edges() -> None:
    nodes = np.array(
        [
            [0.0, 0.0],
            [2.0, 0.0],
            [2.0, 2.0],
            [0.0, 2.0],
        ],
        dtype=np.float64,
    )
    edges = np.array([(0, 1), (1, 2), (2, 3), (3, 0)], dtype=np.int64)

    out_nodes, out_edges, faces = triangulate_mesh2(
        nodes,
        edges,
        guide=TriangulationGuide(max_edge_length=0.75),
    )

    assert len(out_nodes) == 12
    assert len(out_edges) > len(edges)
    assert len(faces) >= 2


def test_unsupported_guide_options_fail_explicitly() -> None:
    nodes = np.array(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0],
        ],
        dtype=np.float64,
    )
    edges = np.array([(0, 1), (1, 2), (2, 3), (3, 0)], dtype=np.int64)

    with pytest.raises(NotImplementedError, match="max_area"):
        triangulate_mesh2(nodes, edges, guide=TriangulationGuide(max_area=0.1))

    with pytest.raises(NotImplementedError, match="min_angle_degrees"):
        triangulate_mesh2(nodes, edges, guide=TriangulationGuide(min_angle_degrees=25.0))
