from __future__ import annotations

import pytest

from cad import Model, SceneError, circle, rectangle


def test_model_layer_hatch_delegates() -> None:
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")
    drawing.layer("SECTION").hatch(rectangle((0, 0), (1, 1)))
    assert drawing.to_dxf_drawing().hatches[0].layer == "SECTION"


def test_model_drawing_block_and_insert_delegates() -> None:
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")
    drawing.block("PIN_MARK").layer("SYMBOL").add(circle((0, 0), 0.025))
    assert drawing.insert("PIN_MARK", at=(1, 1), layer="SYMBOL") is drawing
    assert drawing.to_dxf_drawing().inserts[0].name == "PIN_MARK"


def test_model_write_dxf_preserves_hatch_blocks_inserts_and_linetypes(tmp_path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "production.dxf"
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    drawing = model.drawing("front")
    drawing.layer("PLATE").add(rectangle((0, 0), (1, 1)))
    drawing.layer("SECTION", linetype="HIDDEN").hatch(rectangle((0, 0), (1, 1)))
    drawing.block("PIN_MARK").layer("SYMBOL").add(circle((0, 0), 0.025))
    drawing.insert("PIN_MARK", at=(0.5, 0.5), layer="SYMBOL")

    model.write_dxf(path)
    doc = ezdxf.readfile(path)
    audit = doc.audit()

    assert not audit.errors
    assert "PIN_MARK" in doc.blocks
    assert sum(1 for entity in doc.modelspace() if entity.dxftype() == "HATCH") == 1
    assert sum(1 for entity in doc.modelspace() if entity.dxftype() == "INSERT") == 1


def test_model_write_dxf_preserves_dimensions(tmp_path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "dimensions.dxf"
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    drawing = model.drawing("front")
    drawing.linear_dimension((0, 0), (1, 0), offset=0.1)
    drawing.radius_dimension((0.5, 0.5), 0.2)

    model.write_dxf(path)
    doc = ezdxf.readfile(path)
    audit = doc.audit()

    assert not audit.errors
    assert sum(1 for entity in doc.modelspace() if entity.dxftype() == "DIMENSION") == 2


def test_model_write_dxf_rejects_duplicate_block_names_across_drawings(tmp_path) -> None:
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    model.drawing("front").block("PIN_MARK")
    model.drawing("side").block("PIN_MARK")

    with pytest.raises(SceneError, match="duplicate block"):
        model.write_dxf(tmp_path / "duplicate.dxf")
