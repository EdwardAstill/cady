from __future__ import annotations

from math import acos, degrees

import numpy as np
import pytest

from cady.geometry.polyline import Polyline2, Polyline3
from cady.operations import triangulate
from cady.operations.meshing import closed_polyline_mesh2, closed_polyline_mesh3


def test_triangulate_returns_nodes_edges_and_triangle_faces() -> None:
    nodes, edges = _square()

    out_nodes, out_edges, faces = triangulate(nodes, edges)

    np.testing.assert_allclose(out_nodes, nodes)
    assert faces.shape == (2, 3)
    assert out_edges.shape[1] == 2
    assert len(out_edges) > len(edges)


def test_triangulate_supports_pizza_web_algorithm() -> None:
    nodes = np.array(
        [
            [0.0, 0.0],
            [2.0, 0.0],
            [2.0, 1.0],
            [1.0, 0.35],
            [0.0, 1.0],
        ],
        dtype=np.float64,
    )
    edges = _loop_edges(len(nodes))

    out_nodes, out_edges, faces = triangulate(nodes, edges, algorithm="pizza_web")

    assert len(out_nodes) > len(nodes)
    assert out_edges.shape[1] == 2
    assert faces.shape[1] == 3


def test_triangulate_rejects_unknown_algorithm() -> None:
    nodes, edges = _square()

    with pytest.raises(ValueError, match="unsupported triangulation algorithm"):
        triangulate(nodes, edges, algorithm="missing")


def test_triangulate_rejects_constraints_not_supported_by_algorithm() -> None:
    nodes, edges = _square()

    with pytest.raises(ValueError, match="does not support"):
        triangulate(nodes, edges, algorithm="pizza_web", max_area=0.25)


def test_max_edge_length_refines_boundary_and_faces() -> None:
    nodes = np.array(
        [
            [0.0, 0.0],
            [2.0, 0.0],
            [2.0, 2.0],
            [0.0, 2.0],
        ],
        dtype=np.float64,
    )
    edges = _loop_edges(len(nodes))

    out_nodes, out_edges, faces = triangulate(nodes, edges, max_edge_length=0.75)

    assert len(out_nodes) > len(nodes)
    assert len(out_edges) > len(edges)
    assert len(faces) > 2
    assert _max_face_edge_length(out_nodes, faces) <= 0.75 + 1e-9
    assert _delaunay_violations(out_nodes, faces) == 0


def test_max_area_inserts_steiner_nodes() -> None:
    nodes = np.array(
        [
            [0.0, 0.0],
            [2.0, 0.0],
            [2.0, 2.0],
            [0.0, 2.0],
        ],
        dtype=np.float64,
    )
    edges = _loop_edges(len(nodes))

    out_nodes, out_edges, faces = triangulate(nodes, edges, max_area=0.25)

    np.testing.assert_allclose(out_nodes[:4], nodes)
    np.testing.assert_allclose(out_nodes[4], [1.0, 1.0])
    assert len(out_nodes) > len(nodes)
    assert len(out_edges) > len(edges)
    assert len(faces) > 2
    assert max(_face_areas(out_nodes, faces)) <= 0.25 + 1e-9


def test_min_angle_accepts_output_when_constraint_is_met() -> None:
    nodes, edges = _square()

    out_nodes, _out_edges, faces = triangulate(nodes, edges, min_angle_degrees=20.0)

    assert _min_face_angle(out_nodes, faces) >= 20.0


def test_min_angle_rejects_output_below_constraint() -> None:
    nodes = np.array(
        [
            [0.0, 0.0],
            [4.0, 0.0],
            [4.0, 1.0],
            [0.0, 1.0],
        ],
        dtype=np.float64,
    )
    edges = _loop_edges(len(nodes))

    with pytest.raises(ValueError, match="below min_angle_degrees 20"):
        triangulate(nodes, edges, min_angle_degrees=20.0)


def test_invalid_constraint_values_fail_explicitly() -> None:
    nodes, edges = _square()

    with pytest.raises(ValueError, match="max_area"):
        triangulate(nodes, edges, max_area=0.0)

    with pytest.raises(ValueError, match="min_angle_degrees"):
        triangulate(nodes, edges, min_angle_degrees=60.0)


def test_closed_polyline_mesh2_uses_triangulate() -> None:
    polyline = Polyline2(
        ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
        closed=True,
    )

    mesh = closed_polyline_mesh2(polyline, tolerance=1e-6)

    assert mesh.vertices == polyline.vertices
    assert len(mesh.faces) == 2
    assert mesh.edges


def test_closed_polyline_mesh3_projects_and_lifts_planar_loop() -> None:
    polyline = Polyline3(
        (
            (0.0, 0.0, 2.0),
            (2.0, 0.0, 2.0),
            (2.0, 2.0, 2.0),
            (0.0, 2.0, 2.0),
        ),
        closed=True,
    )

    mesh = closed_polyline_mesh3(polyline, tolerance=1e-6, max_area=0.25)

    assert len(mesh.vertices) > len(polyline.vertices)
    assert len(mesh.faces) > 2
    assert {point[2] for point in mesh.vertices} == {2.0}
    assert max(_face_areas(np.asarray([point[:2] for point in mesh.vertices]), mesh.faces)) <= (
        0.25 + 1e-9
    )


def test_closed_polyline_mesh3_rejects_non_planar_curve() -> None:
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
        closed_polyline_mesh3(polyline, tolerance=1e-3)


def _square() -> tuple[np.ndarray, np.ndarray]:
    nodes = np.array(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0],
        ],
        dtype=np.float64,
    )
    return nodes, _loop_edges(len(nodes))


def _loop_edges(count: int) -> np.ndarray:
    return np.asarray(tuple((index, (index + 1) % count) for index in range(count)), dtype=np.int64)


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


def _min_face_angle(nodes: np.ndarray, faces: np.ndarray) -> float:
    return min(
        _min_triangle_angle(
            float(np.linalg.norm(nodes[a] - nodes[b])),
            float(np.linalg.norm(nodes[b] - nodes[c])),
            float(np.linalg.norm(nodes[c] - nodes[a])),
        )
        for a, b, c in faces
    )


def _min_triangle_angle(ab: float, bc: float, ca: float) -> float:
    return min(
        _angle_degrees(ab, ca, bc),
        _angle_degrees(ab, bc, ca),
        _angle_degrees(bc, ca, ab),
    )


def _angle_degrees(first: float, second: float, opposite: float) -> float:
    cosine = (first * first + second * second - opposite * opposite) / (
        2.0 * first * second
    )
    return degrees(acos(max(-1.0, min(1.0, cosine))))


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
