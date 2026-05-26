"""Tests for DXF HEADER variables."""

import pytest

from cady import DxfDrawing


def test_header_starts_empty() -> None:
    drawing = DxfDrawing()
    assert drawing.header == {}


def test_set_insunits_records_int() -> None:
    drawing = DxfDrawing()
    drawing.set_header("$INSUNITS", 4)  # 4 = millimetres
    assert drawing.header["$INSUNITS"] == 4


def test_set_header_rejects_unknown_variable() -> None:
    drawing = DxfDrawing()
    with pytest.raises(ValueError, match=r"unknown HEADER variable"):
        drawing.set_header("$NOPE", 1)


def test_set_header_returns_self_for_chaining() -> None:
    drawing = DxfDrawing()
    result = drawing.set_header("$INSUNITS", 4)
    assert result is drawing


def test_set_header_rejects_string_for_int_var() -> None:
    drawing = DxfDrawing()
    with pytest.raises(TypeError, match=r"\$INSUNITS requires an int value"):
        drawing.set_header("$INSUNITS", "6")
