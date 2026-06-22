from __future__ import annotations

import pytest

from cady import DxfDrawing, SceneError, circle, line, rectangle
from cady.files.dxf.sections import render_dxf


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


def test_hatch_entity_emits_ansi31() -> None:
    drawing = DxfDrawing()
    drawing.layer("SECTION").hatch(rectangle((0, 0), (1, 1)), pattern="ANSI31", scale=0.025)

    text = render_dxf(drawing)

    assert "\n0\nHATCH\n" in text
    assert "\n2\nANSI31\n" in text
    assert "\n8\nSECTION\n" in text


def test_hatch_round_trip_with_ezdxf(tmp_path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "hatch.dxf"
    drawing = DxfDrawing()
    drawing.layer("SECTION").hatch(rectangle((0, 0), (1, 1)), pattern="ANSI31", scale=0.025)
    drawing.write(path)

    doc = ezdxf.readfile(path)
    audit = doc.audit()
    counts: dict[str, int] = {}
    for entity in doc.modelspace():
        counts[entity.dxftype()] = counts.get(entity.dxftype(), 0) + 1

    assert not audit.errors
    assert counts["HATCH"] == 1


def test_hatch_with_hole_emits_multiple_boundary_paths(tmp_path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "hatch-hole.dxf"
    profile = rectangle((0, 0), (1, 1)).with_hole(circle((0.5, 0.5), 0.2))
    drawing = DxfDrawing()
    drawing.layer("SECTION").hatch(profile, pattern="ANSI31", scale=0.025)
    drawing.write(path)

    doc = ezdxf.readfile(path)
    audit = doc.audit()
    hatch = next(entity for entity in doc.modelspace() if entity.dxftype() == "HATCH")

    assert not audit.errors
    assert len(hatch.paths) == 2
