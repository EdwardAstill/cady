"""Semantic 2D triangle meshes and 3D polygon meshes."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from math import fsum
from operator import index as operator_index
from typing import TYPE_CHECKING, TypeAlias

import numpy as np
from numpy.typing import NDArray

from cady.errors import GeometryError
from cady.operations.transforms import Transform2, Transform3

Point2: TypeAlias = tuple[float, float]
Point3: TypeAlias = tuple[float, float, float]
PointArray2: TypeAlias = NDArray[np.float64]
PointArray3: TypeAlias = NDArray[np.float64]

if TYPE_CHECKING:
    from cady.geometry.wireframe import Wireframe3
    from cady.view import Camera, DisplayStyle, Light
    from cady.view.style import RenderMode
    from cady.view.viewer import Projection

TriangleIndex = tuple[int, int, int]
FaceIndex = tuple[int, ...]
EdgeIndex = tuple[int, int]


@dataclass(frozen=True, slots=True)
class Mesh2:
    """Indexed 2D triangle mesh used at numeric conversion boundaries."""

    vertices: tuple[Point2, ...]
    faces: tuple[TriangleIndex, ...]
    edges: tuple[EdgeIndex, ...] = ()

    def __post_init__(self) -> None:
        vertices = tuple(self.vertices)
        faces = tuple(_triangle_face(face) for face in self.faces)
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
        faces: list[TriangleIndex] = []
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
    def area(self) -> float:
        """Sum of triangle face areas."""
        return float(_mesh2_area(self.vertices, self.faces))

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
    """Indexed 3D polygon mesh with optional explicit display edges."""

    vertices: tuple[Point3, ...]
    faces: tuple[FaceIndex, ...]
    edges: tuple[EdgeIndex, ...] = ()

    def __post_init__(self) -> None:
        vertices = tuple(self.vertices)
        faces = tuple(_polygon_face(face) for face in self.faces)
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
            faces.extend(tuple(index + offset for index in face) for face in mesh.faces)
            edges.extend((a + offset, b + offset) for a, b in mesh.edges)
            offset += len(mesh.vertices)
        return cls(tuple(vertices), tuple(faces), tuple(edges))

    @classmethod
    def from_points(
        cls,
        points: object,
        *,
        tolerance: float = 1e-6,
    ) -> Mesh3:
        """Reconstruct a triangle mesh from array-like 3D points."""
        from cady.operations.advancing_front import advancing_front_surface

        vertices, faces, edges = advancing_front_surface(
            _point_array_from_points(points, tolerance=tolerance),
            tolerance=tolerance,
        )
        return _mesh_from_arrays(vertices, faces, edges)

    @property
    def triangles(self) -> tuple[tuple[Point3, Point3, Point3], ...]:
        return tuple(
            (self.vertices[a], self.vertices[b], self.vertices[c])
            for a, b, c in self.triangulated_faces()
        )

    def triangulated_faces(self, *, tolerance: float = 1e-9) -> tuple[TriangleIndex, ...]:
        """Return triangular faces for render/export/numeric boundaries."""
        _validate_tolerance(tolerance)
        return _triangulated_faces(self.vertices, self.faces, tolerance=tolerance)

    def triangulated(self, *, tolerance: float = 1e-9) -> Mesh3:
        """Return an equivalent mesh whose faces are all triangles."""
        return Mesh3(self.vertices, self.triangulated_faces(tolerance=tolerance), self.edges)

    def decimate(self, target_faces: int, *, tolerance: float = 1e-9) -> Mesh3:
        """Return a simplified triangle mesh with at most ``target_faces`` faces."""
        from cady.operations.mesh_topology import decimate_mesh_data

        target_count = _validate_target_faces(target_faces)
        _validate_tolerance(tolerance)
        faces = self.triangulated_faces(tolerance=tolerance)
        if len(faces) <= target_count:
            return Mesh3(self.vertices, self.faces, self.edges)

        vertices_array = np.array(self.vertices, dtype=np.float64)
        faces_array = np.array(faces, dtype=np.int64)
        edges_array = np.array(self.edges, dtype=np.int64)
        if len(edges_array) == 0:
            edges_array = np.empty((0, 2), dtype=np.int64)
        decimated_vertices, decimated_faces, decimated_edges = decimate_mesh_data(
            vertices_array,
            faces_array,
            edges_array,
            target_faces=target_count,
            tolerance=tolerance,
        )
        return _mesh_from_arrays(decimated_vertices, decimated_faces, decimated_edges)

    @property
    def area(self) -> float:
        """Sum of face surface areas after boundary triangulation."""
        return float(_mesh3_area(self.vertices, self.triangulated_faces()))

    @property
    def volume(self) -> float:
        """Signed-volume tetrahedron integration.

        Computes the enclosed volume by summing signed tetrahedron
        volumes formed from a shared reference point (mean vertex) and
        each triangular face.  Returns the absolute value so the result
        is always non-negative regardless of face winding.
        """
        return float(_mesh3_volume(self.vertices, self.triangulated_faces()))

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
        faces = np.array(self.triangulated_faces(tolerance=tolerance), dtype=np.int64)
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
        from cady.operations.mesh_clipping import close_planar_cap

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
        from cady.operations.mesh_clipping import close_to_plane as _close_to_plane_ops

        _validate_tolerance(tolerance)
        if max_distance <= 0.0:
            raise ValueError("max_distance must be positive")
        vertices, faces, edges = self.to_array(tolerance=tolerance)
        closed_vertices, closed_faces, closed_edges = _close_to_plane_ops(
            vertices,
            faces,
            edges,
            plane_origin,
            plane_normal,
            tolerance=tolerance,
            max_distance=max_distance,
        )
        return _mesh_from_arrays(closed_vertices, closed_faces, closed_edges)

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
        from cady.operations.mesh_clipping import close_boundary as _close_boundary_ops

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

        edge_set = set(_face_edges(self.faces))
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


def _triangle_face(value: tuple[int, int, int]) -> TriangleIndex:
    if len(value) != 3:
        raise ValueError("mesh faces must have exactly three indices")
    return (int(value[0]), int(value[1]), int(value[2]))


def _polygon_face(value: tuple[int, ...]) -> FaceIndex:
    face = tuple(int(index) for index in value)
    if len(face) < 3:
        raise ValueError("mesh faces must have at least three indices")
    return face


def _edge(value: tuple[int, int]) -> EdgeIndex:
    if len(value) != 2:
        raise ValueError("mesh edges must have exactly two indices")
    return (int(value[0]), int(value[1]))


def _reverse_face_winding(faces: tuple[FaceIndex, ...]) -> tuple[FaceIndex, ...]:
    return tuple((face[0], *reversed(face[1:])) for face in faces)


def _face_edges(faces: tuple[FaceIndex, ...]) -> tuple[EdgeIndex, ...]:
    edges: set[EdgeIndex] = set()
    for face in faces:
        indices = tuple(int(index) for index in face)
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
            edges.add((min(start, end), max(start, end)))
    return tuple(sorted(edges))


def _fan_triangulated_face(face: FaceIndex) -> tuple[TriangleIndex, ...]:
    return tuple(
        (int(face[0]), int(face[index]), int(face[index + 1]))
        for index in range(1, len(face) - 1)
    )


def _triangulated_faces(
    vertices: tuple[Point3, ...],
    faces: tuple[FaceIndex, ...],
    *,
    tolerance: float,
) -> tuple[TriangleIndex, ...]:
    triangles: list[TriangleIndex] = []
    for face in faces:
        if len(face) == 3:
            triangles.append((int(face[0]), int(face[1]), int(face[2])))
        else:
            triangles.extend(_triangulated_polygon_face(vertices, face, tolerance=tolerance))
    return tuple(triangles)


def _triangulated_polygon_face(
    vertices: tuple[Point3, ...],
    face: FaceIndex,
    *,
    tolerance: float,
) -> tuple[TriangleIndex, ...]:
    from cady.geometry.plane3 import Plane3
    from cady.operations.triangulation import triangulate2

    points = tuple(vertices[index] for index in face)
    plane = Plane3.fit(points)
    projected = np.asarray([plane.coordinates(point) for point in points], dtype=np.float64)
    boundary = np.asarray(
        tuple((index, (index + 1) % len(face)) for index in range(len(face))),
        dtype=np.int64,
    )
    _nodes, local_faces = triangulate2(projected, boundary, tolerance=tolerance)
    if len(local_faces) == 0:
        return _fan_triangulated_face(face)
    return tuple(
        (int(face[int(a)]), int(face[int(b)]), int(face[int(c)])) for a, b, c in local_faces
    )


def _boundary_halfedges(faces: tuple[FaceIndex, ...]) -> list[tuple[int, int]]:
    occurrences: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for face in faces:
        indices = [int(index) for index in face]
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
    return np.array([vertices[index] for index in loop + [loop[0]]], dtype=np.float64)


def _polyline2_from_loop(vertices: tuple[Point2, ...], loop: list[int]) -> PointArray2:
    return np.array([vertices[index] for index in loop + [loop[0]]], dtype=np.float64)


def _point_array_from_points(points: object, *, tolerance: float) -> PointArray3:
    to_array = getattr(points, "to_array", None)
    if callable(to_array):
        array = np.asarray(to_array(tolerance=tolerance), dtype=np.float64)
    else:
        points_method = getattr(points, "points", None)
        if callable(points_method):
            array = np.asarray(points_method(), dtype=np.float64)
        else:
            array = np.asarray(points, dtype=np.float64)
    return array


def _triangle_area2(
    a: Point2,
    b: Point2,
    c: Point2,
) -> float:
    """Signed area of a 2D triangle (positive for CCW winding)."""
    return 0.5 * ((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]))


def _mesh2_area(
    vertices: tuple[Point2, ...],
    faces: tuple[TriangleIndex, ...],
) -> float:
    if not faces:
        return 0.0
    return float(
        fsum(
            abs(
                _triangle_area2(
                    vertices[a],
                    vertices[b],
                    vertices[c],
                )
            )
            for a, b, c in faces
        )
    )


def _triangle_area3(
    a: Point3,
    b: Point3,
    c: Point3,
) -> float:
    """Area of a 3D triangle via half the cross-product magnitude."""
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    return 0.5 * (cross[0] * cross[0] + cross[1] * cross[1] + cross[2] * cross[2]) ** 0.5


def _mesh3_area(
    vertices: tuple[Point3, ...],
    faces: tuple[TriangleIndex, ...],
) -> float:
    if not faces:
        return 0.0
    return float(fsum(_triangle_area3(vertices[a], vertices[b], vertices[c]) for a, b, c in faces))


def _mesh3_volume(
    vertices: tuple[Point3, ...],
    faces: tuple[TriangleIndex, ...],
) -> float:
    """Tetrahedron integration volume (absolute value).

    Constructs a tetrahedron [origin, v_a, v_b, v_c] for each face
    and sums signed volumes.  Returns the absolute enclosed volume.
    """
    if not faces or not vertices:
        return 0.0

    signed_sum = fsum(
        (
            vertices[a][0] * (vertices[b][1] * vertices[c][2] - vertices[b][2] * vertices[c][1])
            - vertices[a][1] * (vertices[b][0] * vertices[c][2] - vertices[b][2] * vertices[c][0])
            + vertices[a][2] * (vertices[b][0] * vertices[c][1] - vertices[b][1] * vertices[c][0])
        )
        / 6.0
        for a, b, c in faces
    )
    return abs(signed_sum)


def _validate_tolerance(tolerance: float) -> None:
    if float(tolerance) <= 0.0:
        raise ValueError("tolerance must be positive")


def _validate_target_faces(target_faces: int) -> int:
    try:
        count = operator_index(target_faces)
    except TypeError as exc:
        raise TypeError("target_faces must be an integer") from exc
    if count < 1:
        raise ValueError("target_faces must be positive")
    return count
