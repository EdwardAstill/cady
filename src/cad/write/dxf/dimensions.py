from __future__ import annotations

from cad.geom.helpers import midpoint, perpendicular
from cad.geom.shapes2d import Line
from cad.geom.vec import Vec2
from cad.scene.dxf import DimensionEntity
from cad.write.dxf.entities import line_entity, mtext_entity


def _text(text: str, at: Vec2, height: float, layer: str) -> list[str]:
    from cad.scene.dxf import TextEntity

    return mtext_entity(TextEntity(text, at, height, layer))


def _tick(point: Vec2, normal: Vec2, length: float) -> Line:
    half = normal * (length * 0.5)
    return Line(point - half, point + half)


def _offset_dimension(dimension: DimensionEntity) -> list[str]:
    direction = dimension.b - dimension.a
    normal = perpendicular(direction)
    offset = normal * dimension.offset
    start = dimension.a + offset
    end = dimension.b + offset
    tick_length = min(max(direction.length() * 0.06, dimension.text_height * 0.8), 0.06)
    text_gap = normal * (dimension.text_height * 0.6)

    out: list[str] = []
    for line in (
        Line(dimension.a, start),
        Line(dimension.b, end),
        Line(start, end),
        _tick(start, normal, tick_length),
        _tick(end, normal, tick_length),
    ):
        out.extend(line_entity(line, dimension.layer))
    out.extend(
        _text(
            dimension.text,
            midpoint(start, end) + text_gap,
            dimension.text_height,
            dimension.layer,
        )
    )
    return out


def _radius_dimension(dimension: DimensionEntity) -> list[str]:
    radius = dimension.b - dimension.a
    unit = radius.normalised()
    label_point = dimension.b + unit * (dimension.text_height * 1.5)
    out = line_entity(Line(dimension.a, dimension.b), dimension.layer)
    out.extend(_text(dimension.text, label_point, dimension.text_height, dimension.layer))
    return out


def _diameter_dimension(dimension: DimensionEntity) -> list[str]:
    radius = dimension.b - dimension.a
    start = dimension.a - radius
    end = dimension.a + radius
    label_point = end + radius.normalised() * (dimension.text_height * 1.5)
    out = line_entity(Line(start, end), dimension.layer)
    out.extend(_text(dimension.text, label_point, dimension.text_height, dimension.layer))
    return out


def dimension_entities(dimension: DimensionEntity) -> list[str]:
    if dimension.kind in {"linear", "aligned"}:
        return _offset_dimension(dimension)
    if dimension.kind == "radius":
        return _radius_dimension(dimension)
    return _diameter_dimension(dimension)
