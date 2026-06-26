"""Build a quarter-sphere wireframe from four polylines.

Usage from the repository root:
    PYTHONPATH=src .venv/bin/python examples/testing/testing.py
"""

from __future__ import annotations

from collections.abc import Iterable
from math import cos, pi, sin

from cady import (
    Camera,
    DirectionalLight,
    DisplayStyle,
    Mesh3D,
    Polyline3D,
    Scene,
    Vec3,
    Wireframe3D,
)
from cady.view import view_scene

Point3 = tuple[float, float, float]

RADIUS = 5.0
SAMPLES = 33
SLICE_Y_VALUES = (-5, -2.5, 0.0, 2.5, 5)
PLANE_GRID_STEPS = 4
ARC_ANGLES = {
    "under": pi / 2.0,
    "around": 0.0,
    "between": pi / 4.0,
}
WIRE_STYLE = DisplayStyle(color=(0.08, 0.28, 0.60), render_mode="wireframe")
PLANE_STYLES = (
    DisplayStyle(color=(0.78, 0.16, 0.12), render_mode="wireframe"),
)
CAMERA = Camera.orthographic(
    position=(9.0, -12.0, 7.0),
    target=(RADIUS / 2.0, 0.0, -RADIUS / 2.0),
    scale=12.0,
)
LIGHT = DirectionalLight(direction=(-1.0, -1.0, -2.0), intensity=1.1)


def main() -> None:
    polylines = quarter_sphere_polylines(radius=RADIUS, samples=SAMPLES)
    wireframe = wireframe_from_polylines(polylines.values())
    planes = slice_planes(radius=RADIUS, y_values=SLICE_Y_VALUES)

    print("quarter sphere wireframe")
    for name, polyline in polylines.items():
        start = format_point(polyline.vertices[0])
        end = format_point(polyline.vertices[-1])
        print(f"{name}: {len(polyline.vertices)} vertices, A={start}, B={end}")
    print_wireframe_summary(wireframe)
    print(f"slice planes: {', '.join(f'y={y:g}' for y, _plane in planes)}")

    view_scene(build_scene(wireframe, planes), title="Quarter sphere slice planes")


def quarter_sphere_polylines(
    *,
    radius: float,
    samples: int,
) -> dict[str, Polyline3D]:
    if radius <= 0.0:
        raise ValueError("radius must be positive")
    if samples < 3:
        raise ValueError("samples must be at least 3")

    a: Point3 = (0.0, -radius, 0.0)
    b: Point3 = (0.0, radius, 0.0)
    polylines: dict[str, Polyline3D] = {
        "diameter": Polyline3D((a, (0.0, 0.0, 0.0), b)),
    }

    for name, angle in ARC_ANGLES.items():
        polylines[name] = Polyline3D(
            sphere_arc(radius=radius, section_angle=angle, samples=samples)
        )
    return polylines


def sphere_arc(
    *,
    radius: float,
    section_angle: float,
    samples: int,
) -> tuple[Point3, ...]:
    """Return an A-to-B semicircle in a rotated great-circle plane."""
    points: list[Point3] = [(0.0, -radius, 0.0)]
    for index in range(1, samples - 1):
        theta = -pi / 2.0 + pi * index / (samples - 1)
        side = radius * cos(theta)
        points.append(
            (
                side * cos(section_angle),
                radius * sin(theta),
                -side * sin(section_angle),
            )
        )
    points.append((0.0, radius, 0.0))
    return tuple(points)


def wireframe_from_polylines(polylines: Iterable[Polyline3D]) -> Wireframe3D:
    vertices: list[Vec3] = []
    vertex_indices: dict[Point3, int] = {}
    edges: list[tuple[int, int]] = []

    for polyline in polylines:
        previous: int | None = None
        for vertex in polyline.vertices:
            point = vertex.tuple()
            current = vertex_indices.get(point)
            if current is None:
                current = len(vertices)
                vertex_indices[point] = current
                vertices.append(Vec3(*point))
            if previous is not None and previous != current:
                edges.append((previous, current))
            previous = current

    return Wireframe3D(tuple(vertices), tuple(edges))


def slice_planes(
    *,
    radius: float,
    y_values: Iterable[float],
) -> tuple[tuple[float, Mesh3D], ...]:
    return tuple(
        (
            y,
            plane_grid(
                y=y,
                x_min=0.0,
                x_max=radius,
                z_min=-radius,
                z_max=0.0,
                steps=PLANE_GRID_STEPS,
            ),
        )
        for y in y_values
    )


def plane_grid(
    *,
    y: float,
    x_min: float,
    x_max: float,
    z_min: float,
    z_max: float,
    steps: int,
) -> Mesh3D:
    vertices = [
        Vec3(x_min, y, z_max),
        Vec3(x_max, y, z_max),
        Vec3(x_max, y, z_min),
        Vec3(x_min, y, z_min),
    ]
    edges = [(0, 1), (1, 2), (2, 3), (3, 0)]

    for step in range(1, steps):
        x = x_min + (x_max - x_min) * step / steps
        z = z_min + (z_max - z_min) * step / steps
        edges.append(_add_segment(vertices, (x, y, z_min), (x, y, z_max)))
        edges.append(_add_segment(vertices, (x_min, y, z), (x_max, y, z)))

    return Mesh3D(tuple(vertices), ((0, 1, 2), (0, 2, 3)), tuple(edges))


def _add_segment(
    vertices: list[Vec3],
    start: Point3,
    end: Point3,
) -> tuple[int, int]:
    start_index = len(vertices)
    vertices.append(Vec3(*start))
    vertices.append(Vec3(*end))
    return (start_index, start_index + 1)


def build_scene(
    wireframe: Wireframe3D,
    planes: Iterable[tuple[float, Mesh3D]],
) -> Scene:
    scene = Scene(name="quarter_sphere_slice_planes").add(
        wireframe,
        name="quarter_sphere_wireframe",
        style=WIRE_STYLE,
    )
    for index, (y, plane) in enumerate(planes):
        scene = scene.add(
            plane,
            name=f"slice_plane_y_{y:g}",
            style=PLANE_STYLES[index % len(PLANE_STYLES)],
        )
    return scene.with_camera(CAMERA, name="isometric").with_light(LIGHT)


def print_wireframe_summary(wireframe: Wireframe3D) -> None:
    lower, upper = wireframe.bounds()
    print(
        f"wireframe: {len(wireframe.vertices)} vertices, {len(wireframe.edges)} edges, "
        f"bounds={format_point(lower)} to {format_point(upper)}"
    )


def format_point(point: Point3 | Vec3) -> str:
    x, y, z = point.tuple() if isinstance(point, Vec3) else point
    return f"({float(x):.3g}, {float(y):.3g}, {float(z):.3g})"


if __name__ == "__main__":
    main()
