from __future__ import annotations

from unittest import mock

import numpy as np
import pytest

from cady import (
    Camera,
    DirectionalLight,
    DisplayStyle,
    Document,
    Mesh3,
    Part,
    PointCloud3,
    Scene,
    box,
)
from cady.view.vispy_viewer import (
    _camera_orientation,
    _mesh_edge_color,
    _orientation_edges,
    _require_vispy,
    _select_vispy_shader_backend,
    _shaded_face_buffers,
    _transform_from_pose,
    _view_relative_orthographic_axis_length,
    _zoomed_orthographic_scale,
    prepare_scene,
)


def test_vispy_viewer_module_imports_without_opening_window() -> None:
    from cady.view import prepare_scene, view_mesh, view_scene, view_target

    assert all((prepare_scene, view_mesh, view_scene, view_target))


def test_require_vispy_raises_when_missing() -> None:
    with (
        mock.patch("cady.view.vispy_viewer._HAS_VISPY", False),
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


def test_prepare_scene_uses_new_scene_camera_light_and_style() -> None:
    scene = (
        Scene("review")
        .add(box(1.0, 0.5, 0.25), style=DisplayStyle(color=(0.2, 0.4, 0.8)))
        .with_camera(
            Camera.perspective(
                position=(1.0, -2.0, 1.5),
                target=(0.0, 0.0, 0.0),
                fov_degrees=35.0,
            ),
            name="iso",
        )
        .with_light(DirectionalLight(direction=(-1.0, -1.0, -2.0), intensity=0.5))
    )

    prepared = prepare_scene(scene, tolerance=1e-3)

    assert prepared.name == "review"
    assert prepared.camera.fov_degrees == 35.0
    assert len(prepared.meshes) == 1
    assert prepared.meshes[0].color == (0.2, 0.4, 0.8)
    assert prepared.meshes[0].vertices.shape[1] == 3
    assert prepared.meshes[0].faces.shape[1] == 3
    assert prepared.light_direction == (-1.0, -1.0, -2.0)


def test_transform_from_pose_preserves_viewer_message() -> None:
    with pytest.raises(
        TypeError,
        match="scene object pose must be Transform3, Pose3-like, or a 3D translation",
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


def test_prepare_scene_accepts_document_targets() -> None:
    document = Document("job").add_part(Part("box").with_body(box(1.0, 0.5, 0.25)))
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


def test_orthographic_zoom_changes_scale_instead_of_camera_distance() -> None:
    scale = 152_661.0
    radius = 181_739.0

    zoomed_in = _zoomed_orthographic_scale(scale, 1.0, radius)
    zoomed_out = _zoomed_orthographic_scale(scale, -1.0, radius)

    assert zoomed_in < scale
    assert zoomed_out > scale
    assert _zoomed_orthographic_scale(radius, 1_000.0, radius) == pytest.approx(
        radius * 0.001
    )


def test_orthographic_axis_length_tracks_view_scale() -> None:
    near = _view_relative_orthographic_axis_length(100.0, (900, 700))
    far = _view_relative_orthographic_axis_length(200.0, (900, 700))

    assert far == pytest.approx(near * 2.0)


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


def test_shaded_face_buffers_split_normals_at_hard_crease() -> None:
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

    render_vertices, render_faces, render_normals = _shaded_face_buffers(vertices, faces)

    assert len(render_vertices) == 6
    assert render_faces[0, 0] != render_faces[1, 0]
    np.testing.assert_allclose(
        render_normals[render_faces[0, 0]],
        [0.0, 0.0, 1.0],
        atol=1e-6,
    )
