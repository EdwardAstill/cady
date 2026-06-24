from __future__ import annotations

import cady.geometry2d as geometry2d
from cady.geometry2d import (
    Arc2D,
    Circle2D,
    ClosedPolyline2D,
    Line2D,
    Polyline2D,
    Profile2D,
    arc2d,
    circle2d,
    line2d,
    polyline2d,
    profile_circle,
    profile_rectangle,
)


def test_factories_return_new_geometry2d_concepts() -> None:
    assert isinstance(line2d((0, 0), (1, 0)), Line2D)
    assert isinstance(arc2d((0, 0), 1, 0, 1), Arc2D)
    assert isinstance(circle2d((0, 0), 1), Circle2D)
    assert isinstance(polyline2d(((0, 0), (1, 0))), Polyline2D)
    assert isinstance(polyline2d(((0, 0), (1, 0), (1, 1)), closed=True), ClosedPolyline2D)
    assert isinstance(profile_rectangle(2, 3), Profile2D)
    assert isinstance(profile_circle(1), Profile2D)


def test_rectangle_is_factory_profile_only_not_public_class() -> None:
    assert not hasattr(geometry2d, "Rectangle")
    assert isinstance(Profile2D.rectangle(2, 3), Profile2D)
