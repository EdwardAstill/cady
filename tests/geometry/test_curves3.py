from __future__ import annotations

from math import pi

import numpy as np
import pytest

from cady import arc3, line3, polyline3, spline3
from cady.errors import GeometryError
from cady.geometry.arc import Arc3
from cady.geometry.mesh import Mesh3
from cady.geometry.polyline import (
    Line3,
    Polyline3,
)
from cady.geometry.spline import Spline3


def _face_normal_z(mesh: Mesh3, face: tuple[int, int, int]) -> float:
    a, b, c = (mesh.vertices[index] for index in face)
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    return ab[0] * ac[1] - ab[1] * ac[0]


def test_closed_polyline3_planar_square_to_mesh() -> None:
    polyline = Polyline3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        closed=True,
    )

    mesh = polyline.to_mesh(tolerance=1e-3)

    assert isinstance(mesh, Mesh3)
    assert mesh.vertices == (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 1.0, 0.0),
    )
    assert len(mesh.faces) == 2
    assert mesh.edges == ((0, 1), (1, 2), (2, 3), (3, 0))
    assert all(_face_normal_z(mesh, face) > 0.0 for face in mesh.faces)


def test_arc3_samples_in_custom_plane() -> None:
    arc = Arc3(
        (0.0, 0.0, 0.0),
        2.0,
        -pi / 2.0,
        pi / 2.0,
        x_axis=(0.0, 0.0, -1.0),
        y_axis=(0.0, 1.0, 0.0),
    )

    assert arc.points()[0] == pytest.approx((0.0, -2.0, 0.0))
    assert arc.points()[-1] == pytest.approx((0.0, 2.0, 0.0))

    array = arc.to_array(tolerance=1e-3)

    assert isinstance(array, np.ndarray)
    assert array.shape[1] == 3
    assert len(array) > 2
    assert array[len(array) // 2].tolist() == pytest.approx(
        [0.0, 0.0, -2.0]
    )


def test_line3_factory_and_sampling() -> None:
    line = line3((0.0, 0.0, 0.0), (1.0, 2.0, 3.0))

    assert isinstance(line, Line3)
    assert line.points() == ((0.0, 0.0, 0.0), (1.0, 2.0, 3.0))
    assert line.to_array(tolerance=1e-3).tolist() == [
        [0.0, 0.0, 0.0],
        [1.0, 2.0, 3.0],
    ]


def test_curve3_length_properties_are_exact_for_lines_and_arcs() -> None:
    line = Line3((0.0, 0.0, 0.0), (2.0, 3.0, 6.0))
    arc = Arc3((0.0, 0.0, 0.0), 2.0, 0.0, pi / 2.0)
    polyline = Polyline3((line, arc))

    assert line.length == pytest.approx(7.0)
    assert arc.length == pytest.approx(pi)
    assert polyline.length == pytest.approx(7.0 + pi)


def test_spline3_factory_and_adaptive_sampling() -> None:
    spline = spline3(
        (
            (0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
            (1.0, 0.0, 0.0),
        )
    )

    array = spline.to_array(tolerance=1e-2)

    assert isinstance(spline, Spline3)
    assert array[0].tolist() == pytest.approx([0.0, 0.0, 0.0])
    assert array[-1].tolist() == pytest.approx([1.0, 0.0, 0.0])
    assert len(array) > 2


def test_polyline3_composes_curves_and_discretises_to_lines() -> None:
    line = Line3((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    arc = Arc3(
        (1.0, 1.0, 0.0),
        1.0,
        -pi / 2.0,
        0.0,
    )
    spline = Spline3(
        (
            (2.0, 1.0, 0.0),
            (2.0, 2.0, 0.0),
            (3.0, 2.0, 0.0),
            (3.0, 1.0, 0.0),
        )
    )

    polyline = polyline3((line,)).add(arc).add(spline)
    discretised = polyline.discretise(tolerance=1e-2)
    discretized = polyline.discretize(tolerance=1e-2)

    assert isinstance(polyline, Polyline3)
    assert polyline.curves == (line, arc, spline)
    assert polyline.vertices[0] == (0.0, 0.0, 0.0)
    assert polyline.vertices[-1] == (3.0, 1.0, 0.0)
    assert all(isinstance(curve, Line3) for curve in discretised.curves)
    assert discretised.vertices == discretized.vertices
    assert discretised.vertices[0] == (0.0, 0.0, 0.0)
    assert discretised.vertices[-1] == (3.0, 1.0, 0.0)
    assert len(polyline.to_array(tolerance=1e-2)) == len(discretised.vertices)


def test_arc3_factory_and_polyline_from_curves() -> None:
    arc = arc3(
        (0.0, 0.0, 0.0),
        1.0,
        0.0,
        pi,
        x_axis=(1.0, 0.0, 0.0),
        y_axis=(0.0, 0.0, 1.0),
    )

    polyline = Polyline3.from_curves((arc,), tolerance=1e-3)

    assert isinstance(arc, Arc3)
    assert polyline.vertices[0] == pytest.approx((1.0, 0.0, 0.0))
    assert polyline.vertices[-1] == pytest.approx((-1.0, 0.0, 0.0))
    assert len(polyline.vertices) > 2


def test_closed_polyline3_rejects_non_planar_loop() -> None:
    polyline = Polyline3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 1.0),
            (0.0, 1.0, 0.0),
        ),
        closed=True,
    )

    with pytest.raises(GeometryError, match="non-planar"):
        polyline.to_mesh(tolerance=1e-3)


def test_polyline3_is_open_wire_data_without_to_mesh() -> None:
    polyline = Polyline3(((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)))

    assert polyline.points() == ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    with pytest.raises(GeometryError, match="must be closed"):
        polyline.to_mesh(tolerance=1e-3)


def test_closed_polyline3_dedupes_repeated_final_vertex() -> None:
    polyline = Polyline3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0),
        ),
        closed=True,
    )

    assert polyline.vertices == (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    )
    assert polyline.points() == (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0),
    )
    assert len(polyline.to_mesh(tolerance=1e-3).vertices) == 3


def test_closed_polyline3_to_array_omits_repeated_closing_vertex() -> None:
    polyline = Polyline3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        closed=True,
    )

    array = polyline.to_array(tolerance=1e-3)

    assert array.tolist() == [
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ]
