"""Semantic 2D triangle meshes and 3D polygon meshes."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from operator import index as operator_index
from typing import TYPE_CHECKING, TypeAlias

import numpy as np
from numpy.typing import NDArray

from cady.geometry.point import Point2 as Point2Value
from cady.geometry.point import Point3 as Point3Value
from cady.geometry.point import point2, point3
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
        from cady.operations.mesh.statistics import mesh2_area

        return mesh2_area(self.vertices, self.faces)

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
        from cady.operations.mesh.boundaries import boundary_polylines

        if not self.faces:
            from cady.errors import GeometryError

            raise GeometryError("mesh has no faces; boundary is undefined")
        return boundary_polylines(self.vertices, self.faces)

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
        from cady.operations.mesh.faces import triangulated_faces

        _validate_tolerance(tolerance)
        return triangulated_faces(self.vertices, self.faces, tolerance=tolerance)

    def merge_coplanar_faces(self, *, tolerance: float = 1e-9) -> Mesh3:
        """Merge connected coplanar face groups into larger polygon faces."""
        from cady.operations.mesh.faces import merge_coplanar_faces_data

        _validate_tolerance(tolerance)
        vertices, faces, edges = merge_coplanar_faces_data(
            self.vertices,
            self.faces,
            tolerance=tolerance,
        )
        return Mesh3(vertices, faces, edges)

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
        from cady.operations.mesh.faces import triangulate_mesh_data

        _validate_tolerance(tolerance)
        vertices, faces, edges = triangulate_mesh_data(
            self.vertices,
            self.faces,
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
        from cady.operations.mesh.cleanup import snap_close_mesh_data

        _validate_tolerance(tolerance)
        vertices, faces, edges = snap_close_mesh_data(
            self.vertices,
            self.faces,
            self.edges,
            tolerance=tolerance,
        )
        return Mesh3(vertices, faces, edges)

    @property
    def area(self) -> float:
        """Sum of face surface areas after boundary triangulation."""
        from cady.operations.mesh.statistics import mesh3_area

        return mesh3_area(self.vertices, self.triangulated_faces())

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
        from cady.operations.mesh.statistics import mesh3_volume

        return mesh3_volume(self.vertices, self.triangulated_faces())

    @property
    def closed(self) -> bool:
        """Return True when every face edge is shared by exactly two faces."""
        from cady.operations.mesh.boundaries import faces_are_closed

        return faces_are_closed(self.faces)

    @property
    def boundary(self) -> tuple[Point3, Point3]:
        return self.bounds()

    @property
    def boundary_loops(self) -> tuple[PointArray3, ...]:
        from cady.operations.mesh.boundaries import boundary_polylines

        if not self.faces:
            from cady.errors import GeometryError

            raise GeometryError("mesh has no faces; boundary is undefined")
        return boundary_polylines(self.vertices, self.faces)

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
        from cady.operations.mesh.faces import reverse_face_winding

        mirrored = self.transformed(Transform3(self.vertices).mirror(plane_origin, plane_normal))
        return Mesh3(mirrored.vertices, reverse_face_winding(self.faces), self.edges)

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
        from cady.operations.mesh.boundaries import close_planar_boundaries_data

        _validate_tolerance(tolerance)
        if not self.faces:
            return self
        faces, edges = close_planar_boundaries_data(
            self.vertices,
            self.faces,
            tolerance=tolerance,
        )
        if faces == self.faces:
            return self
        return Mesh3(self.vertices, faces, edges)

    def to_wireframe(self) -> Wireframe3:
        """Extract all edges from faces as a Wireframe3."""
        from cady.geometry.wireframe import Wireframe3 as WF
        from cady.operations.mesh.faces import face_edges

        edge_set = set(face_edges(self.faces))
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
