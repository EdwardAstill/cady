from __future__ import annotations

import pytest

from cady.geometry import Circle2, Line2, Line3, Plane3, PointCloud3, Region2, Surface3
from cady.geometry.mesh import Mesh2, Mesh3
from cady.geometry.polyline import Polyline2
from cady.operations import discretise, distance, intersect, mesh, triangulate
from cady.operations.intersections import InfiniteLine3, LineIntersection2, LinePlaneIntersection


def test_distance_dispatches_points_lines_and_planes() -> None:
    assert distance((0.0, 0.0), (3.0, 4.0)) == 5.0
    assert distance(
        Line3((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
        Line3((0.0, 1.0, 0.0), (1.0, 1.0, 0.0)),
    ) == pytest.approx(1.0)

    plane = Plane3.world_xy()
    assert distance(Line3((0.0, 0.0, 1.0), (0.0, 0.0, 2.0)), plane) == pytest.approx(1.0)
    assert distance(Line3((0.0, 0.0, -1.0), (0.0, 0.0, 1.0)), plane) == 0.0


def test_intersect_dispatches_lines_and_planes_with_parameters() -> None:
    line_hit = intersect(
        Line2((0.0, 0.0), (1.0, 1.0)),
        Line2((0.0, 1.0), (1.0, 0.0)),
    )

    assert isinstance(line_hit, LineIntersection2)
    assert line_hit.point == pytest.approx((0.5, 0.5))
    assert line_hit.left_parameter == pytest.approx(0.5)
    assert line_hit.right_parameter == pytest.approx(0.5)

    plane_hit = intersect(Line3((0.0, 0.0, -1.0), (0.0, 0.0, 1.0)), Plane3.world_xy())

    assert isinstance(plane_hit, LinePlaneIntersection)
    assert plane_hit.point == pytest.approx((0.0, 0.0, 0.0))
    assert plane_hit.line_parameter == pytest.approx(0.5)


def test_intersect_plane_surfaces_returns_operation_line() -> None:
    first = Surface3.world_xy()
    second = Surface3.plane(origin=(0.0, 2.0, 0.0), normal=(0.0, 1.0, 0.0))

    result = intersect(first, second)

    assert isinstance(result, InfiniteLine3)
    assert result.point == pytest.approx((0.0, 2.0, 0.0))
    assert abs(result.direction[0]) == pytest.approx(1.0)
    assert result.direction[1] == pytest.approx(0.0)
    assert result.direction[2] == pytest.approx(0.0)


def test_discretise_dispatches_closed_curve_to_polyline() -> None:
    polyline = discretise(Circle2((0.0, 0.0), 1.0), tolerance=1e-2)

    assert isinstance(polyline, Polyline2)
    assert polyline.closed is True
    assert len(polyline.vertices) > 8


def test_mesh_dispatches_closed_curve_region_surface_region_and_point_cloud() -> None:
    curve_mesh = mesh(Circle2((0.0, 0.0), 1.0), tolerance=1e-2)
    assert isinstance(curve_mesh, Mesh2)
    assert len(curve_mesh.faces) > 1

    region_mesh = mesh(Region2.rectangle(1.0, 2.0), tolerance=1e-3)
    assert isinstance(region_mesh, Mesh2)
    assert len(region_mesh.faces) == 2

    surface = Surface3.parametric(lambda u, v: u, lambda u, v: v, lambda u, v: u + v)
    surface_mesh = mesh(Region2.rectangle(1.0, 1.0), surface=surface, tolerance=1e-3)
    assert isinstance(surface_mesh, Mesh3)
    assert surface_mesh.bounds() == ((0.0, 0.0, 0.0), (1.0, 1.0, 2.0))

    cloud_mesh = mesh(PointCloud3(((0.0, 0.0, 0.0), (1.0, 2.0, 3.0))), tolerance=1e-3)
    assert isinstance(cloud_mesh, Mesh3)
    assert cloud_mesh.vertices == ((0.0, 0.0, 0.0), (1.0, 2.0, 3.0))
    assert cloud_mesh.faces == ()


def test_triangulate_dispatches_raw_polygon_and_meshable_values() -> None:
    triangles = triangulate(((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)), tolerance=1e-3)
    assert len(triangles) == 1
    assert set(triangles[0]) == {(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)}

    triangulated = triangulate(Circle2((0.0, 0.0), 1.0), tolerance=1e-2)
    assert isinstance(triangulated, Mesh2)
