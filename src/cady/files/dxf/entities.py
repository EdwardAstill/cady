from __future__ import annotations

from collections.abc import Iterable
from math import degrees

from cady.domain.base import Shape2D
from cady.domain.drawing import TextEntity
from cady.domain.shapes2d import Arc, Circle, Line, Path, Polyline, Rectangle, Spline
from cady.domain.vec import Vec2
from cady.files.dxf.codes import (
    ANGLE_END,
    ANGLE_START,
    COUNT,
    FLAGS,
    HEIGHT,
    LAYER,
    RADIUS,
    TEXT,
    X,
    Y,
    Z,
)
from cady.files.dxf.emit import pairs
from cady.ops.tessellate import curves_to_polyline


def line_entity(shape: Line, layer: str) -> list[str]:
    return pairs(
        (
            (0, "LINE"),
            (100, "AcDbEntity"),
            (LAYER, layer),
            (100, "AcDbLine"),
            (X, shape.a.x),
            (Y, shape.a.y),
            (Z, 0.0),
            (11, shape.b.x),
            (21, shape.b.y),
            (31, 0.0),
        )
    )


def lwpolyline_entity(points: Iterable[Vec2], closed: bool, layer: str) -> list[str]:
    vertices = tuple(points)
    if closed and vertices[0] == vertices[-1]:
        vertices = vertices[:-1]
    items: list[tuple[int, object]] = [
        (0, "LWPOLYLINE"),
        (100, "AcDbEntity"),
        (LAYER, layer),
        (100, "AcDbPolyline"),
        (COUNT, len(vertices)),
        (FLAGS, 1 if closed else 0),
    ]
    for point in vertices:
        items.extend(((X, point.x), (Y, point.y)))
    return pairs(items)


def circle_entity(shape: Circle, layer: str) -> list[str]:
    return pairs(
        (
            (0, "CIRCLE"),
            (100, "AcDbEntity"),
            (LAYER, layer),
            (100, "AcDbCircle"),
            (X, shape.centre.x),
            (Y, shape.centre.y),
            (Z, 0.0),
            (RADIUS, shape.radius),
        )
    )


def arc_entity(shape: Arc, layer: str) -> list[str]:
    return pairs(
        (
            (0, "ARC"),
            (100, "AcDbEntity"),
            (LAYER, layer),
            (100, "AcDbCircle"),
            (X, shape.centre.x),
            (Y, shape.centre.y),
            (Z, 0.0),
            (RADIUS, shape.radius),
            (100, "AcDbArc"),
            (ANGLE_START, degrees(shape.start_rad)),
            (ANGLE_END, degrees(shape.end_rad)),
        )
    )


def mtext_entity(text: TextEntity) -> list[str]:
    return pairs(
        (
            (0, "MTEXT"),
            (100, "AcDbEntity"),
            (LAYER, text.layer),
            (100, "AcDbMText"),
            (X, text.at.x),
            (Y, text.at.y),
            (Z, 0.0),
            (HEIGHT, text.height),
            (TEXT, text.text),
        )
    )


def shape_entities(shape: Shape2D, layer: str, *, tolerance: float = 1e-3) -> list[str]:
    out: list[str] = []
    if isinstance(shape, Line):
        out.extend(line_entity(shape, layer))
    elif isinstance(shape, Arc):
        out.extend(arc_entity(shape, layer))
    elif isinstance(shape, Circle):
        out.extend(circle_entity(shape, layer))
    elif isinstance(shape, Rectangle):
        out.extend(lwpolyline_entity(shape.points(), True, layer))
    elif isinstance(shape, Polyline):
        out.extend(lwpolyline_entity(shape.points(), shape.closed, layer))
    elif isinstance(shape, Spline):
        flat = curves_to_polyline(shape, tolerance=tolerance)
        out.extend(lwpolyline_entity(flat.points(), flat.closed, layer))
    elif isinstance(shape, Path):
        for segment in shape.segments:
            out.extend(shape_entities(segment, layer, tolerance=tolerance))
    else:
        flat = curves_to_polyline(shape, tolerance=tolerance)
        out.extend(lwpolyline_entity(flat.points(), flat.closed, layer))
    for hole in getattr(shape, "inner_loops", ()):
        out.extend(shape_entities(hole, layer, tolerance=tolerance))
    return out
