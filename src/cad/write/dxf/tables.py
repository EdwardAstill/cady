from __future__ import annotations

from collections.abc import Iterable

from cad.scene.dxf import Layer
from cad.write.dxf.emit import pairs


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
