"""Smoke tests for VisPy viewer. ViSpy is optional — tests are skipped when absent."""

from __future__ import annotations

import importlib
from unittest import mock

import numpy as np
import pytest


def test_vispy_viewer_module_imports() -> None:
    """The module must be importable regardless of vispy presence."""
    from cady.visualisation.vispy_viewer import vispy_view_mesh, vispy_view_meshes

    assert vispy_view_mesh
    assert vispy_view_meshes


def test_require_vispy_raises_when_missing() -> None:
    """_require_vispy raises ImportError when vispy is not installed."""
    with mock.patch("cady.visualisation.vispy_viewer._HAS_VISPY", False):
        from cady.visualisation.vispy_viewer import _require_vispy

        with pytest.raises(ImportError, match="requires vispy"):
            _require_vispy()


def test_require_vispy_passes_when_present() -> None:
    """_require_vispy does not raise when vispy is installed."""
    from cady.visualisation.vispy_viewer import _require_vispy

    # Should not raise — vispy is installed in the test environment.
    _require_vispy()


def test_orientation_edges_hide_coplanar_triangle_diagonal() -> None:
    from cady.visualisation.vispy_viewer import _orientation_edges

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


def test_orientation_edges_hide_nearly_flat_face_change() -> None:
    from math import cos, radians, sin

    from cady.visualisation.vispy_viewer import _orientation_edges

    angle = radians(5.0)
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, -cos(angle), sin(angle)],
        ],
        dtype=np.float32,
    )
    faces = np.array([[0, 1, 2], [0, 3, 1]], dtype=np.uint32)

    edges = {tuple(sorted(edge)) for edge in _orientation_edges(vertices, faces).tolist()}

    assert (0, 1) not in edges


def test_orientation_edges_keep_isolated_shallow_crease() -> None:
    from math import cos, radians, sin

    from cady.visualisation.vispy_viewer import _orientation_edges

    angle = radians(20.0)
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, -cos(angle), sin(angle)],
        ],
        dtype=np.float32,
    )
    faces = np.array([[0, 1, 2], [0, 3, 1]], dtype=np.uint32)

    edges = {tuple(sorted(edge)) for edge in _orientation_edges(vertices, faces).tolist()}

    assert (0, 1) in edges


def test_orientation_edges_keep_cube_crease_edges() -> None:
    from cady import prism
    from cady.visualisation.vispy_viewer import _orientation_edges

    mesh = prism((0, 0, 0), (1, 1, 1)).to_array(tolerance=1e-2)
    vertices = np.array(mesh.vertices, dtype=np.float32)
    faces = np.array(mesh.faces, dtype=np.uint32)

    visible_edges = _orientation_edges(vertices, faces)

    assert len(visible_edges) == 12


def test_orientation_edges_hide_small_circle_extrusion_side_facets() -> None:
    from cady import circle
    from cady.visualisation.vispy_viewer import _orientation_edges

    mesh = circle((0, 0), 0.1).extrude("+z", 0.04).to_array(tolerance=1e-3)
    vertices = np.array(mesh.vertices, dtype=np.float32)
    faces = np.array(mesh.faces, dtype=np.uint32)

    visible_edges = _orientation_edges(vertices, faces)
    vertical_edges = [
        edge
        for edge in visible_edges
        if abs(float(vertices[edge[0], 2] - vertices[edge[1], 2])) > 1e-7
    ]
    segment_count = len(
        {(round(float(vertex[0]), 9), round(float(vertex[1]), 9)) for vertex in vertices}
    )

    assert vertical_edges == []
    assert len(visible_edges) == segment_count * 2


def test_orientation_edges_suppress_extrusion_cap_artifacts() -> None:
    from cady import circle, rectangle
    from cady.ops.tessellate import curves_to_polyline
    from cady.visualisation.vispy_viewer import _orientation_edges

    profile = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))
    mesh = profile.extrude("+z", 0.04).to_array(tolerance=1e-3)
    vertices = np.array(mesh.vertices, dtype=np.float32)
    faces = np.array(mesh.faces, dtype=np.uint32)

    visible_edges = _orientation_edges(vertices, faces)

    vertical_edges = [
        edge
        for edge in visible_edges
        if abs(float(vertices[edge[0], 2] - vertices[edge[1], 2])) > 1e-7
    ]
    outer_segment_count = len(
        {point.tuple() for point in curves_to_polyline(profile, tolerance=1e-3).points()}
    )
    hole_segment_count = len(
        {
            point.tuple()
            for point in curves_to_polyline(profile.inner_loops[0], tolerance=1e-3).points()
        }
    )

    assert len(vertical_edges) == outer_segment_count
    assert len(visible_edges) == (outer_segment_count + hole_segment_count) * 2 + len(
        vertical_edges
    )


def test_orientation_edges_hide_smooth_sphere_tessellation() -> None:
    from cady import sphere
    from cady.visualisation.vispy_viewer import _orientation_edges

    mesh = sphere((0, 0, 0), 0.5).to_array(tolerance=1e-3)
    vertices = np.array(mesh.vertices, dtype=np.float32)
    faces = np.array(mesh.faces, dtype=np.uint32)

    visible_edges = _orientation_edges(vertices, faces)

    assert len(visible_edges) == 0


def test_shaded_face_buffers_share_normals_across_smooth_join() -> None:
    from math import cos, radians, sin

    from cady.visualisation.vispy_viewer import _shaded_face_buffers

    angle = radians(5.0)
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, -cos(angle), sin(angle)],
        ],
        dtype=np.float32,
    )
    faces = np.array([[0, 1, 2], [0, 3, 1]], dtype=np.uint32)

    render_vertices, render_faces, render_normals = _shaded_face_buffers(vertices, faces)

    assert len(render_vertices) == 4
    assert render_faces[0, 0] == render_faces[1, 0]
    assert render_faces[0, 1] == render_faces[1, 2]
    np.testing.assert_allclose(
        np.linalg.norm(render_normals, axis=1),
        np.ones(len(render_normals)),
        atol=1e-6,
    )


def test_shaded_face_buffers_split_normals_at_hard_crease() -> None:
    from cady.visualisation.vispy_viewer import _shaded_face_buffers

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
    assert render_faces[0, 1] != render_faces[1, 2]
    np.testing.assert_allclose(
        render_normals[render_faces[0, 0]],
        [0.0, 0.0, 1.0],
        atol=1e-6,
    )
    np.testing.assert_allclose(
        np.abs(render_normals[render_faces[1, 0]]),
        [0.0, 1.0, 0.0],
        atol=1e-6,
    )


def test_model_matrix_maps_local_centre_to_global_origin() -> None:
    from cady.visualisation.vispy_viewer import _apply_view_orbit, _model_matrix

    centre = np.array([10.0, -5.0, 3.0], dtype=np.float32)
    orientation = _apply_view_orbit(np.eye(4, dtype=np.float32), 30.0, 20.0)

    transformed = np.array([*centre, 1.0], dtype=np.float32) @ _model_matrix(centre, orientation)

    np.testing.assert_allclose(transformed, [0.0, 0.0, 0.0, 1.0], atol=1e-6)


def test_view_orbit_uses_screen_axes_after_existing_local_rotation() -> None:
    from cady.visualisation.vispy_viewer import _apply_view_orbit, _rotation_matrix

    orientation = _rotation_matrix(90.0, (1.0, 0.0, 0.0))
    orientation = _apply_view_orbit(orientation, 90.0, 0.0)

    transformed = np.array([0.0, 0.0, 1.0, 1.0], dtype=np.float32) @ orientation

    np.testing.assert_allclose(transformed[:3], [0.0, -1.0, 0.0], atol=1e-6)


@pytest.mark.skipif(
    importlib.util.find_spec("vispy") is None,
    reason="VisPy not installed.",
)
def test_vispy_view_mesh_with_real_data() -> None:
    """Canvas can be constructed with real mesh data (no display needed)."""
    from cady import prism
    from cady.visualisation.vispy_viewer import _make_canvas

    mesh = prism((0, 0, 0), (1, 1, 1)).to_array(tolerance=1e-2)
    import numpy as np

    vertices = np.array(mesh.vertices, dtype=np.float32)
    faces = np.array(mesh.faces, dtype=np.uint32)
    from cady.visualisation.vispy_viewer import _orientation_edges

    edges = _orientation_edges(vertices, faces)

    canvas = _make_canvas(
        [vertices],
        [faces],
        [np.tile(np.array((0.0, 0.0, 1.0), dtype=np.float32), (len(vertices), 1))],
        [(0.5, 0.6, 0.8)],
        [vertices],
        [edges],
        (0.1, 0.1, 0.1),
        title="test",
    )
    assert canvas is not None
