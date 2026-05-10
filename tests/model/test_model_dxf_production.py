from __future__ import annotations

from cad import Model, circle, rectangle


def test_model_layer_hatch_delegates() -> None:
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")
    drawing.layer("SECTION").hatch(rectangle((0, 0), (1, 1)))
    assert drawing.to_dxf_drawing().hatches[0].layer == "SECTION"


def test_model_drawing_block_and_insert_delegates() -> None:
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")
    drawing.block("PIN_MARK").layer("SYMBOL").add(circle((0, 0), 0.025))
    assert drawing.insert("PIN_MARK", at=(1, 1), layer="SYMBOL") is drawing
    assert drawing.to_dxf_drawing().inserts[0].name == "PIN_MARK"
