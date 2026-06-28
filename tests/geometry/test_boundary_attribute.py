from __future__ import annotations

from math import pi

from cady.geometry import (
    Arc2,
    Arc3,
    Circle2,
    ClosedPolyline3,
    Ellipse2,
    Line2,
    Line3,
    Mesh2,
    Mesh3,
    PointCloud2,
    PointCloud3,
    Polyline2,
    Polyline3,
    Region2,
    Spline2,
    Spline3,
    Wireframe3,
)


def test_finite_geometry_boundary_matches_bounds() -> None:
    values = (
        Line2((0.0, 1.0), (2.0, 3.0)),
        Line3((0.0, 1.0, 2.0), (3.0, 4.0, 5.0)),
        Arc2((0.0, 0.0), 1.0, 0.0, pi / 2.0),
        Arc3((0.0, 0.0, 0.0), 1.0, 0.0, pi / 2.0),
        Circle2((1.0, 2.0), 3.0),
        Ellipse2((1.0, 2.0), 3.0, 1.0),
        Polyline2(((0.0, 0.0), (2.0, 1.0))),
        Polyline3(((0.0, 0.0, 0.0), (1.0, 2.0, 3.0))),
        ClosedPolyline3(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))),
        Spline2(((0.0, 0.0), (1.0, 2.0), (2.0, 1.0), (3.0, 0.0))),
        Spline3(
            (
                (0.0, 0.0, 0.0),
                (1.0, 2.0, 3.0),
                (2.0, 1.0, 4.0),
                (3.0, 0.0, 5.0),
            )
        ),
        Mesh2(((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)), ((0, 1, 2),)),
        Mesh3(
            ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 2.0)),
            ((0, 1, 2),),
        ),
        PointCloud2(((0.0, 0.0), (2.0, 3.0))),
        PointCloud3(((0.0, 0.0, 0.0), (2.0, 3.0, 4.0))),
        Region2.rectangle(2.0, 3.0, origin=(1.0, 1.0)),
        Wireframe3.from_edges(
            ((0.0, 0.0, 0.0), (2.0, 3.0, 4.0)),
            ((0, 1),),
        ),
    )

    for value in values:
        assert value.boundary == value.bounds()
