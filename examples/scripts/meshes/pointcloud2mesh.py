"""Visualise advancing-front meshing from an array of 3D points.

Usage:
    PYTHONPATH=src .venv/bin/python examples/scripts/meshes/pointcloud2mesh.py
    PYTHONPATH=src .venv/bin/python examples/scripts/meshes/pointcloud2mesh.py --no-view
    PYTHONPATH=src .venv/bin/python examples/scripts/meshes/pointcloud2mesh.py --grid-size 13
"""

from __future__ import annotations

import argparse
from math import cos, isfinite, pi, sin
from random import Random
from typing import NamedTuple

from cady.geometry import Mesh3, PointCloud3
from cady.view import DisplayStyle, Scene

Point3 = tuple[float, float, float]


class SurfaceSample(NamedTuple):
    point: Point3


class MeshingCase(NamedTuple):
    name: str
    cloud: PointCloud3
    mesh: Mesh3


POINT_STYLE = DisplayStyle(
    color=(0.02, 0.28, 0.36),
    point_size=7.0,
    render_mode="points",
)
MESH_STYLE = DisplayStyle(
    color=(0.74, 0.54, 0.18),
    opacity=0.58,
    render_mode="shaded",
)
Y_RANDOM_SEED = 84731


def surface_samples(grid_size: int) -> tuple[SurfaceSample, ...]:
    """Sample a warped height-field surface in row-major grid order."""
    _validate_grid_size(grid_size)
    y_columns = _irregular_y_columns(grid_size)
    samples: list[SurfaceSample] = []
    denominator = grid_size - 1
    for row in range(grid_size):
        for column in range(grid_size):
            x = -1.0 + 2.0 * column / denominator
            y = y_columns[column][row]
            point = (x, y, _surface_z(x, y))
            samples.append(SurfaceSample(point))
    return tuple(samples)


def mesh_from_samples(samples: tuple[SurfaceSample, ...], *, grid_size: int) -> Mesh3:
    """Build an advancing-front mesh from point positions only."""
    _validate_sample_grid(samples, grid_size)
    return Mesh3.from_points(tuple(sample.point for sample in samples))


def build_cases(grid_size: int = 9) -> tuple[MeshingCase, ...]:
    samples = surface_samples(grid_size)
    return (
        MeshingCase(
            "advancing-front point array",
            PointCloud3(sample.point for sample in samples),
            mesh_from_samples(samples, grid_size=grid_size),
        ),
    )


def build_scene(cases: tuple[MeshingCase, ...]) -> Scene:
    scene = Scene("point cloud to mesh")
    for case in cases:
        scene = scene.add(case.mesh, name=f"{case.name} mesh", style=MESH_STYLE)
        scene = scene.add(case.cloud, name=f"{case.name} samples", style=POINT_STYLE)
    return scene


def scene_summary(cases: tuple[MeshingCase, ...]) -> str:
    lines = ["cady point cloud meshing demo"]
    for case in cases:
        lower, upper = case.mesh.bounds()
        lines.append("")
        lines.append(case.name)
        lines.append(f"  points: {len(case.cloud.vertices)}")
        lines.append(
            f"  mesh: {len(case.mesh.vertices)} vertices, {len(case.mesh.edges)} edges, "
            f"{len(case.mesh.faces)} faces, bounds={_format_point(lower)} to {_format_point(upper)}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build and visualise meshes generated from sampled point clouds",
    )
    parser.add_argument("--grid-size", type=int, default=9)
    parser.add_argument("--tolerance", type=float, default=1e-3)
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Print summaries without opening the VisPy viewer",
    )
    args = parser.parse_args()

    if args.tolerance <= 0.0 or not isfinite(args.tolerance):
        raise ValueError("tolerance must be positive")

    cases = build_cases(args.grid_size)
    print(scene_summary(cases))
    print(f"\n  grid: {args.grid_size} x {args.grid_size}")
    print(f"  tolerance: {args.tolerance}")

    if args.no_view:
        print("\nVisPy viewer skipped.")
        print("Done.")
        return

    from cady.view import view_scene

    view_scene(build_scene(cases), tolerance=args.tolerance, title="point cloud to mesh")
    print("\nDone.")


def _validate_grid_size(grid_size: int) -> None:
    if grid_size < 3:
        raise ValueError("grid_size must be at least 3")


def _validate_sample_grid(samples: tuple[SurfaceSample, ...], grid_size: int) -> None:
    _validate_grid_size(grid_size)
    expected = grid_size * grid_size
    if len(samples) != expected:
        raise ValueError(f"expected {expected} samples for a {grid_size} x {grid_size} grid")


def _surface_z(x: float, y: float) -> float:
    return (
        0.22 * sin(1.7 * pi * x + 0.35) * cos(1.25 * pi * y - 0.2)
        + 0.11 * sin(3.1 * pi * (x - 0.45 * y))
        + 0.08 * x * y
    )


def _irregular_y_columns(grid_size: int) -> tuple[tuple[float, ...], ...]:
    rng = Random(Y_RANDOM_SEED)
    columns: list[tuple[float, ...]] = []
    base_step = 2.0 / (grid_size - 1)
    for _column in range(grid_size):
        y_values = [-1.0]
        for _row in range(1, grid_size):
            step = base_step * rng.uniform(0.72, 1.28)
            y_values.append(y_values[-1] + step)
        span = y_values[-1] - y_values[0]
        columns.append(tuple(-1.0 + 2.0 * (y - y_values[0]) / span for y in y_values))
    return tuple(columns)


def _format_point(point: Point3) -> str:
    return "(" + ", ".join(f"{coordinate:.3g}" for coordinate in point) + ")"


if __name__ == "__main__":
    main()
