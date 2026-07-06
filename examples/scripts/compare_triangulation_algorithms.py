"""Compare cady's 2D polygon triangulation algorithms.

Run from the repository root:

    PYTHONPATH=src .venv/bin/python examples/scripts/compare_triangulation_algorithms.py

Pass ``--view`` to open a scene comparing the generated meshes.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, TypeAlias

import numpy as np
from numpy.typing import NDArray

from cady import Camera, DisplayStyle, Mesh3, Scene
from cady.operations import triangulate as triangulate2d

Point2: TypeAlias = tuple[float, float]
EdgeIndex: TypeAlias = tuple[int, int]
FaceIndex: TypeAlias = tuple[int, int, int]
AlgorithmName: TypeAlias = Literal["ear_delaunay_refinement", "pizza_web"]

TOLERANCE = 1e-6
ALGORITHMS: tuple[AlgorithmName, ...] = ("ear_delaunay_refinement", "pizza_web")

SHAPES: tuple[tuple[str, tuple[Point2, ...]], ...] = (
    (
        "coastal concave",
        (
            (-1.65, -0.25),
            (-1.05, -0.9),
            (-0.2, -0.82),
            (0.35, -1.18),
            (1.35, -0.6),
            (1.7, 0.18),
            (0.85, 0.5),
            (0.55, 1.1),
            (-0.28, 0.68),
            (-1.18, 0.96),
            (-1.58, 0.35),
        ),
    ),
    (
        "narrow channel",
        (
            (-2.0, -1.0),
            (2.0, -1.0),
            (2.0, -0.55),
            (-1.15, -0.55),
            (-1.15, 0.55),
            (2.0, 0.55),
            (2.0, 1.0),
            (-2.0, 1.0),
        ),
    ),
    (
        "comb teeth",
        (
            (-2.0, -1.0),
            (2.0, -1.0),
            (2.0, 1.0),
            (1.65, 1.0),
            (1.65, 0.15),
            (1.25, 0.15),
            (1.25, 1.0),
            (0.85, 1.0),
            (0.85, 0.15),
            (0.45, 0.15),
            (0.45, 1.0),
            (0.05, 1.0),
            (0.05, 0.15),
            (-0.35, 0.15),
            (-0.35, 1.0),
            (-0.75, 1.0),
            (-0.75, 0.15),
            (-1.15, 0.15),
            (-1.15, 1.0),
            (-2.0, 1.0),
        ),
    ),
    (
        "crescent moon",
        (
            (0.9, -1.15),
            (0.15, -1.45),
            (-0.75, -1.25),
            (-1.35, -0.7),
            (-1.55, 0.0),
            (-1.35, 0.7),
            (-0.75, 1.25),
            (0.15, 1.45),
            (0.9, 1.15),
            (0.45, 0.72),
            (0.18, 0.25),
            (0.1, -0.25),
            (0.35, -0.78),
        ),
    ),
    (
        "hairline slot",
        (
            (-2.2, -0.28),
            (2.2, -0.28),
            (2.2, -0.18),
            (-1.85, -0.18),
            (-1.85, -0.14),
            (2.2, -0.14),
            (2.2, 0.28),
            (-2.2, 0.28),
        ),
    ),
)

MESH_STYLES = {
    "ear_delaunay_refinement": DisplayStyle(color=(0.35, 0.58, 0.74), opacity=0.86),
    "pizza_web": DisplayStyle(color=(0.84, 0.55, 0.33), opacity=0.86),
}


@dataclass(frozen=True, slots=True)
class TriangulationCase:
    shape_name: str
    algorithm: AlgorithmName
    input_vertices: int
    nodes: NDArray[np.float64]
    edges: NDArray[np.int64]
    faces: NDArray[np.int64]


def loop_edges(count: int) -> NDArray[np.int64]:
    return np.asarray(tuple((index, (index + 1) % count) for index in range(count)), dtype=np.int64)


def triangulate_shape(
    shape_name: str,
    points: Sequence[Point2],
    *,
    algorithm: AlgorithmName,
    tolerance: float = TOLERANCE,
) -> TriangulationCase:
    nodes = np.asarray(points, dtype=np.float64)
    out_nodes, out_edges, faces = triangulate2d(
        nodes,
        loop_edges(len(points)),
        algorithm=algorithm,
        tolerance=tolerance,
    )
    return TriangulationCase(
        shape_name,
        algorithm,
        len(points),
        out_nodes,
        out_edges,
        faces,
    )


def triangulate_shapes(
    shapes: Iterable[tuple[str, Sequence[Point2]]] = SHAPES,
    *,
    algorithms: Iterable[AlgorithmName] = ALGORITHMS,
    tolerance: float = TOLERANCE,
) -> tuple[TriangulationCase, ...]:
    return tuple(
        triangulate_shape(
            name,
            points,
            algorithm=algorithm,
            tolerance=tolerance,
        )
        for name, points in shapes
        for algorithm in algorithms
    )


def mesh_from_case(
    case: TriangulationCase,
    *,
    x_offset: float = 0.0,
    y_offset: float = 0.0,
) -> Mesh3:
    vertices = tuple(
        (float(x + x_offset), float(y + y_offset), 0.0)
        for x, y in case.nodes
    )
    edges: tuple[EdgeIndex, ...] = tuple((int(start), int(end)) for start, end in case.edges)
    faces: tuple[FaceIndex, ...] = tuple(
        (int(first), int(second), int(third)) for first, second, third in case.faces
    )
    return Mesh3(vertices, faces, edges)


def build_scene(cases: Sequence[TriangulationCase]) -> Scene:
    spacing_x = 5.25
    spacing_y = 3.35
    rows = max(1, len({case.shape_name for case in cases}))
    scene = Scene(
        "triangulation_algorithm_comparison",
        camera=Camera.orthographic(
            position=(0.0, 0.0, 16.0),
            target=(0.0, 0.0, 0.0),
            up=(0.0, 1.0, 0.0),
            scale=max(spacing_x * 2.2, spacing_y * rows * 1.05),
        ),
    )
    row_by_shape = {name: index for index, (name, _points) in enumerate(SHAPES)}
    column_by_algorithm = {
        "ear_delaunay_refinement": -0.5,
        "pizza_web": 0.5,
    }
    for case in cases:
        row = row_by_shape[case.shape_name]
        x_offset = column_by_algorithm[case.algorithm] * spacing_x
        y_offset = ((rows - 1) / 2.0 - row) * spacing_y
        scene = scene.add(
            mesh_from_case(case, x_offset=x_offset, y_offset=y_offset),
            name=f"{case.shape_name} - {case.algorithm}",
            style=MESH_STYLES[case.algorithm],
        )
    return scene


def summary(cases: Sequence[TriangulationCase]) -> str:
    lines = ["cady triangulation algorithm comparison"]
    for case in cases:
        lines.append(
            f"{case.shape_name:16} {case.algorithm:24} "
            f"{case.input_vertices:2d} input -> "
            f"{len(case.nodes):3d} nodes, {len(case.edges):3d} edges, {len(case.faces):3d} faces"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--view", action="store_true", help="open a scene comparing the meshes")
    args = parser.parse_args(argv)

    cases = triangulate_shapes()
    print(summary(cases))

    if args.view:
        build_scene(cases).view(tolerance=TOLERANCE)


if __name__ == "__main__":
    main()
