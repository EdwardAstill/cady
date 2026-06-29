"""Edge-only 3D wireframes stored as collections of polylines."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeAlias, cast

import numpy as np

from cady.geometry.mesh import EdgeIndex, Mesh3
from cady.geometry.polyline import Polyline3
from cady.operations.lofting import LoftMesh, loft_section_polylines
from cady.operations.mesh_topology import prune_dangling_edges
from cady.operations.transforms import Transform3

Point3: TypeAlias = tuple[float, float, float]

if TYPE_CHECKING:
    from cady.view import Camera, DisplayStyle, Light
    from cady.view.open_view import Projection
    from cady.view.style import RenderMode

WirePolyline = Polyline3


@dataclass(frozen=True, slots=True, init=False)
class Wireframe3:
    """Edge-only 3D geometry stored as open or closed polylines."""

    polylines: tuple[WirePolyline, ...]
    _vertices: tuple[Point3, ...] = field(repr=False, compare=False)
    _edges: tuple[EdgeIndex, ...] = field(repr=False, compare=False)

    def __init__(
        self,
        polylines: Iterable[WirePolyline] | Iterable[Point3] = (),
        edges: Iterable[EdgeIndex] | None = None,
    ) -> None:
        if edges is None:
            polylines = tuple(_coerce_polyline(item) for item in polylines)
            vertices, edge_values = _indexed_geometry(polylines)
            object.__setattr__(
                self,
                "polylines",
                polylines,
            )
            object.__setattr__(self, "_vertices", vertices)
            object.__setattr__(self, "_edges", edge_values)
            return
        vertices = cast(Iterable[Point3], polylines)
        vertex_values = tuple(vertices)
        edge_values = tuple(_validate_edge(vertex_values, edge) for edge in edges)
        object.__setattr__(
            self,
            "polylines",
            _edge_polylines(vertex_values, edge_values),
        )
        object.__setattr__(self, "_vertices", vertex_values)
        object.__setattr__(self, "_edges", edge_values)

    @classmethod
    def from_polylines(
        cls,
        polylines: Iterable[WirePolyline],
    ) -> Wireframe3:
        """Build a wireframe from open or closed 3D polylines."""
        return cls(polylines)

    @classmethod
    def from_edges(
        cls,
        vertices: Iterable[Point3],
        edges: Iterable[EdgeIndex],
    ) -> Wireframe3:
        """Build a polyline-backed wireframe from indexed edges."""
        return cls(vertices, edges)

    @property
    def vertices(self) -> tuple[Point3, ...]:
        return self._vertices

    @property
    def edges(self) -> tuple[EdgeIndex, ...]:
        return self._edges

    def transformed(self, transform: Transform3) -> Wireframe3:
        array = transform.apply_points(self.vertices)
        vertices = tuple((float(x), float(y), float(z)) for x, y, z in array)
        return Wireframe3.from_edges(vertices, self.edges)

    def mirror(self, plane_origin: object, plane_normal: object) -> Wireframe3:
        return self.transformed(Transform3(self.vertices).mirror(plane_origin, plane_normal))

    def bounds(self) -> tuple[Point3, Point3]:
        if not self.vertices:
            raise ValueError("cannot calculate bounds for an empty wireframe")
        return (
            (
                min(vertex[0] for vertex in self.vertices),
                min(vertex[1] for vertex in self.vertices),
                min(vertex[2] for vertex in self.vertices),
            ),
            (
                max(vertex[0] for vertex in self.vertices),
                max(vertex[1] for vertex in self.vertices),
                max(vertex[2] for vertex in self.vertices),
            ),
        )

    @property
    def boundary(self) -> tuple[Point3, Point3]:
        return self.bounds()

    def to_array(self, *, tolerance: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        _validate_tolerance(tolerance)
        vertices = np.array(self.vertices, dtype=np.float64)
        edges = np.array(self.edges, dtype=np.int64)
        if len(vertices) == 0:
            vertices = np.empty((0, 3), dtype=np.float64)
        if len(edges) == 0:
            edges = np.empty((0, 2), dtype=np.int64)
        return vertices, np.empty((0, 3), dtype=np.int64), edges

    def to_mesh(self, *, tolerance: float) -> Mesh3:
        """Convert crossing-prone wire edges into a triangulated mesh."""
        return _mesh_from_triangulation(_triangulate_wireframe(self, tolerance=tolerance))

    def remove_dangling_edges(self) -> Wireframe3:
        """Return a wireframe with recursively dangling edge branches removed."""
        return _wireframe_from_edges(
            self.vertices,
            prune_dangling_edges(self.edges),
        )

    def split_crossing_edges(self, *, tolerance: float = 1e-6) -> Wireframe3:
        """Return a wireframe with edges split at segment crossings."""
        _validate_tolerance(tolerance)
        if not self.edges:
            return Wireframe3.from_edges(self.vertices, self.edges)

        vertices = list(self.vertices)
        split_points: list[list[tuple[float, int]]] = [
            [(0.0, edge[0]), (1.0, edge[1])] for edge in self.edges
        ]
        edge_bounds = tuple(_edge_bounds(self.vertices, edge) for edge in self.edges)

        for left_index, left_edge in enumerate(self.edges):
            for right_index in range(left_index + 1, len(self.edges)):
                right_edge = self.edges[right_index]
                if set(left_edge) & set(right_edge):
                    continue
                if not _bounds_overlap(
                    edge_bounds[left_index],
                    edge_bounds[right_index],
                    tolerance,
                ):
                    continue

                for left_param, right_param, point in _edge_crossing_points(
                    self.vertices,
                    left_edge,
                    right_edge,
                    tolerance,
                ):
                    vertex_index = _find_or_add_vertex(vertices, point, tolerance)
                    split_points[left_index].append((left_param, vertex_index))
                    split_points[right_index].append((right_param, vertex_index))

        edges: list[EdgeIndex] = []
        edge_keys: set[EdgeIndex] = set()
        for points in split_points:
            ordered = _unique_split_points(points, tolerance)
            for (_, start), (_, end) in zip(ordered, ordered[1:], strict=False):
                _append_unique_edge(edges, edge_keys, start, end)

        return Wireframe3.from_edges(tuple(vertices), tuple(edges))

    # -- Loop triangulation -------------------------------------------------

    def triangulate(
        self,
        *,
        tolerance: float = 1e-3,
    ) -> Wireframe3:
        """Split crossings, remove dangling branches, and triangulate loops."""
        return _wireframe_from_triangulation(_triangulate_wireframe(self, tolerance=tolerance))

    def triangulate_loops(
        self,
        *,
        tolerance: float = 1e-3,
    ) -> Wireframe3:
        """Detect closed edge cycles and triangulate each into a Wireframe3.

        Builds an adjacency graph from edges, walks cycles via DFS, fits a
        best-fit plane (SVD) to each cycle, and triangulates. Dangling
        wireframe branches are pruned from the returned wireframe. Raises
        ``GeometryError`` if no closed loops of length >= 3 are found.
        """
        return _wireframe_from_triangulation(
            _triangulate_loops_to_triangulation(self, tolerance=tolerance)
        )

    # -- Viewing ----------------------------------------------------------

    def view(
        self,
        *,
        name: str | None = None,
        title: str | None = None,
        camera: Camera | None = None,
        style: DisplayStyle | None = None,
        light: Light | None = None,
        color: tuple[float, float, float] | None = None,
        render_mode: RenderMode | None = None,
        projection: Projection = "orthographic",
        center: bool = True,
        tolerance: float = 1e-3,
    ) -> None:
        from cady.view.open_view import open_target_view

        open_target_view(
            self,
            name=name,
            title=title,
            camera=camera,
            style=style,
            light=light,
            color=color,
            render_mode=render_mode,
            projection=projection,
            center=center,
            tolerance=tolerance,
        )


def _edge(value: tuple[int, int]) -> EdgeIndex:
    if len(value) != 2:
        raise ValueError("wireframe edges must have exactly two indices")
    return (int(value[0]), int(value[1]))


def _validate_edge(vertices: tuple[Point3, ...], value: tuple[int, int]) -> EdgeIndex:
    start, end = _edge(value)
    if start < 0 or end < 0:
        raise ValueError("edges must not contain negative indices")
    if vertices and max(start, end) >= len(vertices):
        raise ValueError("edges reference vertices outside the vertex array")
    if not vertices:
        raise ValueError("empty wireframes cannot contain edges")
    return start, end


def _coerce_polyline(value: object) -> WirePolyline:
    if isinstance(value, Polyline3):
        return value
    raise TypeError("wireframe polylines must be Polyline3")


def _edge_polylines(
    vertices: tuple[Point3, ...],
    edges: tuple[EdgeIndex, ...],
) -> tuple[Polyline3, ...]:
    polylines: list[Polyline3] = []
    for edge in edges:
        start, end = edge
        if start != end:
            polylines.append(Polyline3((vertices[start], vertices[end])))
    return tuple(polylines)


def _indexed_geometry(
    polylines: tuple[WirePolyline, ...],
) -> tuple[tuple[Point3, ...], tuple[EdgeIndex, ...]]:
    vertices: list[Point3] = []
    vertex_indices: dict[tuple[float, float, float], int] = {}
    edges: list[EdgeIndex] = []
    edge_keys: set[EdgeIndex] = set()

    for polyline in polylines:
        previous_index: int | None = None
        for point in polyline.points():
            current_index = _find_or_add_exact_vertex(vertices, vertex_indices, point)
            if previous_index is not None:
                _append_unique_edge(edges, edge_keys, previous_index, current_index)
            previous_index = current_index

    return tuple(vertices), tuple(edges)


def _find_or_add_exact_vertex(
    vertices: list[Point3],
    vertex_indices: dict[tuple[float, float, float], int],
    point: Point3,
) -> int:
    key = point
    existing_index = vertex_indices.get(key)
    if existing_index is not None:
        return existing_index

    new_index = len(vertices)
    vertex_indices[key] = new_index
    vertices.append(point)
    return new_index


def _append_unique_edge(
    edges: list[EdgeIndex],
    edge_keys: set[EdgeIndex],
    start: int,
    end: int,
) -> None:
    if start == end:
        return

    key = (start, end) if start < end else (end, start)
    if key in edge_keys:
        return
    edge_keys.add(key)
    edges.append((start, end))


@dataclass(frozen=True, slots=True)
class _WireframeTriangulation:
    vertices: tuple[Point3, ...]
    faces: tuple[tuple[int, int, int], ...]


def _triangulate_wireframe(
    wireframe: Wireframe3,
    *,
    tolerance: float,
) -> _WireframeTriangulation:
    section_triangulation = _loft_section_wireframe_to_triangulation(
        wireframe,
        tolerance=tolerance,
    )
    if section_triangulation is not None:
        return section_triangulation
    split = wireframe.split_crossing_edges(tolerance=tolerance)
    return _triangulate_loops_to_triangulation(
        split.remove_dangling_edges(),
        tolerance=tolerance,
    )


def _remove_dangling_edges(edges: tuple[EdgeIndex, ...]) -> tuple[EdgeIndex, ...]:
    return prune_dangling_edges(edges)


def _wireframe_from_edges(
    vertices: tuple[Point3, ...],
    edges: tuple[EdgeIndex, ...],
) -> Wireframe3:
    if not edges:
        return Wireframe3.from_edges((), ())

    ordered_vertices = tuple(sorted({index for edge in edges for index in edge}))
    remap = {old: new for new, old in enumerate(ordered_vertices)}
    compact_vertices = tuple(vertices[index] for index in ordered_vertices)
    compact_edges = tuple((remap[a], remap[b]) for a, b in edges)
    return Wireframe3.from_edges(compact_vertices, compact_edges)


def _edge_bounds(
    vertices: tuple[Point3, ...],
    edge: EdgeIndex,
) -> tuple[Point3, Point3]:
    start = vertices[edge[0]]
    end = vertices[edge[1]]
    return (
        (min(start[0], end[0]), min(start[1], end[1]), min(start[2], end[2])),
        (max(start[0], end[0]), max(start[1], end[1]), max(start[2], end[2])),
    )


def _bounds_overlap(
    left: tuple[Point3, Point3],
    right: tuple[Point3, Point3],
    tolerance: float,
) -> bool:
    left_lower, left_upper = left
    right_lower, right_upper = right
    return not (
        left_upper[0] + tolerance < right_lower[0]
        or right_upper[0] + tolerance < left_lower[0]
        or left_upper[1] + tolerance < right_lower[1]
        or right_upper[1] + tolerance < left_lower[1]
        or left_upper[2] + tolerance < right_lower[2]
        or right_upper[2] + tolerance < left_lower[2]
    )


def _loft_section_wireframe_to_triangulation(
    wireframe: Wireframe3,
    *,
    tolerance: float,
) -> _WireframeTriangulation | None:
    loft_mesh = loft_section_polylines(
        (vertices for vertices in _wireframe_polylines(wireframe)),
        tolerance=tolerance,
    )
    if loft_mesh is None:
        return None
    return _triangulation_from_loft_mesh(loft_mesh)


def _wireframe_polylines(wireframe: Wireframe3) -> tuple[tuple[Point3, ...], ...]:
    adjacency: dict[int, list[int]] = {}
    for a, b in wireframe.edges:
        adjacency.setdefault(a, []).append(b)
        adjacency.setdefault(b, []).append(a)

    visited_vertices: set[int] = set()
    polylines: list[tuple[Point3, ...]] = []
    for vertex in sorted(adjacency):
        if vertex in visited_vertices:
            continue

        stack = [vertex]
        component: set[int] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency.get(current, ()))
        visited_vertices.update(component)

        endpoints = sorted(index for index in component if len(adjacency[index]) <= 1)
        start = endpoints[0] if endpoints else min(component)
        ordered = _walk_polyline_component(start, component, adjacency)
        if len(ordered) >= 2:
            polylines.append(tuple(wireframe.vertices[index] for index in ordered))
    return tuple(polylines)


def _walk_polyline_component(
    start: int,
    component: set[int],
    adjacency: dict[int, list[int]],
) -> tuple[int, ...]:
    ordered = [start]
    previous: int | None = None
    current = start
    while True:
        candidates = [
            index
            for index in sorted(adjacency.get(current, ()))
            if index in component and index != previous and index not in ordered
        ]
        if not candidates:
            break
        previous, current = current, candidates[0]
        ordered.append(current)
    return tuple(ordered)


def _edges_from_faces(faces: tuple[tuple[int, int, int], ...]) -> tuple[EdgeIndex, ...]:
    edges: set[EdgeIndex] = set()
    for a, b, c in faces:
        for start, end in ((a, b), (b, c), (c, a)):
            edges.add((min(start, end), max(start, end)))
    return tuple(sorted(edges))


def _wireframe_from_triangulation(triangulation: _WireframeTriangulation) -> Wireframe3:
    return Wireframe3.from_edges(
        triangulation.vertices,
        _edges_from_faces(triangulation.faces),
    )


def _mesh_from_triangulation(triangulation: _WireframeTriangulation) -> Mesh3:
    return Mesh3(
        triangulation.vertices,
        triangulation.faces,
        _edges_from_faces(triangulation.faces),
    )


def _triangulation_from_loft_mesh(loft_mesh: LoftMesh) -> _WireframeTriangulation:
    return _WireframeTriangulation(
        tuple((float(x), float(y), float(z)) for x, y, z in loft_mesh.vertices),
        loft_mesh.faces,
    )


def _triangulate_loops_to_triangulation(
    wireframe: Wireframe3,
    *,
    tolerance: float,
) -> _WireframeTriangulation:
    from cady.errors import GeometryError
    from cady.geometry.plane3 import Plane3
    from cady.operations.triangulation import triangulate2

    neighbours: dict[int, set[int]] = {}
    for a, b in wireframe.edges:
        neighbours.setdefault(a, set()).add(b)
        neighbours.setdefault(b, set()).add(a)

    used_cycle_edges: set[tuple[int, int]] = set()
    cycles: list[list[int]] = []

    for start in sorted(neighbours):
        visited: set[int] = set()
        stack: list[tuple[int, int | None, list[int]]] = [(start, None, [start])]
        while stack:
            vertex, parent, path = stack.pop()
            if vertex in visited:
                continue
            visited.add(vertex)
            found_cycle = False
            for neighbour in sorted(neighbours.get(vertex, set())):
                edge_key = (min(vertex, neighbour), max(vertex, neighbour))
                if edge_key in used_cycle_edges:
                    continue
                if neighbour == parent:
                    continue
                if neighbour == start and len(path) >= 3:
                    cycle = path
                    for index in range(len(cycle)):
                        a, b = cycle[index], cycle[(index + 1) % len(cycle)]
                        used_cycle_edges.add((min(a, b), max(a, b)))
                    cycles.append(cycle)
                    found_cycle = True
                    break
                if neighbour not in visited:
                    stack.append((neighbour, vertex, path + [neighbour]))
            if found_cycle:
                break

    cycles = [cycle for cycle in cycles if len(cycle) >= 3]
    if not cycles:
        raise GeometryError("no closed edge loops of length >= 3 found")

    faces: list[tuple[int, int, int]] = []
    for loop in cycles:
        loop_points = tuple(wireframe.vertices[index] for index in loop)
        plane = Plane3.fit(loop_points)
        deviation = plane.max_deviation(loop_points)
        if deviation > tolerance:
            raise GeometryError(
                f"edge loop is non-planar (max deviation {deviation:.3e} > "
                f"tolerance {tolerance:.3e})"
            )
        projected = [plane.coordinates(point) for point in loop_points]
        projected_array = np.asarray(projected, dtype=np.float64)
        edges = np.asarray(
            tuple((index, (index + 1) % len(projected)) for index in range(len(projected))),
            dtype=np.int64,
        )
        _nodes, face_array = triangulate2(projected_array, edges, tolerance=tolerance)
        for a, b, c in face_array:
            faces.append((loop[int(a)], loop[int(c)], loop[int(b)]))

    return _triangulation_without_dangling_source_edges(
        wireframe.vertices,
        tuple(faces),
        wireframe.edges,
    )


def _edge_crossing_points(
    vertices: tuple[Point3, ...],
    left_edge: EdgeIndex,
    right_edge: EdgeIndex,
    tolerance: float,
) -> tuple[tuple[float, float, Point3], ...]:
    left_start = _array3(vertices[left_edge[0]])
    left_end = _array3(vertices[left_edge[1]])
    right_start = _array3(vertices[right_edge[0]])
    right_end = _array3(vertices[right_edge[1]])
    left_direction = left_end - left_start
    right_direction = right_end - right_start
    left_length = float(np.linalg.norm(left_direction))
    right_length = float(np.linalg.norm(right_direction))
    if left_length <= tolerance or right_length <= tolerance:
        return ()

    cross = np.cross(left_direction, right_direction)
    if float(np.linalg.norm(cross)) <= tolerance * left_length * right_length:
        return _collinear_crossing_points(
            left_start,
            left_end,
            right_start,
            right_end,
            tolerance,
        )

    matrix = np.column_stack((left_direction, -right_direction))
    params, *_ = np.linalg.lstsq(matrix, right_start - left_start, rcond=None)
    left_param = float(params[0])
    right_param = float(params[1])
    if not (
        _param_in_segment(left_param, tolerance, left_length)
        and _param_in_segment(right_param, tolerance, right_length)
    ):
        return ()

    left_point = left_start + left_direction * left_param
    right_point = right_start + right_direction * right_param
    if float(np.linalg.norm(left_point - right_point)) > tolerance:
        return ()

    point = (left_point + right_point) / 2.0
    return ((_clamp_unit(left_param), _clamp_unit(right_param), _vec3_from_array(point)),)


def _collinear_crossing_points(
    left_start: np.ndarray,
    left_end: np.ndarray,
    right_start: np.ndarray,
    right_end: np.ndarray,
    tolerance: float,
) -> tuple[tuple[float, float, Point3], ...]:
    left_direction = left_end - left_start
    right_direction = right_end - right_start
    if (
        float(np.linalg.norm(np.cross(left_direction, right_start - left_start))) > tolerance
        or float(np.linalg.norm(np.cross(left_direction, right_end - left_start))) > tolerance
    ):
        return ()

    points: list[tuple[float, float, Point3]] = []
    for point in (left_start, left_end, right_start, right_end):
        left_param = _point_parameter(point, left_start, left_end)
        right_param = _point_parameter(point, right_start, right_end)
        if _param_in_segment(left_param, tolerance, float(np.linalg.norm(left_direction))) and (
            _param_in_segment(right_param, tolerance, float(np.linalg.norm(right_direction)))
        ):
            _append_crossing_point(
                points,
                _clamp_unit(left_param),
                _clamp_unit(right_param),
                _vec3_from_array(point),
                tolerance,
            )
    return tuple(points)


def _append_crossing_point(
    points: list[tuple[float, float, Point3]],
    left_param: float,
    right_param: float,
    point: Point3,
    tolerance: float,
) -> None:
    for _, _, existing in points:
        if _distance(existing, point) <= tolerance:
            return
    points.append((left_param, right_param, point))


def _unique_split_points(
    points: list[tuple[float, int]],
    tolerance: float,
) -> tuple[tuple[float, int], ...]:
    ordered = sorted(points, key=lambda item: (item[0], item[1]))
    unique: list[tuple[float, int]] = []
    for param, vertex_index in ordered:
        if unique and (abs(param - unique[-1][0]) <= tolerance or vertex_index == unique[-1][1]):
            continue
        unique.append((_clamp_unit(param), vertex_index))
    return tuple(unique)


def _find_or_add_vertex(vertices: list[Point3], point: Point3, tolerance: float) -> int:
    for index, vertex in enumerate(vertices):
        if _distance(vertex, point) <= tolerance:
            return index
    vertices.append(point)
    return len(vertices) - 1


def _point_parameter(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> float:
    direction = end - start
    denominator = float(np.dot(direction, direction))
    if denominator == 0.0:
        return 0.0
    return float(np.dot(point - start, direction) / denominator)


def _param_in_segment(param: float, tolerance: float, segment_length: float) -> bool:
    slack = tolerance / segment_length if segment_length > 0.0 else tolerance
    return -slack <= param <= 1.0 + slack


def _clamp_unit(value: float) -> float:
    return min(1.0, max(0.0, value))


def _array3(vertex: Point3) -> np.ndarray:
    return np.array(vertex, dtype=np.float64)


def _vec3_from_array(value: np.ndarray) -> Point3:
    return (float(value[0]), float(value[1]), float(value[2]))


def _distance(left: Point3, right: Point3) -> float:
    return float(np.linalg.norm(_array3(left) - _array3(right)))


def _triangulation_without_dangling_source_edges(
    vertices: tuple[Point3, ...],
    faces: tuple[tuple[int, int, int], ...],
    edges: tuple[EdgeIndex, ...],
) -> _WireframeTriangulation:
    live_edges = _remove_dangling_edges(edges)

    used_vertices = {index for face in faces for index in face}
    used_vertices.update(index for edge in live_edges for index in edge)
    if not used_vertices:
        return _WireframeTriangulation((), ())

    ordered_vertices = tuple(sorted(used_vertices))
    remap = {old: new for new, old in enumerate(ordered_vertices)}
    compact_vertices = tuple(vertices[index] for index in ordered_vertices)
    compact_faces = tuple((remap[a], remap[b], remap[c]) for a, b, c in faces)
    return _WireframeTriangulation(compact_vertices, compact_faces)


def _validate_tolerance(tolerance: float) -> None:
    if float(tolerance) <= 0.0:
        raise ValueError("tolerance must be positive")
