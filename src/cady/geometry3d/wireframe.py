from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from cady.geometry3d.mesh import EdgeIndex, Mesh3D
from cady.numeric.mesh3d import ArrayMesh3
from cady.numeric.transform import Transform3
from cady.vec import Vec3, promote3

if TYPE_CHECKING:
    from cady.view import Camera, DisplayStyle, Light
    from cady.view.open_view import Projection
    from cady.view.style import RenderMode


@dataclass(frozen=True, slots=True)
class Wireframe3D:
    """Edge-only 3D geometry — vertices connected by edges, no faces."""

    vertices: tuple[Vec3, ...]
    edges: tuple[EdgeIndex, ...]

    def __post_init__(self) -> None:
        vertices = tuple(promote3(vertex) for vertex in self.vertices)
        edges = tuple(_edge(edge) for edge in self.edges)
        for edge in edges:
            if min(edge) < 0:
                raise ValueError("edges must not contain negative indices")
            if vertices and max(edge) >= len(vertices):
                raise ValueError("edges reference vertices outside the vertex array")
            if not vertices:
                raise ValueError("empty wireframes cannot contain edges")
        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "edges", edges)

    def transformed(self, transform: Transform3) -> Wireframe3D:
        array = transform.apply_points([vertex.tuple() for vertex in self.vertices])
        vertices = tuple(Vec3(float(x), float(y), float(z)) for x, y, z in array)
        return Wireframe3D(vertices, self.edges)

    def mirror(self, plane_origin: object, plane_normal: object) -> Wireframe3D:
        return self.transformed(Transform3.mirror(plane_origin, plane_normal))

    def bounds(self) -> tuple[Vec3, Vec3]:
        if not self.vertices:
            raise ValueError("cannot calculate bounds for an empty wireframe")
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

    def to_array(self, *, tolerance: float) -> ArrayMesh3:
        _validate_tolerance(tolerance)
        vertices = np.array([vertex.tuple() for vertex in self.vertices], dtype=np.float64)
        edges = np.array(self.edges, dtype=np.int64)
        if len(vertices) == 0:
            vertices = np.empty((0, 3), dtype=np.float64)
        if len(edges) == 0:
            edges = np.empty((0, 2), dtype=np.int64)
        return ArrayMesh3(vertices, np.empty((0, 3), dtype=np.int64), edges)

    # -- Edge-based closing → Mesh3D --------------------------------------

    def close_planar(
        self,
        plane_origin: object,
        plane_normal: object,
        *,
        tolerance: float = 1e-3,
    ) -> Mesh3D:
        """Cap open edges on a plane, returning a triangulated Mesh3D.

        Finds edges whose both endpoints lie on the plane (within
        ``tolerance``), stitches them into loops, and triangulates each loop.
        Returns a ``Mesh3D`` with the cap faces and the original wireframe
        edges preserved as display overlay.
        """
        from cady.errors import GeometryError
        from cady.ops.mesh_cut import (
            project_loop,
            stitch_segments,
            triangulate_loop,
            unit3,
            vector3,
        )

        _validate_tolerance(tolerance)
        origin_np = vector3(plane_origin, name="plane_origin")
        normal_np = unit3(plane_normal, name="plane_normal")

        vertices_list = [np.array((v.x, v.y, v.z), dtype=np.float64) for v in self.vertices]

        # Filter edges where both endpoints are on the plane
        plane_edges: list[tuple[int, int]] = []
        for a, b in self.edges:
            dist_a = float(np.dot(vertices_list[a] - origin_np, normal_np))
            dist_b = float(np.dot(vertices_list[b] - origin_np, normal_np))
            if abs(dist_a) <= tolerance and abs(dist_b) <= tolerance:
                plane_edges.append((a, b))

        if not plane_edges:
            raise GeometryError("no edges lie on the specified plane")

        loops = stitch_segments(plane_edges)
        if not loops:
            raise GeometryError("could not stitch planar edges into a closed loop")

        # Validate each loop is closed — stitch_segments may return open chains
        plane_edge_set = {(min(a, b), max(a, b)) for a, b in plane_edges}
        closed_loops: list[list[int]] = []
        for loop in loops:
            closing_key = (min(loop[-1], loop[0]), max(loop[-1], loop[0]))
            if closing_key in plane_edge_set:
                closed_loops.append(loop)

        if not closed_loops:
            raise GeometryError("no closed planar edge loops found")

        cap_faces: list[tuple[int, int, int]] = []
        for loop in closed_loops:
            projected = project_loop(loop, vertices_list, origin_np, normal_np)
            for a, b, c in triangulate_loop(projected, tolerance):
                cap_faces.append((loop[a], loop[c], loop[b]))

        return Mesh3D(self.vertices, tuple(cap_faces), self.edges)

    def triangulate_loops(
        self,
        *,
        tolerance: float = 1e-3,
    ) -> Mesh3D:
        """Detect closed edge cycles and triangulate each into a Mesh3D.

        Builds an adjacency graph from edges, walks cycles via DFS, fits a
        best-fit plane (SVD) to each cycle, and triangulates.  Raises
        ``GeometryError`` if no closed loops of length >= 3 are found.
        """
        from cady.errors import GeometryError
        from cady.ops.mesh_cut import (
            fit_plane_svd,
            max_plane_deviation,
            project_loop,
            triangulate_loop,
        )

        _validate_tolerance(tolerance)

        # Build adjacency map
        neighbours: dict[int, set[int]] = {}
        for a, b in self.edges:
            neighbours.setdefault(a, set()).add(b)
            neighbours.setdefault(b, set()).add(a)

        # DFS cycle detection — edge-aware to handle connected components
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
                        for i in range(len(cycle)):
                            a, b = cycle[i], cycle[(i + 1) % len(cycle)]
                            used_cycle_edges.add((min(a, b), max(a, b)))
                        cycles.append(cycle)
                        found_cycle = True
                        break
                    if neighbour not in visited:
                        stack.append((neighbour, vertex, path + [neighbour]))
                if found_cycle:
                    break

        cycles = [c for c in cycles if len(c) >= 3]
        if not cycles:
            raise GeometryError("no closed edge loops of length >= 3 found")

        vertices_list = [np.array((v.x, v.y, v.z), dtype=np.float64) for v in self.vertices]

        all_faces: list[tuple[int, int, int]] = []
        for loop in cycles:
            loop_points = np.array([vertices_list[i] for i in loop], dtype=np.float64)
            loop_origin, loop_normal = fit_plane_svd(loop_points)
            deviation = max_plane_deviation(loop_points, loop_origin, loop_normal)
            if deviation > tolerance:
                raise GeometryError(
                    f"edge loop is non-planar (max deviation {deviation:.3e} > "
                    f"tolerance {tolerance:.3e})"
                )
            projected = project_loop(loop, vertices_list, loop_origin, loop_normal)
            for a, b, c in triangulate_loop(projected, tolerance):
                all_faces.append((loop[a], loop[c], loop[b]))

        return Mesh3D(self.vertices, tuple(all_faces), self.edges)

    def close_to_plane(
        self,
        plane_origin: object,
        plane_normal: object,
        *,
        tolerance: float = 1e-3,
        max_distance: float,
    ) -> Mesh3D:
        """Project near-plane boundary edges to the plane and create wall faces.

        For each edge where both endpoints are within ``max_distance`` of the
        plane, projects the endpoints to the plane and creates two triangle
        faces forming a quadrilateral wall between the original edge and its
        projection.  Returns a ``Mesh3D`` with the wall faces and the
        original wireframe edges preserved as a display overlay.

        This does **not** triangulate the projected loop as a cap — only the
        connecting wall faces are created.
        """
        from cady.errors import GeometryError
        from cady.ops.mesh_cut import unit3, vector3

        _validate_tolerance(tolerance)
        if max_distance <= 0.0:
            raise ValueError("max_distance must be positive")

        origin_np = vector3(plane_origin, name="plane_origin")
        normal_np = unit3(plane_normal, name="plane_normal")

        # Collect edges near the plane
        near_edges: list[tuple[int, int, float, float]] = []
        for a, b in self.edges:
            va = np.array(self.vertices[a].tuple(), dtype=np.float64)
            vb = np.array(self.vertices[b].tuple(), dtype=np.float64)
            dist_a = float(np.dot(va - origin_np, normal_np))
            dist_b = float(np.dot(vb - origin_np, normal_np))
            if abs(dist_a) <= max_distance and abs(dist_b) <= max_distance:
                near_edges.append((a, b, dist_a, dist_b))

        if not near_edges:
            raise GeometryError("no edges found within max_distance of the plane")

        # Build combined vertex list: originals + projected copies
        proj_index: dict[int, int] = {}
        all_vertices = list(self.vertices)

        for a, b, dist_a, dist_b in near_edges:
            if a not in proj_index:
                proj_a = self.vertices[a].tuple()
                proj = (
                    proj_a[0] - dist_a * float(normal_np[0]),
                    proj_a[1] - dist_a * float(normal_np[1]),
                    proj_a[2] - dist_a * float(normal_np[2]),
                )
                proj_index[a] = len(all_vertices)
                all_vertices.append(Vec3(*proj))
            if b not in proj_index:
                proj_b = self.vertices[b].tuple()
                proj = (
                    proj_b[0] - dist_b * float(normal_np[0]),
                    proj_b[1] - dist_b * float(normal_np[1]),
                    proj_b[2] - dist_b * float(normal_np[2]),
                )
                proj_index[b] = len(all_vertices)
                all_vertices.append(Vec3(*proj))

        # Create wall faces: two triangles per near edge
        wall_faces: list[tuple[int, int, int]] = []
        for a, b, _, _ in near_edges:
            pa = proj_index[a]
            pb = proj_index[b]
            # Quad (a, b, pb, pa) -> triangles with outward normals
            wall_faces.append((a, b, pb))
            wall_faces.append((a, pb, pa))

        return Mesh3D(tuple(all_vertices), tuple(wall_faces), self.edges)

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


def _validate_tolerance(tolerance: float) -> None:
    if float(tolerance) <= 0.0:
        raise ValueError("tolerance must be positive")
