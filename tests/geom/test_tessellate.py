from __future__ import annotations

from collections import Counter
from math import hypot, isclose, pi

from cady import circle, prism, rectangle
from cady.geom.tessellate import (
    curves_to_polyline,
    extrusion_to_triangles,
    polygon_to_triangles,
    revolution_to_triangles,
)


def tri_area(tri) -> float:  # noqa: ANN001
    a, b, c = tri
    return abs((a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y)) / 2)


def test_circle_chord_error() -> None:
    poly = curves_to_polyline(circle((0, 0), 1), tolerance=1e-3)
    assert max(abs(hypot(point.x, point.y) - 1) for point in poly.points()) < 1e-3


def test_polygon_with_hole_area_and_vertices() -> None:
    hole = circle((0.5, 0.5), 0.2)
    tris = polygon_to_triangles(rectangle((0, 0), (1, 1)).with_hole(hole), tolerance=1e-3)
    area = sum(tri_area(tri) for tri in tris)
    assert isclose(area, 1 - pi * 0.2**2, rel_tol=0.01)
    for tri in tris:
        assert all(hypot(vertex.x - 0.5, vertex.y - 0.5) >= 0.2 for vertex in tri)


def test_prism_exactly_12_triangles() -> None:
    from cady.geom.tessellate import prism_to_triangles

    assert len(prism_to_triangles(prism((0, 0, 0), (2, 2, 1)))) == 12


def test_extrusion_triangles_nonempty() -> None:
    solid = rectangle((0, 0), (1, 1)).extrude("+z", 0.1)
    assert extrusion_to_triangles(solid, tolerance=1e-3)


def test_revolution_watertight() -> None:
    rev = rectangle((1, 0), (1, 1)).revolve(((0, 0, 0), (0, 0, 1)))
    tris = revolution_to_triangles(rev, tolerance=5e-2)
    edges: Counter[tuple[tuple[float, float, float], tuple[float, float, float]]] = Counter()
    for tri in tris:
        pts = [p.tuple() for p in tri]
        for a, b in zip(pts, pts[1:] + pts[:1], strict=True):
            edges[tuple(sorted((a, b)))] += 1
    assert set(edges.values()) == {2}
