from __future__ import annotations

import cady.geometry as geometry
from cady.geometry import (
    Arc2,
    Circle2,
    Line2,
    Polyline2,
    Region2,
)


def test_constructors_return_new_geometry_concepts() -> None:
    assert isinstance(Line2((0, 0), (1, 0)), Line2)
    assert isinstance(Arc2((0, 0), (1, 0), (0, 1)), Arc2)
    assert isinstance(Circle2((0, 0), 1), Circle2)
    assert isinstance(Polyline2(((0, 0), (1, 0))), Polyline2)
    closed = Polyline2(((0, 0), (1, 0), (1, 1)), closed=True)
    assert isinstance(closed, Polyline2)
    assert closed.closed is True
    assert isinstance(Region2.rectangle(2, 3), Region2)
    assert isinstance(Region2.circle(1), Region2)


def test_rectangle_is_region_constructor_only_not_public_class() -> None:
    assert not hasattr(geometry, "Rectangle")
    assert isinstance(Region2.rectangle(2, 3), Region2)
