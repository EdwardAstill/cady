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

    assert len(out_nodes) > 12
    assert len(out_edges) > len(edges)
    assert len(faces) >= 2
    assert _max_face_edge_length(out_nodes, faces) <= 0.75 + 1e-9
    assert _delaunay_violations(out_nodes, faces) == 0


def test_triangulation_guide_max_area_inserts_steiner_nodes() -> None:
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
        guide=TriangulationGuide(max_area=0.25),
    )

    np.testing.assert_allclose(out_nodes[:4], nodes)
    np.testing.assert_allclose(out_nodes[4], [1.0, 1.0])
    assert len(out_nodes) > len(nodes)
    assert len(out_edges) > len(edges)
    assert len(faces) > 2
    assert max(_face_areas(out_nodes, faces)) <= 0.25 + 1e-9


def test_triangulation_guide_refines_planar_3d_curve_with_steiner_nodes() -> None:
    polyline = Polyline3(
        (
            (0.0, 0.0, 2.0),
            (2.0, 0.0, 2.0),
            (2.0, 2.0, 2.0),
            (0.0, 2.0, 2.0),
        ),
        closed=True,
    )

    mesh = triangulate_curve3(
        polyline,
        tolerance=1e-6,
        guide=TriangulationGuide(max_area=0.25),
    )

    assert len(mesh.vertices) > len(polyline.vertices)
    assert len(mesh.faces) > 2
    assert mesh.vertices[4] == (1.0, 1.0, 2.0)
    assert {point[2] for point in mesh.vertices} == {2.0}
    assert mesh.edges == tuple((index, (index + 1) % 4) for index in range(4))


def test_invalid_guide_options_fail_explicitly() -> None:
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

    with pytest.raises(ValueError, match="max_area"):
        triangulate_mesh2(nodes, edges, guide=TriangulationGuide(max_area=0.0))

    with pytest.raises(ValueError, match="min_angle_degrees"):
        triangulate_mesh2(nodes, edges, guide=TriangulationGuide(min_angle_degrees=60.0))


def _max_face_edge_length(nodes: np.ndarray, faces: np.ndarray) -> float:
    return max(
        float(np.linalg.norm(nodes[start] - nodes[end]))
        for face in faces
        for start, end in zip(face, (*face[1:], face[0]), strict=True)
    )


def _face_areas(nodes: np.ndarray, faces: np.ndarray) -> tuple[float, ...]:
    areas: list[float] = []
    for a, b, c in faces:
        ab = nodes[b] - nodes[a]
        ac = nodes[c] - nodes[a]
        areas.append(abs(float(ab[0] * ac[1] - ab[1] * ac[0])) / 2.0)
    return tuple(areas)


def _delaunay_violations(nodes: np.ndarray, faces: np.ndarray) -> int:
    edge_faces: dict[tuple[int, int], list[tuple[int, int, int]]] = {}
    for face_raw in faces:
        face = (int(face_raw[0]), int(face_raw[1]), int(face_raw[2]))
        for start, end in zip(face, (*face[1:], face[0]), strict=True):
            edge = (min(start, end), max(start, end))
            edge_faces.setdefault(edge, []).append(face)

    violations = 0
    for edge, adjacent in edge_faces.items():
        if len(adjacent) != 2:
            continue
        left, right = adjacent
        a, b = edge
        c = next(index for index in left if index not in edge)
        d = next(index for index in right if index not in edge)
        if _point_in_circumcircle(nodes[a], nodes[b], nodes[c], nodes[d]):
            violations += 1
    return violations


def _point_in_circumcircle(
    a: np.ndarray,
    b: np.ndarray,
    c: np.ndarray,
    point: np.ndarray,
) -> bool:
    ax = float(a[0] - point[0])
    ay = float(a[1] - point[1])
    bx = float(b[0] - point[0])
    by = float(b[1] - point[1])
    cx = float(c[0] - point[0])
    cy = float(c[1] - point[1])
    determinant = (
        (ax * ax + ay * ay) * (bx * cy - cx * by)
        - (bx * bx + by * by) * (ax * cy - cx * ay)
        + (cx * cx + cy * cy) * (ax * by - bx * ay)
    )
    if _cross(a, b, c) < 0.0:
        determinant = -determinant
    return determinant > 1e-9


def _cross(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    return float((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
