"""Ready-made Wireframe3 examples."""

from __future__ import annotations

from math import cos, pi, sin

from cady import Polyline3, Wireframe3

Point3 = tuple[float, float, float]
Edge = tuple[int, int]


CUBE_SKELETON = Wireframe3.from_edges(
    (
        (-1.0, -1.0, -1.0),
        (1.0, -1.0, -1.0),
        (1.0, 1.0, -1.0),
        (-1.0, 1.0, -1.0),
        (-1.0, -1.0, 1.0),
        (1.0, -1.0, 1.0),
        (1.0, 1.0, 1.0),
        (-1.0, 1.0, 1.0),
    ),
    (
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    ),
)

TETRA_FRAME = Wireframe3.from_edges(
    (
        (1.1, 1.1, 1.1),
        (-1.1, -1.1, 1.1),
        (-1.1, 1.1, -1.1),
        (1.1, -1.1, -1.1),
    ),
    ((0, 1), (0, 2), (0, 3), (1, 2), (2, 3), (3, 1)),
)

ROOF_TRUSS = Wireframe3.from_edges(
    (
        (-2.0, -0.8, 0.0),
        (-1.0, -0.8, 0.0),
        (0.0, -0.8, 0.0),
        (1.0, -0.8, 0.0),
        (2.0, -0.8, 0.0),
        (-2.0, 0.8, 0.0),
        (-1.0, 0.8, 0.0),
        (0.0, 0.8, 0.0),
        (1.0, 0.8, 0.0),
        (2.0, 0.8, 0.0),
        (-1.0, 0.0, 1.0),
        (0.0, 0.0, 1.35),
        (1.0, 0.0, 1.0),
    ),
    (
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 4),
        (5, 6),
        (6, 7),
        (7, 8),
        (8, 9),
        (0, 5),
        (1, 6),
        (2, 7),
        (3, 8),
        (4, 9),
        (1, 10),
        (6, 10),
        (2, 11),
        (7, 11),
        (3, 12),
        (8, 12),
        (10, 11),
        (11, 12),
        (0, 10),
        (4, 12),
    ),
)

HELIX_PATH = Wireframe3.from_polylines(
    (
        Polyline3(
            (
                (
                    cos(2.0 * pi * index / 20.0),
                    sin(2.0 * pi * index / 20.0),
                    -1.4 + 2.8 * index / 79.0,
                )
                for index in range(80)
            )
        ),
    )
)

LADDER = Wireframe3.from_edges(
    (
        *((-1.0, 0.0, index * 0.35) for index in range(9)),
        *((1.0, 0.0, index * 0.35) for index in range(9)),
    ),
    tuple((index, index + 1) for index in range(8))
    + tuple((index + 9, index + 10) for index in range(8))
    + tuple((index, index + 9) for index in range(9)),
)

WIREFRAMES = {
    "cube_skeleton": CUBE_SKELETON,
    "tetra_frame": TETRA_FRAME,
    "roof_truss": ROOF_TRUSS,
    "helix_path": HELIX_PATH,
    "ladder": LADDER,
}


def main() -> None:
    for name, wireframe in WIREFRAMES.items():
        print(f"{name}: {len(wireframe.vertices)} vertices, {len(wireframe.edges)} edges")


if __name__ == "__main__":
    main()
