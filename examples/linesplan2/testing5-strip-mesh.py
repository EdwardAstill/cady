"""Build a strip-triangulated quarter-sphere lines-plan mesh.

This version keeps the slice-plane nodes exactly as before, but it does not
force every longitudinal polyline to have the same refined node count.

Instead:
    1. Slice every longitudinal polyline with the y-planes.
    2. Refine each plane-to-plane section by arc length along its source line.
    3. Build each strip between neighbouring longitudinal lines from the two
       refined boundary chains.
    4. Weld all strips into one Mesh3D so shared longitudinal rows are not seams.

Usage from the repository root:
    PYTHONPATH=src .venv/bin/python examples/testing/testing5-strip-mesh.py
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import ceil, sqrt

from wireframe import LINESPLAN, RADIUS, WIREFRAME_OBJECTS

from cady import (
    Camera,
    DirectionalLight,
    DisplayStyle,
    Mesh3D,
    PointCloud3D,
    Polyline3D,
    Scene,
    Vec3,
    Wireframe3D,
)
from cady.view import view_scene

Point3 = tuple[float, float, float]
PointLike3 = Point3 | Vec3
EdgeIndex = tuple[int, int]
FaceIndex = tuple[int, int, int]
NodeArray = list[list[Vec3]]

MIN_SLICE_Y = -5.0
MAX_SLICE_Y = 5.0
SLICES = 8
PLANE_GRID_STEPS = 4
INTERSECTION_TOLERANCE = 1e-9

# Set this to None to use only the slice-plane nodes.
# Set it to a positive value to add extra nodes along each longitudinal
# polyline wherever the source-curve distance between neighbouring slice nodes
# would exceed this value.
MAX_SEGMENT_LENGTH: float | None = None

# None means refine every longitudinal row. Use, for example, (1,) to refine
# only the second longitudinal row. These are zero-based row indices.
REFINEMENT_ROWS: tuple[int, ...] | None = None

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


@dataclass(frozen=True)
class StripInterval:
    """One station-to-station chain on a refined longitudinal row."""

    node_indices: tuple[int, ...]
    parameters: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.node_indices) != len(self.parameters):
            raise ValueError("node_indices and parameters must have matching lengths")
        if len(self.node_indices) < 2:
            raise ValueError("a strip interval must contain at least two nodes")


@dataclass
class RefinedPolylineRow:
    """One longitudinal row with optional distance-limited inserted nodes."""

    points: list[Vec3]
    intervals: list[StripInterval]


@dataclass
class StripMeshData:
    """The refined rows and final welded mesh used for display."""

    base_node_array: NodeArray
    refined_rows: list[RefinedPolylineRow]
    mesh: Mesh3D

    @property
    def refined_node_count(self) -> int:
        return sum(len(row.points) for row in self.refined_rows)


# -----------------------------------------------------------------------------
# Example
# -----------------------------------------------------------------------------


def main() -> None:
    linesplan = LINESPLAN
    y_values = slice_y_values(min_y=MIN_SLICE_Y, max_y=MAX_SLICE_Y, slices=SLICES)

    wireframes = WIREFRAME_OBJECTS
    planes = slice_planes(radius=RADIUS, y_values=y_values)
    strip_mesh = build_distance_refined_strip_mesh(
        linesplan,
        y_values=y_values,
        max_segment_length=MAX_SEGMENT_LENGTH,
        refinement_rows=REFINEMENT_ROWS,
    )

    print_scene_summary(linesplan, wireframes, planes, strip_mesh)

    view_scene(
        build_scene(wireframes, planes, strip_mesh.mesh),
        title="Quarter sphere strip mesh",
    )


# -----------------------------------------------------------------------------
# Slicing and wireframe display
# -----------------------------------------------------------------------------


def slice_y_values(*, min_y: float, max_y: float, slices: int) -> tuple[float, ...]:
    if slices <= 2:
        raise ValueError("slices must be greater than 2")
    if min_y >= max_y:
        raise ValueError("min_y must be less than max_y")

    step = (max_y - min_y) / (slices - 1)
    return tuple(min_y + step * index for index in range(slices))


def slice_linesplan(
    polylines: Iterable[Polyline3D],
    *,
    y_values: Iterable[float],
    tolerance: float = INTERSECTION_TOLERANCE,
) -> NodeArray:
    """Return one row of y-plane intersections for each source polyline."""
    require_positive_tolerance(tolerance)

    rows: NodeArray = []
    y_planes = tuple(y_values)
    for polyline_index, polyline in enumerate(polylines, start=1):
        rows.append(
            slice_polyline_at_y_values(
                polyline,
                y_planes,
                polyline_index=polyline_index,
                tolerance=tolerance,
            )
        )

    return rows


def slice_polyline_at_y_values(
    polyline: Polyline3D,
    y_values: tuple[float, ...],
    *,
    polyline_index: int,
    tolerance: float,
) -> list[Vec3]:
    row: list[Vec3] = []

    for y in y_values:
        point = polyline_y_intersection(polyline, y, tolerance=tolerance)
        if point is None:
            raise ValueError(
                f"slice plane y={y:g} does not intersect polyline_{polyline_index}"
            )
        row.append(point)

    return row


def polyline_y_intersection(
    polyline: Polyline3D,
    y: float,
    *,
    tolerance: float,
) -> Vec3 | None:
    intersections: list[Vec3] = []
    vertices = polyline_vertices(polyline)

    for start, end in zip(vertices, vertices[1:], strict=False):
        point = segment_y_intersection(start, end, y, tolerance=tolerance)
        if point is not None:
            append_unique_point(intersections, point, tolerance=tolerance)

    if not intersections:
        return None
    if len(intersections) > 1:
        raise ValueError(f"slice plane y={y:g} intersects a polyline more than once")
    return intersections[0]


def segment_y_intersection(
    start: Vec3,
    end: Vec3,
    y: float,
    *,
    tolerance: float,
) -> Vec3 | None:
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

    return Vec3(
        lerp(start.x, end.x, t),
        y,
        lerp(start.z, end.z, t),
    )


# -----------------------------------------------------------------------------
# Distance-refined strip mesh
# -----------------------------------------------------------------------------


def build_distance_refined_strip_mesh(
    polylines: Iterable[Polyline3D],
    *,
    y_values: Iterable[float],
    max_segment_length: float | None,
    refinement_rows: Iterable[int] | None = None,
    tolerance: float = INTERSECTION_TOLERANCE,
) -> StripMeshData:
    """Build one welded mesh from separately triangulated longitudinal strips."""
    require_positive_tolerance(tolerance)
    if max_segment_length is not None:
        require_positive_length(max_segment_length, name="max_segment_length")

    linesplan = tuple(polylines)
    y_planes = tuple(y_values)
    base_nodes = slice_linesplan(linesplan, y_values=y_planes, tolerance=tolerance)
    selected_rows = selected_refinement_rows(
        row_count=len(base_nodes),
        refinement_rows=refinement_rows,
    )

    refined_rows = [
        refine_polyline_row(
            polyline,
            base_row,
            max_segment_length=(max_segment_length if row_index in selected_rows else None),
            tolerance=tolerance,
        )
        for row_index, (polyline, base_row) in enumerate(zip(linesplan, base_nodes, strict=True))
    ]
    mesh = refined_rows_to_strip_mesh(refined_rows, tolerance=tolerance)

    return StripMeshData(base_nodes, refined_rows, mesh)


def selected_refinement_rows(
    *,
    row_count: int,
    refinement_rows: Iterable[int] | None,
) -> set[int]:
    if refinement_rows is None:
        return set(range(row_count))

    selected = set(refinement_rows)
    for row_index in selected:
        if row_index < 0 or row_index >= row_count:
            raise ValueError(f"refinement row {row_index} is outside the linesplan")
    return selected


def refine_polyline_row(
    polyline: Polyline3D,
    base_row: Iterable[Vec3],
    *,
    max_segment_length: float | None,
    tolerance: float,
) -> RefinedPolylineRow:
    """Refine one longitudinal row by arc length between slice-plane nodes."""
    base_points = tuple(base_row)
    if len(base_points) < 2:
        raise ValueError("a polyline row must have at least two slice nodes")

    source_points = polyline_vertices(polyline)
    source_distances = cumulative_polyline_distances(source_points)
    base_distances = tuple(
        polyline_distance_at_point(
            source_points,
            source_distances,
            point,
            tolerance=tolerance,
        )
        for point in base_points
    )

    refined_points: list[Vec3] = []
    intervals: list[StripInterval] = []

    for interval_index in range(len(base_points) - 1):
        interval = refined_interval_points(
            source_points,
            source_distances,
            base_points[interval_index],
            base_points[interval_index + 1],
            base_distances[interval_index],
            base_distances[interval_index + 1],
            max_segment_length=max_segment_length,
            tolerance=tolerance,
        )
        intervals.append(
            append_interval_points(
                refined_points,
                interval,
                reuse_previous_endpoint=interval_index > 0,
                tolerance=tolerance,
            )
        )

    return RefinedPolylineRow(refined_points, intervals)


def refined_interval_points(
    source_points: tuple[Vec3, ...],
    source_distances: tuple[float, ...],
    start_point: Vec3,
    end_point: Vec3,
    start_distance: float,
    end_distance: float,
    *,
    max_segment_length: float | None,
    tolerance: float,
) -> list[tuple[Vec3, float]]:
    """Return ordered (point, parameter) values for one station interval."""
    length = abs(end_distance - start_distance)
    segment_count = required_segment_count(
        length,
        max_segment_length=max_segment_length,
        tolerance=tolerance,
    )
    direction = 1.0 if end_distance >= start_distance else -1.0

    samples: list[tuple[Vec3, float]] = []
    for index in range(segment_count + 1):
        parameter = index / segment_count
        if index == 0:
            point = start_point
        elif index == segment_count:
            point = end_point
        else:
            target_distance = start_distance + direction * length * parameter
            point = point_at_polyline_distance(
                source_points,
                source_distances,
                target_distance,
            )
        samples.append((point, parameter))

    return samples


def required_segment_count(
    length: float,
    *,
    max_segment_length: float | None,
    tolerance: float,
) -> int:
    if max_segment_length is None or length <= max_segment_length + tolerance:
        return 1
    return max(1, ceil(length / max_segment_length))


def append_interval_points(
    row_points: list[Vec3],
    interval_points: list[tuple[Vec3, float]],
    *,
    reuse_previous_endpoint: bool,
    tolerance: float,
) -> StripInterval:
    node_indices: list[int] = []
    parameters: list[float] = []

    for index, (point, parameter) in enumerate(interval_points):
        if reuse_previous_endpoint and index == 0:
            if not row_points:
                raise ValueError("cannot reuse an endpoint in an empty row")
            if not points_close(row_points[-1], point, tolerance=tolerance):
                raise ValueError("adjacent refined intervals do not share an endpoint")
            node_index = len(row_points) - 1
        else:
            node_index = len(row_points)
            row_points.append(point)

        node_indices.append(node_index)
        parameters.append(parameter)

    return StripInterval(tuple(node_indices), tuple(parameters))


def refined_rows_to_strip_mesh(
    refined_rows: Iterable[RefinedPolylineRow],
    *,
    tolerance: float = INTERSECTION_TOLERANCE,
) -> Mesh3D:
    """Triangulate each neighbouring-row strip and weld all strips together."""
    require_positive_tolerance(tolerance)

    rows = list(refined_rows)
    if len(rows) < 2:
        raise ValueError("at least two refined rows are required to build strips")

    vertices: list[Vec3] = []
    vertex_lookup: dict[Point3, int] = {}
    row_vertex_indices = [
        [index_point(vertices, vertex_lookup, point) for point in row.points]
        for row in rows
    ]

    faces: list[FaceIndex] = []
    edges: list[EdgeIndex] = []
    seen_edges: set[EdgeIndex] = set()

    for row_index in range(len(rows) - 1):
        add_strip_faces(
            rows[row_index],
            row_vertex_indices[row_index],
            rows[row_index + 1],
            row_vertex_indices[row_index + 1],
            faces=faces,
            edges=edges,
            seen_edges=seen_edges,
            vertices=vertices,
            tolerance=tolerance,
        )

    return Mesh3D(tuple(vertices), tuple(faces), tuple(edges))


def add_strip_faces(
    top_row: RefinedPolylineRow,
    top_vertex_indices: list[int],
    bottom_row: RefinedPolylineRow,
    bottom_vertex_indices: list[int],
    *,
    faces: list[FaceIndex],
    edges: list[EdgeIndex],
    seen_edges: set[EdgeIndex],
    vertices: list[Vec3],
    tolerance: float,
) -> None:
    if len(top_row.intervals) != len(bottom_row.intervals):
        raise ValueError("neighbouring refined rows have different station counts")

    for top_interval, bottom_interval in zip(
        top_row.intervals,
        bottom_row.intervals,
        strict=True,
    ):
        top_chain = [top_vertex_indices[index] for index in top_interval.node_indices]
        bottom_chain = [
            bottom_vertex_indices[index] for index in bottom_interval.node_indices
        ]
        add_chain_edges(top_chain, edges, seen_edges)
        add_chain_edges(bottom_chain, edges, seen_edges)
        add_cross_station_edges(top_chain, bottom_chain, edges, seen_edges)
        add_zipper_faces(
            top_chain,
            top_interval.parameters,
            bottom_chain,
            bottom_interval.parameters,
            faces=faces,
            edges=edges,
            seen_edges=seen_edges,
            vertices=vertices,
            tolerance=tolerance,
        )


def add_zipper_faces(
    top_chain: list[int],
    top_parameters: tuple[float, ...],
    bottom_chain: list[int],
    bottom_parameters: tuple[float, ...],
    *,
    faces: list[FaceIndex],
    edges: list[EdgeIndex],
    seen_edges: set[EdgeIndex],
    vertices: list[Vec3],
    tolerance: float,
) -> None:
    """Triangulate a two-boundary strip by merging each side's parameters."""
    if len(top_chain) != len(top_parameters):
        raise ValueError("top chain and parameter counts do not match")
    if len(bottom_chain) != len(bottom_parameters):
        raise ValueError("bottom chain and parameter counts do not match")

    top_index = 0
    bottom_index = 0

    while top_index < len(top_chain) - 1 or bottom_index < len(bottom_chain) - 1:
        if top_index == len(top_chain) - 1:
            face = (
                top_chain[top_index],
                bottom_chain[bottom_index],
                bottom_chain[bottom_index + 1],
            )
            bottom_index += 1
        elif (
            bottom_index == len(bottom_chain) - 1
            or top_parameters[top_index + 1] <= bottom_parameters[bottom_index + 1]
        ):
            face = (
                top_chain[top_index],
                bottom_chain[bottom_index],
                top_chain[top_index + 1],
            )
            top_index += 1
        else:
            face = (
                top_chain[top_index],
                bottom_chain[bottom_index],
                bottom_chain[bottom_index + 1],
            )
            bottom_index += 1

        append_valid_face(
            faces,
            edges,
            seen_edges,
            face,
            vertices=vertices,
            tolerance=tolerance,
        )


def add_chain_edges(
    chain: list[int],
    edges: list[EdgeIndex],
    seen_edges: set[EdgeIndex],
) -> None:
    for start, end in zip(chain, chain[1:], strict=False):
        append_unique_edge(edges, (start, end), seen=seen_edges)


def add_cross_station_edges(
    top_chain: list[int],
    bottom_chain: list[int],
    edges: list[EdgeIndex],
    seen_edges: set[EdgeIndex],
) -> None:
    append_unique_edge(edges, (top_chain[0], bottom_chain[0]), seen=seen_edges)
    append_unique_edge(edges, (top_chain[-1], bottom_chain[-1]), seen=seen_edges)


def append_valid_face(
    faces: list[FaceIndex],
    edges: list[EdgeIndex],
    seen_edges: set[EdgeIndex],
    face: FaceIndex,
    *,
    vertices: list[Vec3],
    tolerance: float,
) -> None:
    if is_degenerate_face(face, vertices=vertices, tolerance=tolerance):
        return

    faces.append(face)
    a, b, c = face
    append_unique_edge(edges, (a, b), seen=seen_edges)
    append_unique_edge(edges, (b, c), seen=seen_edges)
    append_unique_edge(edges, (c, a), seen=seen_edges)


def is_degenerate_face(
    face: FaceIndex,
    *,
    vertices: list[Vec3],
    tolerance: float,
) -> bool:
    a, b, c = face
    if a == b or b == c or c == a:
        return True

    area_twice = cross_length(
        subtract(vertices[b], vertices[a]),
        subtract(vertices[c], vertices[a]),
    )
    return area_twice <= tolerance


# -----------------------------------------------------------------------------
# Polyline arc-length helpers
# -----------------------------------------------------------------------------


def polyline_vertices(polyline: Polyline3D) -> tuple[Vec3, ...]:
    vertices = tuple(as_vec3(vertex) for vertex in polyline.vertices)
    if len(vertices) < 2:
        raise ValueError("source polyline must contain at least two vertices")
    return vertices


def cumulative_polyline_distances(vertices: tuple[Vec3, ...]) -> tuple[float, ...]:
    distances = [0.0]
    for start, end in zip(vertices, vertices[1:], strict=False):
        distances.append(distances[-1] + distance(start, end))
    return tuple(distances)


def polyline_distance_at_point(
    vertices: tuple[Vec3, ...],
    distances: tuple[float, ...],
    point: Vec3,
    *,
    tolerance: float,
) -> float:
    best_segment_distance = float("inf")
    best_path_distance: float | None = None

    for index, (start, end) in enumerate(zip(vertices, vertices[1:], strict=False)):
        segment_length = distances[index + 1] - distances[index]
        if segment_length <= tolerance:
            continue

        t = point_segment_parameter(start, end, point)
        if t < -tolerance or t > 1.0 + tolerance:
            continue

        t = clamp(t, 0.0, 1.0)
        closest = interpolate_vec3(start, end, t)
        segment_distance = distance(closest, point)

        if segment_distance < best_segment_distance:
            best_segment_distance = segment_distance
            best_path_distance = distances[index] + t * segment_length

    if best_path_distance is None or best_segment_distance > tolerance:
        raise ValueError("slice-generated point does not lie on its source polyline")

    return best_path_distance


def point_at_polyline_distance(
    vertices: tuple[Vec3, ...],
    distances: tuple[float, ...],
    target_distance: float,
) -> Vec3:
    target_distance = clamp(target_distance, distances[0], distances[-1])

    for index, (start, end) in enumerate(zip(vertices, vertices[1:], strict=False)):
        segment_start = distances[index]
        segment_end = distances[index + 1]
        if target_distance > segment_end:
            continue

        segment_length = segment_end - segment_start
        if segment_length == 0.0:
            return start

        t = (target_distance - segment_start) / segment_length
        return interpolate_vec3(start, end, t)

    return vertices[-1]


# -----------------------------------------------------------------------------
# Display geometry
# -----------------------------------------------------------------------------


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
        x = lerp(x_min, x_max, step / steps)
        z = lerp(z_min, z_max, step / steps)
        edges.append(add_display_segment(vertices, (x, y, z_min), (x, y, z_max)))
        edges.append(add_display_segment(vertices, (x_min, y, z), (x_max, y, z)))

    return Mesh3D(tuple(vertices), ((0, 1, 2), (0, 2, 3)), tuple(edges))


def add_display_segment(
    vertices: list[Vec3],
    start: Point3,
    end: Point3,
) -> EdgeIndex:
    start_index = len(vertices)
    vertices.append(Vec3(*start))
    vertices.append(Vec3(*end))
    return start_index, start_index + 1


def build_scene(
    wireframes: Iterable[Wireframe3D],
    planes: Iterable[tuple[float, Mesh3D]],
    nodes: Mesh3D | Iterable[Iterable[Vec3]] | PointCloud3D | None = None,
) -> Scene:
    scene = Scene(name="quarter_sphere_strip_mesh")
    for index, wireframe in enumerate(wireframes, start=1):
        scene = scene.add(
            wireframe,
            name=f"quarter_sphere_wireframe_{index}",
            style=WIRE_STYLE,
        )

    scene = add_planes_to_scene(scene, planes)
    scene = add_nodes_to_scene(scene, nodes)

    return scene.with_camera(CAMERA, name="isometric").with_light(LIGHT)


def add_planes_to_scene(
    scene: Scene,
    planes: Iterable[tuple[float, Mesh3D]],
) -> Scene:
    for index, (y, plane) in enumerate(planes):
        scene = scene.add(
            plane,
            name=f"slice_plane_y_{y:g}",
            style=PLANE_STYLES[index % len(PLANE_STYLES)],
        )
    return scene


def add_nodes_to_scene(
    scene: Scene,
    nodes: Mesh3D | Iterable[Iterable[Vec3]] | PointCloud3D | None,
) -> Scene:
    if nodes is None:
        return scene

    node_mesh, node_cloud = nodes_to_scene_geometry(nodes)

    if node_mesh is not None and node_mesh.vertices and (node_mesh.edges or node_mesh.faces):
        scene = scene.add(
            node_mesh,
            name="distance_refined_strip_mesh",
            style=NODE_MESH_STYLE,
        )

    if node_cloud.vertices:
        scene = scene.add(
            node_cloud,
            name="distance_refined_nodes",
            style=NODE_STYLE,
        )

    return scene


def nodes_to_scene_geometry(
    nodes: Mesh3D | Iterable[Iterable[Vec3]] | PointCloud3D,
) -> tuple[Mesh3D | None, PointCloud3D]:
    if isinstance(nodes, Mesh3D):
        return nodes, PointCloud3D(nodes.vertices)

    if isinstance(nodes, PointCloud3D):
        return None, nodes

    points = tuple(unique_points(nodes, tolerance=INTERSECTION_TOLERANCE))
    return None, PointCloud3D(points)


# -----------------------------------------------------------------------------
# Geometry helpers
# -----------------------------------------------------------------------------


def as_vec3(point: PointLike3) -> Vec3:
    if isinstance(point, Vec3):
        return point
    return Vec3(*point)


def interpolate_vec3(start: Vec3, end: Vec3, t: float) -> Vec3:
    return Vec3(
        lerp(start.x, end.x, t),
        lerp(start.y, end.y, t),
        lerp(start.z, end.z, t),
    )


def lerp(start: float, end: float, t: float) -> float:
    return start + (end - start) * t


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def point_segment_parameter(start: Vec3, end: Vec3, point: Vec3) -> float:
    segment = subtract(end, start)
    offset = subtract(point, start)
    length_squared = dot(segment, segment)
    if length_squared == 0.0:
        return 0.0
    return dot(offset, segment) / length_squared


def distance(left: Vec3, right: Vec3) -> float:
    delta = subtract(right, left)
    return sqrt(dot(delta, delta))


def subtract(left: Vec3, right: Vec3) -> Vec3:
    return Vec3(left.x - right.x, left.y - right.y, left.z - right.z)


def dot(left: Vec3, right: Vec3) -> float:
    return left.x * right.x + left.y * right.y + left.z * right.z


def cross(left: Vec3, right: Vec3) -> Vec3:
    return Vec3(
        left.y * right.z - left.z * right.y,
        left.z * right.x - left.x * right.z,
        left.x * right.y - left.y * right.x,
    )


def cross_length(left: Vec3, right: Vec3) -> float:
    value = cross(left, right)
    return sqrt(dot(value, value))


def points_close(left: Vec3, right: Vec3, *, tolerance: float) -> bool:
    return (
        abs(left.x - right.x) <= tolerance
        and abs(left.y - right.y) <= tolerance
        and abs(left.z - right.z) <= tolerance
    )


def append_unique_point(
    points: list[Vec3],
    point: Vec3,
    *,
    tolerance: float,
) -> None:
    if any(points_close(existing, point, tolerance=tolerance) for existing in points):
        return
    points.append(point)


def unique_points(
    point_groups: Iterable[Iterable[Vec3]],
    *,
    tolerance: float,
) -> tuple[Vec3, ...]:
    points: list[Vec3] = []
    for group in point_groups:
        for point in group:
            append_unique_point(points, point, tolerance=tolerance)
    return tuple(points)


# -----------------------------------------------------------------------------
# Topology helpers
# -----------------------------------------------------------------------------


def index_point(
    vertices: list[Vec3],
    vertex_lookup: dict[Point3, int],
    point: PointLike3,
) -> int:
    vertex = as_vec3(point)
    key = vertex.tuple()
    existing_index = vertex_lookup.get(key)
    if existing_index is not None:
        return existing_index

    new_index = len(vertices)
    vertex_lookup[key] = new_index
    vertices.append(vertex)
    return new_index


def append_unique_edge(
    edges: list[EdgeIndex],
    edge: EdgeIndex,
    *,
    seen: set[EdgeIndex] | None = None,
) -> None:
    start, end = edge
    if start == end:
        return

    key = edge_key(edge)
    if seen is None:
        if any(edge_key(existing) == key for existing in edges):
            return
    elif key in seen:
        return

    edges.append(edge)
    if seen is not None:
        seen.add(key)


def edge_key(edge: EdgeIndex) -> EdgeIndex:
    start, end = edge
    return (start, end) if start < end else (end, start)


# -----------------------------------------------------------------------------
# Validation and reporting
# -----------------------------------------------------------------------------


def require_positive_length(value: float, *, name: str) -> None:
    if value <= 0.0:
        raise ValueError(f"{name} must be positive")


def require_positive_tolerance(tolerance: float) -> None:
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")


def print_scene_summary(
    linesplan: Iterable[Polyline3D],
    wireframes: Iterable[Wireframe3D],
    planes: Iterable[tuple[float, Mesh3D]],
    strip_mesh: StripMeshData,
) -> None:
    print("quarter sphere wireframe")
    for index, polyline in enumerate(linesplan, start=1):
        start = format_point(polyline.vertices[0])
        end = format_point(polyline.vertices[-1])
        print(f"polyline_{index}: {len(polyline.vertices)} vertices, A={start}, B={end}")

    print_wireframe_summary(wireframes)
    print(f"slice planes: {', '.join(f'y={y:g}' for y, _plane in planes)}")
    print(
        "base node array: "
        f"{len(strip_mesh.base_node_array)} rows x "
        f"{len(strip_mesh.base_node_array[0])} columns"
    )
    print(
        "base intersection nodes: "
        f"{len(unique_points(strip_mesh.base_node_array, tolerance=INTERSECTION_TOLERANCE))}"
    )
    print(f"refined row nodes before welding: {strip_mesh.refined_node_count}")
    print(
        "display mesh: "
        f"{len(strip_mesh.mesh.vertices)} vertices, "
        f"{len(strip_mesh.mesh.edges)} edges, "
        f"{len(strip_mesh.mesh.faces)} faces"
    )
    if MAX_SEGMENT_LENGTH is None:
        print("distance refinement: disabled")
    else:
        print(f"distance refinement: max segment length {MAX_SEGMENT_LENGTH:g}")


def print_wireframe_summary(wireframes: Iterable[Wireframe3D]) -> None:
    for index, wireframe in enumerate(wireframes, start=1):
        lower, upper = wireframe.bounds()
        print(
            f"wireframe_{index}: {len(wireframe.vertices)} vertices, "
            f"{len(wireframe.edges)} edges, "
            f"bounds={format_point(lower)} to {format_point(upper)}"
        )


def format_point(point: PointLike3) -> str:
    x, y, z = point.tuple() if isinstance(point, Vec3) else point
    return f"({float(x):.3g}, {float(y):.3g}, {float(z):.3g})"


if __name__ == "__main__":
    main()
