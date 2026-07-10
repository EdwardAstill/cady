"""Semantic 2D triangle meshes and 3D polygon meshes."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import floor, fsum, sqrt
from operator import index as operator_index
from typing import TYPE_CHECKING, TypeAlias

import numpy as np
from numpy.typing import NDArray

from cady.errors import GeometryError
from cady.geometry._coordinates import point2, point3
from cady.geometry.point import Point2 as Point2Value
from cady.geometry.point import Point3 as Point3Value
from cady.operations.transforms import Transform2, Transform3

Point2: TypeAlias = Sequence[float]
Point3: TypeAlias = Sequence[float]
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
        vertices = tuple(point2(vertex, name="vertex") for vertex in self.vertices)
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

    def face_areas(self) -> np.ndarray:
        """Return one area per triangle face."""
        from cady.operations.mesh.statistics import face_areas

        return face_areas(self.triangles)

    def radius_ratios(self) -> np.ndarray:
        """Return one radius ratio per triangle face."""
        from cady.operations.mesh.statistics import radius_ratios

        return radius_ratios(self.triangles)

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
            Point2Value(
                min(vertex[0] for vertex in self.vertices),
                min(vertex[1] for vertex in self.vertices),
            ),
            Point2Value(
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
        vertices = tuple(point3(vertex, name="vertex") for vertex in self.vertices)
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
        from cady.operations.surface_reconstruction import advancing_front_surface

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

    def merge_coplanar_faces(self, *, tolerance: float = 1e-9) -> Mesh3:
        """Merge connected coplanar face groups into larger polygon faces."""
        _validate_tolerance(tolerance)
        face_groups = _coplanar_face_groups(self.vertices, self.faces, tolerance=tolerance)
        faces: list[FaceIndex] = []
        for group in face_groups:
            if len(group.indices) > 1 and group.boundary is not None:
                faces.append(group.boundary)
            else:
                faces.extend(self.faces[index] for index in group.indices)
        if not faces:
            return Mesh3(self.vertices, (), ())

        simplified_faces = tuple(
            _simplified_face_boundary(self.vertices, face, tolerance=tolerance) for face in faces
        )
        vertices, remapped_faces, edges = _compact_polygon_mesh(
            self.vertices,
            simplified_faces,
            _face_edges(simplified_faces),
        )
        return Mesh3(vertices, remapped_faces, edges)

    def triangulate(
        self,
        *,
        tolerance: float = 1e-9,
        algorithm: str = "ear_delaunay_refinement",
        target_edge_length: float | None = None,
        max_edge_length: float | None = None,
        max_area: float | None = None,
        min_angle_degrees: float | None = None,
    ) -> Mesh3:
        """Merge connected coplanar faces, then triangulate the merged polygon faces."""
        _validate_tolerance(tolerance)
        merged = self.merge_coplanar_faces(tolerance=tolerance)
        face_groups = tuple(_FaceGroup((index,), face) for index, face in enumerate(merged.faces))
        vertices, faces, edges = _triangulated_mesh(
            merged.vertices,
            merged.faces,
            face_groups,
            tolerance=tolerance,
            algorithm=algorithm,
            target_edge_length=target_edge_length,
            max_edge_length=max_edge_length,
            max_area=max_area,
            min_angle_degrees=min_angle_degrees,
        )
        return Mesh3(vertices, faces, edges)

    def decimate(self, target_faces: int, *, tolerance: float = 1e-9) -> Mesh3:
        """Return a simplified triangle mesh with at most ``target_faces`` faces."""
        from cady.operations.mesh.topology import decimate_mesh_data

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

    def remesh(
        self,
        *,
        target_edge_length: float | None = None,
        iterations: int = 10,
        feature_angle_degrees: float | None = 50.0,
        protect_boundary: bool = True,
        long_factor: float = 4.0 / 3.0,
        short_factor: float = 4.0 / 5.0,
        relaxation: float = 0.5,
        project: bool = True,
        tolerance: float = 1e-9,
    ) -> Mesh3:
        """Return a feature-preserving isotropic triangle remesh."""
        from cady.operations.mesh.topology import remesh_mesh_data

        _validate_tolerance(tolerance)
        remeshed_vertices, remeshed_faces, remeshed_edges = remesh_mesh_data(
            self.vertices,
            self.triangulated_faces(tolerance=tolerance),
            self.edges,
            target_edge_length=target_edge_length,
            iterations=iterations,
            feature_angle_degrees=feature_angle_degrees,
            protect_boundary=protect_boundary,
            long_factor=long_factor,
            short_factor=short_factor,
            relaxation=relaxation,
            project=project,
            tolerance=tolerance,
        )
        return _mesh_from_arrays(remeshed_vertices, remeshed_faces, remeshed_edges)

    def snap_close_nodes(self, *, tolerance: float) -> Mesh3:
        """Return a mesh with vertices closer than ``tolerance`` merged."""
        _validate_tolerance(tolerance)
        vertices, remap = _snap_close_vertices(self.vertices, tolerance=tolerance)
        faces = _snap_remap_faces(self.faces, remap)
        edges = _snap_remap_edges(self.edges, remap)
        return Mesh3(vertices, faces, edges)

    @property
    def area(self) -> float:
        """Sum of face surface areas after boundary triangulation."""
        return float(_mesh3_area(self.vertices, self.triangulated_faces()))

    def face_areas(self) -> np.ndarray:
        """Return one area per triangulated face."""
        from cady.operations.mesh.statistics import face_areas

        return face_areas(self.triangles)

    def radius_ratios(self) -> np.ndarray:
        """Return one radius ratio per triangulated face."""
        from cady.operations.mesh.statistics import radius_ratios

        return radius_ratios(self.triangles)

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
    def closed(self) -> bool:
        """Return True when every face edge is shared by exactly two faces."""
        return _faces_are_closed(self.faces)

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
        originals stay connected, creating thin gaps that ``close_mesh``
        can fill.
        """
        from cady.operations.mesh.clipping import close_planar_cap

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
        from cady.operations.mesh.clipping import close_to_plane as _close_to_plane_ops

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

    def close_mesh(
        self,
        *,
        tolerance: float = 1e-3,
    ) -> Mesh3:
        """Close planar boundary loops with polygon faces.

        Detects boundary edges (edges appearing in exactly one face), stitches
        them into loops, validates that each loop is planar, and adds one
        polygon face per loop.

        Raises ``ValueError`` if any boundary loop is non-planar.
        """
        _validate_tolerance(tolerance)
        if not self.faces:
            return self

        loops = _mesh_boundary_loops(self.faces)
        if not loops:
            return self

        cap_faces: list[FaceIndex] = []
        for loop in loops:
            face = tuple(reversed(loop))
            _validate_planar_boundary_loop(self.vertices, face, tolerance=tolerance)
            cap_faces.append(face)

        faces = (*self.faces, *cap_faces)
        return Mesh3(self.vertices, faces, _face_edges(faces))

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


def _faces_are_closed(faces: tuple[FaceIndex, ...]) -> bool:
    if not faces:
        return False

    counts: dict[EdgeIndex, int] = {}
    for face in faces:
        indices = tuple(int(index) for index in face)
        for start, end in zip(indices, indices[1:] + indices[:1], strict=True):
            edge = (min(start, end), max(start, end))
            counts[edge] = counts.get(edge, 0) + 1

    return bool(counts) and all(count == 2 for count in counts.values())


def _snap_close_vertices(
    points: tuple[Point3, ...],
    *,
    tolerance: float,
) -> tuple[tuple[Point3, ...], tuple[int, ...]]:
    cells: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    vertices: list[Point3] = []
    remap: list[int] = []

    for point in points:
        vertex = (float(point[0]), float(point[1]), float(point[2]))
        match = _nearest_snap_vertex(vertex, vertices, cells, tolerance=tolerance)
        if match is None:
            match = len(vertices)
            vertices.append(vertex)
            cells[_snap_cell(vertex, tolerance)].append(match)
        remap.append(match)

    return tuple(vertices), tuple(remap)


def _nearest_snap_vertex(
    point: Point3,
    vertices: list[Point3],
    cells: dict[tuple[int, int, int], list[int]],
    *,
    tolerance: float,
) -> int | None:
    best_index: int | None = None
    best_distance = tolerance
    for cell in _snap_neighbour_cells(_snap_cell(point, tolerance)):
        for index in cells.get(cell, ()):
            distance = _length3(_sub3(point, vertices[index]))
            if distance <= best_distance:
                best_index = index
                best_distance = distance
    return best_index


def _snap_cell(point: Point3, tolerance: float) -> tuple[int, int, int]:
    return (
        floor(point[0] / tolerance),
        floor(point[1] / tolerance),
        floor(point[2] / tolerance),
    )


def _snap_neighbour_cells(cell: tuple[int, int, int]) -> Iterable[tuple[int, int, int]]:
    x, y, z = cell
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                yield (x + dx, y + dy, z + dz)


def _snap_remap_faces(
    faces: tuple[FaceIndex, ...],
    remap: tuple[int, ...],
) -> tuple[FaceIndex, ...]:
    cleaned_faces: list[FaceIndex] = []
    seen_faces: set[tuple[int, ...]] = set()

    for face in faces:
        mapped: list[int] = []
        for index in face:
            new_index = remap[index]
            if not mapped or mapped[-1] != new_index:
                mapped.append(new_index)
        if len(mapped) > 1 and mapped[0] == mapped[-1]:
            mapped.pop()
        if len(set(mapped)) < 3:
            continue

        clean = tuple(mapped)
        key = tuple(sorted(clean))
        if key in seen_faces:
            continue
        seen_faces.add(key)
        cleaned_faces.append(clean)

    return tuple(cleaned_faces)


def _snap_remap_edges(
    edges: tuple[EdgeIndex, ...],
    remap: tuple[int, ...],
) -> tuple[EdgeIndex, ...]:
    cleaned_edges: set[EdgeIndex] = set()
    for start, end in edges:
        remapped_start = remap[start]
        remapped_end = remap[end]
        if remapped_start != remapped_end:
            cleaned_edges.add(_edge_key(remapped_start, remapped_end))
    return tuple(sorted(cleaned_edges))


def _simplified_face_boundary(
    vertices: tuple[Point3, ...],
    face: FaceIndex,
    *,
    tolerance: float,
) -> FaceIndex:
    simplified: list[int] = list(face)
    while len(simplified) > 3:
        next_face: list[int] = [
            current
            for index, current in enumerate(simplified)
            if not _is_straight_boundary_vertex(
                vertices,
                simplified[index - 1],
                current,
                simplified[(index + 1) % len(simplified)],
                tolerance=tolerance,
            )
        ]
        if len(next_face) < 3 or len(next_face) == len(simplified):
            break
        simplified = next_face
    return tuple(simplified)


def _is_straight_boundary_vertex(
    vertices: tuple[Point3, ...],
    previous: int,
    current: int,
    following: int,
    *,
    tolerance: float,
) -> bool:
    before = _sub3(vertices[current], vertices[previous])
    after = _sub3(vertices[following], vertices[current])
    before_length = _length3(before)
    after_length = _length3(after)
    if before_length <= tolerance or after_length <= tolerance:
        return True
    if _dot3(before, after) <= 0.0:
        return False
    return _length3(_cross3(before, after)) <= tolerance * max(before_length, after_length)


def _compact_polygon_mesh(
    vertices: tuple[Point3, ...],
    faces: tuple[FaceIndex, ...],
    edges: tuple[EdgeIndex, ...],
) -> tuple[tuple[Point3, ...], tuple[FaceIndex, ...], tuple[EdgeIndex, ...]]:
    used = sorted(
        {index for face in faces for index in face}
        | {index for edge in edges for index in edge}
    )
    if len(used) == len(vertices) and all(old == new for new, old in enumerate(used)):
        return vertices, faces, edges

    remap = {old: new for new, old in enumerate(used)}
    remapped_faces = tuple(tuple(remap[index] for index in face) for face in faces)
    remapped_edges = tuple(
        sorted(
            _edge_key(remap[start], remap[end])
            for start, end in edges
            if start in remap and end in remap
        )
    )
    return tuple(vertices[index] for index in used), remapped_faces, remapped_edges


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


def _triangulated_mesh(
    vertices: tuple[Point3, ...],
    faces: tuple[FaceIndex, ...],
    face_groups: tuple[_FaceGroup, ...],
    *,
    tolerance: float,
    algorithm: str,
    target_edge_length: float | None,
    max_edge_length: float | None,
    max_area: float | None,
    min_angle_degrees: float | None,
) -> tuple[tuple[Point3, ...], tuple[TriangleIndex, ...], tuple[EdgeIndex, ...]]:
    output_vertices = list(vertices)
    output_faces: list[TriangleIndex] = []
    output_edges: set[EdgeIndex] = set()

    for group in face_groups:
        if len(group.indices) > 1 and group.boundary is not None:
            _extend_triangulated_face_group(
                vertices,
                faces,
                group,
                output_vertices,
                output_faces,
                output_edges,
                tolerance=tolerance,
                algorithm=algorithm,
                target_edge_length=target_edge_length,
                max_edge_length=max_edge_length,
                max_area=max_area,
                min_angle_degrees=min_angle_degrees,
            )
            continue

        for face_index in group.indices:
            _extend_triangulated_face(
                vertices,
                faces[face_index],
                output_vertices,
                output_faces,
                output_edges,
                tolerance=tolerance,
                algorithm=algorithm,
                target_edge_length=target_edge_length,
                max_edge_length=max_edge_length,
                max_area=max_area,
                min_angle_degrees=min_angle_degrees,
            )

    return tuple(output_vertices), tuple(output_faces), tuple(sorted(output_edges))


def _extend_triangulated_face(
    vertices: tuple[Point3, ...],
    face: FaceIndex,
    output_vertices: list[Point3],
    output_faces: list[TriangleIndex],
    output_edges: set[EdgeIndex],
    *,
    tolerance: float,
    algorithm: str,
    target_edge_length: float | None,
    max_edge_length: float | None,
    max_area: float | None,
    min_angle_degrees: float | None,
) -> None:
    from cady.geometry.plane3 import Plane3
    from cady.operations.triangulate import triangulate

    points = tuple(vertices[index] for index in face)
    plane = Plane3.fit(points)
    deviation = plane.max_deviation(points)
    if deviation > tolerance:
        raise ValueError(
            f"3D face is non-planar (max deviation {deviation:.3e} > "
            f"tolerance {tolerance:.3e})"
        )
    nodes = np.asarray([plane.coordinates(point) for point in points], dtype=np.float64)
    boundary = np.asarray(
        tuple((index, (index + 1) % len(face)) for index in range(len(face))),
        dtype=np.int64,
    )
    nodes_out, edges_out, local_faces = triangulate(
        nodes,
        boundary,
        algorithm=algorithm,
        tolerance=tolerance,
        **_triangulation_constraints(
            target_edge_length=target_edge_length,
            max_edge_length=max_edge_length,
            max_area=max_area,
            min_angle_degrees=min_angle_degrees,
        ),
    )
    index_map = list(face)
    for index in range(len(face), len(nodes_out)):
        index_map.append(len(output_vertices))
        x, y = nodes_out[index]
        output_vertices.append(plane.point(float(x), float(y)))

    for a, b, c in local_faces:
        output_faces.append((index_map[int(a)], index_map[int(b)], index_map[int(c)]))
    for start, end in edges_out:
        output_edges.add(_edge_key(index_map[int(start)], index_map[int(end)]))


def _extend_triangulated_face_group(
    vertices: tuple[Point3, ...],
    faces: tuple[FaceIndex, ...],
    group: _FaceGroup,
    output_vertices: list[Point3],
    output_faces: list[TriangleIndex],
    output_edges: set[EdgeIndex],
    *,
    tolerance: float,
    algorithm: str,
    target_edge_length: float | None,
    max_edge_length: float | None,
    max_area: float | None,
    min_angle_degrees: float | None,
) -> None:
    boundary = group.boundary
    if boundary is None:
        return
    _extend_triangulated_face(
        vertices,
        boundary,
        output_vertices,
        output_faces,
        output_edges,
        tolerance=tolerance,
        algorithm=algorithm,
        target_edge_length=target_edge_length,
        max_edge_length=max_edge_length,
        max_area=max_area,
        min_angle_degrees=min_angle_degrees,
    )


def _triangulation_constraints(
    *,
    target_edge_length: float | None,
    max_edge_length: float | None,
    max_area: float | None,
    min_angle_degrees: float | None,
) -> dict[str, float]:
    constraints: dict[str, float] = {}
    if target_edge_length is not None:
        constraints["target_edge_length"] = target_edge_length
    if max_edge_length is not None:
        constraints["max_edge_length"] = max_edge_length
    if max_area is not None:
        constraints["max_area"] = max_area
    if min_angle_degrees is not None:
        constraints["min_angle_degrees"] = min_angle_degrees
    return constraints


@dataclass(frozen=True, slots=True)
class _FaceGroup:
    indices: tuple[int, ...]
    boundary: FaceIndex | None


def _coplanar_face_groups(
    vertices: tuple[Point3, ...],
    faces: tuple[FaceIndex, ...],
    *,
    tolerance: float,
) -> tuple[_FaceGroup, ...]:
    face_planes = tuple(_face_plane(vertices, face, tolerance=tolerance) for face in faces)
    neighbours = _face_neighbours(faces)
    groups: list[_FaceGroup] = []
    visited: set[int] = set()

    for face_index in range(len(faces)):
        if face_index in visited:
            continue

        group = _connected_coplanar_group(
            face_index,
            neighbours,
            face_planes,
            vertices,
            faces,
            tolerance=tolerance,
        )
        visited.update(group)
        groups.append(_face_group(faces, group))

    return tuple(groups)


def _face_group(faces: tuple[FaceIndex, ...], group: tuple[int, ...]) -> _FaceGroup:
    if len(group) == 1:
        return _FaceGroup(group, faces[group[0]])
    return _FaceGroup(group, _simple_boundary_loop(faces[index] for index in group))


def _connected_coplanar_group(
    start: int,
    neighbours: tuple[tuple[int, ...], ...],
    face_planes: tuple[_FacePlane | None, ...],
    vertices: tuple[Point3, ...],
    faces: tuple[FaceIndex, ...],
    *,
    tolerance: float,
) -> tuple[int, ...]:
    start_plane = face_planes[start]
    if start_plane is None:
        return (start,)

    group: list[int] = []
    pending: deque[int] = deque((start,))
    seen = {start}
    while pending:
        face_index = pending.popleft()
        group.append(face_index)
        for neighbour in neighbours[face_index]:
            if neighbour in seen:
                continue
            plane = face_planes[neighbour]
            if plane is None:
                continue
            parallel = _parallel_normals(start_plane.normal, plane.normal, tolerance=tolerance)
            same_plane = _same_plane(start_plane, vertices, faces[neighbour], tolerance=tolerance)
            if parallel and same_plane:
                seen.add(neighbour)
                pending.append(neighbour)

    return tuple(sorted(group))


def _simple_boundary_loop(group_faces: Iterable[FaceIndex]) -> FaceIndex | None:
    edge_counts: defaultdict[EdgeIndex, int] = defaultdict(int)
    directed_edges: list[EdgeIndex] = []
    for face in group_faces:
        for start, end in _directed_face_edges(face):
            edge_counts[_edge_key(start, end)] += 1
            directed_edges.append((start, end))

    boundary_edges = [
        (start, end) for start, end in directed_edges if edge_counts[_edge_key(start, end)] == 1
    ]
    if len(boundary_edges) < 3:
        return None

    next_by_start: dict[int, int] = {}
    for start, end in boundary_edges:
        if start in next_by_start:
            return _undirected_boundary_loop(boundary_edges)
        next_by_start[start] = end

    start = min(next_by_start)
    loop = [start]
    current = start
    while True:
        if current not in next_by_start:
            return _undirected_boundary_loop(boundary_edges)
        current = next_by_start[current]
        if current == start:
            break
        if current in loop:
            return _undirected_boundary_loop(boundary_edges)
        loop.append(current)

    if len(loop) != len(boundary_edges):
        return _undirected_boundary_loop(boundary_edges)
    return tuple(loop)


def _undirected_boundary_loop(boundary_edges: Iterable[EdgeIndex]) -> FaceIndex | None:
    neighbours: defaultdict[int, list[int]] = defaultdict(list)
    edge_count = 0
    for start, end in boundary_edges:
        neighbours[start].append(end)
        neighbours[end].append(start)
        edge_count += 1

    if any(len(values) != 2 for values in neighbours.values()):
        return None

    start = min(neighbours)
    previous = None
    current = start
    loop: list[int] = []
    while True:
        loop.append(current)
        options = neighbours[current]
        next_value = options[0] if options[0] != previous else options[1]
        previous, current = current, next_value
        if current == start:
            break
        if current in loop:
            return None

    if len(loop) != edge_count:
        return None
    return tuple(loop)


def _face_neighbours(faces: tuple[FaceIndex, ...]) -> tuple[tuple[int, ...], ...]:
    faces_by_edge: defaultdict[EdgeIndex, list[int]] = defaultdict(list)
    for face_index, face in enumerate(faces):
        for edge in _directed_face_edges(face):
            faces_by_edge[_edge_key(*edge)].append(face_index)

    neighbours: list[set[int]] = [set() for _ in faces]
    for face_indices in faces_by_edge.values():
        for face_index in face_indices:
            neighbours[face_index].update(index for index in face_indices if index != face_index)
    return tuple(tuple(sorted(values)) for values in neighbours)


@dataclass(frozen=True, slots=True)
class _FacePlane:
    point: Point3
    normal: Point3


def _face_plane(
    vertices: tuple[Point3, ...],
    face: FaceIndex,
    *,
    tolerance: float,
) -> _FacePlane | None:
    points = tuple(vertices[index] for index in face)
    origin = points[0]
    for index in range(1, len(points) - 1):
        normal = _cross3(_sub3(points[index], origin), _sub3(points[index + 1], origin))
        length = _length3(normal)
        if length > tolerance:
            return _FacePlane(origin, _canonical_normal(_scale3(normal, 1.0 / length), tolerance))
    return None


def _same_plane(
    plane: _FacePlane,
    vertices: tuple[Point3, ...],
    face: FaceIndex,
    *,
    tolerance: float,
) -> bool:
    return all(
        abs(_dot3(_sub3(vertices[index], plane.point), plane.normal)) <= tolerance
        for index in face
    )


def _parallel_normals(left: Point3, right: Point3, *, tolerance: float) -> bool:
    return 1.0 - abs(_dot3(left, right)) <= tolerance


def _directed_face_edges(face: FaceIndex) -> tuple[EdgeIndex, ...]:
    return tuple(zip(face, face[1:] + face[:1], strict=True))


def _edge_key(start: int, end: int) -> EdgeIndex:
    return (min(start, end), max(start, end))


def _canonical_normal(normal: Point3, tolerance: float) -> Point3:
    for component in normal:
        if abs(component) <= tolerance:
            continue
        if component < 0.0:
            return (-normal[0], -normal[1], -normal[2])
        break
    return normal


def _sub3(left: Point3, right: Point3) -> Point3:
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def _scale3(vector: Point3, value: float) -> Point3:
    return (vector[0] * value, vector[1] * value, vector[2] * value)


def _dot3(left: Point3, right: Point3) -> float:
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]


def _cross3(left: Point3, right: Point3) -> Point3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _length3(vector: Point3) -> float:
    return sqrt(_dot3(vector, vector))


def _triangulated_polygon_face(
    vertices: tuple[Point3, ...],
    face: FaceIndex,
    *,
    tolerance: float,
) -> tuple[TriangleIndex, ...]:
    from cady.geometry.plane3 import Plane3
    from cady.operations.triangulate import triangulate

    points = tuple(vertices[index] for index in face)
    plane = Plane3.fit(points)
    projected = np.asarray([plane.coordinates(point) for point in points], dtype=np.float64)
    boundary = np.asarray(
        tuple((index, (index + 1) % len(face)) for index in range(len(face))),
        dtype=np.int64,
    )
    _nodes, _edges, local_faces = triangulate(projected, boundary, tolerance=tolerance)
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


def _mesh_boundary_loops(faces: tuple[FaceIndex, ...]) -> list[list[int]]:
    halfedges = _boundary_halfedges(faces)
    if not halfedges:
        return []

    neighbours: defaultdict[int, list[int]] = defaultdict(list)
    unused_edges: set[EdgeIndex] = set()
    for start, end in halfedges:
        edge = _edge_key(start, end)
        unused_edges.add(edge)
        neighbours[start].append(end)
        neighbours[end].append(start)

    if any(len(values) != 2 for values in neighbours.values()):
        raise GeometryError("mesh boundary is not a closed polyline")

    loops: list[list[int]] = []
    while unused_edges:
        start = min(index for edge in unused_edges for index in edge)
        loop: list[int] = []
        previous: int | None = None
        current = start

        while True:
            loop.append(current)
            candidates = [
                candidate
                for candidate in sorted(neighbours[current])
                if candidate != previous and _edge_key(current, candidate) in unused_edges
            ]
            if not candidates:
                raise GeometryError("mesh boundary is not a closed polyline")
            following = candidates[0]
            unused_edges.remove(_edge_key(current, following))
            previous, current = current, following
            if current == start:
                break
            if current in loop:
                raise GeometryError("mesh boundary is not a closed polyline")

        if len(loop) < 3:
            raise GeometryError("mesh boundary is not a closed polyline")
        loops.append(loop)

    return sorted(loops, key=lambda loop: (-len(loop), loop))


def _validate_planar_boundary_loop(
    vertices: tuple[Point3, ...],
    face: FaceIndex,
    *,
    tolerance: float,
) -> None:
    from cady.geometry.plane3 import Plane3

    points = tuple(vertices[index] for index in face)
    plane = Plane3.fit(points)
    deviation = plane.max_deviation(points)
    if deviation > tolerance:
        raise ValueError(
            f"Boundary loop is non-planar (max deviation {deviation:.3e} > "
            f"tolerance {tolerance:.3e})"
        )


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
