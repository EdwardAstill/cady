from __future__ import annotations

from math import isclose, pi

from cady import line, prism
from cady.domain.vec import Vec2, Vec3
from cady.ops.transforms import (
    mirror2,
    mirror_point2,
    mirror_point3,
    rotate2,
    rotate_point2,
    rotate_point3,
    scale2,
    scale_point2,
    translate2,
    translate3,
    translate_point2,
    translate_point3,
)


def test_point2_transforms() -> None:
    assert translate_point2(Vec2(1, 2), 3, 4) == Vec2(4, 6)
    rotated = rotate_point2(Vec2(1, 0), (0, 0), pi / 2)
    assert isclose(rotated.x, 0, abs_tol=1e-9)
    assert isclose(rotated.y, 1, abs_tol=1e-9)
    assert scale_point2(Vec2(2, 3), 2, centre=(1, 1)) == Vec2(3, 5)
    assert mirror_point2(Vec2(2, 0), (0, 0), (0, 1)) == Vec2(-2, 0)


def test_shape2_transforms() -> None:
    moved = translate2(line((0, 0), (1, 0)), 1, 2)
    assert moved.points() == (Vec2(1, 2), Vec2(2, 2))

    rotated = rotate2(line((0, 0), (1, 0)), (0, 0), pi / 2)
    assert isclose(rotated.points()[-1].x, 0, abs_tol=1e-9)
    assert isclose(rotated.points()[-1].y, 1, abs_tol=1e-9)

    scaled = scale2(line((1, 1), (2, 1)), 2, centre=(1, 1))
    assert scaled.points()[-1] == Vec2(3, 1)

    mirrored = mirror2(line((0, 0), (1, 0)), line((0, 0), (0, 1)))
    assert mirrored.points()[-1] == Vec2(-1, 0)


def test_point3_transforms() -> None:
    assert translate_point3(Vec3(1, 2, 3), 4, 5, 6) == Vec3(5, 7, 9)

    rotated = rotate_point3(Vec3(1, 0, 0), (0, 0, 0), (0, 0, 1), pi / 2)
    assert isclose(rotated.x, 0, abs_tol=1e-9)
    assert isclose(rotated.y, 1, abs_tol=1e-9)

    assert mirror_point3(Vec3(1, 2, 3), (0, 0, 0), (1, 0, 0)) == Vec3(-1, 2, 3)


def test_shape3_transforms() -> None:
    moved = translate3(prism((0, 0, 0), (1, 1, 1)), 1, 2, 3)

    assert moved.bounds() == (Vec3(1, 2, 3), Vec3(2, 3, 4))
