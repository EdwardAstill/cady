"""Interactive 3D mesh viewer using VisPy.

Lazy-imported — VisPy is loaded only when a viewer function is called.
"""

from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Sequence
from math import cos, radians
from typing import Any, Protocol, cast

import numpy as np

from cady.visualisation.styles import MESH_COLOR, MESH_EDGE_COLOR

_VERT_SHADER = """
uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
attribute vec3 a_position;
attribute vec3 a_normal;
attribute vec3 a_color;
varying vec3 v_color;
varying vec3 v_normal;
void main() {
    v_color = a_color;
    v_normal = normalize((u_model * vec4(a_normal, 0.0)).xyz);
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

_FRAG_SHADER = """
uniform vec3 u_light_direction;
uniform vec3 u_ambient_light;
uniform vec3 u_diffuse_light;
uniform float u_lighting;
varying vec3 v_color;
varying vec3 v_normal;
void main() {
    vec3 normal = normalize(v_normal);
    float diffuse = abs(dot(normal, normalize(u_light_direction)));
    vec3 lit = v_color * clamp(u_ambient_light + diffuse * u_diffuse_light, 0.0, 1.0);
    gl_FragColor = vec4(mix(v_color, lit, u_lighting), 1.0);
}
"""

_HAS_VISPY = importlib.util.find_spec("vispy") is not None
_EDGE_ANGLE_TOLERANCE_DEGREES = 15.0
_CURVED_PATCH_ANGLE_TOLERANCE_DEGREES = 35.0
_MIN_CURVED_PATCH_ROOTS = 4
_MAX_CURVED_PATCH_ROOT_FACES = 4


class _MeshLike(Protocol):
    vertices: Sequence[Sequence[float]]
    faces: Sequence[Sequence[int]]


class _ToArrayLike(Protocol):
    def to_array(self, *, tolerance: float) -> _MeshLike: ...


def _require_vispy() -> None:
    if not _HAS_VISPY:
        raise ImportError("Interactive 3D viewing requires vispy; install cady[visualisation]")


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return (
        int(hex_color[0:2], 16) / 255.0,
        int(hex_color[2:4], 16) / 255.0,
        int(hex_color[4:6], 16) / 255.0,
    )


def _face_normals(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    triangles = vertices[faces]
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    valid = lengths > 1e-12
    normals[valid] = normals[valid] / lengths[valid, None]
    return normals.astype(np.float32, copy=False), valid


def _coordinate_tolerance(vertices: np.ndarray) -> float:
    if len(vertices) == 0:
        return 1e-12
    span = float(np.max(np.ptp(vertices, axis=0)))
    return max(span * 1e-10, 1e-12)


def _vertex_key(vertex: np.ndarray, coordinate_tolerance: float) -> tuple[int, int, int]:
    scaled = np.rint(vertex / coordinate_tolerance).astype(np.int64)
    return (int(scaled[0]), int(scaled[1]), int(scaled[2]))


def _coordinate_edge_ownership(
    vertices: np.ndarray, faces: np.ndarray, valid_faces: np.ndarray
) -> tuple[
    dict[tuple[tuple[int, int, int], tuple[int, int, int]], list[int]],
    dict[tuple[tuple[int, int, int], tuple[int, int, int]], tuple[int, int]],
]:
    coordinate_tolerance = _coordinate_tolerance(vertices)
    edge_faces: dict[tuple[tuple[int, int, int], tuple[int, int, int]], list[int]] = {}
    edge_indices: dict[tuple[tuple[int, int, int], tuple[int, int, int]], tuple[int, int]] = {}
    for face_index, face in enumerate(faces):
        if not valid_faces[face_index]:
            continue
        face_edges = ((face[0], face[1]), (face[1], face[2]), (face[2], face[0]))
        for start, end in face_edges:
            start_index = int(start)
            end_index = int(end)
            start_key = _vertex_key(vertices[start_index], coordinate_tolerance)
            end_key = _vertex_key(vertices[end_index], coordinate_tolerance)
            if start_key == end_key:
                continue
            edge = (start_key, end_key) if start_key <= end_key else (end_key, start_key)
            edge_faces.setdefault(edge, []).append(face_index)
            edge_indices.setdefault(edge, (start_index, end_index))
    return edge_faces, edge_indices


def _smooth_face_roots(
    normals: np.ndarray,
    edge_faces: dict[tuple[tuple[int, int, int], tuple[int, int, int]], list[int]],
    *,
    angle_tolerance_degrees: float,
    curved_patch_angle_tolerance_degrees: float = _CURVED_PATCH_ANGLE_TOLERANCE_DEGREES,
) -> np.ndarray:
    cos_tolerance = cos(radians(angle_tolerance_degrees))
    parents = list(range(len(normals)))

    def find(face_index: int) -> int:
        while parents[face_index] != face_index:
            parents[face_index] = parents[parents[face_index]]
            face_index = parents[face_index]
        return face_index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parents[right_root] = left_root

    for owners in edge_faces.values():
        for i, left in enumerate(owners):
            for right in owners[i + 1 :]:
                if abs(float(np.dot(normals[left], normals[right]))) >= cos_tolerance:
                    union(left, right)

    cos_curved_tolerance = cos(radians(curved_patch_angle_tolerance_degrees))
    if cos_curved_tolerance < cos_tolerance:
        roots = [find(face_index) for face_index in range(len(normals))]
        root_face_counts = np.bincount(np.array(roots, dtype=np.int64), minlength=len(normals))
        curved_adjacency: dict[int, set[int]] = {}
        for owners in edge_faces.values():
            for i, left in enumerate(owners):
                for right in owners[i + 1 :]:
                    left_root = find(left)
                    right_root = find(right)
                    if left_root == right_root:
                        continue
                    if (
                        root_face_counts[left_root] > _MAX_CURVED_PATCH_ROOT_FACES
                        or root_face_counts[right_root] > _MAX_CURVED_PATCH_ROOT_FACES
                    ):
                        continue
                    dot = abs(float(np.dot(normals[left], normals[right])))
                    if dot >= cos_curved_tolerance:
                        curved_adjacency.setdefault(left_root, set()).add(right_root)
                        curved_adjacency.setdefault(right_root, set()).add(left_root)

        visited: set[int] = set()
        for root in tuple(curved_adjacency):
            if root in visited:
                continue
            component: list[int] = []
            stack = [root]
            visited.add(root)
            while stack:
                current = stack.pop()
                component.append(current)
                for neighbour in curved_adjacency.get(current, set()):
                    if neighbour in visited:
                        continue
                    visited.add(neighbour)
                    stack.append(neighbour)

            if len(component) < _MIN_CURVED_PATCH_ROOTS:
                continue
            first = component[0]
            for other in component[1:]:
                union(first, other)

    return np.array([find(face_index) for face_index in range(len(normals))], dtype=np.int64)


def _orientation_edges(
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    angle_tolerance_degrees: float = _EDGE_ANGLE_TOLERANCE_DEGREES,
    include_boundary_edges: bool = True,
) -> np.ndarray:
    """Boundaries between smooth face patches, excluding internal tessellation."""
    if len(faces) == 0:
        return np.empty((0, 2), dtype=np.uint32)

    normals, valid_normals = _face_normals(vertices, faces)
    edge_faces, edge_indices = _coordinate_edge_ownership(vertices, faces, valid_normals)
    smooth_roots = _smooth_face_roots(
        normals,
        edge_faces,
        angle_tolerance_degrees=angle_tolerance_degrees,
    )

    visible: list[tuple[int, int]] = []
    for edge, owners in edge_faces.items():
        representative = edge_indices[edge]
        owner_roots = {int(smooth_roots[owner]) for owner in owners}
        if len(owner_roots) > 1 or (len(owners) == 1 and include_boundary_edges):
            visible.append(representative)

    return np.array(sorted(visible), dtype=np.uint32).reshape((-1, 2))


def _shaded_face_buffers(
    vertices: np.ndarray,
    faces: np.ndarray,
    *,
    angle_tolerance_degrees: float = _EDGE_ANGLE_TOLERANCE_DEGREES,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Duplicate hard-edge vertices and build smooth normals per face patch."""
    if len(faces) == 0:
        return (
            np.empty((0, 3), dtype=np.float32),
            np.empty((0, 3), dtype=np.uint32),
            np.empty((0, 3), dtype=np.float32),
        )

    normals, valid_normals = _face_normals(vertices, faces)
    edge_faces, _edge_indices = _coordinate_edge_ownership(vertices, faces, valid_normals)
    smooth_roots = _smooth_face_roots(
        normals,
        edge_faces,
        angle_tolerance_degrees=angle_tolerance_degrees,
    )

    coordinate_tolerance = _coordinate_tolerance(vertices)
    render_indices_by_key: dict[tuple[tuple[int, int, int], int], int] = {}
    render_vertices: list[np.ndarray] = []
    normal_sums: list[np.ndarray] = []
    render_faces: list[tuple[int, int, int]] = []

    for face_index, face in enumerate(faces):
        if not valid_normals[face_index]:
            continue

        root = int(smooth_roots[face_index])
        face_render_indices: list[int] = []
        for vertex_index in face:
            original_index = int(vertex_index)
            key = (_vertex_key(vertices[original_index], coordinate_tolerance), root)
            render_index = render_indices_by_key.get(key)
            if render_index is None:
                render_index = len(render_vertices)
                render_indices_by_key[key] = render_index
                render_vertices.append(vertices[original_index])
                normal_sums.append(np.zeros(3, dtype=np.float32))

            face_normal = normals[face_index]
            if float(np.dot(normal_sums[render_index], face_normal)) < 0.0:
                face_normal = -face_normal
            normal_sums[render_index] = normal_sums[render_index] + face_normal
            face_render_indices.append(render_index)

        render_faces.append(
            (face_render_indices[0], face_render_indices[1], face_render_indices[2])
        )

    if not render_vertices:
        return (
            np.empty((0, 3), dtype=np.float32),
            np.empty((0, 3), dtype=np.uint32),
            np.empty((0, 3), dtype=np.float32),
        )

    render_normals = np.array(normal_sums, dtype=np.float32)
    lengths = np.linalg.norm(render_normals, axis=1)
    valid = lengths > 1e-12
    render_normals[valid] = render_normals[valid] / lengths[valid, None]
    return (
        np.array(render_vertices, dtype=np.float32),
        np.array(render_faces, dtype=np.uint32),
        render_normals,
    )


def _translation_matrix(offset: tuple[float, float, float] | np.ndarray) -> np.ndarray:
    matrix = np.eye(4, dtype=np.float32)
    matrix[3, :3] = np.asarray(offset, dtype=np.float32)
    return matrix


def _rotation_matrix(angle_degrees: float, axis: tuple[float, float, float]) -> np.ndarray:
    axis_array = np.asarray(axis, dtype=np.float32)
    length = float(np.linalg.norm(axis_array))
    if length == 0.0:
        raise ValueError("rotation axis must be non-zero")
    x, y, z = axis_array / length
    c = cos(radians(angle_degrees))
    s = np.sin(radians(angle_degrees))
    one_c = 1.0 - c
    matrix = np.array(
        [
            [c + x * x * one_c, y * x * one_c + z * s, z * x * one_c - y * s, 0.0],
            [x * y * one_c - z * s, c + y * y * one_c, z * y * one_c + x * s, 0.0],
            [x * z * one_c + y * s, y * z * one_c - x * s, c + z * z * one_c, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    return matrix


def _apply_view_orbit(orientation: np.ndarray, dx_degrees: float, dy_degrees: float) -> np.ndarray:
    """Update local-to-global orientation using screen/view X and Y axes."""
    yaw = _rotation_matrix(dx_degrees, (0.0, 1.0, 0.0))
    pitch = _rotation_matrix(dy_degrees, (1.0, 0.0, 0.0))
    return (orientation @ yaw @ pitch).astype(np.float32, copy=False)


def _model_matrix(local_centre: np.ndarray, orientation: np.ndarray) -> np.ndarray:
    """Map local mesh coordinates to centred global/view coordinates."""
    return (_translation_matrix(-local_centre) @ orientation).astype(np.float32, copy=False)


def _make_canvas(
    face_vertices: list[np.ndarray],
    face_indices: list[np.ndarray],
    face_normals: list[np.ndarray],
    face_rgb: list[tuple[float, float, float]],
    edge_vertices: list[np.ndarray],
    edge_indices: list[np.ndarray],
    edge_rgb: tuple[float, float, float],
    *,
    title: str,
) -> object:
    _require_vispy()

    app = cast(Any, importlib.import_module("vispy.app"))
    gloo = cast(Any, importlib.import_module("vispy.gloo"))
    transforms = cast(Any, importlib.import_module("vispy.util.transforms"))
    perspective = transforms.perspective
    canvas_base = cast(type[Any], app.Canvas)

    class _Canvas(canvas_base):
        def __init__(self) -> None:
            super().__init__(  # pyright: ignore[reportUnknownMemberType]
                title=title,
                keys="interactive",
                size=(900, 700),
                config={"samples": 4},
            )

            self._program = gloo.Program(_VERT_SHADER, _FRAG_SHADER)

            # ── pack per-vertex position+color arrays ──────────────────────
            self._face_data: list[tuple[np.ndarray, object]] = []  # (packed_vertices, index_buffer)
            for verts, indices, normals, rgb in zip(
                face_vertices, face_indices, face_normals, face_rgb, strict=True
            ):
                n = len(verts)
                colors = np.tile(np.array(rgb, dtype=np.float32), (n, 1))
                packed = np.hstack([verts, normals, colors]).astype(np.float32)
                self._face_data.append((packed, gloo.IndexBuffer(indices)))

            self._edge_data: list[tuple[np.ndarray, object]] = []
            for verts, indices in zip(edge_vertices, edge_indices, strict=True):
                n = len(verts)
                colors = np.tile(np.array(edge_rgb, dtype=np.float32), (n, 1))
                normals = np.tile(np.array((0.0, 0.0, 1.0), dtype=np.float32), (n, 1))
                packed = np.hstack([verts, normals, colors]).astype(np.float32)
                self._edge_data.append((packed, gloo.IndexBuffer(indices)))

            # ── bounding box ───────────────────────────────────────────────
            all_v = np.vstack(face_vertices)
            self._local_centre = (all_v.min(axis=0) + all_v.max(axis=0)) / 2.0
            spans = all_v.max(axis=0) - all_v.min(axis=0)
            self._radius = float(np.max(spans)) * 1.2 or 1.0
            self._distance = self._radius * 2.5
            self._pan = np.zeros(2, dtype=np.float32)

            # ── orbit state ────────────────────────────────────────────────
            self._orientation = _apply_view_orbit(np.eye(4, dtype=np.float32), 25.0, 35.0)

            # ── mouse state ────────────────────────────────────────────────
            self._last_mouse: tuple[float, float] | None = None
            self._mouse_button: int | None = None
            self._dragging = False

            self._program["u_light_direction"] = (0.2, 0.45, 0.9)
            self._program["u_ambient_light"] = (0.38, 0.38, 0.38)
            self._program["u_diffuse_light"] = (0.72, 0.72, 0.72)

            gloo.set_state(
                clear_color="white",
                depth_test=True,
                polygon_offset=(1, 1),
                blend_func=("src_alpha", "one_minus_src_alpha"),
                line_width=1.0,
            )

            self._update_matrices()
            self.show()

        def _update_matrices(self) -> None:
            width, height = cast(tuple[int, int], self.physical_size)
            gloo.set_viewport(0, 0, width, height)

            projection = perspective(45.0, width / float(height), 0.01, 1000.0)
            view = _translation_matrix((self._pan[0], self._pan[1], -self._distance))
            model = _model_matrix(self._local_centre, self._orientation)

            self._program["u_projection"] = projection
            self._program["u_view"] = view
            self._program["u_model"] = model

        def on_draw(self, event: object) -> None:
            gloo.clear(color=True, depth=True)

            gloo.set_state(
                blend=False,
                depth_test=True,
                depth_mask=True,
                polygon_offset_fill=True,
            )
            self._program["u_lighting"] = 1.0
            for packed, ibuf in self._face_data:
                self._program["a_position"] = packed[:, :3]
                self._program["a_normal"] = packed[:, 3:6]
                self._program["a_color"] = packed[:, 6:]
                self._program.draw("triangles", ibuf)

            gloo.set_state(
                blend=True,
                depth_test=True,
                depth_mask=False,
                polygon_offset_fill=False,
            )
            self._program["u_lighting"] = 0.0
            for packed, ibuf in self._edge_data:
                self._program["a_position"] = packed[:, :3]
                self._program["a_normal"] = packed[:, 3:6]
                self._program["a_color"] = packed[:, 6:]
                self._program.draw("lines", ibuf)
            gloo.set_state(depth_mask=True)

        def on_resize(self, event: object) -> None:
            self._update_matrices()

        def on_mouse_press(self, event: Any) -> None:
            self._last_mouse = event.pos
            self._mouse_button = event.button

        def on_mouse_release(self, event: object) -> None:
            self._last_mouse = None
            self._mouse_button = None

        def on_mouse_move(self, event: Any) -> None:
            if self._last_mouse is None:
                return
            x, y = event.pos
            last_x, last_y = self._last_mouse
            dx = x - last_x
            dy = y - last_y

            if self._mouse_button == 1:  # left → orbit
                self._orientation = _apply_view_orbit(self._orientation, dx * 0.5, dy * 0.5)
            elif self._mouse_button == 2:  # middle → pan
                self._pan[0] += dx * self._radius * 0.003
                self._pan[1] -= dy * self._radius * 0.003

            self._last_mouse = event.pos
            self._update_matrices()
            self.update()

        def on_mouse_wheel(self, event: Any) -> None:
            self._distance -= event.delta[1] * self._radius * 0.1
            self._distance = max(self._radius * 0.5, min(self._distance, self._radius * 20.0))
            self._update_matrices()
            self.update()

    return _Canvas()


def _prepare_mesh(
    mesh: _MeshLike, face_rgb: tuple[float, float, float], edge_rgb: tuple[float, float, float]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return (face_vertices, face_indices, face_normals, edge_vertices, edge_indices)."""
    verts = np.array(mesh.vertices, dtype=np.float32)
    faces = np.array(mesh.faces, dtype=np.uint32)
    edges = _orientation_edges(verts, faces)
    render_vertices, render_faces, render_normals = _shaded_face_buffers(verts, faces)
    return render_vertices, render_faces, render_normals, verts, edges


def _mesh_from_object(mesh: object, *, tolerance: float) -> _MeshLike:
    if hasattr(mesh, "to_array") and not hasattr(mesh, "vertices"):
        return cast(_ToArrayLike, mesh).to_array(tolerance=tolerance)
    return cast(_MeshLike, mesh)


def vispy_view_mesh(
    mesh: object,
    *,
    title: str = "cady 3D viewer",
    tolerance: float = 1e-3,
) -> None:
    _require_vispy()
    app = cast(Any, importlib.import_module("vispy.app"))

    mesh_like = _mesh_from_object(mesh, tolerance=tolerance)

    fv, fi, fn, ev, ei = _prepare_mesh(
        mesh_like,
        _hex_to_rgb(MESH_COLOR),
        _hex_to_rgb(MESH_EDGE_COLOR),
    )
    _make_canvas(
        [fv],
        [fi],
        [fn],
        [_hex_to_rgb(MESH_COLOR)],
        [ev],
        [ei],
        _hex_to_rgb(MESH_EDGE_COLOR),
        title=title,
    )
    app.run()


def vispy_view_meshes(
    meshes: list[object],
    *,
    title: str = "cady 3D viewer",
    tolerance: float = 1e-3,
) -> None:
    _require_vispy()
    app = cast(Any, importlib.import_module("vispy.app"))

    face_rgb = _hex_to_rgb(MESH_COLOR)
    edge_rgb = _hex_to_rgb(MESH_EDGE_COLOR)

    fvs: list[np.ndarray] = []
    fis: list[np.ndarray] = []
    fns: list[np.ndarray] = []
    evs: list[np.ndarray] = []
    eis: list[np.ndarray] = []
    for mesh in meshes:
        mesh_like = _mesh_from_object(mesh, tolerance=tolerance)
        fv, fi, fn, ev, ei = _prepare_mesh(mesh_like, face_rgb, edge_rgb)
        fvs.append(fv)
        fis.append(fi)
        fns.append(fn)
        evs.append(ev)
        eis.append(ei)

    _make_canvas(fvs, fis, fns, [face_rgb] * len(fvs), evs, eis, edge_rgb, title=title)
    app.run()
