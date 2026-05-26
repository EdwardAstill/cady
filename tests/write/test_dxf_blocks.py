from __future__ import annotations

import pytest

from cady import DxfDrawing, SceneError, circle
from cady.write.dxf.sections import render_dxf


def test_block_definition_records_entities() -> None:
    drawing = DxfDrawing()
    block = drawing.block("PIN_MARK", base=(0, 0))
    assert block.layer("SYMBOL").add(circle((0, 0), 0.025)) is block.layers["SYMBOL"]
    assert drawing.blocks["PIN_MARK"] is block


def test_block_definition_rejects_duplicate_name() -> None:
    drawing = DxfDrawing()
    drawing.block("PIN_MARK")
    with pytest.raises(SceneError, match="duplicate"):
        drawing.block("PIN_MARK")


def test_insert_requires_existing_block() -> None:
    with pytest.raises(SceneError, match="block"):
        DxfDrawing().insert("MISSING", at=(0, 0))


def test_insert_rejects_non_positive_scale() -> None:
    drawing = DxfDrawing()
    drawing.block("PIN_MARK")
    with pytest.raises(SceneError, match="scale"):
        drawing.insert("PIN_MARK", at=(0, 0), scale=0)


def test_block_and_insert_emit_dxf_tokens() -> None:
    drawing = DxfDrawing()
    drawing.block("PIN_MARK").layer("SYMBOL").add(circle((0, 0), 0.025))
    drawing.insert("PIN_MARK", at=(1, 1), layer="SYMBOL")
    drawing.insert("PIN_MARK", at=(2, 1), layer="SYMBOL", rotation=90)

    text = render_dxf(drawing)

    assert "\n0\nBLOCK\n" in text
    assert "\n2\nPIN_MARK\n" in text
    assert text.count("\n0\nINSERT\n") == 2
    assert "\n50\n90\n" in text


def test_block_insert_round_trip_with_ezdxf(tmp_path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "blocks.dxf"
    drawing = DxfDrawing()
    drawing.block("PIN_MARK").layer("SYMBOL").add(circle((0, 0), 0.025))
    drawing.insert("PIN_MARK", at=(1, 1), layer="SYMBOL")
    drawing.insert("PIN_MARK", at=(2, 1), layer="SYMBOL")
    drawing.write(path)

    doc = ezdxf.readfile(path)
    audit = doc.audit()

    assert not audit.errors
    assert "PIN_MARK" in doc.blocks
    assert sum(1 for entity in doc.modelspace() if entity.dxftype() == "INSERT") == 2
