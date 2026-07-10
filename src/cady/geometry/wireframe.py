"""Edge-only 3D wireframes stored as collections of polylines."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeAlias, cast

import numpy as np

from cady.geometry._coordinates import point3
from cady.geometry.mesh import EdgeIndex, Mesh3
from cady.geometry.point import Point3 as Point3Value
from cady.geometry.polyline import Polyline3
from cady.operations.transforms import Transform3

Point3: TypeAlias = Sequence[float]

if TYPE_CHECKING:
    from cady.view import Camera, DisplayStyle, Light
    from cady.view.style import RenderMode
    from cady.view.viewer import Projection

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
        vertex_values = tuple(point3(vertex, name="vertex") for vertex in vertices)
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
            Point3Value(
                min(vertex[0] for vertex in self.vertices),
                min(vertex[1] for vertex in self.vertices),
                min(vertex[2] for vertex in self.vertices),
            ),
            Point3Value(
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
        from cady.operations.wireframes import wireframe_to_mesh

        return wireframe_to_mesh(self, tolerance=tolerance)

    def remove_dangling_edges(self) -> Wireframe3:
        """Return a wireframe with recursively dangling edge branches removed."""
        from cady.operations.wireframes import remove_dangling_edges

        return remove_dangling_edges(self)

    def split_crossing_edges(self, *, tolerance: float = 1e-6) -> Wireframe3:
        """Return a wireframe with edges split at segment crossings."""
        from cady.operations.wireframes import split_crossing_edges

        return split_crossing_edges(self, tolerance=tolerance)

    # -- Loop triangulation -------------------------------------------------

    def triangulate(
        self,
        *,
        tolerance: float = 1e-3,
    ) -> Wireframe3:
        """Split crossings, remove dangling branches, and triangulate loops."""
        from cady.operations.wireframes import triangulate

        return triangulate(self, tolerance=tolerance)

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
        from cady.operations.wireframes import triangulate_loops

        return triangulate_loops(self, tolerance=tolerance)

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
        from cady.view.viewer import open_target_view

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
    key = (float(point[0]), float(point[1]), float(point[2]))
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


def _validate_tolerance(tolerance: float) -> None:
    if float(tolerance) <= 0.0:
        raise ValueError("tolerance must be positive")
