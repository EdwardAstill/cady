"""Ready-made PointCloud2 and PointCloud3 examples."""

from __future__ import annotations

from math import cos, pi, sin

from cady import PointCloud2, PointCloud3

GRID_2D = PointCloud2(
    (float(x), float(y))
    for x in range(-3, 4)
    for y in range(-2, 3)
    if (x + y) % 2 == 0
)

RING_3D = PointCloud3(
    (
        1.4 * cos(2.0 * pi * index / 36.0),
        1.4 * sin(2.0 * pi * index / 36.0),
        0.18 * sin(8.0 * pi * index / 36.0),
    )
    for index in range(36)
)

HELIX_3D = PointCloud3(
    (
        cos(2.0 * pi * index / 18.0),
        sin(2.0 * pi * index / 18.0),
        -1.2 + 2.4 * index / 53.0,
    )
    for index in range(54)
)

SADDLE_3D = PointCloud3(
    (
        x / 3.0,
        y / 3.0,
        0.18 * ((x / 3.0) ** 2 - (y / 3.0) ** 2),
    )
    for x in range(-4, 5)
    for y in range(-4, 5)
)

POINTCLOUDS = {
    "grid_2d": GRID_2D,
    "ring_3d": RING_3D,
    "helix_3d": HELIX_3D,
    "saddle_3d": SADDLE_3D,
}


def main() -> None:
    for name, cloud in POINTCLOUDS.items():
        print(f"{name}: {len(cloud.vertices)} points")


if __name__ == "__main__":
    main()
