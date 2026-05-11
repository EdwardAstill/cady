from __future__ import annotations

import pytest

from cad import DxfDrawing, SceneError
from cad.write.dxf.sections import render_dxf


def test_linear_dimension_records_horizontal_measurement() -> None:
    drawing = DxfDrawing()
    assert drawing.linear_dimension((0, 0), (1, 0), offset=0.1, layer="DIM") is drawing

    dimension = drawing.dimensions[0]
    assert dimension.kind == "linear"
    assert dimension.text == "1"
    assert dimension.layer == "DIM"


def test_linear_dimension_rejects_non_orthogonal_points() -> None:
    with pytest.raises(SceneError, match="aligned"):
        DxfDrawing().linear_dimension((0, 0), (1, 1), offset=0.1)


def test_aligned_dimension_records_sloped_measurement() -> None:
    drawing = DxfDrawing()
    drawing.aligned_dimension((0, 0), (3, 4), offset=0.2)

    assert drawing.dimensions[0].kind == "aligned"
    assert drawing.dimensions[0].text == "5"


def test_radius_and_diameter_dimensions_record_default_text() -> None:
    drawing = DxfDrawing()
    drawing.radius_dimension((0, 0), 0.12)
    drawing.diameter_dimension((1, 0), 0.12)

    assert drawing.dimensions[0].text == "R0.12"
    assert drawing.dimensions[1].text == "DIA 0.24"


def test_dimension_entities_emit_lines_and_text() -> None:
    drawing = DxfDrawing()
    drawing.linear_dimension((0, 0), (1, 0), offset=0.1, layer="DIM")
    text = render_dxf(drawing)

    assert text.count("\n0\nLINE\n") >= 3
    assert "\n0\nMTEXT\n" in text
    assert "\n1\n1\n" in text


def test_dimensions_round_trip_with_ezdxf(tmp_path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "dimensions.dxf"
    drawing = DxfDrawing()
    drawing.linear_dimension((0, 0), (1, 0), offset=0.1)
    drawing.aligned_dimension((0, 0), (1, 1), offset=0.1)
    drawing.radius_dimension((0.5, 0.5), 0.2)
    drawing.diameter_dimension((1.5, 0.5), 0.2)
    drawing.write(path)

    doc = ezdxf.readfile(path)
    audit = doc.audit()
    counts: dict[str, int] = {}
    for entity in doc.modelspace():
        counts[entity.dxftype()] = counts.get(entity.dxftype(), 0) + 1

    assert not audit.errors
    assert counts["LINE"] >= 10
    assert counts["MTEXT"] == 4
