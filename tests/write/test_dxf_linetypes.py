from __future__ import annotations

import pytest

from cad import DxfDrawing, Model, SceneError, line
from cad.write.dxf.sections import render_dxf


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


def test_ltype_table_emits_used_builtin_linetype() -> None:
    drawing = DxfDrawing()
    drawing.layer("CENTERLINES", color=3, linetype="CENTER").add(line((0, 0), (1, 0)))

    text = render_dxf(drawing)

    assert "\n2\nLTYPE\n" in text
    assert "\n2\nCENTER\n" in text
    assert "\n8\nCENTERLINES\n" in text
    assert "\n6\nCENTER\n" in text


def test_linetype_round_trip_with_ezdxf(tmp_path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "linetype.dxf"
    drawing = DxfDrawing()
    drawing.layer("HIDDEN_LINES", color=8, linetype="HIDDEN").add(line((0, 0), (1, 0)))
    drawing.write(path)

    audit = ezdxf.readfile(path).audit()

    assert not audit.errors
