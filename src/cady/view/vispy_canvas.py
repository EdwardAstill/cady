"""Internal VisPy canvas runtime for interactive scene viewing."""

from __future__ import annotations

import importlib
import importlib.util
from typing import Any, cast

import numpy as np

from cady.view.draw_batches import DrawBatch, build_canvas_geometry
from cady.view.interaction import (
    ViewerInteractionState,
    axis_toggle_key_pressed,
    number_key_name,
    projection_clip_planes,
)
from cady.view.overlay_renderers import create_local_axes_renderer, create_scale_bar_renderer
from cady.view.render_scene import RenderScene

_VERT_SHADER = """
uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;
uniform float u_point_size;
attribute vec3 a_position;
attribute vec3 a_normal;
attribute vec3 a_color;
varying vec3 v_color;
varying vec3 v_normal;
void main() {
    v_color = a_color;
    v_normal = normalize((u_model * vec4(a_normal, 0.0)).xyz);
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
    gl_PointSize = u_point_size;
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

_OVERLAY_VERT_SHADER = """
attribute vec2 a_position;
void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
}
"""

_OVERLAY_FRAG_SHADER = """
uniform vec3 u_color;
void main() {
    gl_FragColor = vec4(u_color, 1.0);
}
"""

_HAS_VISPY = importlib.util.find_spec("vispy") is not None


def _require_vispy() -> None:
    if not _HAS_VISPY:
        raise ImportError("Interactive 3D viewing requires vispy; install cady[view]")


def _select_vispy_shader_backend(gl: Any) -> None:
    """Keep VisPy's shader conversion aligned with the active GL context."""
    version = gl.glGetParameter(gl.GL_VERSION)
    if isinstance(version, bytes):
        version = version.decode("utf-8", errors="replace")
    if not str(version).startswith("OpenGL ES"):
        return

    backend_name = getattr(gl.current_backend, "__name__", "")
    if ".es" not in backend_name:
        gl.use_gl("es2")


def _make_vispy_canvas(
    render_scene: RenderScene,
    *,
    title: str | None = None,
) -> object:
    _require_vispy()

    app = cast(Any, importlib.import_module("vispy.app"))
    gloo = cast(Any, importlib.import_module("vispy.gloo"))
    transforms = cast(Any, importlib.import_module("vispy.util.transforms"))
    visuals = cast(Any, importlib.import_module("vispy.visuals"))
    perspective = transforms.perspective
    ortho = transforms.ortho
    canvas_base = cast(type[Any], app.Canvas)
    geometry = build_canvas_geometry(render_scene, gloo)

    class VispyCanvas(canvas_base):
        def __init__(self) -> None:
            super().__init__(  # pyright: ignore[reportUnknownMemberType]
                title=title or render_scene.name,
                keys="interactive",
                size=(900, 700),
                config={"samples": 4},
            )

            _select_vispy_shader_backend(gloo.gl)
            self._program = gloo.Program(_VERT_SHADER, _FRAG_SHADER)
            self._overlay_program = gloo.Program(_OVERLAY_VERT_SHADER, _OVERLAY_FRAG_SHADER)
            self._face_batches = geometry.face_batches
            self._edge_batches = geometry.edge_batches
            self._point_batches = geometry.point_batches
            self._interaction = ViewerInteractionState.from_camera(
                render_scene.camera,
                local_centre=geometry.bounds.local_centre,
                radius=geometry.bounds.radius,
            )
            self._local_axes = create_local_axes_renderer(
                render_scene,
                local_centre=geometry.bounds.local_centre,
                gloo=gloo,
            )
            self._scale_bar = create_scale_bar_renderer(
                render_scene,
                overlay_program=self._overlay_program,
                visuals=visuals,
                viewport_size=self.physical_size,
                gloo=gloo,
            )

            self._last_mouse: tuple[float, float] | None = None
            self._mouse_button: int | None = None

            self._configure_program_uniforms()
            self._configure_canvas_state()

            self._update_matrices()
            self.show()

        def _configure_program_uniforms(self) -> None:
            self._program["u_light_direction"] = render_scene.light_direction
            self._program["u_ambient_light"] = render_scene.ambient_light
            self._program["u_diffuse_light"] = render_scene.diffuse_light
            self._program["u_point_size"] = 4.0

        def _configure_canvas_state(self) -> None:
            gloo.set_state(
                clear_color="white",
                depth_test=True,
                polygon_offset=(1, 1),
                blend_func=("src_alpha", "one_minus_src_alpha"),
                line_width=1.0,
            )

        def _projection(self, width: int, height: int) -> np.ndarray:
            near, far = projection_clip_planes(
                self._interaction.radius,
                self._interaction.distance,
                self._interaction.camera,
            )
            aspect = width / float(max(height, 1))
            if self._interaction.camera.projection == "orthographic":
                half_height = self._interaction.orthographic_scale / 2.0
                half_width = half_height * aspect
                return cast(
                    np.ndarray,
                    ortho(-half_width, half_width, -half_height, half_height, near, far),
                )
            return cast(
                np.ndarray,
                perspective(self._interaction.camera.fov_degrees, aspect, near, far),
            )

        def _update_matrices(self) -> None:
            width, height = cast(tuple[int, int], self.physical_size)
            gloo.set_viewport(0, 0, width, height)

            if self._local_axes is not None:
                self._local_axes.update_length(
                    self._interaction.local_axis_length((width, height))
                )
            if self._scale_bar is not None:
                self._scale_bar.update(
                    camera=self._interaction.camera,
                    distance=self._interaction.distance,
                    orthographic_scale=self._interaction.orthographic_scale,
                    viewport_size=(width, height),
                    logical_size=cast(tuple[int, int], self.size),
                )

            self._program["u_projection"] = self._projection(width, height)
            self._program["u_view"] = self._interaction.view_matrix()
            self._program["u_model"] = self._interaction.model_matrix()

        def _draw_batch(self, batch: DrawBatch) -> None:
            self._program["a_position"] = batch.positions
            self._program["a_normal"] = batch.normals
            self._program["a_color"] = batch.colors
            if batch.primitive == "points":
                self._program["u_point_size"] = batch.point_size
                self._program.draw(batch.primitive)
                return
            self._program.draw(batch.primitive, batch.index_buffer)

        def _draw_face_batches(self) -> None:
            gloo.set_state(
                blend=False,
                depth_test=True,
                depth_mask=True,
                polygon_offset_fill=True,
            )
            self._program["u_lighting"] = 1.0
            for batch in self._face_batches:
                self._draw_batch(batch)

        def _draw_edge_batches(self) -> None:
            gloo.set_state(
                blend=True,
                depth_test=True,
                depth_mask=False,
                polygon_offset_fill=False,
                line_width=1.0,
            )
            self._program["u_lighting"] = 0.0
            for batch in self._edge_batches:
                self._draw_batch(batch)

        def _draw_point_batches(self) -> None:
            if not self._point_batches:
                return
            gloo.set_state(
                blend=True,
                depth_test=True,
                depth_mask=False,
                polygon_offset_fill=False,
            )
            for batch in self._point_batches:
                self._draw_batch(batch)

        def _draw_local_axes(self) -> None:
            if self._local_axes is not None:
                self._local_axes.draw(self._program)

        def _draw_scale_bar(self) -> None:
            if self._scale_bar is not None:
                self._scale_bar.draw(canvas=self, camera=self._interaction.camera)

        def on_draw(self, event: object) -> None:
            gloo.clear(color=True, depth=True)
            self._draw_face_batches()
            self._draw_edge_batches()
            self._draw_point_batches()
            self._draw_local_axes()
            self._draw_scale_bar()
            gloo.set_state(depth_mask=True, line_width=1.0)

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

            if self._mouse_button == 1:
                self._interaction.orbit(dx, dy)
            elif self._mouse_button == 2:
                self._interaction.pan_by_pixels(dx, dy)

            self._last_mouse = event.pos
            self._update_matrices()
            self.update()

        def on_mouse_wheel(self, event: Any) -> None:
            self._interaction.zoom(event.delta[1])
            self._update_matrices()
            self.update()

        def on_key_press(self, event: Any) -> None:
            if axis_toggle_key_pressed(event.key):
                if self._local_axes is None:
                    return
                self._local_axes.toggle()
                self.update()
                return
            digit = number_key_name(event.key)
            if digit is None:
                return
            if not self._interaction.set_orientation_for_key(digit):
                return
            self._update_matrices()
            self.update()

    return VispyCanvas()


__all__ = [
    "_make_vispy_canvas",
    "_require_vispy",
    "_select_vispy_shader_backend",
]
