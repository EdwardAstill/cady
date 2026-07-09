from __future__ import annotations

from unittest import mock

import numpy as np
import pytest

from cady import (
    Body3,
    Camera,
    DirectionalLight,
    DisplayStyle,
    Document,
    Mesh3,
    Part,
    PointCloud3,
    ScaleBarOverlay,
    Scene,
)
from cady.view.scene import prepare_scene
from cady.view.scene import transform_from_pose as _transform_from_pose
from cady.view.vispy.canvas import (
    _drag_mode_for_mouse,
    _require_vispy,
    _select_vispy_shader_backend,
)
from cady.view.vispy.draw_batches import element_index_data as _element_index_data
from cady.view.vispy.draw_batches import line_batch as _line_batch
from cady.view.vispy.draw_batches import mesh_edge_color as _mesh_edge_color
from cady.view.vispy.interaction import (
    ViewerInteractionState,
    pan_world_units_per_pixel,
    space_key_pressed,
)
from cady.view.vispy.interaction import (
    camera_orientation as _camera_orientation,
)
from cady.view.vispy.interaction import (
    projection_clip_planes as _projection_clip_planes,
)
from cady.view.vispy.interaction import (
    view_relative_orthographic_axis_length as _view_relative_orthographic_axis_length,
)
from cady.view.vispy.interaction import (
    zoomed_orthographic_scale as _zoomed_orthographic_scale,
)
from cady.view.vispy.mesh_buffers import (
    flat_face_buffers as _flat_face_buffers,
)
from cady.view.vispy.mesh_buffers import (
    orientation_edges as _orientation_edges,
)
from cady.view.vispy.overlays import (
    scale_bar_for_camera as _scale_bar_for_camera,
)
from cady.view.vispy.overlays import (
    scale_bar_for_visible_height as _scale_bar_for_visible_height,
)
from cady.view.vispy.overlays import (
    scale_bar_overlay as _scale_bar_overlay,
)


class _FakeGloo:
    @staticmethod
    def IndexBuffer(data: np.ndarray) -> np.ndarray:
        return np.asarray(data)


def test_vispy_viewer_module_imports_without_opening_window() -> None:
    from cady.view import prepare_scene, view_scene

    assert all((prepare_scene, view_scene))


def test_require_vispy_raises_when_missing() -> None:
    with (
        mock.patch("cady.view.vispy.canvas._HAS_VISPY", False),
        pytest.raises(ImportError, match="requires vispy"),
    ):
        _require_vispy()


def test_select_vispy_shader_backend_uses_es_for_opengl_es_context() -> None:
    gl = mock.Mock()
    gl.GL_VERSION = object()
    gl.glGetParameter.return_value = "OpenGL ES 3.2 NVIDIA"
    gl.current_backend.__name__ = "vispy.gloo.gl.gl2"

    _select_vispy_shader_backend(gl)

    gl.glGetParameter.assert_called_once_with(gl.GL_VERSION)
    gl.use_gl.assert_called_once_with("es2")


def test_select_vispy_shader_backend_leaves_desktop_context() -> None:
    gl = mock.Mock()
    gl.GL_VERSION = object()
    gl.glGetParameter.return_value = "4.6.0 NVIDIA"
    gl.current_backend.__name__ = "vispy.gloo.gl.gl2"

    _select_vispy_shader_backend(gl)

    gl.use_gl.assert_not_called()


def test_space_key_pressed_accepts_vispy_key_names() -> None:
    key = mock.Mock()
    key.name = "Space"

    assert space_key_pressed(key)
    assert space_key_pressed(" ")
    assert not space_key_pressed("A")


def test_drag_mode_maps_space_primary_drag_to_pan() -> None:
    assert _drag_mode_for_mouse(1, space_pressed=False) == "orbit"
    assert _drag_mode_for_mouse(1, space_pressed=True) == "pan"
    assert _drag_mode_for_mouse(2, space_pressed=False) == "pan"
    assert _drag_mode_for_mouse(3, space_pressed=False) == "pan"
    assert _drag_mode_for_mouse(None, space_pressed=True) is None


def test_prepare_scene_uses_new_scene_camera_light_and_style() -> None:
    scene = Scene(
        "review",
        camera=Camera.perspective(
            position=(1.0, -2.0, 1.5),
            target=(0.0, 0.0, 0.0),
            fov_degrees=35.0,
        ),
        lights=(
            DirectionalLight(direction=(-1.0, -1.0, -2.0), intensity=0.5),
        ),
    ).add(
        Body3.box(width=1.0, depth=0.5, height=0.25),
        style=DisplayStyle(color=(0.2, 0.4, 0.8)),
    )

    prepared = prepare_scene(scene, tolerance=1e-3)

    assert prepared.name == "review"
    assert prepared.camera.fov_degrees == 35.0
    assert len(prepared.meshes) == 1
    assert prepared.meshes[0].color == (0.2, 0.4, 0.8)
    assert prepared.meshes[0].vertices.shape[1] == 3
    assert prepared.meshes[0].faces.shape[1] == 3
    assert prepared.light_direction == (-1.0, -1.0, -2.0)


def test_prepare_scene_carries_scene_overlays() -> None:
    overlay = ScaleBarOverlay(min_pixels=24.0, max_pixels=96.0)
    prepared = prepare_scene(
        Scene("overlay", overlays=(overlay,)).add(
            Body3.box(width=1.0, depth=1.0, height=1.0)
        )
    )

    assert prepared.overlays == (overlay,)
    assert _scale_bar_overlay(prepared) is overlay

    hidden = prepare_scene(
        Scene("hidden", overlays=(ScaleBarOverlay(visible=False),)).add(
            Body3.box(width=1.0, depth=1.0, height=1.0)
        )
    )

    assert _scale_bar_overlay(hidden) is None


def test_transform_from_pose_preserves_viewer_message() -> None:
    with pytest.raises(
        TypeError,
        match="scene object pose must be Transform3-like or a 3D translation",
    ):
        _transform_from_pose((1.0, 2.0))


def test_prepare_scene_accepts_wire_polyline_targets() -> None:
    wire = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.5), (1.0, 1.0, 0.5))
    scene = Scene("wires").add(
        wire,
        name="station",
        style=DisplayStyle(color=(0.05, 0.23, 0.55), render_mode="wireframe"),
    )

    prepared = prepare_scene(scene, tolerance=1e-3)

    assert prepared.meshes == ()
    assert len(prepared.lines) == 1
    assert prepared.lines[0].name == "station"
    assert prepared.lines[0].color == (0.05, 0.23, 0.55)
    np.testing.assert_allclose(
        prepared.lines[0].vertices,
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.5], [1.0, 1.0, 0.5]],
    )
    np.testing.assert_array_equal(prepared.lines[0].indices, [[0, 1], [1, 2]])


def test_vispy_line_batches_use_uint16_indices_when_possible() -> None:
    wire = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.5), (1.0, 1.0, 0.5))
    prepared = prepare_scene(Scene("wires").add(wire), tolerance=1e-3)

    batch = _line_batch(prepared.lines[0], _FakeGloo())

    assert isinstance(batch.index_buffer, np.ndarray)
    assert batch.index_buffer.dtype == np.uint16
    np.testing.assert_array_equal(batch.index_buffer, [[0, 1], [1, 2]])


def test_vispy_index_data_keeps_uint32_when_needed() -> None:
    indices = np.array([[0, np.iinfo(np.uint16).max + 1]], dtype=np.uint32)

    converted = _element_index_data(indices)

    assert converted.dtype == np.uint32


def test_prepare_scene_uses_explicit_mesh_edges_for_wire_meshes() -> None:
    mesh = Mesh3(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.5), (1.0, 1.0, 0.5)),
        (),
        ((0, 1), (1, 2)),
    )
    scene = Scene("mesh wires").add(mesh, style=DisplayStyle(render_mode="wireframe"))

    prepared = prepare_scene(scene, tolerance=1e-3)

    assert prepared.lines == ()
    assert len(prepared.meshes) == 1
    np.testing.assert_array_equal(prepared.meshes[0].faces, np.empty((0, 3), dtype=np.uint32))
    np.testing.assert_array_equal(prepared.meshes[0].edges, [[0, 1], [1, 2]])


def test_prepare_scene_triangulates_polygon_mesh_faces_for_viewer() -> None:
    mesh = Mesh3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        ((0, 1, 2, 3),),
    )
    scene = Scene("polygon").add(mesh)

    prepared = prepare_scene(scene, tolerance=1e-9)

    assert mesh.faces == ((0, 1, 2, 3),)
    np.testing.assert_array_equal(prepared.meshes[0].faces, [[3, 0, 1], [1, 2, 3]])


def test_prepare_scene_accepts_document_targets() -> None:
    document = Document("job").add_part(
        Part("box").with_body(Body3.box(width=1.0, depth=0.5, height=0.25))
    )
    scene = Scene("document").add(document)

    prepared = prepare_scene(scene, tolerance=1e-3)

    assert len(prepared.meshes) == 1
    assert prepared.lines == ()


def test_prepare_scene_accepts_point_cloud_targets() -> None:
    cloud = PointCloud3(((0.0, 0.0, 0.0), (1.0, 2.0, 3.0)))
    scene = Scene("points").add(
        cloud,
        name="samples",
        style=DisplayStyle(color=(0.9, 0.6, 0.1), point_size=8.0),
    )

    prepared = prepare_scene(scene, tolerance=1e-3)

    assert prepared.lines == ()
    assert len(prepared.meshes) == 1
    assert prepared.meshes[0].name == "samples"
    assert prepared.meshes[0].render_mode == "points"
    assert prepared.meshes[0].point_size == 8.0
    assert prepared.meshes[0].color == (0.9, 0.6, 0.1)
    np.testing.assert_allclose(
        prepared.meshes[0].vertices,
        [[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]],
    )
    np.testing.assert_array_equal(
        prepared.meshes[0].faces,
        np.empty((0, 3), dtype=np.uint32),
    )
    np.testing.assert_array_equal(
        prepared.meshes[0].edges,
        np.empty((0, 2), dtype=np.uint32),
    )


def test_wireframe_mesh_edges_use_style_color() -> None:
    mesh = Mesh3(
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.5)),
        (),
        ((0, 1),),
    )
    scene = Scene("orange edge").add(
        mesh,
        style=DisplayStyle(color=(1.0, 0.3, 0.1), render_mode="wireframe"),
    )

    prepared = prepare_scene(scene, tolerance=1e-3)

    assert _mesh_edge_color(prepared.meshes[0]) == (1.0, 0.3, 0.1)


def test_camera_orientation_maps_camera_position_to_view_z() -> None:
    camera = Camera.look_at(position=(0.0, -2.0, 0.0), target=(0.0, 0.0, 0.0))

    orientation = _camera_orientation(camera)
    view_direction = np.array(camera.position, dtype=np.float32) @ orientation[:3, :3]

    np.testing.assert_allclose(view_direction, [0.0, 0.0, 2.0], atol=1e-6)


def test_pan_moves_view_without_changing_orbit_orientation() -> None:
    camera = Camera.perspective(
        position=(0.0, -10.0, 0.0),
        target=(0.0, 0.0, 0.0),
    )
    state = ViewerInteractionState.from_camera(
        camera,
        local_center=np.zeros(3, dtype=np.float32),
        radius=5.0,
    )
    orientation = state.orientation.copy()
    units_per_pixel = pan_world_units_per_pixel(
        camera,
        distance=state.distance,
        orthographic_scale=state.orthographic_scale,
        viewport_size=(900, 700),
    )

    state.pan_by_pixels(70.0, 35.0, (900, 700))

    np.testing.assert_allclose(state.orientation, orientation)
    np.testing.assert_allclose(
        state.pan,
        [70.0 * units_per_pixel, -35.0 * units_per_pixel],
        rtol=1e-6,
    )
    view = state.view_matrix()
    assert view[3, 0] == pytest.approx(state.pan[0])
    assert view[3, 1] == pytest.approx(state.pan[1])
    assert view[3, 2] == pytest.approx(-state.distance)


def test_perspective_pan_speed_tracks_camera_distance() -> None:
    camera = Camera.perspective(
        position=(0.0, -10.0, 0.0),
        target=(0.0, 0.0, 0.0),
    )
    state = ViewerInteractionState.from_camera(
        camera,
        local_center=np.zeros(3, dtype=np.float32),
        radius=5.0,
    )

    state.distance = 10.0
    state.pan_by_pixels(10.0, 0.0, (900, 700))
    near_pan = float(state.pan[0])
    state.pan[:] = 0.0
    state.distance = 20.0
    state.pan_by_pixels(10.0, 0.0, (900, 700))

    assert state.pan[0] == pytest.approx(near_pan * 2.0)


def test_orthographic_pan_speed_tracks_view_scale() -> None:
    camera = Camera.orthographic(
        position=(0.0, -10.0, 0.0),
        target=(0.0, 0.0, 0.0),
        scale=100.0,
    )
    state = ViewerInteractionState.from_camera(
        camera,
        local_center=np.zeros(3, dtype=np.float32),
        radius=5.0,
    )

    state.orthographic_scale = 100.0
    state.pan_by_pixels(10.0, 0.0, (900, 700))
    near_pan = float(state.pan[0])
    state.pan[:] = 0.0
    state.orthographic_scale = 200.0
    state.pan_by_pixels(10.0, 0.0, (900, 700))

    assert state.pan[0] == pytest.approx(near_pan * 2.0)


def test_orthographic_zoom_changes_scale_instead_of_camera_distance() -> None:
    scale = 152_661.0
    radius = 181_739.0

    zoomed_in = _zoomed_orthographic_scale(scale, 1.0, radius)
    zoomed_out = _zoomed_orthographic_scale(scale, -1.0, radius)

    assert zoomed_in < scale
    assert zoomed_out > scale
    assert _zoomed_orthographic_scale(radius, 1_000.0, radius) < radius * 0.001
    assert _zoomed_orthographic_scale(
        radius,
        1_000.0,
        radius,
        minimum=radius * 0.001,
    ) == pytest.approx(radius * 0.001)


def test_projection_clip_planes_extend_beyond_camera_far_when_needed() -> None:
    camera = Camera.orthographic(
        position=(0.0, -10.0, 0.0),
        target=(0.0, 0.0, 0.0),
        scale=1.0,
    )

    near, far = _projection_clip_planes(2_000_000.0, 10.0, camera)

    assert near > 0.0
    assert far > camera.far


def test_orthographic_axis_length_tracks_view_scale() -> None:
    near = _view_relative_orthographic_axis_length(100.0, (900, 700))
    far = _view_relative_orthographic_axis_length(200.0, (900, 700))

    assert far == pytest.approx(near * 2.0)


def test_scale_bar_starts_at_one_unit_then_steps_down_when_zoomed_in() -> None:
    one_unit = _scale_bar_for_visible_height(7.0, (900, 700))
    zoomed_in = _scale_bar_for_visible_height(1.4, (900, 700))
    zoomed_in_further = _scale_bar_for_visible_height(0.7, (900, 700))

    assert one_unit.label == "1 unit"
    assert one_unit.length_units == pytest.approx(1.0)
    assert zoomed_in.label == "1e-1 units"
    assert zoomed_in.length_units == pytest.approx(0.1)
    assert zoomed_in.width_pixels < one_unit.width_pixels
    assert zoomed_in_further.label == "1e-1 units"
    assert zoomed_in_further.width_pixels > zoomed_in.width_pixels


def test_scale_bar_steps_up_when_one_unit_would_be_too_small() -> None:
    zoomed_out = _scale_bar_for_visible_height(70.0, (900, 700))

    assert zoomed_out.label == "1e1 units"
    assert zoomed_out.length_units == pytest.approx(10.0)
    assert zoomed_out.width_pixels == pytest.approx(100.0)


def test_scale_bar_is_only_available_for_orthographic_cameras() -> None:
    orthographic = _scale_bar_for_camera(
        Camera.orthographic(position=(0, -4, 2), target=(0, 0, 0), scale=7.0),
        distance=4.5,
        orthographic_scale=7.0,
        viewport_size=(900, 700),
    )
    perspective = _scale_bar_for_camera(
        Camera.perspective(position=(0, -4, 2), target=(0, 0, 0), fov_degrees=45.0),
        distance=4.5,
        orthographic_scale=7.0,
        viewport_size=(900, 700),
    )

    assert orthographic is not None
    assert orthographic.label == "1 unit"
    assert perspective is None


def test_orientation_edges_hide_coplanar_triangle_diagonal() -> None:
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
        ],
        dtype=np.float32,
    )
    faces = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.uint32)

    edges = {tuple(sorted(edge)) for edge in _orientation_edges(vertices, faces).tolist()}

    assert edges == {(0, 1), (1, 2), (2, 3), (0, 3)}


def test_flat_face_buffers_duplicate_vertices_per_face() -> None:
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )
    faces = np.array([[0, 1, 2], [0, 3, 1]], dtype=np.uint32)

    render_vertices, render_faces, render_normals = _flat_face_buffers(vertices, faces)

    assert len(render_vertices) == 6
    assert render_faces[0, 0] != render_faces[1, 0]
    np.testing.assert_allclose(
        render_normals[render_faces[0, 0]],
        [0.0, 0.0, 1.0],
        atol=1e-6,
    )
    np.testing.assert_allclose(
        render_normals[render_faces[1, 0]],
        [0.0, 1.0, 0.0],
        atol=1e-6,
    )
