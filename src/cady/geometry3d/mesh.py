from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from cady.numeric.mesh3d import ArrayMesh3, ArrayPolyline3
from cady.numeric.transform import Transform3
from cady.vec import Vec3, promote3

if TYPE_CHECKING:
    from cady.geometry3d.wireframe import Wireframe3D
    from cady.view import Camera, DisplayStyle, Light
    from cady.view.open_view import Projection
    from cady.view.style import RenderMode

FaceIndex = tuple[int, int, int]
EdgeIndex = tuple[int, int]


@dataclass(frozen=True, slots=True)
class Mesh3D:
    vertices: tuple[Vec3, ...]
    faces: tuple[FaceIndex, ...]
    edges: tuple[EdgeIndex, ...] = ()

    def __post_init__(self) -> None:
        vertices = tuple(promote3(vertex) for vertex in self.vertices)
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
    def from_array(cls, mesh: ArrayMesh3) -> Mesh3D:
        vertices = tuple(Vec3(float(x), float(y), float(z)) for x, y, z in mesh.vertices)
        faces = tuple(tuple(int(index) for index in face) for face in mesh.faces)
        edges = tuple(tuple(int(index) for index in edge) for edge in mesh.edges)
        return cls(vertices, faces, edges)  # type: ignore[arg-type]

    @classmethod
    def merged(cls, meshes: Iterable[Mesh3D]) -> Mesh3D:
        vertices: list[Vec3] = []
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
    def triangles(self) -> tuple[tuple[Vec3, Vec3, Vec3], ...]:
        return tuple(
            (self.vertices[a], self.vertices[b], self.vertices[c]) for a, b, c in self.faces
        )

    @property
    def boundary(self) -> ArrayPolyline3:
        return self._array_without_display_edges().boundary

    @property
    def boundary_loops(self) -> tuple[ArrayPolyline3, ...]:
        return self._array_without_display_edges().boundary_loops

    def _array_without_display_edges(self) -> ArrayMesh3:
        vertices = np.array([vertex.tuple() for vertex in self.vertices], dtype=np.float64)
        faces = np.array(self.faces, dtype=np.int64)
        if len(vertices) == 0:
            vertices = np.empty((0, 3), dtype=np.float64)
        if len(faces) == 0:
            faces = np.empty((0, 3), dtype=np.int64)
        return ArrayMesh3(vertices, faces)

    def to_array(self, *, tolerance: float) -> ArrayMesh3:
        _validate_tolerance(tolerance)
        vertices = np.array([vertex.tuple() for vertex in self.vertices], dtype=np.float64)
        faces = np.array(self.faces, dtype=np.int64)
        edges = np.array(self.edges, dtype=np.int64)
        if len(vertices) == 0:
            vertices = np.empty((0, 3), dtype=np.float64)
        if len(faces) == 0:
            faces = np.empty((0, 3), dtype=np.int64)
        if len(edges) == 0:
            edges = np.empty((0, 2), dtype=np.int64)
        return ArrayMesh3(vertices, faces, edges)

    def transformed(self, transform: Transform3) -> Mesh3D:
        array = transform.apply_points([vertex.tuple() for vertex in self.vertices])
        vertices = tuple(Vec3(float(x), float(y), float(z)) for x, y, z in array)
        return Mesh3D(vertices, self.faces, self.edges)

    def mirror(self, plane_origin: object, plane_normal: object) -> Mesh3D:
        mirrored = self.transformed(Transform3.mirror(plane_origin, plane_normal))
        return Mesh3D(mirrored.vertices, _reverse_face_winding(self.faces), self.edges)

    def bounds(self) -> tuple[Vec3, Vec3]:
        if not self.vertices:
            raise ValueError("cannot calculate bounds for an empty mesh")
        return (
            Vec3(
                min(vertex.x for vertex in self.vertices),
                min(vertex.y for vertex in self.vertices),
                min(vertex.z for vertex in self.vertices),
            ),
            Vec3(
                max(vertex.x for vertex in self.vertices),
                max(vertex.y for vertex in self.vertices),
                max(vertex.z for vertex in self.vertices),
            ),
        )

    def close_planar(
        self,
        plane_origin: object,
        plane_normal: object,
        *,
        tolerance: float = 1e-3,
        snap_tolerance: float | None = None,
    ) -> Mesh3D:
        """Cap an open mesh at an explicit plane.

        Detects boundary edges on the plane and triangulates the resulting
        loops. Returns a new ``Mesh3D`` with the cap faces added.

        When *snap_tolerance* is ``None`` (default), only boundary vertices
        already on the plane (within *tolerance*) are used for the cap.

        When *snap_tolerance* is set, boundary vertices within that distance
        of the plane but not already on it are projected onto the plane.
        New projected vertices are appended and used for the cap while the
        originals stay connected, creating thin gaps that ``close_boundary``
        can fill.
        """
        from cady.ops.mesh_cut import close_planar_cap

        _validate_tolerance(tolerance)
        if snap_tolerance is not None and snap_tolerance <= 0.0:
            raise ValueError("snap_tolerance must be positive")
        array = self.to_array(tolerance=tolerance)
        capped = close_planar_cap(
            array,
            plane_origin,
            plane_normal,
            tolerance=tolerance,
            snap_tolerance=snap_tolerance,
        )
        return Mesh3D.from_array(capped)

    def close_to_plane(
        self,
        plane_origin: object,
        plane_normal: object,
        *,
        tolerance: float = 1e-3,
        max_distance: float,
    ) -> Mesh3D:
        """Project near-plane mesh edges to a plane and create wall faces.

        Uses explicit display edges when present, otherwise uses mesh boundary
        edges. Dangling degree-1 edge branches are pruned before wall faces are
        generated.
        """
        from cady.errors import GeometryError
        from cady.ops.mesh_cut import unit3, vector3

        _validate_tolerance(tolerance)
        if max_distance <= 0.0:
            raise ValueError("max_distance must be positive")

        origin_np = vector3(plane_origin, name="plane_origin")
        normal_np = unit3(plane_normal, name="plane_normal")
        source_edges = self.edges if self.edges else _boundary_edges_from_faces(self.faces)
        live_edges = _prune_dangling_edges(source_edges)

        near_edges: list[tuple[int, int, float, float]] = []
        for a, b in live_edges:
            va = np.array(self.vertices[a].tuple(), dtype=np.float64)
            vb = np.array(self.vertices[b].tuple(), dtype=np.float64)
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
                projected = _project_to_plane(self.vertices[a], dist_a, normal_np)
                projected_index[a] = len(all_vertices)
                all_vertices.append(projected)
            if b not in projected_index:
                projected = _project_to_plane(self.vertices[b], dist_b, normal_np)
                projected_index[b] = len(all_vertices)
                all_vertices.append(projected)

        wall_faces: list[FaceIndex] = []
        for a, b, _, _ in near_edges:
            pa = projected_index[a]
            pb = projected_index[b]
            wall_faces.append((a, b, pb))
            wall_faces.append((a, pb, pa))

        display_edges = live_edges if self.edges else ()
        return _compact_mesh(
            tuple(all_vertices),
            self.faces + tuple(wall_faces),
            display_edges,
        )

    def close_boundary(
        self,
        *,
        tolerance: float = 1e-3,
    ) -> Mesh3D:
        """Close all planar boundary holes in the mesh.

        Detects boundary edges (edges appearing in exactly one face), stitches
        them into loops, fits a best-fit plane to each loop, and triangulates
        planar loops.

        Raises ``ValueError`` if any boundary loop is non-planar.
        """
        from cady.ops.mesh_cut import close_boundary as _close_boundary_ops

        _validate_tolerance(tolerance)
        array = self.to_array(tolerance=tolerance)
        closed = _close_boundary_ops(array, tolerance=tolerance)
        return Mesh3D.from_array(closed)

    def close_holes(
        self,
        *,
        tolerance: float = 1e-3,
        max_hole_edges: int | None = None,
    ) -> Mesh3D:
        """Fill non-planar holes via advancing-front triangulation.

        Not yet implemented.
        """
        raise NotImplementedError(
            "close_holes is not implemented; use close_boundary for planar hole filling"
        )

    def to_wireframe(self) -> Wireframe3D:
        """Extract all edges from faces as a Wireframe3D."""
        from cady.geometry3d.wireframe import Wireframe3D as WF

        edge_set: set[tuple[int, int]] = set()
        for a, b, c in self.faces:
            for start, end in ((a, b), (b, c), (c, a)):
                edge_set.add((min(start, end), max(start, end)))
        return WF(self.vertices, tuple(sorted(edge_set)))

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


def _boundary_edges_from_faces(faces: tuple[FaceIndex, ...]) -> tuple[EdgeIndex, ...]:
    counts: dict[EdgeIndex, int] = {}
    for a, b, c in faces:
        for start, end in ((a, b), (b, c), (c, a)):
            edge = (min(start, end), max(start, end))
            counts[edge] = counts.get(edge, 0) + 1
    return tuple(edge for edge, count in counts.items() if count == 1)


def _prune_dangling_edges(edges: tuple[EdgeIndex, ...]) -> tuple[EdgeIndex, ...]:
    live_edges = list(edges)
    live_vertices = {index for edge in live_edges for index in edge}

    while live_edges:
        degrees = {index: 0 for index in live_vertices}
        for a, b in live_edges:
            degrees[a] = degrees.get(a, 0) + 1
            degrees[b] = degrees.get(b, 0) + 1

        dangling = {index for index, degree in degrees.items() if degree == 1}
        if not dangling:
            break

        live_vertices.difference_update(dangling)
        live_edges = [
            (a, b)
            for a, b in live_edges
            if a in live_vertices and b in live_vertices
        ]

    return tuple(live_edges)


def _project_to_plane(
    vertex: Vec3,
    distance: float,
    normal: np.ndarray,
) -> Vec3:
    x, y, z = vertex.tuple()
    return Vec3(
        x - distance * float(normal[0]),
        y - distance * float(normal[1]),
        z - distance * float(normal[2]),
    )


def _compact_mesh(
    vertices: tuple[Vec3, ...],
    faces: tuple[FaceIndex, ...],
    edges: tuple[EdgeIndex, ...],
) -> Mesh3D:
    used_vertices = {index for face in faces for index in face}
    used_vertices.update(index for edge in edges for index in edge)
    if not used_vertices:
        return Mesh3D((), (), ())

    ordered_vertices = tuple(sorted(used_vertices))
    remap = {old: new for new, old in enumerate(ordered_vertices)}
    compact_vertices = tuple(vertices[index] for index in ordered_vertices)
    compact_faces = tuple((remap[a], remap[b], remap[c]) for a, b, c in faces)
    compact_edges = tuple((remap[a], remap[b]) for a, b in edges)
    return Mesh3D(compact_vertices, compact_faces, compact_edges)


def _validate_tolerance(tolerance: float) -> None:
    if float(tolerance) <= 0.0:
        raise ValueError("tolerance must be positive")
