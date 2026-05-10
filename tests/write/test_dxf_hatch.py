from __future__ import annotations

import pytest

from cad import DxfDrawing, SceneError, line, rectangle


def test_layer_hatch_records_closed_boundary() -> None:
    drawing = DxfDrawing()
    layer = drawing.layer("SECTION")
    assert layer.hatch(rectangle((0, 0), (1, 1)), pattern="ANSI31", scale=0.025) is layer
    assert drawing.hatches[0].layer == "SECTION"
    assert drawing.hatches[0].pattern == "ANSI31"


def test_layer_hatch_rejects_open_boundary() -> None:
    with pytest.raises(SceneError, match="closed"):
        DxfDrawing().layer("SECTION").hatch(line((0, 0), (1, 0)))


def test_layer_hatch_rejects_unknown_pattern() -> None:
    with pytest.raises(SceneError, match="ANSI31"):
        DxfDrawing().layer("SECTION").hatch(rectangle((0, 0), (1, 1)), pattern="SOLID")


def test_layer_hatch_rejects_non_positive_scale() -> None:
    with pytest.raises(SceneError, match="scale"):
        DxfDrawing().layer("SECTION").hatch(rectangle((0, 0), (1, 1)), scale=0)
