"""Semantic 2D and 3D triangle meshes."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias, cast

import numpy as np

from cady.errors import GeometryError
from cady.operations.meshes import (
    boundary_edges_from_faces,
    compact_mesh_data,
    project_point_to_plane,
    prune_dangling_edges,
)
from cady.operations.transforms import Transform2, Transform3

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]

if TYPE_CHECKING:
    from cady.geometry.wireframe import Wireframe3
    from cady.operations.arrays import PointArray2, PointArray3
    from cady.view import Camera, DisplayStyle, Light
    from cady.view.open_view import Projection
    from cady.view.style import RenderMode

FaceIndex = tuple[int, int, int]
EdgeIndex = tuple[int, int]


@dataclass(frozen=True, slots=True)
class Mesh2:
    """Indexed 2D triangle mesh used at numeric conversion boundaries."""

    vertices: tuple[Point2, ...]
    faces: tuple[FaceIndex, ...]
    edges: tuple[EdgeIndex, ...] = ()

    def __post_init__(self) -> None:
        vertices = tuple(self.vertices)
        faces = tuple(_face(face) for face in self.faces)
        edges = tuple(_edge(edge) for edge in self.edges)
        for face in faces:
            if min(face) < 0:
                raise ValueError("faces must not contain negative indices")
            if vertices and max(face) >= len(vertices):
                raise ValueError("faces reference vertices outside the vertex array")
            if not vertices:
                raise ValueError("empty meshes cannot contain faces")
        for edge in edges:
            if min(edge) < 0:
                raise ValueError("edges must not contain negative indices")
            if vertices and max(edge) >= len(vertices):
                raise ValueError("edges reference vertices outside the vertex array")
            if not vertices:
                raise ValueError("empty meshes cannot contain edges")
        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "faces", faces)
        object.__setattr__(self, "edges", edges)

    @classmethod
    def merged(cls, meshes: Iterable[Mesh2]) -> Mesh2:
        vertices: list[Point2] = []
        faces: list[FaceIndex] = []
        edges: list[EdgeIndex] = []
        offset = 0
        for mesh in meshes:
            vertices.extend(mesh.vertices)
            faces.extend((a + offset, b + offset, c + offset) for a, b, c in mesh.faces)
            edges.extend((a + offset, b + offset) for a, b in mesh.edges)
            offset += len(mesh.vertices)
        return cls(tuple(vertices), tuple(faces), tuple(edges))

    @property
    def triangles(self) -> tuple[tuple[Point2, Point2, Point2], ...]:
        return tuple(
            (self.vertices[a], self.vertices[b], self.vertices[c]) for a, b, c in self.faces
        )

    @property
    def boundary(self) -> tuple[Point2, Point2]:
        return self.bounds()

    @property
    def boundary_loops(self) -> tuple[PointArray2, ...]:
        if not self.faces:
            raise GeometryError("mesh has no faces; boundary is undefined")
        return tuple(
            _polyline2_from_loop(self.vertices, loop)
            for loop in _boundary_loops(_boundary_halfedges(self.faces))
        )

    def to_array(self, *, tolerance: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        _validate_tolerance(tolerance)
        vertices = np.array(self.vertices, dtype=np.float64)
        faces = np.array(self.faces, dtype=np.int64)
        edges = np.array(self.edges, dtype=np.int64)
        if len(vertices) == 0:
            vertices = np.empty((0, 2), dtype=np.float64)
        if len(faces) == 0:
            faces = np.empty((0, 3), dtype=np.int64)
        if len(edges) == 0:
            edges = np.empty((0, 2), dtype=np.int64)
        return vertices, faces, edges

    def transformed(self, transform: Transform2) -> Mesh2:
        array = transform.array
        vertices = tuple((float(x), float(y)) for x, y in array)
        return Mesh2(vertices, self.faces, self.edges)

    def bounds(self) -> tuple[Point2, Point2]:
        if not self.vertices:
            raise ValueError("cannot calculate bounds for an empty mesh")
        return (
            (
                min(vertex[0] for vertex in self.vertices),
                min(vertex[1] for vertex in self.vertices),
            ),
            (
                max(vertex[0] for vertex in self.vertices),
                max(vertex[1] for vertex in self.vertices),
            ),
        )


@dataclass(frozen=True, slots=True)
class Mesh3:
    """Indexed 3D triangle mesh with optional explicit display edges."""

    vertices: tuple[Point3, ...]
    faces: tuple[FaceIndex, ...]
    edges: tuple[EdgeIndex, ...] = ()

    def __post_init__(self) -> None:
        vertices = tuple(self.vertices)
        faces = tuple(_face(face) for face in self.faces)
        edges = tuple(_edge(edge) for edge in self.edges)
        for face in faces:
            if min(face) < 0:
                raise ValueError("faces must not contain negative indices")
            if vertices and max(face) >= len(vertices):
                raise ValueError("faces reference vertices outside the vertex array")
            if not vertices:
                raise ValueError("empty meshes cannot contain faces")
        for edge in edges:
            if min(edge) < 0:
                raise ValueError("edges must not contain negative indices")
            if vertices and max(edge) >= len(vertices):
                raise ValueError("edges reference vertices outside the vertex array")
            if not vertices:
                raise ValueError("empty meshes cannot contain edges")
        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "faces", faces)
        object.__setattr__(self, "edges", edges)

    @classmethod
    def merged(cls, meshes: Iterable[Mesh3]) -> Mesh3:
        vertices: list[Point3] = []
        faces: list[FaceIndex] = []
        edges: list[EdgeIndex] = []
        offset = 0
        for mesh in meshes:
            vertices.extend(mesh.vertices)
            faces.extend((a + offset, b + offset, c + offset) for a, b, c in mesh.faces)
            edges.extend((a + offset, b + offset) for a, b in mesh.edges)
            offset += len(mesh.vertices)
        return cls(tuple(vertices), tuple(faces), tuple(edges))

    @property
    def triangles(self) -> tuple[tuple[Point3, Point3, Point3], ...]:
        return tuple(
            (self.vertices[a], self.vertices[b], self.vertices[c]) for a, b, c in self.faces
        )

    @property
    def boundary(self) -> tuple[Point3, Point3]:
        return self.bounds()

    @property
    def boundary_loops(self) -> tuple[PointArray3, ...]:
        if not self.faces:
            raise GeometryError("mesh has no faces; boundary is undefined")
        return tuple(
            _polyline_from_loop(self.vertices, loop)
            for loop in _boundary_loops(_boundary_halfedges(self.faces))
        )

    def to_array(self, *, tolerance: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        _validate_tolerance(tolerance)
        vertices = np.array(self.vertices, dtype=np.float64)
        faces = np.array(self.faces, dtype=np.int64)
        edges = np.array(self.edges, dtype=np.int64)
        if len(vertices) == 0:
            vertices = np.empty((0, 3), dtype=np.float64)
        if len(faces) == 0:
            faces = np.empty((0, 3), dtype=np.int64)
        if len(edges) == 0:
            edges = np.empty((0, 2), dtype=np.int64)
        return vertices, faces, edges

    def transformed(self, transform: Transform3) -> Mesh3:
        array = transform.apply_points(self.vertices)
        vertices = tuple((float(x), float(y), float(z)) for x, y, z in array)
        return Mesh3(vertices, self.faces, self.edges)

    def mirror(self, plane_origin: object, plane_normal: object) -> Mesh3:
        mirrored = self.transformed(Transform3(self.vertices).mirror(plane_origin, plane_normal))
        return Mesh3(mirrored.vertices, _reverse_face_winding(self.faces), self.edges)

    def bounds(self) -> tuple[Point3, Point3]:
        if not self.vertices:
            raise ValueError("cannot calculate bounds for an empty mesh")
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

    def close_planar(
        self,
        plane_origin: object,
        plane_normal: object,
        *,
        tolerance: float = 1e-3,
        snap_tolerance: float | None = None,
    ) -> Mesh3:
        """Cap an open mesh at an explicit plane.

        Detects boundary edges on the plane and triangulates the resulting
        loops. Returns a new ``Mesh3`` with the cap faces added.

        When *snap_tolerance* is ``None`` (default), only boundary vertices
        already on the plane (within *tolerance*) are used for the cap.

        When *snap_tolerance* is set, boundary vertices within that distance
        of the plane but not already on it are projected onto the plane.
        New projected vertices are appended and used for the cap while the
        originals stay connected, creating thin gaps that ``close_boundary``
        can fill.
        """
        from cady.operations.meshes import close_planar_cap

        _validate_tolerance(tolerance)
        if snap_tolerance is not None and snap_tolerance <= 0.0:
            raise ValueError("snap_tolerance must be positive")
        vertices, faces, edges = self.to_array(tolerance=tolerance)
        capped_vertices, capped_faces, capped_edges = close_planar_cap(
            vertices,
            faces,
            edges,
            plane_origin,
            plane_normal,
            tolerance=tolerance,
            snap_tolerance=snap_tolerance,
        )
        return _mesh_from_arrays(capped_vertices, capped_faces, capped_edges)

    def close_to_plane(
        self,
        plane_origin: object,
        plane_normal: object,
        *,
        tolerance: float = 1e-3,
        max_distance: float,
    ) -> Mesh3:
        """Project near-plane mesh edges to a plane and create wall faces.

        Uses explicit display edges when present, otherwise uses mesh boundary
        edges. Dangling degree-1 edge branches are pruned before wall faces are
        generated.
        """
        from cady.errors import GeometryError
        from cady.operations.projections import unit3, vector3

        _validate_tolerance(tolerance)
        if max_distance <= 0.0:
            raise ValueError("max_distance must be positive")

        origin_np = vector3(plane_origin, name="plane_origin")
        normal_np = unit3(plane_normal, name="plane_normal")
        source_edges = self.edges if self.edges else boundary_edges_from_faces(self.faces)
        live_edges = prune_dangling_edges(source_edges)

        near_edges: list[tuple[int, int, float, float]] = []
        for a, b in live_edges:
            va = np.array(self.vertices[a], dtype=np.float64)
            vb = np.array(self.vertices[b], dtype=np.float64)
            dist_a = float(np.dot(va - origin_np, normal_np))
            dist_b = float(np.dot(vb - origin_np, normal_np))
            if abs(dist_a) <= max_distance and abs(dist_b) <= max_distance:
                near_edges.append((a, b, dist_a, dist_b))

        if not near_edges:
            raise GeometryError("no edges found within max_distance of the plane")

        projected_index: dict[int, int] = {}
        all_vertices = list(self.vertices)

        for a, b, dist_a, dist_b in near_edges:
            if a not in projected_index:
                projected = tuple(
                    float(value)
                    for value in project_point_to_plane(self.vertices[a], dist_a, normal_np)
                )
                projected_index[a] = len(all_vertices)
                all_vertices.append(cast(Point3, projected))
            if b not in projected_index:
                projected = tuple(
                    float(value)
                    for value in project_point_to_plane(self.vertices[b], dist_b, normal_np)
                )
                projected_index[b] = len(all_vertices)
                all_vertices.append(cast(Point3, projected))

        wall_faces: list[FaceIndex] = []
        for a, b, _, _ in near_edges:
            pa = projected_index[a]
            pb = projected_index[b]
            wall_faces.append((a, b, pb))
            wall_faces.append((a, pb, pa))

        display_edges = live_edges if self.edges else ()
        compact_vertices, compact_faces, compact_edges = compact_mesh_data(
            tuple(all_vertices),
            self.faces + tuple(wall_faces),
            display_edges,
        )
        return Mesh3(
            tuple((float(x), float(y), float(z)) for x, y, z in compact_vertices),
            compact_faces,
            compact_edges,
        )

    def close_boundary(
        self,
        *,
        tolerance: float = 1e-3,
    ) -> Mesh3:
        """Close all planar boundary holes in the mesh.

        Detects boundary edges (edges appearing in exactly one face), stitches
        them into loops, fits a best-fit plane to each loop, and triangulates
        planar loops.

        Raises ``ValueError`` if any boundary loop is non-planar.
        """
        from cady.operations.meshes import close_boundary as _close_boundary_ops

        _validate_tolerance(tolerance)
        vertices, faces, edges = self.to_array(tolerance=tolerance)
        closed_vertices, closed_faces, closed_edges = _close_boundary_ops(
            vertices,
            faces,
            edges,
            tolerance=tolerance,
        )
        return _mesh_from_arrays(closed_vertices, closed_faces, closed_edges)

    def close_holes(
        self,
        *,
        tolerance: float = 1e-3,
        max_hole_edges: int | None = None,
    ) -> Mesh3:
        """Fill non-planar holes via advancing-front triangulation.

        Not yet implemented.
        """
        raise NotImplementedError(
            "close_holes is not implemented; use close_boundary for planar hole filling"
        )

    def to_wireframe(self) -> Wireframe3:
        """Extract all edges from faces as a Wireframe3."""
        from cady.geometry.wireframe import Wireframe3 as WF

        edge_set: set[tuple[int, int]] = set()
        for a, b, c in self.faces:
            for start, end in ((a, b), (b, c), (c, a)):
                edge_set.add((min(start, end), max(start, end)))
        return WF.from_edges(self.vertices, tuple(sorted(edge_set)))

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


def _mesh_from_arrays(
    vertices: np.ndarray,
    faces: np.ndarray,
    edges: np.ndarray | None = None,
) -> Mesh3:
    vertex_values = tuple((float(x), float(y), float(z)) for x, y, z in vertices)
    face_values = tuple((int(a), int(b), int(c)) for a, b, c in faces)
    edge_values: tuple[EdgeIndex, ...] = ()
    if edges is not None:
        edge_values = tuple((int(a), int(b)) for a, b in edges)
    return Mesh3(vertex_values, face_values, edge_values)


def _face(value: tuple[int, int, int]) -> FaceIndex:
    if len(value) != 3:
        raise ValueError("mesh faces must have exactly three indices")
    return (int(value[0]), int(value[1]), int(value[2]))


def _edge(value: tuple[int, int]) -> EdgeIndex:
    if len(value) != 2:
        raise ValueError("mesh edges must have exactly two indices")
    return (int(value[0]), int(value[1]))


def _reverse_face_winding(faces: tuple[FaceIndex, ...]) -> tuple[FaceIndex, ...]:
    return tuple((a, c, b) for a, b, c in faces)


def _boundary_halfedges(faces: tuple[FaceIndex, ...]) -> list[tuple[int, int]]:
    occurrences: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for face in faces:
        indices = [int(face[0]), int(face[1]), int(face[2])]
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
            occurrences[(min(start, end), max(start, end))].append((start, end))

    if any(len(edge_occurrences) > 2 for edge_occurrences in occurrences.values()):
        raise GeometryError("mesh boundary is undefined for non-manifold edges")

    return sorted(
        edge_occurrences[0]
        for edge_occurrences in occurrences.values()
        if len(edge_occurrences) == 1
    )


def _boundary_loops(halfedges: list[tuple[int, int]]) -> list[list[int]]:
    outgoing: dict[int, int] = {}
    incoming: dict[int, int] = {}
    unused_edges = set(halfedges)

    for start, end in halfedges:
        if start == end:
            raise GeometryError("mesh boundary is not a closed polyline")
        if start in outgoing or end in incoming:
            raise GeometryError("mesh boundary is not a closed polyline")
        outgoing[start] = end
        incoming[end] = start

    if set(outgoing) != set(incoming):
        raise GeometryError("mesh boundary is not a closed polyline")

    loops: list[list[int]] = []
    while unused_edges:
        # Walk each directed boundary cycle once and preserve its vertex order.
        start, _ = min(unused_edges)
        loop = [start]
        current = start

        while True:
            following = outgoing.get(current)
            if following is None or (current, following) not in unused_edges:
                raise GeometryError("mesh boundary is not a closed polyline")
            unused_edges.remove((current, following))
            current = following
            if current == start:
                break
            if current in loop:
                raise GeometryError("mesh boundary is not a closed polyline")
            loop.append(current)

        if len(loop) < 3:
            raise GeometryError("mesh boundary is not a closed polyline")
        loops.append(loop)

    return sorted(loops, key=lambda loop: (-len(loop), loop))


def _polyline_from_loop(vertices: tuple[Point3, ...], loop: list[int]) -> PointArray3:
    from cady.operations.arrays import as_points3

    return as_points3([vertices[index] for index in loop + [loop[0]]], name="vertices")


def _polyline2_from_loop(vertices: tuple[Point2, ...], loop: list[int]) -> PointArray2:
    from cady.operations.arrays import as_points2

    return as_points2([vertices[index] for index in loop + [loop[0]]], name="vertices")


def _validate_tolerance(tolerance: float) -> None:
    if float(tolerance) <= 0.0:
        raise ValueError("tolerance must be positive")
