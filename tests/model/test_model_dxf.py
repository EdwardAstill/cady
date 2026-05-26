from __future__ import annotations

import pytest

from cady import Model, SceneError, circle, rectangle, sphere
from cady.scene import DxfDrawing


def test_drawing_layer_delegates_to_dxf_drawing() -> None:
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")
    layer = drawing.layer("PLATE", color=7, linetype="CENTER").add(rectangle((0, 0), (1, 1)))
    assert layer is drawing.layer("PLATE")

    dxf = drawing.to_dxf_drawing()
    assert isinstance(dxf, DxfDrawing)
    assert "PLATE" in dxf.layers
    assert len(dxf.layers["PLATE"].entities) == 1
    assert dxf.layers["PLATE"].linetype == "CENTER"


def test_drawing_text_delegates_to_dxf_drawing() -> None:
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")
    assert drawing.add_text("PLATE", at=(0, 0), height=0.1, layer="TEXT") is drawing
    assert drawing.to_dxf_drawing().texts[0].text == "PLATE"


def test_drawing_rejects_3d_shapes() -> None:
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")
    with pytest.raises(SceneError):
        drawing.layer("BAD").add(sphere((0, 0, 0), 1))  # type: ignore[arg-type]


def test_model_write_dxf_round_trips(tmp_path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "model.dxf"

    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    model.drawing("front").layer("PLATE").add(rectangle((0, 0), (1, 1)))
    model.drawing("holes").layer("HOLES", color=1).add(circle((0.5, 0.5), 0.2))
    assert model.write_dxf(path) is model

    doc = ezdxf.readfile(path)
    audit = doc.audit()
    assert not audit.errors
    counts: dict[str, int] = {}
    for entity in doc.modelspace():
        counts[entity.dxftype()] = counts.get(entity.dxftype(), 0) + 1
    assert counts["LWPOLYLINE"] == 1
    assert counts["CIRCLE"] == 1


def test_model_write_dxf_matches_direct_scene_for_single_drawing(tmp_path) -> None:
    direct_path = tmp_path / "direct.dxf"
    model_path = tmp_path / "model.dxf"

    direct = DxfDrawing()
    direct.layer("PLATE").add(rectangle((0, 0), (1, 1)))
    direct.write(direct_path)

    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    model.drawing("front").layer("PLATE").add(rectangle((0, 0), (1, 1)))
    model.write_dxf(model_path)

    assert model_path.read_text(encoding="ascii") == direct_path.read_text(encoding="ascii")
