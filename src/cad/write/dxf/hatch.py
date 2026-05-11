from __future__ import annotations

from cad.geom.base import Shape2D
from cad.geom.tessellate import curves_to_polyline
from cad.geom.vec import Vec2
from cad.scene.dxf import HatchEntity
from cad.write.dxf.codes import LAYER, X, Y, Z
from cad.write.dxf.emit import pairs


def hatch_boundary_points(boundary: Shape2D) -> tuple[Vec2, ...]:
    points = boundary.points()
    if len(points) < 4 or points[0] == points[1]:
        points = curves_to_polyline(boundary, tolerance=1e-3).points()
    if points[0] == points[-1]:
        points = points[:-1]
    return points


def _boundary_path(points: tuple[Vec2, ...], flags: int) -> list[tuple[int, object]]:
    items: list[tuple[int, object]] = [
        (92, flags),
        (72, 0),
        (73, 1),
        (93, len(points)),
    ]
    for vertex in points:
        items.extend(((X, vertex.x), (Y, vertex.y)))
    items.append((97, 0))
    return items


def hatch_entity(hatch: HatchEntity) -> list[str]:
    loops = (hatch.boundary, *hatch.boundary.inner_loops)
    items: list[tuple[int, object]] = [
        (0, "HATCH"),
        (100, "AcDbEntity"),
        (LAYER, hatch.layer),
        (100, "AcDbHatch"),
        (X, 0.0),
        (Y, 0.0),
        (Z, 0.0),
        (210, 0.0),
        (220, 0.0),
        (230, 1.0),
        (2, hatch.pattern),
        (70, 0),
        (71, 0),
        (91, len(loops)),
    ]
    for index, loop in enumerate(loops):
        items.extend(_boundary_path(hatch_boundary_points(loop), 3 if index == 0 else 18))
    items.extend(
        (
            (75, 1),
            (76, 1),
            (52, hatch.angle),
            (41, hatch.scale),
            (77, 0),
            (78, 1),
            (53, 90.0),
            (43, 0.0),
            (44, 0.0),
            (45, -3.175 * hatch.scale),
            (46, 0.0),
            (79, 0),
            (98, 0),
        )
    )
    return pairs(items)
