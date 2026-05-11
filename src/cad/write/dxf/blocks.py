from __future__ import annotations

from cad.scene.dxf import BlockDefinition, DxfDrawing, InsertEntity
from cad.write.dxf.codes import LAYER, X, Y, Z
from cad.write.dxf.emit import pairs
from cad.write.dxf.entities import mtext_entity, shape_entities


def block_definition(block: BlockDefinition) -> list[str]:
    body = pairs(
        (
            (0, "BLOCK"),
            (100, "AcDbEntity"),
            (LAYER, "0"),
            (100, "AcDbBlockBegin"),
            (2, block.name),
            (70, 0),
            (X, block.base.x),
            (Y, block.base.y),
            (Z, 0.0),
            (3, block.name),
            (1, ""),
        )
    )
    for layer in block.layers.values():
        for shape in layer.entities:
            body.extend(shape_entities(shape, layer.name))
    for text in block.texts:
        body.extend(mtext_entity(text))
    body.extend(
        pairs(
            (
                (0, "ENDBLK"),
                (100, "AcDbEntity"),
                (LAYER, "0"),
                (100, "AcDbBlockEnd"),
            )
        )
    )
    return body


def dimension_block_names(drawing: DxfDrawing) -> tuple[str, ...]:
    existing = set(drawing.blocks)
    names: list[str] = []
    candidate = 1
    for _dimension in drawing.dimensions:
        name = f"*D{candidate}"
        while name in existing:
            candidate += 1
            name = f"*D{candidate}"
        names.append(name)
        existing.add(name)
        candidate += 1
    return tuple(names)


def dimension_block_definition(name: str) -> list[str]:
    return pairs(
        (
            (0, "BLOCK"),
            (100, "AcDbEntity"),
            (LAYER, "0"),
            (100, "AcDbBlockBegin"),
            (2, name),
            (70, 1),
            (X, 0.0),
            (Y, 0.0),
            (Z, 0.0),
            (3, name),
            (1, ""),
            (0, "ENDBLK"),
            (100, "AcDbEntity"),
            (LAYER, "0"),
            (100, "AcDbBlockEnd"),
        )
    )


def blocks_section_body(
    drawing: DxfDrawing, dim_block_names: tuple[str, ...]
) -> list[str]:
    body: list[str] = []
    for block in drawing.blocks.values():
        body.extend(block_definition(block))
    for name in dim_block_names:
        body.extend(dimension_block_definition(name))
    return body


def insert_entity(insert: InsertEntity) -> list[str]:
    items: list[tuple[int, object]] = [
        (0, "INSERT"),
        (100, "AcDbEntity"),
        (LAYER, insert.layer),
        (100, "AcDbBlockReference"),
        (2, insert.name),
        (X, insert.at.x),
        (Y, insert.at.y),
        (Z, 0.0),
        (41, insert.scale),
        (42, insert.scale),
        (43, insert.scale),
        (50, insert.rotation),
    ]
    return pairs(items)
