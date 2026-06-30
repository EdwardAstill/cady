"""Build and repair a quarter-sphere lines-plan mesh.

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
PointLike3 = tuple[float, float, float] | Point3
EdgeIndex = tuple[int, int]
FaceIndex = tuple[int, int, int]
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
    """Structured node array produced by slicing each source polyline."""

    node_array: NodeArray

    def __post_init__(self) -> None:
        self.node_array = _as_node_array(self.node_array)

    def to_mesh(self) -> Mesh3:
        return node_array_to_mesh(self.node_array)


@dataclass(frozen=True)
class RowEdge:
    """A horizontal edge selected from a rectangular node array."""

    row: int
    left_column: int
    fraction: float = 0.5

    @property
    def right_column(self) -> int:
        return self.left_column + 1


@dataclass(frozen=True)
class MeshEdge:
    """An undirected edge in a Mesh3."""

    start: int
    end: int

    def contains(self, index: int) -> bool:
        return index == self.start or index == self.end

    def matches(self, a: int, b: int) -> bool:
        return _same_edge((self.start, self.end), (a, b))


# -----------------------------------------------------------------------------
# Example
# -----------------------------------------------------------------------------


def main() -> None:
    linesplan = quarter_sphere_linesplan(radius=RADIUS, samples=SAMPLES)
    y_values = slice_y_values(min_y=MIN_SLICE_Y, max_y=MAX_SLICE_Y, slices=SLICES)

    wireframe = wireframe_from_polylines(linesplan)
    planes = slice_planes(radius=RADIUS, y_values=y_values)
    wireframe_array = split_wireframe_with_planes(linesplan, y_values=y_values)

    node_array = wireframe_array.node_array
    node_mesh = wireframe_array.to_mesh()

    repair_point = node_on_original_line_by_one_based_position(
        linesplan,
        node_array,
        position=10.5,
    )
    node_mesh, node_array = add_node_by_one_based_position(
        node_mesh,
        node_array,
        position=10.5,
        point=repair_point,
    )

    print_scene_summary(linesplan, wireframe, planes, node_array)

    view_scene(
        build_scene(wireframe, planes, node_mesh),
        title="Quarter sphere slice planes",
    )


# -----------------------------------------------------------------------------
# Lines-plan construction
# -----------------------------------------------------------------------------


def quarter_sphere_linesplan(*, radius: float, samples: int) -> list[Polyline3]:
    if radius <= 0.0:
        raise ValueError("radius must be positive")
    if samples < 3:
        raise ValueError("samples must be at least 3")

    sample_offsets = semicircle_sample_offsets(radius=radius, samples=samples)
    linesplan = [
        Polyline3(tuple((side, y, 0.0) for side, y in sample_offsets)),
        Polyline3(
            tuple(
                (side * DIAGONAL_SCALE, y, -side * DIAGONAL_SCALE)
                for side, y in sample_offsets
            )
        ),
        Polyline3(tuple((0.0, y, -side) for side, y in sample_offsets)),
    ]
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
        offsets.append((radius * cos(theta), radius * sin(theta)))

    offsets.append((0.0, radius))
    return tuple(offsets)


def validate_matching_y_bounds(
    polylines: Iterable[Polyline3],
    *,
    tolerance: float = INTERSECTION_TOLERANCE,
) -> None:
    _require_positive_tolerance(tolerance)

    linesplan = tuple(polylines)
    if not linesplan:
        raise ValueError("linesplan must contain at least one polyline")

    expected = polyline_y_bounds(linesplan[0])
    for index, polyline in enumerate(linesplan[1:], start=2):
        actual = polyline_y_bounds(polyline)
        if not _bounds_close(expected, actual, tolerance=tolerance):
            raise ValueError(
                "all linesplan polylines must have the same y bounds; "
                f"polyline_1=({expected[0]:g}, {expected[1]:g}), "
                f"polyline_{index}=({actual[0]:g}, {actual[1]:g})"
            )


def polyline_y_bounds(polyline: Polyline3) -> tuple[float, float]:
    if not polyline.vertices:
        raise ValueError("linesplan polylines must contain at least one vertex")

    y_values = [vertex.y for vertex in polyline.vertices]
    return min(y_values), max(y_values)


def _bounds_close(
    left: tuple[float, float],
    right: tuple[float, float],
    *,
    tolerance: float,
) -> bool:
    return (
        abs(left[0] - right[0]) <= tolerance
        and abs(left[1] - right[1]) <= tolerance
    )


# -----------------------------------------------------------------------------
# Wireframe and slicing
# -----------------------------------------------------------------------------


def slice_y_values(*, min_y: float, max_y: float, slices: int) -> tuple[float, ...]:
    if slices <= 2:
        raise ValueError("slices must be greater than 2")
    if min_y >= max_y:
        raise ValueError("min_y must be less than max_y")

    step = (max_y - min_y) / (slices - 1)
    return tuple(min_y + step * index for index in range(slices))


def wireframe_from_polylines(polylines: Iterable[Polyline3]) -> Wireframe3:
    vertices: list[Point3] = []
    vertex_indices: dict[Point3, int] = {}
    edges: list[EdgeIndex] = []

    for polyline in polylines:
        previous_index: int | None = None
        for vertex in polyline.vertices:
            current_index = _index_vertex(vertices, vertex_indices, vertex)
            if previous_index is not None and previous_index != current_index:
                edges.append((previous_index, current_index))
            previous_index = current_index

    return Wireframe3(tuple(vertices), tuple(edges))


def split_wireframe_with_planes(
    polylines: Iterable[Polyline3],
    *,
    y_values: Iterable[float],
    tolerance: float = INTERSECTION_TOLERANCE,
) -> WireframeArray:
    """Return one row of slice intersections for each source polyline."""
    _require_positive_tolerance(tolerance)

    rows: NodeArray = []
    for polyline_index, polyline in enumerate(polylines, start=1):
        rows.append(
            _slice_polyline_at_y_values(
                polyline,
                tuple(y_values),
                polyline_index=polyline_index,
                tolerance=tolerance,
            )
        )

    return WireframeArray(rows)


def _index_vertex(
    vertices: list[Point3],
    vertex_indices: dict[Point3, int],
    vertex: Point3,
) -> int:
    point = vertex.tuple()
    existing_index = vertex_indices.get(point)
    if existing_index is not None:
        return existing_index

    new_index = len(vertices)
    vertex_indices[point] = new_index
    vertices.append(Point3(*point))
    return new_index


def _slice_polyline_at_y_values(
    polyline: Polyline3,
    y_values: tuple[float, ...],
    *,
    polyline_index: int,
    tolerance: float,
) -> list[Point3]:
    row: list[Point3] = []

    for y in y_values:
        point = _polyline_y_intersection(polyline, y, tolerance=tolerance)
        if point is None:
            raise ValueError(
                f"slice plane y={y:g} does not intersect polyline_{polyline_index}"
            )
        row.append(point)

    return row


def _polyline_y_intersection(
    polyline: Polyline3,
    y: float,
    *,
    tolerance: float,
) -> Point3 | None:
    intersections: list[Point3] = []
    vertices = tuple(polyline.vertices)

    for start, end in zip(vertices, vertices[1:], strict=False):
        point = _edge_y_intersection(start, end, y, tolerance=tolerance)
        if point is not None:
            _append_unique_point(intersections, point, tolerance=tolerance)

    if not intersections:
        return None
    if len(intersections) > 1:
        raise ValueError(f"slice plane y={y:g} intersects a polyline more than once")
    return intersections[0]


def _edge_y_intersection(
    start: Point3,
    end: Point3,
    y: float,
    *,
    tolerance: float,
) -> Point3 | None:
    start_delta = start.y - y
    end_delta = end.y - y

    if abs(start_delta) <= tolerance:
        return start
    if abs(end_delta) <= tolerance:
        return end
    if start_delta * end_delta > 0.0:
        return None

    span = end.y - start.y
    if abs(span) <= tolerance:
        return None

    t = (y - start.y) / span
    if not -tolerance <= t <= 1.0 + tolerance:
        return None

    return Point3(
        start.x + (end.x - start.x) * t,
        y,
        start.z + (end.z - start.z) * t,
    )


# -----------------------------------------------------------------------------
# Mesh creation from a rectangular node array
# -----------------------------------------------------------------------------


def node_array_to_point_cloud(
    node_array: Iterable[Iterable[Point3]],
    *,
    tolerance: float = INTERSECTION_TOLERANCE,
) -> PointCloud3:
    """Flatten a node array into a unique point cloud for display."""
    _require_positive_tolerance(tolerance)
    return PointCloud3(_unique_points(node_array, tolerance=tolerance))


def node_array_to_mesh(
    node_array: Iterable[Iterable[Point3]],
    *,
    tolerance: float = INTERSECTION_TOLERANCE,
) -> Mesh3:
    """Connect a rectangular node array as a row-major triangular mesh."""
    _require_positive_tolerance(tolerance)

    rows = _as_node_array(node_array)
    _require_rectangular_node_array(rows, tolerance=tolerance)

    vertices, row_indices = _row_major_vertices(rows)
    return Mesh3(
        tuple(vertices),
        _grid_faces(row_indices),
        _grid_edges(row_indices),
    )


def _row_major_vertices(rows: NodeArray) -> tuple[list[Point3], list[list[int]]]:
    vertices: list[Point3] = []
    row_indices: list[list[int]] = []

    for row in rows:
        indices: list[int] = []
        for point in row:
            indices.append(len(vertices))
            vertices.append(point)
        row_indices.append(indices)

    return vertices, row_indices


def _grid_edges(row_indices: list[list[int]]) -> tuple[EdgeIndex, ...]:
    edges: list[EdgeIndex] = []

    for row, next_row in _neighboring_rows(row_indices):
        for column, vertex in enumerate(row):
            if column + 1 < len(row):
                edges.append((vertex, row[column + 1]))
            if column < len(next_row):
                edges.append((vertex, next_row[column]))

    return tuple(edges)


def _grid_faces(row_indices: list[list[int]]) -> tuple[FaceIndex, ...]:
    faces: list[FaceIndex] = []

    for row, next_row in _neighboring_rows(row_indices):
        for column in range(min(len(row), len(next_row)) - 1):
            top_left = row[column]
            top_right = row[column + 1]
            bottom_left = next_row[column]
            bottom_right = next_row[column + 1]

            faces.append((top_left, bottom_left, top_right))
            faces.append((top_right, bottom_left, bottom_right))

    return tuple(faces)


def _neighboring_rows(rows: list[list[int]]) -> Iterable[tuple[list[int], list[int]]]:
    for row_index, row in enumerate(rows):
        next_row = rows[row_index + 1] if row_index + 1 < len(rows) else []
        yield row, next_row


# -----------------------------------------------------------------------------
# Local mesh repair: insert one node on one existing row edge
# -----------------------------------------------------------------------------


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
    """Insert one local node by splitting one row edge.

    The selected edge is:
        node_array[row_index][left_column_index]
            ->
        node_array[row_index][left_column_index + 1]

    The returned node_array is unchanged. It remains the structured base grid;
    the inserted local node belongs to the unstructured Mesh3.
    """
    _require_positive_tolerance(tolerance)

    rows = _as_node_array(node_array)
    row_edge = RowEdge(row_index, left_column_index, t)
    _require_valid_row_edge(rows, row_edge, tolerance=tolerance)

    mesh_edge = _mesh_edge_from_row_edge(rows, row_edge)
    new_point = _new_point_for_split(
        mesh,
        mesh_edge,
        point=point,
        fraction=row_edge.fraction,
        tolerance=tolerance,
        require_point_on_current_edge=require_point_on_current_edge,
    )

    if new_point is None:
        return mesh, rows

    return _split_mesh_edge(mesh, mesh_edge, new_point), rows


def add_node_by_one_based_position(
    mesh: Mesh3,
    node_array: NodeArray,
    *,
    position: float,
    point: PointLike3 | None = None,
    tolerance: float = INTERSECTION_TOLERANCE,
    require_point_on_current_edge: bool = False,
) -> tuple[Mesh3, NodeArray]:
    """Insert a local node from shorthand notation such as position=10.5.

    In a row-major grid, position=10.5 means split the one-based row edge
    10--11 halfway. The shorthand only supports horizontal row edges.
    """
    _require_positive_tolerance(tolerance)

    rows = _as_node_array(node_array)
    row_edge = _row_edge_from_one_based_position(rows, position, tolerance=tolerance)

    return add_node(
        mesh,
        rows,
        row_index=row_edge.row,
        left_column_index=row_edge.left_column,
        point=point,
        t=row_edge.fraction,
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
    """Return the source-polyline point for shorthand notation such as 10.5."""
    _require_positive_tolerance(tolerance)

    rows = _as_node_array(node_array)
    row_edge = _row_edge_from_one_based_position(rows, position, tolerance=tolerance)

    source_lines = tuple(polylines)
    if row_edge.row >= len(source_lines):
        raise ValueError("position selects a node_array row without a source polyline")

    y = _row_edge_y_value(rows, row_edge)
    point = _polyline_y_intersection(source_lines[row_edge.row], y, tolerance=tolerance)
    if point is None:
        raise ValueError("source polyline does not contain the requested y position")

    return point


def _row_edge_from_one_based_position(
    rows: NodeArray,
    position: float,
    *,
    tolerance: float,
) -> RowEdge:
    _require_rectangular_node_array(rows, tolerance=tolerance)

    if position <= 0.0:
        raise ValueError("position must be positive")

    left_node_number = int(position)
    fraction = position - left_node_number
    if not 0.0 < fraction < 1.0:
        raise ValueError(
            "position must lie strictly between two one-based node numbers, "
            "for example 10.5"
        )

    columns = len(rows[0])
    left_flat_index = left_node_number - 1
    row_index, left_column_index = divmod(left_flat_index, columns)

    row_edge = RowEdge(row_index, left_column_index, fraction)
    _require_valid_row_edge(rows, row_edge, tolerance=tolerance)
    return row_edge


def _require_valid_row_edge(
    rows: NodeArray,
    row_edge: RowEdge,
    *,
    tolerance: float,
) -> None:
    _require_rectangular_node_array(rows, tolerance=tolerance)

    if row_edge.row < 0 or row_edge.row >= len(rows):
        raise ValueError(f"row_index={row_edge.row} is outside the node_array")

    row = rows[row_edge.row]
    if row_edge.left_column < 0 or row_edge.right_column >= len(row):
        raise ValueError(
            "left_column_index must select an edge inside one row; "
            f"got left_column_index={row_edge.left_column}, row length={len(row)}"
        )

    if not 0.0 < row_edge.fraction < 1.0:
        raise ValueError("t must be strictly between 0 and 1")


def _mesh_edge_from_row_edge(rows: NodeArray, row_edge: RowEdge) -> MeshEdge:
    start = _row_major_index(rows, row_edge.row, row_edge.left_column)
    end = _row_major_index(rows, row_edge.row, row_edge.right_column)
    return MeshEdge(start, end)


def _row_major_index(rows: NodeArray, row_index: int, column_index: int) -> int:
    return sum(len(row) for row in rows[:row_index]) + column_index


def _row_edge_y_value(rows: NodeArray, row_edge: RowEdge) -> float:
    start = rows[row_edge.row][row_edge.left_column]
    end = rows[row_edge.row][row_edge.right_column]
    return _lerp(start.y, end.y, row_edge.fraction)


def _new_point_for_split(
    mesh: Mesh3,
    edge: MeshEdge,
    *,
    point: PointLike3 | None,
    fraction: float,
    tolerance: float,
    require_point_on_current_edge: bool,
) -> Point3 | None:
    start = _mesh_vertex(mesh, edge.start)
    end = _mesh_vertex(mesh, edge.end)
    new_point = (
        _as_vec3(point)
        if point is not None
        else _interpolate_vec3(start, end, fraction)
    )

    if _points_close(new_point, start, tolerance=tolerance):
        return None
    if _points_close(new_point, end, tolerance=tolerance):
        return None

    if require_point_on_current_edge:
        distance = _point_segment_distance(start, end, new_point)
        if distance > tolerance:
            raise ValueError(
                "new node is not on the selected current mesh edge; "
                f"distance={distance:g}, tolerance={tolerance:g}"
            )

    return new_point


def _mesh_vertex(mesh: Mesh3, index: int) -> Point3:
    if index < 0 or index >= len(mesh.vertices):
        raise ValueError(
            "mesh does not contain the expected row-major node_array vertices"
        )
    return mesh.vertices[index]


def _split_mesh_edge(mesh: Mesh3, edge: MeshEdge, new_point: Point3) -> Mesh3:
    """Split one mesh edge and every triangular face that uses it."""
    if edge.start == edge.end:
        raise ValueError("cannot split a zero-length topology edge")

    new_index = len(mesh.vertices)
    vertices = tuple(mesh.vertices) + (new_point,)

    faces, opposite_vertices, split_face_count = _faces_after_edge_split(
        mesh.faces,
        edge,
        new_index,
    )
    edge_was_explicit = any(edge.matches(*stored_edge) for stored_edge in mesh.edges)

    if split_face_count == 0 and not edge_was_explicit:
        raise ValueError(
            "selected edge was not found in mesh faces or explicit mesh edges"
        )

    edges = _edges_after_edge_split(mesh.edges, edge, new_index)
    for opposite in opposite_vertices:
        _append_unique_edge(edges, (new_index, opposite))

    return Mesh3(vertices, tuple(faces), tuple(edges))


def _faces_after_edge_split(
    faces: Iterable[FaceIndex],
    edge: MeshEdge,
    new_index: int,
) -> tuple[list[FaceIndex], list[int], int]:
    new_faces: list[FaceIndex] = []
    opposite_vertices: list[int] = []
    split_face_count = 0

    for face in faces:
        if not _face_contains_edge(face, edge):
            new_faces.append(face)
            continue

        split_faces, opposite = _split_face(face, edge, new_index)
        new_faces.extend(split_faces)
        opposite_vertices.append(opposite)
        split_face_count += 1

    return new_faces, opposite_vertices, split_face_count


def _face_contains_edge(face: FaceIndex, edge: MeshEdge) -> bool:
    return edge.start in face and edge.end in face and edge.start != edge.end


def _split_face(
    face: FaceIndex,
    edge: MeshEdge,
    new_index: int,
) -> tuple[tuple[FaceIndex, FaceIndex], int]:
    """Split a triangle along an edge while preserving the face winding."""
    for start, end, opposite in _directed_face_edges(face):
        if edge.matches(start, end):
            return (
                (start, new_index, opposite),
                (new_index, end, opposite),
            ), opposite

    raise ValueError("face does not contain the requested split edge")


def _directed_face_edges(face: FaceIndex) -> tuple[tuple[int, int, int], ...]:
    a, b, c = face
    return (
        (a, b, c),
        (b, c, a),
        (c, a, b),
    )


def _edges_after_edge_split(
    edges: Iterable[EdgeIndex],
    split_edge: MeshEdge,
    new_index: int,
) -> list[EdgeIndex]:
    new_edges: list[EdgeIndex] = []
    seen: set[EdgeIndex] = set()
    split_was_explicit = False

    for edge in edges:
        if split_edge.matches(*edge):
            split_was_explicit = True
            _append_split_edge(new_edges, seen, edge, new_index)
        else:
            _append_unique_edge(new_edges, edge, seen=seen)

    if not split_was_explicit:
        _append_unique_edge(new_edges, (split_edge.start, new_index), seen=seen)
        _append_unique_edge(new_edges, (new_index, split_edge.end), seen=seen)

    return new_edges


def _append_split_edge(
    edges: list[EdgeIndex],
    seen: set[EdgeIndex],
    original_edge: EdgeIndex,
    new_index: int,
) -> None:
    start, end = original_edge
    _append_unique_edge(edges, (start, new_index), seen=seen)
    _append_unique_edge(edges, (new_index, end), seen=seen)


# -----------------------------------------------------------------------------
# Display geometry
# -----------------------------------------------------------------------------


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
        x = _lerp(x_min, x_max, step / steps)
        z = _lerp(z_min, z_max, step / steps)
        edges.append(_add_display_segment(vertices, (x, y, z_min), (x, y, z_max)))
        edges.append(_add_display_segment(vertices, (x_min, y, z), (x_max, y, z)))

    return Mesh3(tuple(vertices), ((0, 1, 2), (0, 2, 3)), tuple(edges))


def _add_display_segment(
    vertices: list[Point3],
    start: Point3,
    end: Point3,
) -> EdgeIndex:
    start_index = len(vertices)
    vertices.append(Point3(*start))
    vertices.append(Point3(*end))
    return start_index, start_index + 1


def build_scene(
    wireframe: Wireframe3,
    planes: Iterable[tuple[float, Mesh3]],
    nodes: Mesh3 | WireframeArray | Iterable[Iterable[Point3]] | PointCloud3 | None = None,
) -> Scene:
    scene = Scene(
        name="quarter_sphere_slice_planes",
        camera=CAMERA,
        lights=(LIGHT,),
    ).add(
        wireframe,
        name="quarter_sphere_wireframe",
        style=WIRE_STYLE,
    )

    scene = _add_planes_to_scene(scene, planes)
    scene = _add_nodes_to_scene(scene, nodes)

    return scene


def _add_planes_to_scene(
    scene: Scene,
    planes: Iterable[tuple[float, Mesh3]],
) -> Scene:
    for index, (y, plane) in enumerate(planes):
        scene = scene.add(
            plane,
            name=f"slice_plane_y_{y:g}",
            style=PLANE_STYLES[index % len(PLANE_STYLES)],
        )
    return scene


def _add_nodes_to_scene(
    scene: Scene,
    nodes: Mesh3 | WireframeArray | Iterable[Iterable[Point3]] | PointCloud3 | None,
) -> Scene:
    if nodes is None:
        return scene

    node_mesh, node_cloud = _nodes_to_scene_geometry(nodes)

    if (
        node_mesh is not None
        and node_mesh.vertices
        and (node_mesh.edges or node_mesh.faces)
    ):
        scene = scene.add(
            node_mesh,
            name="plane_intersection_mesh",
            style=NODE_MESH_STYLE,
        )

    if node_cloud.vertices:
        scene = scene.add(
            node_cloud,
            name="plane_intersection_nodes",
            style=NODE_STYLE,
        )

    return scene


def _nodes_to_scene_geometry(
    nodes: Mesh3 | WireframeArray | Iterable[Iterable[Point3]] | PointCloud3,
) -> tuple[Mesh3 | None, PointCloud3]:
    if isinstance(nodes, Mesh3):
        return nodes, PointCloud3(nodes.vertices)

    if isinstance(nodes, PointCloud3):
        return None, nodes

    node_array = nodes.node_array if isinstance(nodes, WireframeArray) else _as_node_array(nodes)

    return node_array_to_mesh(node_array), node_array_to_point_cloud(node_array)


# -----------------------------------------------------------------------------
# Small geometry helpers
# -----------------------------------------------------------------------------


def _as_node_array(node_array: Iterable[Iterable[PointLike3]]) -> NodeArray:
    return [[_as_vec3(point) for point in row] for row in node_array]


def _as_vec3(point: PointLike3) -> Point3:
    if isinstance(point, Point3):
        return point
    return Point3(*point)


def _interpolate_vec3(start: Point3, end: Point3, t: float) -> Point3:
    return Point3(
        _lerp(start.x, end.x, t),
        _lerp(start.y, end.y, t),
        _lerp(start.z, end.z, t),
    )


def _lerp(start: float, end: float, t: float) -> float:
    return start + (end - start) * t


def _point_segment_distance(start: Point3, end: Point3, point: Point3) -> float:
    t = _point_segment_parameter(start, end, point)
    closest = _interpolate_vec3(start, end, max(0.0, min(1.0, t)))
    return _distance(closest, point)


def _point_segment_parameter(start: Point3, end: Point3, point: Point3) -> float:
    ab = _subtract(end, start)
    ap = _subtract(point, start)
    length_squared = _dot(ab, ab)
    if length_squared == 0.0:
        return 0.0
    return _dot(ap, ab) / length_squared


def _distance(left: Point3, right: Point3) -> float:
    delta = _subtract(right, left)
    return sqrt(_dot(delta, delta))


def _subtract(left: Point3, right: Point3) -> Point3:
    return Point3(left.x - right.x, left.y - right.y, left.z - right.z)


def _dot(left: Point3, right: Point3) -> float:
    return left.x * right.x + left.y * right.y + left.z * right.z


def _points_close(left: Point3, right: Point3, *, tolerance: float) -> bool:
    return (
        abs(left.x - right.x) <= tolerance
        and abs(left.y - right.y) <= tolerance
        and abs(left.z - right.z) <= tolerance
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


def _unique_points(
    point_groups: Iterable[Iterable[Point3]],
    *,
    tolerance: float,
) -> tuple[Point3, ...]:
    points: list[Point3] = []
    for group in point_groups:
        for point in group:
            _append_unique_point(points, point, tolerance=tolerance)
    return tuple(points)


# -----------------------------------------------------------------------------
# Small topology helpers
# -----------------------------------------------------------------------------


def _append_unique_edge(
    edges: list[EdgeIndex],
    edge: EdgeIndex,
    *,
    seen: set[EdgeIndex] | None = None,
) -> None:
    start, end = edge
    if start == end:
        return

    key = _edge_key(edge)
    if seen is None:
        if any(_edge_key(existing) == key for existing in edges):
            return
    elif key in seen:
        return

    edges.append(edge)
    if seen is not None:
        seen.add(key)


def _same_edge(left: EdgeIndex, right: EdgeIndex) -> bool:
    return _edge_key(left) == _edge_key(right)


def _edge_key(edge: EdgeIndex) -> EdgeIndex:
    start, end = edge
    return (start, end) if start < end else (end, start)


# -----------------------------------------------------------------------------
# Validation and reporting
# -----------------------------------------------------------------------------


def _require_positive_tolerance(tolerance: float) -> None:
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")


def _require_rectangular_node_array(
    node_array: Iterable[Iterable[Point3]],
    *,
    tolerance: float = INTERSECTION_TOLERANCE,
) -> None:
    _require_positive_tolerance(tolerance)

    rows = [list(row) for row in node_array]
    if not rows:
        raise ValueError("node array must contain at least one row")

    expected_columns = len(rows[0])
    if expected_columns == 0:
        raise ValueError("node array rows must contain at least one point")

    for row_number, row in enumerate(rows[1:], start=2):
        if len(row) != expected_columns:
            raise ValueError(
                "node array rows must all have the same point count; "
                f"row_1={expected_columns}, row_{row_number}={len(row)}"
            )


def print_scene_summary(
    linesplan: Iterable[Polyline3],
    wireframe: Wireframe3,
    planes: Iterable[tuple[float, Mesh3]],
    node_array: NodeArray,
) -> None:
    print("quarter sphere wireframe")
    for index, polyline in enumerate(linesplan, start=1):
        start = format_point(polyline.vertices[0])
        end = format_point(polyline.vertices[-1])
        print(f"polyline_{index}: {len(polyline.vertices)} vertices, A={start}, B={end}")

    print_wireframe_summary(wireframe)
    print(f"slice planes: {', '.join(f'y={y:g}' for y, _plane in planes)}")
    print(f"node array: {len(node_array)} rows x {len(node_array[0])} columns")
    print(f"intersection nodes: {len(node_array_to_point_cloud(node_array).vertices)}")


def print_wireframe_summary(wireframe: Wireframe3) -> None:
    lower, upper = wireframe.bounds()
    print(
        f"wireframe: {len(wireframe.vertices)} vertices, {len(wireframe.edges)} edges, "
        f"bounds={format_point(lower)} to {format_point(upper)}"
    )


def format_point(point: PointLike3) -> str:
    x, y, z = point.tuple() if isinstance(point, Point3) else point
    return f"({float(x):.3g}, {float(y):.3g}, {float(z):.3g})"


if __name__ == "__main__":
    main()
