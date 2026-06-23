"""Interactive 3D mesh viewer using VisPy.

Lazy-imported — VisPy is loaded only when a viewer function is called.
The module itself is importable without vispy installed.
"""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass

from cady.visualisation.styles import MESH_COLOR

# ── shaders ──────────────────────────────────────────────────────────────────

_VERT_SHADER = """
uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

attribute vec3 a_position;

void main(void)
{
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

_FRAG_SHADER = """
uniform vec4 u_color;

void main(void)
{
    gl_FragColor = u_color;
}
"""


# ── colour helpers ───────────────────────────────────────────────────────────

def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return (r, g, b, alpha)


# ── guard ────────────────────────────────────────────────────────────────────

_HAS_VISPY = importlib.util.find_spec("vispy") is not None


def _require_vispy() -> None:
    if not _HAS_VISPY:
        raise ImportError(
            "Interactive 3D viewing requires vispy; install cady[visualisation]"
        )


# ── canvas ───────────────────────────────────────────────────────────────────

def _make_canvas(
    meshes: list[tuple[np.ndarray, np.ndarray, tuple[float, float, float, float]]],
    *,
    title: str = "cady 3D viewer",
) -> object:
    """Create and return a VisPy canvas (lazy imports vispy)."""
    _require_vispy()
    from vispy import app as _app
    from vispy import gloo as _gloo
    from vispy.util.transforms import perspective as _perspective
    from vispy.util.transforms import rotate as _rotate
    from vispy.util.transforms import translate as _translate

    class _MeshCanvas(_app.Canvas):
        """Interactive VisPy canvas for viewing one or more triangulated meshes."""

        def __init__(self) -> None:
            super().__init__(title=title, keys="interactive", size=(900, 700))

            # Compile shader program (shared across all meshes).
            self._program = _gloo.Program(_VERT_SHADER, _FRAG_SHADER)

            # Build per-mesh vertex + index buffers.
            self._draws: list[tuple[object, object, tuple[float, float, float, float]]] = []
            for vertices, faces, color in meshes:
                vbuf = _gloo.VertexBuffer(vertices)
                ibuf = _gloo.IndexBuffer(faces)
                self._draws.append((vbuf, ibuf, color))

            # Compute combined bounding box for camera setup.
            all_v = np.vstack([v for v, _, _ in meshes])
            self._centre = (all_v.min(axis=0) + all_v.max(axis=0)) / 2.0
            spans = all_v.max(axis=0) - all_v.min(axis=0)
            self._radius = float(np.max(spans)) * 1.2 or 1.0
            self._distance = self._radius * 2.5

            # Orbit angles.
            self._theta = 25.0
            self._phi = 35.0

            # Mouse state.
            self._last_mouse: tuple[float, float] | None = None
            self._mouse_button: int | None = None

            # Render state.
            _gloo.set_state(clear_color="white", depth_test=True, cull_face=False)

            self._update_matrices()
            self.show()

        def _update_matrices(self) -> None:
            width, height = self.physical_size
            _gloo.set_viewport(0, 0, width, height)

            aspect = width / float(height)
            projection = _perspective(fovy=45.0, aspect=aspect, znear=0.01, zfar=1000.0)
            view = _translate((0.0, 0.0, -self._distance), dtype=np.float32)

            model = np.eye(4, dtype=np.float32)
            model = np.dot(_translate(tuple(-self._centre), dtype=np.float32), model)
            model = np.dot(_rotate(self._theta, (0, 1, 0)), model)
            model = np.dot(_rotate(self._phi, (1, 0, 0)), model)
            model = np.dot(_translate(tuple(self._centre), dtype=np.float32), model)

            self._program["u_projection"] = projection
            self._program["u_view"] = view
            self._program["u_model"] = model

        def on_draw(self, event: object) -> None:
            _gloo.clear(color=True, depth=True)
            for vbuf, ibuf, color in self._draws:
                self._program["a_position"] = vbuf
                self._program["u_color"] = color
                self._program.draw("triangles", ibuf)

        def on_resize(self, event: object) -> None:
            self._update_matrices()

        def on_mouse_press(self, event: object) -> None:
            self._last_mouse = event.pos
            self._mouse_button = event.button

        def on_mouse_release(self, event: object) -> None:
            self._last_mouse = None
            self._mouse_button = None

        def on_mouse_move(self, event: object) -> None:
            if self._last_mouse is None:
                return
            x, y = event.pos
            last_x, last_y = self._last_mouse
            dx = x - last_x
            dy = y - last_y

            if self._mouse_button == 1:
                self._theta += dx * 0.5
                self._phi += dy * 0.5
            elif self._mouse_button == 2:
                self._centre[0] += dx * self._radius * 0.003
                self._centre[1] -= dy * self._radius * 0.003

            self._last_mouse = event.pos
            self._update_matrices()
            self.update()

        def on_mouse_wheel(self, event: object) -> None:
            self._distance -= event.delta[1] * self._radius * 0.1
            self._distance = max(self._radius * 0.5, min(self._distance, self._radius * 20.0))
            self._update_matrices()
            self.update()

    return _MeshCanvas()


# ── public API ───────────────────────────────────────────────────────────────

def vispy_view_mesh(
    mesh: object,
    *,
    title: str = "cady 3D viewer",
    tolerance: float = 1e-3,
    face_color: str = MESH_COLOR,
    face_alpha: float = 0.65,
) -> None:
    """Open an interactive VisPy window for a single mesh.

    Args:
        mesh: An ArrayMesh3 or any object with ``.vertices`` (N×3) and
              ``.faces`` (M×3) attributes.
        title: Window title.
        tolerance: Tessellation tolerance (unused when mesh is already an
                   ArrayMesh3; used when the object has ``.to_array()``).
        face_color: Hex face color.
        face_alpha: Face opacity (0–1).
    """
    _require_vispy()
    from vispy import app as _app

    if hasattr(mesh, "to_array") and not hasattr(mesh, "vertices"):
        mesh = mesh.to_array(tolerance=tolerance)

    vertices = np.array(mesh.vertices, dtype=np.float32)
    faces = np.array(mesh.faces, dtype=np.uint32)
    color = _hex_to_rgba(face_color, face_alpha)

    _make_canvas([(vertices, faces, color)], title=title)
    _app.run()


def vispy_view_meshes(
    meshes: list[object],
    *,
    title: str = "cady 3D viewer",
    tolerance: float = 1e-3,
    face_color: str = MESH_COLOR,
    face_alpha: float = 0.65,
) -> None:
    """Open an interactive VisPy window for multiple meshes.

    Args:
        meshes: List of ArrayMesh3-compatible objects.
        title: Window title.
        tolerance: Tessellation tolerance.
        face_color: Hex face color applied to all meshes.
        face_alpha: Face opacity (0–1).
    """
    _require_vispy()
    from vispy import app as _app

    rgba = _hex_to_rgba(face_color, face_alpha)
    prepared: list[tuple[np.ndarray, np.ndarray, tuple[float, float, float, float]]] = []
    for mesh in meshes:
        if hasattr(mesh, "to_array") and not hasattr(mesh, "vertices"):
            mesh = mesh.to_array(tolerance=tolerance)
        vertices = np.array(mesh.vertices, dtype=np.float32)
        faces = np.array(mesh.faces, dtype=np.uint32)
        prepared.append((vertices, faces, rgba))

    _make_canvas(prepared, title=title)
    _app.run()
