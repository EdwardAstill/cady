from __future__ import annotations

from math import pi, sqrt

import pytest

from cady.errors import GeometryError
from cady.geometry.arc import Arc3
from cady.geometry.line import Line3
from cady.geometry.mesh import Mesh3
from cady.geometry.point import Point3
from cady.geometry.polyline import (
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
        (0.0, -2.0, 0.0),
        (0.0, 0.0, -2.0),
    )

    assert arc.points()[0] == pytest.approx((0.0, -2.0, 0.0))
    assert arc.points()[-1] == pytest.approx((0.0, 2.0, 0.0))

    assert not hasattr(arc, "to_array")

    polyline = arc.discretize(tolerance=1e-3)
    assert len(polyline.vertices) > 2
    assert polyline.vertices[len(polyline.vertices) // 2] == pytest.approx(
        (0.0, 0.0, -2.0)
    )

    coarse = arc.discretize(tolerance=1.0, min_segments=1)
    limited = arc.discretize(tolerance=1.0, max_segment_length=0.25)
    assert len(limited.vertices) > len(coarse.vertices)


def test_line3_factory_and_sampling() -> None:
    line = Line3((0.0, 0.0, 0.0), (1.0, 2.0, 3.0))

    assert isinstance(line, Line3)
    assert isinstance(line.start, Point3)
    assert line.points() == ((0.0, 0.0, 0.0), (1.0, 2.0, 3.0))
    assert line.to_array(tolerance=1e-3).tolist() == [
        [0.0, 0.0, 0.0],
        [1.0, 2.0, 3.0],
    ]


def test_curve3_length_properties_are_exact_for_lines_and_arcs() -> None:
    line = Line3((0.0, 0.0, 0.0), (2.0, 3.0, 6.0))
    arc = Arc3(
        (0.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        (sqrt(2.0), sqrt(2.0), 0.0),
    )
    polyline = Polyline3((line, arc))

    assert line.length == pytest.approx(7.0)
    assert arc.length == pytest.approx(pi)
    assert polyline.length == pytest.approx(7.0 + pi)


def test_spline3_length_property_contributes_to_polyline_length() -> None:
    spline = Spline3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (3.0, 0.0, 0.0),
        )
    )
    line = Line3((3.0, 0.0, 0.0), (3.0, 4.0, 0.0))
    polyline = Polyline3((spline, line))

    assert spline.length == pytest.approx(3.0)
    assert polyline.length == pytest.approx(7.0)


def test_spline3_factory_and_adaptive_sampling() -> None:
    spline = Spline3(
        (
            (0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (1.0, 1.0, 0.0),
            (1.0, 0.0, 0.0),
        )
    )

    polyline = spline.discretize(tolerance=1e-2)

    assert isinstance(spline, Spline3)
    assert not hasattr(spline, "to_array")
    assert polyline.vertices[0] == pytest.approx((0.0, 0.0, 0.0))
    assert polyline.vertices[-1] == pytest.approx((1.0, 0.0, 0.0))
    assert len(polyline.vertices) > 2


def test_spline3_can_be_defined_by_points_and_vectors() -> None:
    spline = Spline3(
        ((0.0, 0.0, 0.0), (3.0, 0.0, 0.0)),
        ((3.0, 0.0, 0.0), (3.0, 0.0, 0.0)),
    )

    assert spline.control_points == (
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        (3.0, 0.0, 0.0),
    )
    assert isinstance(spline.control_points[0], Point3)
    assert spline.length == pytest.approx(3.0)


def test_polyline3_composes_curves_and_discretizes_to_lines() -> None:
    line = Line3((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    arc = Arc3(
        (1.0, 1.0, 0.0),
        (1.0, 0.0, 0.0),
        (1.0 + 2.0**-0.5, 1.0 - 2.0**-0.5, 0.0),
    )
    spline = Spline3(
        (
            (2.0, 1.0, 0.0),
            (2.0, 2.0, 0.0),
            (3.0, 2.0, 0.0),
            (3.0, 1.0, 0.0),
        )
    )

    polyline = Polyline3((line,)).add(arc).add(spline)
    discretized = polyline.discretize(tolerance=1e-2)

    assert isinstance(polyline, Polyline3)
    assert polyline.curves == (line, arc, spline)
    assert polyline.vertices[0] == (0.0, 0.0, 0.0)
    assert polyline.vertices[-1] == (3.0, 1.0, 0.0)
    assert all(isinstance(curve, Line3) for curve in discretized.curves)
    assert discretized.vertices[0] == (0.0, 0.0, 0.0)
    assert discretized.vertices[-1] == (3.0, 1.0, 0.0)
    with pytest.raises(GeometryError, match="discretize"):
        polyline.to_array(tolerance=1e-2)
    assert len(discretized.to_array(tolerance=1e-2)) == len(discretized.vertices)


def test_arc3_factory_and_polyline_from_curves() -> None:
    arc = Arc3(
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
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


def test_polyline3_start_end_and_reverse_preserves_line_segments() -> None:
    first = Line3((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))
    second = Line3((1.0, 0.0, 0.0), (1.0, 2.0, 0.0))
    polyline = Polyline3((first, second))

    assert polyline.start == (0.0, 0.0, 0.0)
    assert polyline.end == (1.0, 2.0, 0.0)

    reversed_polyline = polyline.reverse()

    assert reversed_polyline.start == (1.0, 2.0, 0.0)
    assert reversed_polyline.end == (0.0, 0.0, 0.0)
    assert reversed_polyline.curves == (
        Line3((1.0, 2.0, 0.0), (1.0, 0.0, 0.0)),
        Line3((1.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
    )


def test_polyline3_discontinuities_return_sharp_turn_vertices() -> None:
    polyline = Polyline3(
        (
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 0.0, 1.0),
        )
    )

    assert polyline.discontinuities(min_angle_degrees=45.0) == ((2.0, 0.0, 0.0),)
    assert polyline.discontinuities(min_angle_degrees=100.0) == ()


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
