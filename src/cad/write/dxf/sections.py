from __future__ import annotations

from pathlib import Path

from cad.errors import WriteError
from cad.geom.vec import Vec2
from cad.scene.dxf import DxfDrawing
from cad.write.dxf.emit import pairs
from cad.write.dxf.entities import mtext_entity, shape_entities


def _section(name: str, body: list[str]) -> list[str]:
    return ["0", "SECTION", "2", name, *body, "0", "ENDSEC"]


def _header(bounds: tuple[Vec2, Vec2]) -> list[str]:
    mn, mx = bounds
    return _section(
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


def _tables(drawing: DxfDrawing) -> list[str]:
    layer_body = pairs(((0, "TABLE"), (2, "LAYER"), (70, len(drawing.layers) + 1)))
    layer_body.extend(pairs(((0, "LAYER"), (2, "0"), (70, 0), (62, 7), (6, "CONTINUOUS"))))
    for layer in drawing.layers.values():
        layer_body.extend(
            pairs(((0, "LAYER"), (2, layer.name), (70, 0), (62, layer.color), (6, layer.linetype)))
        )
    layer_body.extend(pairs(((0, "ENDTAB"),)))
    return _section("TABLES", layer_body)


def _entities(drawing: DxfDrawing) -> list[str]:
    body: list[str] = []
    for layer in drawing.layers.values():
        for shape in layer.entities:
            body.extend(shape_entities(shape, layer.name))
    for text in drawing.texts:
        body.extend(mtext_entity(text))
    return _section("ENTITIES", body)


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
        Vec2(min(p.x for p in points), min(p.y for p in points)),
        Vec2(max(p.x for p in points), max(p.y for p in points)),
    )


def render_dxf(drawing: DxfDrawing) -> str:
    entity_count = sum(len(layer.entities) for layer in drawing.layers.values()) + len(
        drawing.texts
    )
    if entity_count == 0:
        raise WriteError("cannot write empty DXF drawing")
    lines: list[str] = []
    lines.extend(_header(_bounds(drawing)))
    lines.extend(_section("CLASSES", []))
    lines.extend(_tables(drawing))
    lines.extend(_section("BLOCKS", []))
    lines.extend(_entities(drawing))
    lines.extend(_section("OBJECTS", []))
    lines.extend(("0", "EOF"))
    return "\n".join(lines) + "\n"


def write_dxf(drawing: DxfDrawing, path: Path) -> None:
    path.write_text(render_dxf(drawing), encoding="ascii")
