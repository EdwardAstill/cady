from __future__ import annotations

from cad.errors import WriteError
from cad.geom.vec import Vec2
from cad.scene.dxf import DxfDrawing
from cad.write.dxf.emit import pairs
from cad.write.dxf.entities import mtext_entity, shape_entities
from cad.write.dxf.tables import layer_table, linetype_table


def section(name: str, body: list[str]) -> list[str]:
    return ["0", "SECTION", "2", name, *body, "0", "ENDSEC"]


def _header(bounds: tuple[Vec2, Vec2]) -> list[str]:
    mn, mx = bounds
    return section(
        "HEADER",
        pairs(
            (
                (9, "$ACADVER"),
                (1, "AC1032"),
                (9, "$INSUNITS"),
                (70, 6),
                (9, "$EXTMIN"),
                (10, mn.x),
                (20, mn.y),
                (30, 0.0),
                (9, "$EXTMAX"),
                (10, mx.x),
                (20, mx.y),
                (30, 0.0),
            )
        ),
    )


def _entities(drawing: DxfDrawing) -> list[str]:
    body: list[str] = []
    for layer in drawing.layers.values():
        for shape in layer.entities:
            body.extend(shape_entities(shape, layer.name))
    for text in drawing.texts:
        body.extend(mtext_entity(text))
    return section("ENTITIES", body)


def _bounds(drawing: DxfDrawing) -> tuple[Vec2, Vec2]:
    points: list[Vec2] = []
    for layer in drawing.layers.values():
        for entity in layer.entities:
            mn, mx = entity.bounds()
            points.extend((mn, mx))
    for text in drawing.texts:
        points.append(text.at)
    if not points:
        return (Vec2(0, 0), Vec2(0, 0))
    return (
        Vec2(min(point.x for point in points), min(point.y for point in points)),
        Vec2(max(point.x for point in points), max(point.y for point in points)),
    )


def _entity_count(drawing: DxfDrawing) -> int:
    return sum(len(layer.entities) for layer in drawing.layers.values()) + len(drawing.texts)


def render_document(drawing: DxfDrawing) -> str:
    if _entity_count(drawing) == 0:
        raise WriteError("cannot write empty DXF drawing")

    lines: list[str] = []
    lines.extend(_header(_bounds(drawing)))
    lines.extend(section("CLASSES", []))
    layers = tuple(drawing.layers.values())
    lines.extend(section("TABLES", [*linetype_table(layers), *layer_table(layers)]))
    lines.extend(section("BLOCKS", []))
    lines.extend(_entities(drawing))
    lines.extend(section("OBJECTS", []))
    lines.extend(("0", "EOF"))
    return "\n".join(lines) + "\n"
