from __future__ import annotations

from dataclasses import FrozenInstanceError
from math import isclose, pi

import pytest

from cad import arc, circle, line, polyline, prism, rectangle, sphere, spline
from cad.geom.base import Shape2D, Shape3D, parse_axis
from cad.geom.shapes2d import Path
from cad.geom.shapes3d import Extrusion, Revolution
from cad.geom.vec import Vec2, Vec3


def test_vec2_ops() -> None:
    assert Vec2(1, 2) + Vec2(3, 4) == (4, 6)
    assert Vec2(3, 4).length() == 5
    assert Vec2(2, 0).normalised() == (1, 0)


def test_vec3_ops() -> None:
    assert Vec3(1, 0, 0).cross(Vec3(0, 1, 0)) == (0, 0, 1)
    assert Vec3(0, 3, 4).length() == 5
    assert Vec3(0, 2, 0).normalised() == (0, 1, 0)


def test_shape_families_are_disjoint() -> None:
    assert isinstance(line((0, 0), (1, 0)), Shape2D)
    assert not isinstance(line((0, 0), (1, 0)), Shape3D)
    assert isinstance(sphere((0, 0, 0), 1), Shape3D)
    assert not isinstance(sphere((0, 0, 0), 1), Shape2D)


def test_frozen_shape() -> None:
    shape = line((0, 0), (1, 0))
    with pytest.raises(FrozenInstanceError):
        shape.a = Vec2(2, 0)  # type: ignore[misc]


def test_line_bounds_and_close() -> None:
    closed = line((0, 0), (1, 0)).close()
    assert closed.closed
    assert isinstance(closed, Path)


def test_arc_bounds_and_points() -> None:
    shape = arc((0, 0), 1, 0, pi)
    mn, mx = shape.bounds()
    assert mn == (-1, 0)
    assert mx == (1, 1)


def test_circle_validation_and_bounds() -> None:
    with pytest.raises(ValueError):
        circle((0, 0), -1)
    assert circle((0, 0), 2).bounds() == (Vec2(-2, -2), Vec2(2, 2))


def test_rectangle_translate_acceptance() -> None:
    assert rectangle((0, 0), (1, 1)).translate(2, 0).bounds() == ((2, 0), (3, 1))


def test_polyline_validation() -> None:
    with pytest.raises(ValueError):
        polyline([])
    with pytest.raises(ValueError):
        polyline([(0, 0)], closed=True)


def test_spline_validation() -> None:
    with pytest.raises(ValueError):
        spline([(0, 0), (1, 0), (1, 1)])
    assert spline([(0, 0), (1, 0), (1, 1), (2, 1)]).bounds()[1] == (2, 1)


def test_path_composition() -> None:
    path = line((0, 0), (1, 0)) + line((1, 0), (1, 1))
    assert isinstance(path, Path)
    assert path.points()[-1] == (1, 1)


def test_path_rejects_discontinuity() -> None:
    with pytest.raises(ValueError):
        line((0, 0), (1, 0)) + line((0.5, 0), (2, 0))


def test_with_hole_closed_only() -> None:
    with pytest.raises(ValueError):
        line((0, 0), (1, 0)).with_hole(circle((0, 0), 0.1))
    assert rectangle((0, 0), (1, 1)).with_hole(circle((0.5, 0.5), 0.1)).inner_loops


def test_2d_transforms() -> None:
    shape = line((0, 0), (1, 0)).rotate((0, 0), pi / 2)
    assert isclose(shape.points()[-1].x, 0, abs_tol=1e-9)
    assert isclose(shape.points()[-1].y, 1, abs_tol=1e-9)
    assert line((0, 0), (1, 0)).mirror(line((0, 0), (0, 1))).points()[-1] == (-1, 0)


def test_2d_subtract_message() -> None:
    with pytest.raises(TypeError, match="with_hole.*Stage 6"):
        circle((0, 0), 1) - circle((0, 0), 0.5)


def test_axis_parser() -> None:
    assert parse_axis("+z") == "+z"
    with pytest.raises(ValueError):
        parse_axis("diagonal")  # type: ignore[arg-type]


def test_sphere_and_prism_bounds() -> None:
    assert sphere((0, 0, 0), 1).bounds() == (Vec3(-1, -1, -1), Vec3(1, 1, 1))
    assert prism((0, 0, 0), (1, 2, 3)).bounds() == (Vec3(0, 0, 0), Vec3(1, 2, 3))


def test_extrusion_value_validation() -> None:
    with pytest.raises(ValueError):
        line((0, 0), (1, 0)).extrude(axis="+z", distance=0.04)
    with pytest.raises(ValueError):
        circle((0, 0), 1).extrude(axis="+z", distance=0)
    with pytest.raises(ValueError):
        circle((0, 0), 1).extrude(axis="diagonal", distance=0.04)  # type: ignore[arg-type]
    assert isinstance(rectangle((0, 0), (1, 1)).extrude("+z", 1), Extrusion)


def test_revolution_value() -> None:
    rev = rectangle((1, 0), (1, 1)).revolve(line((0, 0), (0, 1)))
    assert isinstance(rev, Revolution)
    with pytest.raises(ValueError):
        rectangle((1, 0), (1, 1)).revolve(line((0, 0), (0, 1)), 0)


def test_3d_transforms() -> None:
    moved = prism((0, 0, 0), (1, 1, 1)).translate(1, 2, 3)
    assert moved.bounds() == (Vec3(1, 2, 3), Vec3(2, 3, 4))


def test_3d_subtract_message() -> None:
    with pytest.raises(TypeError, match="Stage 6"):
        prism((0, 0, 0), (1, 1, 1)) - prism((0, 0, 0), (0.5, 0.5, 0.5))
