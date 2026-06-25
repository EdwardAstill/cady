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


def _validate_tolerance(tolerance: float) -> None:
    if float(tolerance) <= 0.0:
        raise ValueError("tolerance must be positive")
