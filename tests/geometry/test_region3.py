from __future__ import annotations

from cady.geometry import Polyline2, Region2, Region3, Surface2, Surface3
from cady.geometry.surface import Surface2 as Surface2FromModule
from cady.operations.arrays import PointArray2, as_points2


class TriangleRegion:
    @property
    def boundary(self) -> tuple[tuple[float, float], tuple[float, float]]:
        return (0.0, 0.0), (1.0, 1.0)

    @property
    def closed(self) -> bool:
        return True

    def to_array(self, *, tolerance: float) -> PointArray2:
        return as_points2(((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)), name="vertices")


def test_surface2_parametric_functions_define_points() -> None:
    surface = Surface2.parametric(lambda u, v: u + 1.0, lambda u, v: v * 2.0)

    assert Surface2 is Surface2FromModule
    assert surface.point(2.0, 3.0) == (3.0, 6.0)
    assert Surface2.world_xy().point(2.0, 3.0) == (2.0, 3.0)


def test_surface3_parametric_functions_define_points_and_normals() -> None:
    surface = Surface3.parametric(
        lambda u, v: u,
        lambda u, v: v,
        lambda u, v: u + v,
    )

    assert surface.point(2.0, 3.0) == (2.0, 3.0, 5.0)
    normal = surface.normal(0.0, 0.0)
    assert normal[0] < 0.0
    assert normal[1] < 0.0
    assert normal[2] > 0.0


def test_region_from_region_meshes_single_planar_cap() -> None:
    source = TriangleRegion()
    region = Region3.from_region(source)
    mesh = region.to_mesh(tolerance=1e-3)

    assert region.boundary == ((0.0, 0.0, 0.0), (1.0, 1.0, 0.0))
    assert len(mesh.faces) == 1
    assert mesh.bounds() == ((0.0, 0.0, 0.0), (1.0, 1.0, 0.0))


def test_region3_boundary_uses_region2_outer_boundary() -> None:
    boundary = Polyline2(
        ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        closed=True,
    )
    region = Region3.from_region(Region2(boundary))

    assert region.boundary == ((0.0, 0.0, 0.0), (1.0, 1.0, 0.0))


def test_region_from_region_maps_domain_through_parametric_surface() -> None:
    surface = Surface3.parametric(
        lambda u, v: u,
        lambda u, v: v,
        lambda u, v: u + v,
    )

    mesh = Region3.from_region(TriangleRegion(), surface=surface).to_mesh(tolerance=1e-3)

    assert mesh.bounds() == ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))


def test_region_from_points_projects_ordered_loop() -> None:
    region = Region3.from_points(
        (
            (0.0, 0.0, 2.0),
            (1.0, 0.0, 2.0),
            (0.0, 1.0, 2.0),
        )
    )

    assert region.to_mesh(tolerance=1e-3).bounds() == (
        (0.0, 0.0, 2.0),
        (1.0, 1.0, 2.0),
    )


def test_region_convex_hull_discards_inner_points() -> None:
    region = Region3.convex_hull(
        (
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (1.0, 0.5, 0.0),
            (2.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
        )
    )

    mesh = region.to_mesh(tolerance=1e-3)
    assert mesh.bounds() == ((0.0, 0.0, 0.0), (2.0, 2.0, 0.0))
