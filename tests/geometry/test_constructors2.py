from __future__ import annotations

import cady.geometry as geometry
from cady.geometry import (
    Arc2,
    Circle2,
    ClosedPolyline2,
    Line2,
    Polyline2,
    Profile2,
)
from cady.operations import (
    arc2,
    circle2,
    line2,
    polyline2,
    profile_circle,
    profile_rectangle,
)


def test_constructors_return_new_geometry_concepts() -> None:
    assert isinstance(line2((0, 0), (1, 0)), Line2)
    assert isinstance(arc2((0, 0), 1, 0, 1), Arc2)
    assert isinstance(circle2((0, 0), 1), Circle2)
    assert isinstance(polyline2(((0, 0), (1, 0))), Polyline2)
    assert isinstance(polyline2(((0, 0), (1, 0), (1, 1)), closed=True), ClosedPolyline2)
    assert isinstance(profile_rectangle(2, 3), Profile2)
    assert isinstance(profile_circle(1), Profile2)


def test_rectangle_is_constructor_profile_only_not_public_class() -> None:
    assert not hasattr(geometry, "Rectangle")
    assert isinstance(Profile2.rectangle(2, 3), Profile2)
