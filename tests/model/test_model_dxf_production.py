from __future__ import annotations

from cad import Model, rectangle


def test_model_layer_hatch_delegates() -> None:
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")
    drawing.layer("SECTION").hatch(rectangle((0, 0), (1, 1)))
    assert drawing.to_dxf_drawing().hatches[0].layer == "SECTION"
