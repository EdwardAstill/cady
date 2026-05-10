from __future__ import annotations

import pytest

from cad import DxfDrawing, Model, SceneError


def test_dxf_layer_accepts_builtin_linetype() -> None:
    layer = DxfDrawing().layer("CENTERLINES", color=3, linetype="CENTER")
    assert layer.linetype == "CENTER"


def test_dxf_layer_rejects_unknown_linetype() -> None:
    with pytest.raises(SceneError, match="linetype"):
        DxfDrawing().layer("X", linetype="DASHDOT")


def test_model_layer_accepts_builtin_linetype() -> None:
    layer = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front").layer(
        "HIDDEN", color=8, linetype="HIDDEN"
    )
    assert layer.name == "HIDDEN"
