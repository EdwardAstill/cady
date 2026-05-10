from __future__ import annotations

from collections.abc import Iterable

from cad.scene.dxf import Layer
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
