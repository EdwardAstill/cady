from __future__ import annotations

from collections.abc import Iterable

from cad.scene.dxf import DimStyle, Layer
from cad.write.dxf.emit import pairs

_LINETYPE_PATTERNS: dict[str, tuple[str, tuple[float, ...]]] = {
    "CONTINUOUS": ("Solid line", ()),
    "HIDDEN": ("Hidden __ __ __ __ __ __", (0.5, -0.25)),
    "CENTER": ("Center ____ _ ____ _ ____", (1.25, -0.25, 0.25, -0.25)),
}


def _ltype_record(name: str) -> list[str]:
    description, pattern = _LINETYPE_PATTERNS[name]
    body = pairs(
        (
            (0, "LTYPE"),
            (2, name),
            (70, 0),
            (3, description),
            (72, 65),
            (73, len(pattern)),
            (40, sum(abs(segment) for segment in pattern)),
        )
    )
    for segment in pattern:
        body.extend(pairs(((49, segment), (74, 0))))
    return body


def linetype_table(layers: Iterable[Layer]) -> list[str]:
    used = {"CONTINUOUS"}
    used.update(layer.linetype for layer in layers if layer.linetype != "CONTINUOUS")
    names = tuple(name for name in ("CONTINUOUS", "HIDDEN", "CENTER") if name in used)
    body = pairs(((0, "TABLE"), (2, "LTYPE"), (70, len(names))))
    for name in names:
        body.extend(_ltype_record(name))
    body.extend(pairs(((0, "ENDTAB"),)))
    return body


def _layer_record(name: str, color: int, linetype: str) -> list[str]:
    return pairs(((0, "LAYER"), (2, name), (70, 0), (62, color), (6, linetype)))


def layer_table(layers: Iterable[Layer]) -> list[str]:
    scene_layers = tuple(layers)
    body = pairs(((0, "TABLE"), (2, "LAYER"), (70, len(scene_layers) + 1)))
    body.extend(_layer_record("0", 7, "CONTINUOUS"))
    for layer in scene_layers:
        body.extend(_layer_record(layer.name, layer.color, layer.linetype))
    body.extend(pairs(((0, "ENDTAB"),)))
    return body


def _dimstyle_record(style: DimStyle) -> list[str]:
    return pairs(
        (
            (0, "DIMSTYLE"),
            (100, "AcDbSymbolTableRecord"),
            (100, "AcDbDimStyleTableRecord"),
            (2, style.name),
            (70, 0),
            (3, ""),
            (4, ""),
            (5, ""),
            (6, ""),
            (7, ""),
            (40, 1.0),
            (41, style.arrow_size),
            (42, style.extension_offset),
            (44, style.extension_extend),
            (140, style.text_height),
            (141, 0.09),
            (142, 0.0),
            (143, 25.4),
            (144, 1.0),
            (147, style.text_gap),
            (171, 3),
            (172, 1),
            (271, style.decimal_places),
            (272, 2),
            (274, 3),
            (340, 0),
        )
    )


_STANDARD_DIMSTYLE = DimStyle(name="Standard")


def dimstyle_table(
    uses_dimstyle: bool,
    dimstyles: Iterable[DimStyle] = (),
    referenced_dimstyles: frozenset[str] = frozenset(),
) -> list[str]:
    if not uses_dimstyle:
        return []
    # Collect styles to emit: Standard always first, then other referenced styles
    styles_by_name: dict[str, DimStyle] = {}
    for style in dimstyles:
        styles_by_name[style.name] = style
    to_emit: list[DimStyle] = [styles_by_name.get("Standard", _STANDARD_DIMSTYLE)]
    for style in styles_by_name.values():
        if style.name != "Standard" and style.name in referenced_dimstyles:
            to_emit.append(style)
    body = pairs(((0, "TABLE"), (2, "DIMSTYLE"), (70, len(to_emit))))
    for style in to_emit:
        body.extend(_dimstyle_record(style))
    body.extend(pairs(((0, "ENDTAB"),)))
    return body
