"""Build a quarter-sphere wireframe from three polylines.

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
    Mesh3,
    PointCloud3,
    Polyline3,
    Scene,
    Wireframe3,
)
from cady.view import view_scene

Point3 = tuple[float, float, float]
EdgeIndex = tuple[int, int]
FaceIndex = tuple[int, int, int]
NodeRows = list[list[Point3]]

RADIUS = 5.0
SAMPLES = 33
MIN_SLICE_Y = -5.0
MAX_SLICE_Y = 5.0
SLICES = 8
PLANE_GRID_STEPS = 4
INTERSECTION_TOLERANCE = 1e-9
ARC_ANGLES = [pi / 2.0, pi / 4.0, 0.0]
WIRE_STYLE = DisplayStyle(color=(0.08, 0.28, 0.60), render_mode="wireframe")
PLANE_STYLES = (
    DisplayStyle(color=(0.78, 0.16, 0.12), render_mode="wireframe"),
)
NODE_STYLE = DisplayStyle(
    color=(0.96, 0.68, 0.08),
    point_size=9.0,
    render_mode="points",
)
NODE_MESH_STYLE = DisplayStyle(
    color=(0.12, 0.56, 0.32),
    render_mode="shaded",
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
    y_values = slice_y_values(min_y=MIN_SLICE_Y, max_y=MAX_SLICE_Y, slices=SLICES)
    planes = slice_planes(radius=RADIUS, y_values=y_values)
    nodes = intersection_nodes(wireframe, y_values=y_values)
    node_cloud = intersection_nodes_to_point_cloud(nodes)

    print("quarter sphere wireframe")
    for name, polyline in polylines.items():
        start = format_point(polyline.vertices[0])
        end = format_point(polyline.vertices[-1])
        print(f"{name}: {len(polyline.vertices)} vertices, A={start}, B={end}")
    print_wireframe_summary(wireframe)
    print(f"slice planes: {', '.join(f'y={y:g}' for y, _plane in planes)}")
    print(f"intersection nodes: {len(node_cloud.vertices)}")

    view_scene(build_scene(wireframe, planes, nodes), title="Quarter sphere slice planes")


def slice_y_values(
    *,
    min_y: float,
    max_y: float,
    slices: int,
) -> tuple[float, ...]:
    if slices <= 2:
        raise ValueError("slices must be greater than 2")
    if min_y >= max_y:
        raise ValueError("min_y must be less than max_y")

    step = (max_y - min_y) / (slices - 1)
    return tuple(min_y + step * index for index in range(slices))


def quarter_sphere_polylines(
    *,
    radius: float,
    samples: int,
) -> dict[str, Polyline3]:
    if radius <= 0.0:
        raise ValueError("radius must be positive")
    if samples < 3:
        raise ValueError("samples must be at least 3")

    return {
        f"arc_{index}": Polyline3(
            sphere_arc(radius=radius, section_angle=angle, samples=samples)
        )
        for index, angle in enumerate(ARC_ANGLES, start=1)
    }


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


def wireframe_from_polylines(polylines: Iterable[Polyline3]) -> Wireframe3:
    vertices: list[Point3] = []
    vertex_indices: dict[Point3, int] = {}
    edges: list[tuple[int, int]] = []

    for polyline in polylines:
        previous: int | None = None
        for vertex in polyline.vertices:
            point = vertex
            current = vertex_indices.get(point)
            if current is None:
                current = len(vertices)
                vertex_indices[point] = current
                vertices.append(point)
            if previous is not None and previous != current:
                edges.append((previous, current))
            previous = current

    return Wireframe3(tuple(vertices), tuple(edges))


def slice_planes(
    *,
    radius: float,
    y_values: Iterable[float],
) -> tuple[tuple[float, Mesh3], ...]:
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
) -> Mesh3:
    vertices = [
        (x_min, y, z_max),
        (x_max, y, z_max),
        (x_max, y, z_min),
        (x_min, y, z_min),
    ]
    edges = [(0, 1), (1, 2), (2, 3), (3, 0)]

    for step in range(1, steps):
        x = x_min + (x_max - x_min) * step / steps
        z = z_min + (z_max - z_min) * step / steps
        edges.append(_add_segment(vertices, (x, y, z_min), (x, y, z_max)))
        edges.append(_add_segment(vertices, (x_min, y, z), (x_max, y, z)))

    return Mesh3(tuple(vertices), ((0, 1, 2), (0, 2, 3)), tuple(edges))


def _add_segment(
    vertices: list[Point3],
    start: Point3,
    end: Point3,
) -> tuple[int, int]:
    start_index = len(vertices)
    vertices.append(start)
    vertices.append(end)
    return (start_index, start_index + 1)


def intersection_nodes(
    wireframe: Wireframe3,
    *,
    y_values: Iterable[float],
    tolerance: float = INTERSECTION_TOLERANCE,
) -> list[list[Point3]]:
    """Return intersection nodes grouped by wireframe edge."""
    _validate_tolerance(tolerance)

    y_planes = tuple(y_values)
    node_rows: list[list[Point3]] = []
    for start_index, end_index in wireframe.edges:
        edge_nodes: list[Point3] = []
        for y in y_planes:
            point = _edge_y_intersection(
                wireframe.vertices[start_index],
                wireframe.vertices[end_index],
                y,
                tolerance=tolerance,
            )
            if point is not None:
                _append_unique_point(edge_nodes, point, tolerance=tolerance)
        node_rows.append(edge_nodes)

    return node_rows


def intersection_nodes_to_point_cloud(
    node_groups: Iterable[Iterable[Point3]],
    *,
    tolerance: float = INTERSECTION_TOLERANCE,
) -> PointCloud3:
    """Flatten grouped intersection nodes into a point cloud for display."""
    _validate_tolerance(tolerance)

    return PointCloud3(_unique_nodes(node_groups, tolerance=tolerance))


def intersection_nodes_to_edge_mesh(
    node_groups: Iterable[Iterable[Point3]],
    *,
    tolerance: float = INTERSECTION_TOLERANCE,
) -> Mesh3:
    """Return a mesh connecting grouped nodes as a row-major grid."""
    _validate_tolerance(tolerance)

    node_rows = _grid_node_rows(node_groups, tolerance=tolerance)
    vertices, row_indices = _index_node_rows(node_rows)
    edges = _grid_edges(row_indices)
    faces = _grid_faces(row_indices)

    return Mesh3(tuple(vertices), tuple(faces), tuple(edges))


def _validate_tolerance(tolerance: float) -> None:
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")


def _unique_nodes(
    node_groups: Iterable[Iterable[Point3]],
    *,
    tolerance: float,
) -> tuple[Point3, ...]:
    nodes: list[Point3] = []
    for group in node_groups:
        for node in group:
            _append_unique_point(nodes, node, tolerance=tolerance)
    return tuple(nodes)


def _grid_node_rows(
    node_groups: Iterable[Iterable[Point3]],
    *,
    tolerance: float,
) -> NodeRows:
    rows = [list(group) for group in node_groups]
    if _is_sparse_edge_intersection_output(rows):
        return _compact_sparse_edge_rows(rows, tolerance=tolerance)
    return rows


def _is_sparse_edge_intersection_output(rows: NodeRows) -> bool:
    return any(not row for row in rows) and all(len(row) <= 1 for row in rows)


def _compact_sparse_edge_rows(
    rows: NodeRows,
    *,
    tolerance: float,
) -> NodeRows:
    grid_rows: NodeRows = []
    current: list[Point3] = []
    previous: Point3 | None = None

    for row in rows:
        if not row:
            continue
        node = row[0]
        if previous is not None and _points_close(previous, node, tolerance=tolerance):
            continue
        if previous is not None and node[1] < previous[1] - tolerance:
            grid_rows.append(current)
            current = []
        current.append(node)
        previous = node

    if current:
        grid_rows.append(current)
    return grid_rows


def _index_node_rows(rows: NodeRows) -> tuple[tuple[Point3, ...], list[list[int]]]:
    vertices: list[Point3] = []
    row_indices: list[list[int]] = []
    for row in rows:
        indices: list[int] = []
        for node in row:
            indices.append(len(vertices))
            vertices.append(node)
        row_indices.append(indices)
    return tuple(vertices), row_indices


def _grid_edges(row_indices: list[list[int]]) -> tuple[EdgeIndex, ...]:
    edges: list[EdgeIndex] = []
    for row_index, row in enumerate(row_indices):
        next_row = _next_row(row_indices, row_index)
        for column_index, vertex_index in enumerate(row):
            if column_index + 1 < len(row):
                edges.append((vertex_index, row[column_index + 1]))
            if column_index < len(next_row):
                edges.append((vertex_index, next_row[column_index]))
    return tuple(edges)


def _grid_faces(row_indices: list[list[int]]) -> tuple[FaceIndex, ...]:
    faces: list[FaceIndex] = []
    for row_index, row in enumerate(row_indices):
        next_row = _next_row(row_indices, row_index)
        for column_index, top_left in enumerate(row):
            if column_index + 1 >= len(row) or column_index + 1 >= len(next_row):
                continue
            top_right = row[column_index + 1]
            bottom_left = next_row[column_index]
            bottom_right = next_row[column_index + 1]
            faces.append((top_left, bottom_left, top_right))
            faces.append((top_right, bottom_left, bottom_right))
    return tuple(faces)


def _next_row(row_indices: list[list[int]], row_index: int) -> list[int]:
    if row_index + 1 >= len(row_indices):
        return []
    return row_indices[row_index + 1]


def _edge_y_intersection(
    start: Point3,
    end: Point3,
    y: float,
    *,
    tolerance: float,
) -> Point3 | None:
    start_delta = start[1] - y
    end_delta = end[1] - y
    start_on_plane = abs(start_delta) <= tolerance
    end_on_plane = abs(end_delta) <= tolerance

    if start_on_plane:
        return start
    if end_on_plane:
        return end
    if start_delta * end_delta > 0.0:
        return None

    span = end[1] - start[1]
    if abs(span) <= tolerance:
        return None

    t = (y - start[1]) / span
    if t < -tolerance or t > 1.0 + tolerance:
        return None
    return (
        start[0] + (end[0] - start[0]) * t,
        y,
        start[2] + (end[2] - start[2]) * t,
    )


def _append_unique_point(
    points: list[Point3],
    point: Point3,
    *,
    tolerance: float,
) -> None:
    if any(_points_close(existing, point, tolerance=tolerance) for existing in points):
        return
    points.append(point)


def _points_close(
    left: Point3,
    right: Point3,
    *,
    tolerance: float,
) -> bool:
    return (
        abs(left[0] - right[0]) <= tolerance
        and abs(left[1] - right[1]) <= tolerance
        and abs(left[2] - right[2]) <= tolerance
    )


def build_scene(
    wireframe: Wireframe3,
    planes: Iterable[tuple[float, Mesh3]],
    nodes: Iterable[Iterable[Point3]] | PointCloud3 | None = None,
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
    if nodes is not None and not isinstance(nodes, PointCloud3):
        node_groups = tuple(tuple(group) for group in nodes)
        node_mesh = intersection_nodes_to_edge_mesh(node_groups)
        if node_mesh.vertices and node_mesh.edges:
            scene = scene.add(
                node_mesh,
                name="plane_intersection_mesh",
                style=NODE_MESH_STYLE,
            )
        nodes = intersection_nodes_to_point_cloud(node_groups)
    if isinstance(nodes, PointCloud3) and nodes.vertices:
        scene = scene.add(
            nodes,
            name="plane_intersection_nodes",
            style=NODE_STYLE,
        )
    return scene.with_camera(CAMERA, name="isometric").with_light(LIGHT)


def print_wireframe_summary(wireframe: Wireframe3) -> None:
    lower, upper = wireframe.bounds()
    print(
        f"wireframe: {len(wireframe.vertices)} vertices, {len(wireframe.edges)} edges, "
        f"bounds={format_point(lower)} to {format_point(upper)}"
    )


def format_point(point: Point3) -> str:
    x, y, z = point
    return f"({float(x):.3g}, {float(y):.3g}, {float(z):.3g})"


if __name__ == "__main__":
    main()
