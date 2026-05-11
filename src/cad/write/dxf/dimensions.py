from __future__ import annotations

from math import atan2, degrees

from cad.geom.helpers import midpoint, perpendicular
from cad.geom.vec import Vec2
from cad.scene.dxf import DimensionEntity
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


def dimension_entities(dimension: DimensionEntity, block_name: str) -> list[str]:
    if dimension.kind in {"linear", "aligned"}:
        return _rotated_dimension(dimension, block_name)
    if dimension.kind == "radius":
        return _radius_dimension(dimension, block_name)
    return _diameter_dimension(dimension, block_name)
