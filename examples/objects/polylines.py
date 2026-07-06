"""Ready-made Polyline2 and Polyline3 examples."""

from __future__ import annotations

from cady import Polyline2, Polyline3

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]


def _to_2d(points: tuple[Point3, ...]) -> tuple[Point2, ...]:
    return tuple((x, y) for x, y, _z in points)


COASTAL_CONCAVE_POINTS: tuple[Point3, ...] = (
    (-1.65, -0.25, 0.0),
    (-1.05, -0.9, 0.0),
    (-0.2, -0.82, 0.0),
    (0.35, -1.18, 0.0),
    (1.35, -0.6, 0.0),
    (1.7, 0.18, 0.0),
    (0.85, 0.5, 0.0),
    (0.55, 1.1, 0.0),
    (-0.28, 0.68, 0.0),
    (-1.18, 0.96, 0.0),
    (-1.58, 0.35, 0.0),
)
NARROW_CHANNEL_POINTS: tuple[Point3, ...] = (
    (-2.0, -1.0, 0.0),
    (2.0, -1.0, 0.0),
    (2.0, -0.55, 0.0),
    (-1.15, -0.55, 0.0),
    (-1.15, 0.55, 0.0),
    (2.0, 0.55, 0.0),
    (2.0, 1.0, 0.0),
    (-2.0, 1.0, 0.0),
)
COMB_POINTS: tuple[Point3, ...] = (
    (-2.0, -1.0, 0.0),
    (2.0, -1.0, 0.0),
    (2.0, 1.0, 0.0),
    (1.65, 1.0, 0.0),
    (1.65, 0.15, 0.0),
    (1.25, 0.15, 0.0),
    (1.25, 1.0, 0.0),
    (0.85, 1.0, 0.0),
    (0.85, 0.15, 0.0),
    (0.45, 0.15, 0.0),
    (0.45, 1.0, 0.0),
    (0.05, 1.0, 0.0),
    (0.05, 0.15, 0.0),
    (-0.35, 0.15, 0.0),
    (-0.35, 1.0, 0.0),
    (-0.75, 1.0, 0.0),
    (-0.75, 0.15, 0.0),
    (-1.15, 0.15, 0.0),
    (-1.15, 1.0, 0.0),
    (-2.0, 1.0, 0.0),
)
CRESCENT_POINTS: tuple[Point3, ...] = (
    (0.9, -1.15, 0.0),
    (0.15, -1.45, 0.0),
    (-0.75, -1.25, 0.0),
    (-1.35, -0.7, 0.0),
    (-1.55, 0.0, 0.0),
    (-1.35, 0.7, 0.0),
    (-0.75, 1.25, 0.0),
    (0.15, 1.45, 0.0),
    (0.9, 1.15, 0.0),
    (0.45, 0.72, 0.0),
    (0.18, 0.25, 0.0),
    (0.1, -0.25, 0.0),
    (0.35, -0.78, 0.0),
)

COASTAL_CONCAVE = Polyline3(COASTAL_CONCAVE_POINTS, closed=True)
NARROW_CHANNEL = Polyline3(NARROW_CHANNEL_POINTS, closed=True)
COMB = Polyline3(COMB_POINTS, closed=True)
CRESCENT = Polyline3(CRESCENT_POINTS, closed=True)
STAR = Polyline2(
    (
        (0.0, 1.6),
        (0.38, 0.48),
        (1.55, 0.48),
        (0.6, -0.18),
        (0.95, -1.35),
        (0.0, -0.62),
        (-0.95, -1.35),
        (-0.6, -0.18),
        (-1.55, 0.48),
        (-0.38, 0.48),
    ),
    closed=True,
)
RISING_ZIGZAG = Polyline3(
    (
        (-1.8, -0.7, 0.0),
        (-1.2, 0.6, 0.35),
        (-0.5, -0.45, 0.7),
        (0.15, 0.75, 1.05),
        (0.9, -0.35, 1.4),
        (1.65, 0.55, 1.75),
    )
)

POLYLINES = {
    "coastal_concave": COASTAL_CONCAVE,
    "narrow_channel": NARROW_CHANNEL,
    "comb": COMB,
    "crescent": CRESCENT,
    "star": STAR,
    "rising_zigzag": RISING_ZIGZAG,
}

POLYLINE2 = {
    "coastal_concave": Polyline2(_to_2d(COASTAL_CONCAVE_POINTS), closed=True),
    "narrow_channel": Polyline2(_to_2d(NARROW_CHANNEL_POINTS), closed=True),
    "comb": Polyline2(_to_2d(COMB_POINTS), closed=True),
    "crescent": Polyline2(_to_2d(CRESCENT_POINTS), closed=True),
    "star": STAR,
}


def main() -> None:
    for name, polyline in POLYLINES.items():
        print(f"{name}: {len(polyline.points())} points, closed={polyline.closed}")


if __name__ == "__main__":
    main()
