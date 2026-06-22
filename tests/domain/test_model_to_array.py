from __future__ import annotations

from cady import Model, prism, rectangle
from cady.numeric import ArrayMesh3, ArrayPolygon2


def test_drawing_part_and_model_to_array() -> None:
    model = Model("demo", created_at="2026-06-22T00:00:00Z")
    model.drawing("front").layer("OUTLINE").add(rectangle((0, 0), (1, 1)))
    model.part("box").add(prism((0, 0, 0), (1, 1, 1)))

    drawing_arrays = model.drawing_arrays()
    part_arrays = model.part("box").to_array()
    model_arrays = model.to_array()

    assert isinstance(drawing_arrays[0], ArrayPolygon2)
    assert isinstance(part_arrays[0], ArrayMesh3)
    assert isinstance(model_arrays[0], ArrayMesh3)
