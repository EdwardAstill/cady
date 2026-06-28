from __future__ import annotations

import cady.geometry as geometry
from cady.geometry import (
    Arc2,
    Circle2,
    Line2,
    Polyline2,
    Region2,
)
from cady.operations import (
    arc2,
    circle2,
    line2,
    polyline2,
    region_circle,
    region_rectangle,
)


def test_constructors_return_new_geometry_concepts() -> None:
    assert isinstance(line2((0, 0), (1, 0)), Line2)
    assert isinstance(arc2((0, 0), 1, 0, 1), Arc2)
    assert isinstance(circle2((0, 0), 1), Circle2)
    assert isinstance(polyline2(((0, 0), (1, 0))), Polyline2)
    closed = polyline2(((0, 0), (1, 0), (1, 1)), closed=True)
    assert isinstance(closed, Polyline2)
    assert closed.closed is True
    assert isinstance(region_rectangle(2, 3), Region2)
    assert isinstance(region_circle(1), Region2)


def test_rectangle_is_region_constructor_only_not_public_class() -> None:
    assert not hasattr(geometry, "Rectangle")
    assert isinstance(Region2.rectangle(2, 3), Region2)
