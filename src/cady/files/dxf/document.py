from __future__ import annotations

from cady.domain.drawing import HEADER_VARS, AngularDimensionEntity, DimensionEntity, DxfDrawing
from cady.domain.vec import Vec2
from cady.errors import WriteError
from cady.files.dxf.blocks import blocks_section_body, insert_entity
from cady.files.dxf.dimensions import dimension_entities
from cady.files.dxf.emit import pairs
from cady.files.dxf.entities import mtext_entity, shape_entities
from cady.files.dxf.hatch import hatch_entity
from cady.files.dxf.plan import DxfRenderPlan, make_render_plan
from cady.files.dxf.tables import dimstyle_table, layer_table, linetype_table
from cady.ops.profiles import perpendicular


def section(name: str, body: list[str]) -> list[str]:
    return ["0", "SECTION", "2", name, *body, "0", "ENDSEC"]


def _header(bounds: tuple[Vec2, Vec2], drawing: DxfDrawing) -> list[str]:
    mn, mx = bounds
    user = drawing.header
    insunits_value: int | float | str = user.get("$INSUNITS", 6)
    fixed: list[tuple[int, int | float | str]] = [
        (9, "$ACADVER"),
        (1, "AC1032"),
        (9, "$INSUNITS"),
        (70, insunits_value),
    ]
    # Emit any other user-set variables (skip $INSUNITS already handled)
    for var_name, var_value in user.items():
        if var_name == "$INSUNITS":
            continue
        group_code = HEADER_VARS[var_name]
        fixed.append((9, var_name))
        fixed.append((group_code, var_value))
    fixed += [
        (9, "$EXTMIN"),
        (10, mn.x),
        (20, mn.y),
        (30, 0.0),
        (9, "$EXTMAX"),
        (10, mx.x),
        (20, mx.y),
        (30, 0.0),
    ]
    return section("HEADER", pairs(tuple(fixed)))


def _entities(drawing: DxfDrawing, plan: DxfRenderPlan) -> list[str]:
    body: list[str] = []
    for layer in plan.layers:
        for shape in layer.entities:
            body.extend(shape_entities(shape, layer.name))
    for text in drawing.texts:
        body.extend(mtext_entity(text))
    for hatch in drawing.hatches:
        body.extend(hatch_entity(hatch))
    for insert in drawing.inserts:
        body.extend(insert_entity(insert))
    for dimension, block_name in zip(
        drawing.dimensions, plan.dimension_block_names, strict=True
    ):
        body.extend(dimension_entities(dimension, block_name))
    return section("ENTITIES", body)


def bounds(drawing: DxfDrawing) -> tuple[Vec2, Vec2]:
    points: list[Vec2] = []
    for layer in drawing.layers.values():
        for entity in layer.entities:
            mn, mx = entity.bounds()
            points.extend((mn, mx))
    for text in drawing.texts:
        points.append(text.at)
    for hatch in drawing.hatches:
        mn, mx = hatch.boundary.bounds()
        points.extend((mn, mx))
    for insert in drawing.inserts:
        points.append(insert.at)
    for dimension in drawing.dimensions:
        mn, mx = _dimension_bounds(dimension)
        points.extend((mn, mx))
    if not points:
        return (Vec2(0, 0), Vec2(0, 0))
    return (
        Vec2(min(point.x for point in points), min(point.y for point in points)),
        Vec2(max(point.x for point in points), max(point.y for point in points)),
    )


def _dimension_bounds(
    dimension: DimensionEntity | AngularDimensionEntity,
) -> tuple[Vec2, Vec2]:
    if isinstance(dimension, AngularDimensionEntity):
        from cady.files.dxf.dimensions import angular_dim_arc_point

        arc_pt = angular_dim_arc_point(dimension)
        pts = [
            Vec2(dimension.center[0], dimension.center[1]),
            Vec2(dimension.p1[0], dimension.p1[1]),
            Vec2(dimension.p2[0], dimension.p2[1]),
            Vec2(arc_pt[0], arc_pt[1]),
        ]
        return (
            Vec2(min(p.x for p in pts), min(p.y for p in pts)),
            Vec2(max(p.x for p in pts), max(p.y for p in pts)),
        )
    points = [dimension.a, dimension.b]
    if dimension.kind in {"linear", "aligned"}:
        offset = perpendicular(dimension.b - dimension.a) * dimension.offset
        points.extend((dimension.a + offset, dimension.b + offset))
    elif dimension.kind == "diameter":
        radius = dimension.b - dimension.a
        points.append(dimension.a - radius)
    return (
        Vec2(min(point.x for point in points), min(point.y for point in points)),
        Vec2(max(point.x for point in points), max(point.y for point in points)),
    )


def _entity_count(drawing: DxfDrawing) -> int:
    return (
        sum(len(layer.entities) for layer in drawing.layers.values())
        + len(drawing.texts)
        + len(drawing.hatches)
        + len(drawing.blocks)
        + len(drawing.inserts)
        + len(drawing.dimensions)
    )


def render_document(drawing: DxfDrawing) -> str:
    if _entity_count(drawing) == 0:
        raise WriteError("cannot write empty DXF drawing")

    plan = make_render_plan(drawing)
    lines: list[str] = []
    lines.extend(_header(bounds(drawing), drawing))
    lines.extend(section("CLASSES", []))
    lines.extend(
        section(
            "TABLES",
            [
                *linetype_table(plan.layers),
                *layer_table(plan.layers),
                *dimstyle_table(plan.uses_dimstyle, plan.dimstyles, plan.referenced_dimstyles),
            ],
        )
    )
    lines.extend(section("BLOCKS", blocks_section_body(drawing, plan.dimension_block_names)))
    lines.extend(_entities(drawing, plan))
    lines.extend(section("OBJECTS", []))
    lines.extend(("0", "EOF"))
    return "\n".join(lines) + "\n"
