"""Visualise boundary loops on a nontrivial triangle mesh.

Usage:
    PYTHONPATH=src .venv/bin/python examples/scripts/visualise_mesh_boundary.py --no-view
    PYTHONPATH=src .venv/bin/python examples/scripts/visualise_mesh_boundary.py
"""

from __future__ import annotations

import argparse
from math import cos, sin

from cady import Camera, DirectionalLight, DisplayStyle, Mesh3D, Scene, Vec3, Wireframe3D
from cady.numeric import ArrayPolyline3

MESH_STYLE = DisplayStyle(color=(0.46, 0.52, 0.50), opacity=0.9)
BOUNDARY_STYLES = (
    DisplayStyle(color=(1.0, 0.08, 0.58), render_mode="wireframe", line_width=2.0),
    DisplayStyle(color=(0.0, 0.42, 1.0), render_mode="wireframe", line_width=2.0),
    DisplayStyle(color=(0.1, 0.72, 0.22), render_mode="wireframe", line_width=2.0),
    DisplayStyle(color=(0.95, 0.78, 0.08), render_mode="wireframe", line_width=2.0),
)
LIGHT = DirectionalLight(direction=(0.35, -0.65, -0.55), intensity=1.0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show the boundary loops of a generated open triangle mesh.",
    )
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Print mesh and boundary summaries without opening a VisPy window.",
    )
    args = parser.parse_args()

    mesh = build_complicated_mesh()
    loops = mesh.boundary_loops
    boundaries = _wireframes_from_boundary_loops(loops)

    print("cady mesh boundary demo")
    print_mesh_summary("mesh", mesh)
    print(
        "  boundary loops: "
        f"{len(loops)} ({_format_loop_edge_counts(loops)})"
    )

    if args.no_view:
        print("VisPy viewer skipped.")
        return

    from cady.visualisation import view_scene

    view_scene(
        build_scene(mesh, boundaries),
        title="boundary loops on complicated mesh",
    )


def build_complicated_mesh() -> Mesh3D:
    x_cells = 32
    y_cells = 24
    vertices: list[Vec3] = []
    for y_index in range(y_cells + 1):
        y = float(y_index)
        for x_index in range(x_cells + 1):
            x = float(x_index)
            z = _surface_height(x, y)
            vertices.append(Vec3(x, y, z))

    faces: list[tuple[int, int, int]] = []
    for y_index in range(y_cells):
        for x_index in range(x_cells):
            if _is_hole_cell(x_index, y_index):
                continue
            lower_left = _grid_index(x_index, y_index, x_cells)
            lower_right = _grid_index(x_index + 1, y_index, x_cells)
            upper_right = _grid_index(x_index + 1, y_index + 1, x_cells)
            upper_left = _grid_index(x_index, y_index + 1, x_cells)
            faces.append((lower_left, lower_right, upper_right))
            faces.append((lower_left, upper_right, upper_left))

    return Mesh3D(tuple(vertices), tuple(faces), _display_edges(faces))


def build_scene(mesh: Mesh3D, boundaries: tuple[Wireframe3D, ...]) -> Scene:
    lower, upper = mesh.bounds()
    centre = _bounds_centre(lower, upper)
    camera = _fit_camera(lower, upper)
    scene = Scene(name="complicated_mesh_boundary").add(mesh, name="mesh", style=MESH_STYLE)
    for index, boundary in enumerate(boundaries, start=1):
        scene = scene.add(
            boundary,
            name=f"boundary_loop_{index}",
            style=_boundary_style(index - 1),
        )
    return scene.with_camera(camera, name="isometric").with_light(LIGHT).with_metadata(
        target=_format_point(centre),
    )


def _surface_height(x: float, y: float) -> float:
    return 0.9 * sin(x * 0.34) + 0.55 * cos(y * 0.41) + 0.25 * sin((x + y) * 0.21)


def _is_hole_cell(x_index: int, y_index: int) -> bool:
    holes = (
        (6, 12, 5, 10),
        (18, 25, 8, 14),
        (10, 16, 15, 20),
    )
    return any(
        x_min <= x_index < x_max and y_min <= y_index < y_max
        for x_min, x_max, y_min, y_max in holes
    )


def _grid_index(x_index: int, y_index: int, x_cells: int) -> int:
    return y_index * (x_cells + 1) + x_index


def _display_edges(faces: list[tuple[int, int, int]]) -> tuple[tuple[int, int], ...]:
    edges: set[tuple[int, int]] = set()
    for a, b, c in faces:
        for start, end in ((a, b), (b, c), (c, a)):
            edges.add((min(start, end), max(start, end)))
    return tuple(sorted(edges))


def _wireframes_from_boundary_loops(
    loops: tuple[ArrayPolyline3, ...],
) -> tuple[Wireframe3D, ...]:
    return tuple(_wireframe_from_boundary_loop(loop) for loop in loops)


def _wireframe_from_boundary_loop(loop: ArrayPolyline3) -> Wireframe3D:
    points = [
        Vec3(float(point[0]), float(point[1]), float(point[2]))
        for point in loop.vertices
    ]
    if len(points) >= 2 and points[0] == points[-1]:
        points = points[:-1]
    edges = tuple((index, (index + 1) % len(points)) for index in range(len(points)))
    return Wireframe3D(tuple(points), edges)


def _boundary_style(index: int) -> DisplayStyle:
    return BOUNDARY_STYLES[index % len(BOUNDARY_STYLES)]


def print_mesh_summary(label: str, mesh: Mesh3D) -> None:
    lower, upper = mesh.bounds()
    print(
        f"{label}: {len(mesh.vertices)} vertices, {len(mesh.edges)} edges, "
        f"{len(mesh.faces)} faces, bounds={_format_point(lower)} to {_format_point(upper)}"
    )


def _fit_camera(lower: Vec3, upper: Vec3) -> Camera:
    centre = _bounds_centre(lower, upper)
    span = (upper.x - lower.x, upper.y - lower.y, upper.z - lower.z)
    scale = max(span[0], span[1], span[2] * 5.0, 1.0) * 1.12
    distance = max(span) * 1.8 or 1.0
    return Camera.orthographic(
        position=(centre.x + distance, centre.y - distance, centre.z + distance * 0.7),
        target=centre.tuple(),
        scale=scale,
    )


def _bounds_centre(lower: Vec3, upper: Vec3) -> Vec3:
    return Vec3(
        (lower.x + upper.x) / 2.0,
        (lower.y + upper.y) / 2.0,
        (lower.z + upper.z) / 2.0,
    )


def _format_point(point: Vec3) -> str:
    return f"({point.x:g}, {point.y:g}, {point.z:g})"


def _format_loop_edge_counts(loops: tuple[ArrayPolyline3, ...]) -> str:
    counts = [max(len(loop.vertices) - 1, 0) for loop in loops]
    return ", ".join(f"{count} edges" for count in counts)


if __name__ == "__main__":
    main()
