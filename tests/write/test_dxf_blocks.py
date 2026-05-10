from __future__ import annotations

import pytest

from cad import DxfDrawing, SceneError, circle


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
