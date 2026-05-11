from __future__ import annotations

import math
from math import atan2, degrees

from cad.geom.helpers import midpoint, perpendicular
from cad.geom.vec import Vec2
from cad.scene.dxf import AngularDimensionEntity, DimensionEntity
from cad.write.dxf.emit import pairs


def _base_dimension(
    dimension: DimensionEntity,
    dimtype: int,
    defpoint: Vec2,
    block_name: str,
) -> list[tuple[int, object]]:
    text_point = midpoint(dimension.a, dimension.b)
    return [
        (0, "DIMENSION"),
        (100, "AcDbEntity"),
        (8, dimension.layer),
        (100, "AcDbDimension"),
        (2, block_name),
        (3, "Standard"),
        (10, defpoint.x),
        (20, defpoint.y),
        (30, 0.0),
        (11, text_point.x),
        (21, text_point.y),
        (31, 0.0),
        (70, dimtype),
        (71, 5),
        (1, dimension.text),
    ]


def _rotated_dimension(dimension: DimensionEntity, block_name: str) -> list[str]:
    direction = dimension.b - dimension.a
    normal = perpendicular(direction)
    defpoint = dimension.a + normal * dimension.offset
    angle = degrees(atan2(direction.y, direction.x))
    items = _base_dimension(dimension, 32, defpoint, block_name)
    items.extend(
        (
            (100, "AcDbAlignedDimension"),
            (13, dimension.a.x),
            (23, dimension.a.y),
            (33, 0.0),
            (14, dimension.b.x),
            (24, dimension.b.y),
            (34, 0.0),
            (50, angle),
            (100, "AcDbRotatedDimension"),
        )
    )
    return pairs(items)


def _radius_dimension(dimension: DimensionEntity, block_name: str) -> list[str]:
    items = _base_dimension(dimension, 36, dimension.a, block_name)
    items.extend(
        (
            (100, "AcDbRadialDimension"),
            (15, dimension.b.x),
            (25, dimension.b.y),
            (35, 0.0),
        )
    )
    return pairs(items)


def _diameter_dimension(dimension: DimensionEntity, block_name: str) -> list[str]:
    radius = dimension.b - dimension.a
    opposite = dimension.a - radius
    items = _base_dimension(dimension, 35, dimension.b, block_name)
    items.extend(
        (
            (100, "AcDbDiametricDimension"),
            (15, opposite.x),
            (25, opposite.y),
            (35, 0.0),
        )
    )
    return pairs(items)


def angular_dim_arc_point(dim: AngularDimensionEntity) -> tuple[float, float]:
    v1 = (dim.p1[0] - dim.center[0], dim.p1[1] - dim.center[1])
    v2 = (dim.p2[0] - dim.center[0], dim.p2[1] - dim.center[1])
    mag1 = math.hypot(*v1)
    mag2 = math.hypot(*v2)
    nx = v1[0] / mag1 + v2[0] / mag2
    ny = v1[1] / mag1 + v2[1] / mag2
    bm = math.hypot(nx, ny)
    if bm == 0:
        return (
            dim.center[0] - v1[1] / mag1 * dim.distance,
            dim.center[1] + v1[0] / mag1 * dim.distance,
        )
    return (
        dim.center[0] + nx / bm * dim.distance,
        dim.center[1] + ny / bm * dim.distance,
    )


def _angular_dimension(dim: AngularDimensionEntity, block_name: str) -> list[str]:
    arc_pt = angular_dim_arc_point(dim)
    items: list[tuple[int, object]] = [
        (0, "DIMENSION"),
        (100, "AcDbEntity"),
        (8, dim.layer),
        (100, "AcDbDimension"),
        (2, block_name),
        (3, dim.dimstyle),
        (10, arc_pt[0]),
        (20, arc_pt[1]),
        (30, 0.0),
        (11, arc_pt[0]),
        (21, arc_pt[1]),
        (31, 0.0),
        (70, 5),
        (1, dim.measurement_text),
        (100, "AcDb3PointAngularDimension"),
        (13, dim.p1[0]),
        (23, dim.p1[1]),
        (33, 0.0),
        (14, dim.p2[0]),
        (24, dim.p2[1]),
        (34, 0.0),
        (15, dim.center[0]),
        (25, dim.center[1]),
        (35, 0.0),
        (16, arc_pt[0]),
        (26, arc_pt[1]),
        (36, 0.0),
    ]
    return pairs(items)


def dimension_entities(
    dimension: DimensionEntity | AngularDimensionEntity, block_name: str
) -> list[str]:
    if isinstance(dimension, AngularDimensionEntity):
        return _angular_dimension(dimension, block_name)
    if dimension.kind in {"linear", "aligned"}:
        return _rotated_dimension(dimension, block_name)
    if dimension.kind == "radius":
        return _radius_dimension(dimension, block_name)
    return _diameter_dimension(dimension, block_name)
