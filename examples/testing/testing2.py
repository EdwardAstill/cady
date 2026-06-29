"""Build a quarter-sphere wireframe from three polylines.

Usage from the repository root:
    PYTHONPATH=src .venv/bin/python examples/testing/testing2.py
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import cos, pi, sin, sqrt
from typing import NamedTuple

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


class Point3(NamedTuple):
    x: float
    y: float
    z: float

    def tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)
EdgeIndex = tuple[int, int]
FaceIndex = tuple[int, int, int]
PointLike3 = tuple[float, float, float] | Point3
NodeArray = list[list[Point3]]

RADIUS = 5.0
SAMPLES = 33
MIN_SLICE_Y = -5.0
MAX_SLICE_Y = 5.0
SLICES = 8
PLANE_GRID_STEPS = 4
INTERSECTION_TOLERANCE = 1e-9
DIAGONAL_SCALE = 1.0 / sqrt(2.0)
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


@dataclass
class WireframeArray:
    node_array: NodeArray

    def __post_init__(self) -> None:
        self.node_array = [
            [_as_vec3(point) for point in row] for row in self.node_array
        ]

    def to_mesh(self) -> Mesh3:
        return node_array_to_mesh(self.node_array)


def main() -> None:
    linesplan = quarter_sphere_linesplan(radius=RADIUS, samples=SAMPLES)
    wireframe = wireframe_from_polylines(linesplan)
    y_values = slice_y_values(min_y=MIN_SLICE_Y, max_y=MAX_SLICE_Y, slices=SLICES)
    planes = slice_planes(radius=RADIUS, y_values=y_values)
    wireframe_array = split_wireframe_with_planes(linesplan, y_values=y_values)
    node_array = wireframe_array.node_array
    node_mesh = wireframe_array.to_mesh()
    repair_node = node_on_original_line_by_one_based_position(
        linesplan,
        node_array,
        position=10.5,
    )
    node_mesh, node_array = add_node_by_one_based_position(
        node_mesh,
        node_array,
        position=10.5,
        point=repair_node,
    )
    node_cloud = node_array_to_point_cloud(node_array)

    print("quarter sphere wireframe")
    for index, polyline in enumerate(linesplan, start=1):
        start = format_point(polyline.vertices[0])
        end = format_point(polyline.vertices[-1])
        print(f"polyline_{index}: {len(polyline.vertices)} vertices, A={start}, B={end}")
    print_wireframe_summary(wireframe)
    print(f"slice planes: {', '.join(f'y={y:g}' for y, _plane in planes)}")
    print(f"node array: {len(node_array)} rows x {len(node_array[0])} columns")
    print(f"intersection nodes: {len(node_cloud.vertices)}")

    view_scene(
        build_scene(wireframe, planes, node_mesh),
        title="Quarter sphere slice planes",
    )


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


def quarter_sphere_linesplan(
    *,
    radius: float,
    samples: int,
) -> list[Polyline3]:
    if radius <= 0.0:
        raise ValueError("radius must be positive")
    if samples < 3:
        raise ValueError("samples must be at least 3")

    sample_offsets = semicircle_sample_offsets(radius=radius, samples=samples)

    x_axis_polyline = Polyline3(
        tuple((side, y, 0.0) for side, y in sample_offsets)
    )
    diagonal_polyline = Polyline3(
        tuple(
            (side * DIAGONAL_SCALE, y, -side * DIAGONAL_SCALE)
            for side, y in sample_offsets
        )
    )
    z_axis_polyline = Polyline3(
        tuple((0.0, y, -side) for side, y in sample_offsets)
    )

    linesplan = [x_axis_polyline, diagonal_polyline, z_axis_polyline]
    validate_matching_y_bounds(linesplan)
    return linesplan


def semicircle_sample_offsets(
    *,
    radius: float,
    samples: int,
) -> tuple[tuple[float, float], ...]:
    offsets: list[tuple[float, float]] = [(0.0, -radius)]
    for index in range(1, samples - 1):
        theta = -pi / 2.0 + pi * index / (samples - 1)
        side = radius * cos(theta)
        offsets.append((side, radius * sin(theta)))
    offsets.append((0.0, radius))
    return tuple(offsets)


def validate_matching_y_bounds(
    polylines: Iterable[Polyline3],
    *,
    tolerance: float = INTERSECTION_TOLERANCE,
) -> None:
    _validate_tolerance(tolerance)

    linesplan = tuple(polylines)
    if not linesplan:
        raise ValueError("linesplan must contain at least one polyline")

    expected_min_y, expected_max_y = polyline_y_bounds(linesplan[0])
    for index, polyline in enumerate(linesplan[1:], start=2):
        min_y, max_y = polyline_y_bounds(polyline)
        if (
            abs(min_y - expected_min_y) > tolerance
            or abs(max_y - expected_max_y) > tolerance
        ):
            raise ValueError(
                "all linesplan polylines must have the same y bounds; "
                f"polyline_1=({expected_min_y:g}, {expected_max_y:g}), "
                f"polyline_{index}=({min_y:g}, {max_y:g})"
            )


def polyline_y_bounds(polyline: Polyline3) -> tuple[float, float]:
    if not polyline.vertices:
        raise ValueError("linesplan polylines must contain at least one vertex")
    y_values = [vertex.y for vertex in polyline.vertices]
    return min(y_values), max(y_values)


def wireframe_from_polylines(polylines: Iterable[Polyline3]) -> Wireframe3:
    vertices: list[Point3] = []
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
                vertices.append(Point3(*point))
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
        Point3(x_min, y, z_max),
        Point3(x_max, y, z_max),
        Point3(x_max, y, z_min),
        Point3(x_min, y, z_min),
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
    vertices.append(Point3(*start))
    vertices.append(Point3(*end))
    return (start_index, start_index + 1)


def split_wireframe_with_planes(
    polylines: Iterable[Polyline3],
    *,
    y_values: Iterable[float],
    tolerance: float = INTERSECTION_TOLERANCE,
) -> WireframeArray:
    """Return polyline-plane intersections grouped by original polyline."""
    _validate_tolerance(tolerance)

    y_planes = tuple(y_values)
    node_array: NodeArray = []
    for polyline_index, polyline in enumerate(polylines, start=1):
        row: list[Point3] = []
        for y in y_planes:
            point = _polyline_y_intersection(
                polyline,
                y,
                tolerance=tolerance,
            )
            if point is None:
                raise ValueError(
                    f"slice plane y={y:g} does not intersect polyline_{polyline_index}"
                )
            row.append(point)
        node_array.append(row)

    return WireframeArray(node_array)


def node_array_to_point_cloud(
    node_array: Iterable[Iterable[Point3]],
    *,
    tolerance: float = INTERSECTION_TOLERANCE,
) -> PointCloud3:
    """Flatten a node array into a point cloud for display."""
    _validate_tolerance(tolerance)

    return PointCloud3(_unique_nodes(node_array, tolerance=tolerance))


def node_array_to_mesh(
    node_array: Iterable[Iterable[Point3]],
    *,
    tolerance: float = INTERSECTION_TOLERANCE,
) -> Mesh3:
    """Return a mesh connecting a node array as a row-major grid."""
    _validate_tolerance(tolerance)

    node_rows = [list(row) for row in node_array]
    _validate_rectangular_node_array(node_rows)
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


def _validate_rectangular_node_array(
    node_array: Iterable[Iterable[Point3]],
    *,
    tolerance: float = INTERSECTION_TOLERANCE,
) -> None:
    _validate_tolerance(tolerance)

    rows = [list(row) for row in node_array]
    if not rows:
        raise ValueError("node array must contain at least one row")
    expected_columns = len(rows[0])
    if expected_columns == 0:
        raise ValueError("node array rows must contain at least one point")
    for row_index, row in enumerate(rows[1:], start=2):
        if len(row) != expected_columns:
            raise ValueError(
                "node array rows must all have the same point count; "
                f"row_1={expected_columns}, row_{row_index}={len(row)}"
            )


def _polyline_y_intersection(
    polyline: Polyline3,
    y: float,
    *,
    tolerance: float,
) -> Point3 | None:
    nodes: list[Point3] = []
    vertices = tuple(polyline.vertices)
    for start, end in zip(vertices, vertices[1:], strict=False):
        point = _edge_y_intersection(start, end, y, tolerance=tolerance)
        if point is not None:
            _append_unique_point(nodes, point, tolerance=tolerance)

    if not nodes:
        return None
    if len(nodes) > 1:
        raise ValueError(f"slice plane y={y:g} intersects a polyline more than once")
    return nodes[0]


def _as_vec3(point: PointLike3) -> Point3:
    if isinstance(point, Point3):
        return point
    return Point3(*point)


def _index_node_rows(rows: NodeArray) -> tuple[tuple[Point3, ...], list[list[int]]]:
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
    start_delta = start.y - y
    end_delta = end.y - y
    start_on_plane = abs(start_delta) <= tolerance
    end_on_plane = abs(end_delta) <= tolerance

    if start_on_plane:
        return start
    if end_on_plane:
        return end
    if start_delta * end_delta > 0.0:
        return None

    span = end.y - start.y
    if abs(span) <= tolerance:
        return None

    t = (y - start.y) / span
    if t < -tolerance or t > 1.0 + tolerance:
        return None
    return Point3(
        start.x + (end.x - start.x) * t,
        y,
        start.z + (end.z - start.z) * t,
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
        abs(left.x - right.x) <= tolerance
        and abs(left.y - right.y) <= tolerance
        and abs(left.z - right.z) <= tolerance
    )


def add_node(
    mesh: Mesh3,
    node_array: NodeArray,
    *,
    row_index: int,
    left_column_index: int,
    point: PointLike3 | None = None,
    t: float = 0.5,
    tolerance: float = INTERSECTION_TOLERANCE,
    require_point_on_current_edge: bool = False,
) -> tuple[Mesh3, NodeArray]:
    """Add one local node by splitting one row edge of a mesh.

    The selected edge is:

        node_array[row_index][left_column_index]
            ->
        node_array[row_index][left_column_index + 1]

    The node_array is returned unchanged because it remains the rectangular
    base grid. The inserted local node belongs to the unstructured mesh.
    """
    _validate_tolerance(tolerance)

    rows = [list(row) for row in node_array]
    _validate_rectangular_node_array(rows, tolerance=tolerance)
    _validate_node_insert_location(rows, row_index, left_column_index)

    start_index = _node_array_vertex_index(rows, row_index, left_column_index)
    end_index = _node_array_vertex_index(rows, row_index, left_column_index + 1)

    if start_index >= len(mesh.vertices) or end_index >= len(mesh.vertices):
        raise ValueError("mesh does not contain the expected row-major node_array vertices")

    start = mesh.vertices[start_index]
    end = mesh.vertices[end_index]

    if point is None:
        if not 0.0 < t < 1.0:
            raise ValueError("t must be strictly between 0 and 1")
        new_node = _interpolate_vec3(start, end, t)
    else:
        new_node = _as_vec3(point)

    if _points_close(new_node, start, tolerance=tolerance):
        return mesh, rows
    if _points_close(new_node, end, tolerance=tolerance):
        return mesh, rows

    if require_point_on_current_edge:
        distance = _point_segment_distance(start, end, new_node)
        if distance > tolerance:
            raise ValueError(
                "new node is not on the selected current mesh edge; "
                f"distance={distance:g}, tolerance={tolerance:g}"
            )

    return (
        _split_mesh_edge(
            mesh,
            start_index,
            end_index,
            new_node,
            tolerance=tolerance,
        ),
        rows,
    )


def add_node_by_one_based_position(
    mesh: Mesh3,
    node_array: NodeArray,
    *,
    position: float,
    point: PointLike3 | None = None,
    tolerance: float = INTERSECTION_TOLERANCE,
    require_point_on_current_edge: bool = False,
) -> tuple[Mesh3, NodeArray]:
    """Add a local node from a shorthand position like 10.5.

    position=10.5 means split one-based row edge 10--11. This only supports
    horizontal row edges and rejects positions that cross a row boundary.
    """
    _validate_tolerance(tolerance)

    rows = [list(row) for row in node_array]
    _validate_rectangular_node_array(rows, tolerance=tolerance)

    row_index, left_column_index, fraction = _one_based_position_to_row_edge(
        rows,
        position,
    )

    return add_node(
        mesh,
        rows,
        row_index=row_index,
        left_column_index=left_column_index,
        point=point,
        t=fraction,
        tolerance=tolerance,
        require_point_on_current_edge=require_point_on_current_edge,
    )


def node_on_original_line_by_one_based_position(
    polylines: Iterable[Polyline3],
    node_array: NodeArray,
    *,
    position: float,
    tolerance: float = INTERSECTION_TOLERANCE,
) -> Point3:
    """Return the source polyline point for a shorthand position like 10.5."""
    _validate_tolerance(tolerance)

    rows = [list(row) for row in node_array]
    _validate_rectangular_node_array(rows, tolerance=tolerance)
    row_index, left_column_index, fraction = _one_based_position_to_row_edge(
        rows,
        position,
    )

    source_lines = tuple(polylines)
    if row_index >= len(source_lines):
        raise ValueError("position selects a node_array row without a source polyline")

    start = rows[row_index][left_column_index]
    end = rows[row_index][left_column_index + 1]
    y = start.y + (end.y - start.y) * fraction
    point = _polyline_y_intersection(source_lines[row_index], y, tolerance=tolerance)
    if point is None:
        raise ValueError("source polyline does not contain the requested y position")

    return point


def _one_based_position_to_row_edge(
    rows: NodeArray,
    position: float,
) -> tuple[int, int, float]:
    columns = len(rows[0])
    if position <= 0.0:
        raise ValueError("position must be positive")

    left_node_number = int(position)
    fraction = position - left_node_number

    if not 0.0 < fraction < 1.0:
        raise ValueError(
            "position must lie strictly between two one-based node numbers, "
            "for example 10.5"
        )

    left_flat_index = left_node_number - 1
    row_index = left_flat_index // columns
    left_column_index = left_flat_index % columns

    if row_index >= len(rows):
        raise ValueError("position is outside the node_array")

    if left_column_index + 1 >= columns:
        raise ValueError(
            "position crosses a row boundary; this function only splits row edges"
        )

    return row_index, left_column_index, fraction


def _validate_node_insert_location(
    node_array: NodeArray,
    row_index: int,
    left_column_index: int,
) -> None:
    if row_index < 0 or row_index >= len(node_array):
        raise ValueError(f"row_index={row_index} is outside the node_array")

    row = node_array[row_index]
    if left_column_index < 0 or left_column_index + 1 >= len(row):
        raise ValueError(
            "left_column_index must select an edge inside the row; "
            f"got left_column_index={left_column_index}, row length={len(row)}"
        )


def _node_array_vertex_index(
    node_array: NodeArray,
    row_index: int,
    column_index: int,
) -> int:
    return sum(len(row) for row in node_array[:row_index]) + column_index


def _interpolate_vec3(
    start: Point3,
    end: Point3,
    t: float,
) -> Point3:
    return Point3(
        start.x + (end.x - start.x) * t,
        start.y + (end.y - start.y) * t,
        start.z + (end.z - start.z) * t,
    )


def _split_mesh_edge(
    mesh: Mesh3,
    start_index: int,
    end_index: int,
    new_node: Point3,
    *,
    tolerance: float,
) -> Mesh3:
    """Split one mesh edge and all faces that use it."""
    _validate_tolerance(tolerance)

    if start_index == end_index:
        raise ValueError("cannot split a zero-length topology edge")

    vertices = list(mesh.vertices)
    new_index = len(vertices)
    vertices.append(new_node)

    faces: list[FaceIndex] = []
    opposite_vertices: list[int] = []
    split_face_count = 0

    for face in mesh.faces:
        if _face_contains_edge(face, start_index, end_index):
            split_faces, opposite = _split_face_on_edge(
                face,
                start_index,
                end_index,
                new_index,
            )
            faces.extend(split_faces)
            opposite_vertices.append(opposite)
            split_face_count += 1
        else:
            faces.append(face)

    edge_was_explicit = _edge_exists(mesh.edges, start_index, end_index)

    if split_face_count == 0 and not edge_was_explicit:
        raise ValueError("selected edge was not found in mesh faces or explicit mesh edges")

    edges = _split_explicit_mesh_edges(
        mesh.edges,
        start_index,
        end_index,
        new_index,
    )

    for opposite in opposite_vertices:
        _append_unique_edge(edges, (new_index, opposite))

    return Mesh3(tuple(vertices), tuple(faces), tuple(edges))


def _face_contains_edge(
    face: FaceIndex,
    start_index: int,
    end_index: int,
) -> bool:
    return start_index != end_index and start_index in face and end_index in face


def _split_face_on_edge(
    face: FaceIndex,
    start_index: int,
    end_index: int,
    new_index: int,
) -> tuple[tuple[FaceIndex, FaceIndex], int]:
    """Split one triangle while preserving its winding direction."""
    opposite = _opposite_face_vertex(face, start_index, end_index)

    if _face_has_directed_edge(face, start_index, end_index):
        return (
            (
                (start_index, new_index, opposite),
                (new_index, end_index, opposite),
            ),
            opposite,
        )

    if _face_has_directed_edge(face, end_index, start_index):
        return (
            (
                (end_index, new_index, opposite),
                (new_index, start_index, opposite),
            ),
            opposite,
        )

    raise ValueError("face does not contain the requested split edge")


def _opposite_face_vertex(
    face: FaceIndex,
    start_index: int,
    end_index: int,
) -> int:
    for vertex_index in face:
        if vertex_index != start_index and vertex_index != end_index:
            return vertex_index
    raise ValueError("degenerate face has no opposite vertex")


def _face_has_directed_edge(
    face: FaceIndex,
    start_index: int,
    end_index: int,
) -> bool:
    a, b, c = face
    return (
        (a == start_index and b == end_index)
        or (b == start_index and c == end_index)
        or (c == start_index and a == end_index)
    )


def _split_explicit_mesh_edges(
    edges: Iterable[EdgeIndex],
    start_index: int,
    end_index: int,
    new_index: int,
) -> list[EdgeIndex]:
    new_edges: list[EdgeIndex] = []
    split_was_explicit = False

    for edge in edges:
        a, b = edge

        if _same_undirected_edge(edge, (start_index, end_index)):
            split_was_explicit = True

            if a == start_index and b == end_index:
                _append_unique_edge(new_edges, (start_index, new_index))
                _append_unique_edge(new_edges, (new_index, end_index))
            else:
                _append_unique_edge(new_edges, (end_index, new_index))
                _append_unique_edge(new_edges, (new_index, start_index))

            continue

        _append_unique_edge(new_edges, edge)

    if not split_was_explicit:
        _append_unique_edge(new_edges, (start_index, new_index))
        _append_unique_edge(new_edges, (new_index, end_index))

    return new_edges


def _edge_exists(
    edges: Iterable[EdgeIndex],
    start_index: int,
    end_index: int,
) -> bool:
    return any(_same_undirected_edge(edge, (start_index, end_index)) for edge in edges)


def _same_undirected_edge(
    left: EdgeIndex,
    right: EdgeIndex,
) -> bool:
    return _edge_key(left) == _edge_key(right)


def _edge_key(edge: EdgeIndex) -> tuple[int, int]:
    start, end = edge
    return (start, end) if start < end else (end, start)


def _append_unique_edge(
    edges: list[EdgeIndex],
    edge: EdgeIndex,
) -> None:
    start, end = edge
    if start == end:
        return

    key = _edge_key(edge)
    if any(_edge_key(existing) == key for existing in edges):
        return

    edges.append(edge)


def _point_segment_distance(
    start: Point3,
    end: Point3,
    point: Point3,
) -> float:
    t = _point_segment_parameter(start, end, point)
    t = max(0.0, min(1.0, t))

    closest = Point3(
        start.x + (end.x - start.x) * t,
        start.y + (end.y - start.y) * t,
        start.z + (end.z - start.z) * t,
    )

    return _distance(closest, point)


def _point_segment_parameter(
    start: Point3,
    end: Point3,
    point: Point3,
) -> float:
    ab_x = end.x - start.x
    ab_y = end.y - start.y
    ab_z = end.z - start.z

    ap_x = point.x - start.x
    ap_y = point.y - start.y
    ap_z = point.z - start.z

    length_squared = ab_x * ab_x + ab_y * ab_y + ab_z * ab_z
    if length_squared == 0.0:
        return 0.0

    return (ap_x * ab_x + ap_y * ab_y + ap_z * ab_z) / length_squared


def _distance(
    left: Point3,
    right: Point3,
) -> float:
    dx = right.x - left.x
    dy = right.y - left.y
    dz = right.z - left.z
    return sqrt(dx * dx + dy * dy + dz * dz)


def build_scene(
    wireframe: Wireframe3,
    planes: Iterable[tuple[float, Mesh3]],
    nodes: Mesh3 | WireframeArray | Iterable[Iterable[Point3]] | PointCloud3 | None = None,
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
    if isinstance(nodes, Mesh3):
        node_mesh = nodes

        if node_mesh.vertices and (node_mesh.edges or node_mesh.faces):
            scene = scene.add(
                node_mesh,
                name="plane_intersection_mesh",
                style=NODE_MESH_STYLE,
            )

        if node_mesh.vertices:
            nodes = PointCloud3(node_mesh.vertices)

    elif nodes is not None and not isinstance(nodes, PointCloud3):
        if isinstance(nodes, WireframeArray):
            node_array = nodes.node_array
            node_mesh = nodes.to_mesh()
        else:
            node_array = [list(group) for group in nodes]
            node_mesh = node_array_to_mesh(node_array)
        if node_mesh.vertices and node_mesh.edges:
            scene = scene.add(
                node_mesh,
                name="plane_intersection_mesh",
                style=NODE_MESH_STYLE,
            )
        nodes = node_array_to_point_cloud(node_array)
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
    x, y, z = point.tuple() if isinstance(point, Point3) else point
    return f"({float(x):.3g}, {float(y):.3g}, {float(z):.3g})"


if __name__ == "__main__":
    main()
