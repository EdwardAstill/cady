from __future__ import annotations

from math import pi

import pytest

from cady import arc3d, line3d, polyline3d, spline3d
from cady.errors import GeometryError
from cady.geometry.mesh3d import Mesh3D
from cady.geometry.polyline3d import (
    Arc3D,
    ClosedPolyline3D,
    Line3D,
    Polyline3D,
    Spline3D,
)
from cady.vec import Vec3


def _face_normal_z(mesh: Mesh3D, face: tuple[int, int, int]) -> float:
    a, b, c = (mesh.vertices[index] for index in face)
    ab = b - a
    ac = c - a
    return ab.cross(ac).z


def test_closed_polyline3d_planar_square_to_mesh() -> None:
    polyline = ClosedPolyline3D(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        )
    )

    mesh = polyline.to_mesh(tolerance=1e-3)

    assert isinstance(mesh, Mesh3D)
    assert mesh.vertices == (
        Vec3(0.0, 0.0, 0.0),
        Vec3(1.0, 0.0, 0.0),
        Vec3(1.0, 1.0, 0.0),
        Vec3(0.0, 1.0, 0.0),
    )
    assert len(mesh.faces) == 2
    assert mesh.edges == ((0, 1), (1, 2), (2, 3), (3, 0))
    assert all(_face_normal_z(mesh, face) > 0.0 for face in mesh.faces)


def test_arc3d_samples_in_custom_plane() -> None:
    arc = Arc3D(
        (0.0, 0.0, 0.0),
        2.0,
        -pi / 2.0,
        pi / 2.0,
        x_axis=(0.0, 0.0, -1.0),
        y_axis=(0.0, 1.0, 0.0),
    )

    assert arc.points()[0].tuple() == pytest.approx((0.0, -2.0, 0.0))
    assert arc.points()[-1].tuple() == pytest.approx((0.0, 2.0, 0.0))

    array = arc.to_array(tolerance=1e-3)

    assert array.vertices.shape[1] == 3
    assert len(array.vertices) > 2
    assert array.vertices[len(array.vertices) // 2].tolist() == pytest.approx(
        [0.0, 0.0, -2.0]
    )


def test_line3d_factory_and_sampling() -> None:
    line = line3d((0.0, 0.0, 0.0), (1.0, 2.0, 3.0))

    assert isinstance(line, Line3D)
    assert line.points() == (Vec3(0.0, 0.0, 0.0), Vec3(1.0, 2.0, 3.0))
    assert line.to_array(tolerance=1e-3).vertices.tolist() == [
        [0.0, 0.0, 0.0],
        [1.0, 2.0, 3.0],
    ]


def test_spline3d_factory_and_adaptive_sampling() -> None:
    spline = spline3d(
        (
            (0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
            (1.0, 0.0, 0.0),
        )
    )

    array = spline.to_array(tolerance=1e-2)

    assert isinstance(spline, Spline3D)
    assert array.vertices[0].tolist() == pytest.approx([0.0, 0.0, 0.0])
    assert array.vertices[-1].tolist() == pytest.approx([1.0, 0.0, 0.0])
    assert len(array.vertices) > 2


def test_polyline3d_composes_curves_and_discretises_to_lines() -> None:
    line = Line3D((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    arc = Arc3D(
        (1.0, 1.0, 0.0),
        1.0,
        -pi / 2.0,
        0.0,
    )
    spline = Spline3D(
        (
            (2.0, 1.0, 0.0),
            (2.0, 2.0, 0.0),
            (3.0, 2.0, 0.0),
            (3.0, 1.0, 0.0),
        )
    )

    polyline = polyline3d((line,)).add(arc).add(spline)
    discretised = polyline.discretise(tolerance=1e-2)
    discretized = polyline.discretize(tolerance=1e-2)

    assert isinstance(polyline, Polyline3D)
    assert polyline.curves == (line, arc, spline)
    assert polyline.vertices[0] == Vec3(0.0, 0.0, 0.0)
    assert polyline.vertices[-1] == Vec3(3.0, 1.0, 0.0)
    assert all(isinstance(curve, Line3D) for curve in discretised.curves)
    assert discretised.vertices == discretized.vertices
    assert discretised.vertices[0] == Vec3(0.0, 0.0, 0.0)
    assert discretised.vertices[-1] == Vec3(3.0, 1.0, 0.0)
    assert len(polyline.to_array(tolerance=1e-2).vertices) == len(discretised.vertices)


def test_arc3d_factory_and_polyline_from_curves() -> None:
    arc = arc3d(
        (0.0, 0.0, 0.0),
        1.0,
        0.0,
        pi,
        x_axis=(1.0, 0.0, 0.0),
        y_axis=(0.0, 0.0, 1.0),
    )

    polyline = Polyline3D.from_curves((arc,), tolerance=1e-3)

    assert isinstance(arc, Arc3D)
    assert polyline.vertices[0].tuple() == pytest.approx((1.0, 0.0, 0.0))
    assert polyline.vertices[-1].tuple() == pytest.approx((-1.0, 0.0, 0.0))
    assert len(polyline.vertices) > 2


def test_closed_polyline3d_rejects_non_planar_loop() -> None:
    polyline = ClosedPolyline3D(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 1.0),
            (0.0, 1.0, 0.0),
        )
    )

    with pytest.raises(GeometryError, match="non-planar"):
        polyline.to_mesh(tolerance=1e-3)


def test_polyline3d_is_open_wire_data_without_to_mesh() -> None:
    polyline = Polyline3D(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)))

    assert polyline.points() == (Vec3(0.0, 0.0, 0.0), Vec3(1.0, 0.0, 0.0))
    assert not hasattr(polyline, "to_mesh")


def test_closed_polyline3d_dedupes_repeated_final_vertex() -> None:
    polyline = ClosedPolyline3D(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0),
        )
    )

    assert polyline.vertices == (
        Vec3(0.0, 0.0, 0.0),
        Vec3(1.0, 0.0, 0.0),
        Vec3(0.0, 1.0, 0.0),
    )
    assert polyline.points() == (
        Vec3(0.0, 0.0, 0.0),
        Vec3(1.0, 0.0, 0.0),
        Vec3(0.0, 1.0, 0.0),
        Vec3(0.0, 0.0, 0.0),
    )
    assert len(polyline.to_mesh(tolerance=1e-3).vertices) == 3
