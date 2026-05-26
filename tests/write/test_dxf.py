from __future__ import annotations

from pathlib import Path

import pytest

from cady import DxfDrawing, WriteError, arc, circle, line, rectangle
from cady.write.dxf.sections import render_dxf


def smoke_drawing() -> DxfDrawing:
    d = DxfDrawing()
    d.layer("PLATE", 7).add(rectangle((0, 0), (1, 1))).add(circle((0.5, 0.5), 0.2))
    d.layer("CUTS", 1).add(line((0, 0), (1, 1))).add(arc((0.5, 0.5), 0.25, 0, 1.0))
    d.add_text("SMOKE", (0, 0), 0.1, "TEXT")
    return d


def test_dxf_smoke_round_trip(tmp_path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "out.dxf"
    smoke_drawing().write(path)
    doc = ezdxf.readfile(path)
    audit = doc.audit()
    assert not audit.errors
    counts = {}
    for entity in doc.modelspace():
        counts[entity.dxftype()] = counts.get(entity.dxftype(), 0) + 1
    assert counts["CIRCLE"] == 1
    assert counts["LWPOLYLINE"] == 1
    assert counts["MTEXT"] == 1


def test_dxf_circle_round_trip(tmp_path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "circle.dxf"
    drawing = DxfDrawing()
    drawing.layer("C").add(circle((1.5, 2.5), 0.75))
    drawing.write(path)
    entity = next(iter(ezdxf.readfile(path).modelspace()))
    assert entity.dxf.center.x == pytest.approx(1.5, rel=1e-9)
    assert entity.dxf.center.y == pytest.approx(2.5, rel=1e-9)
    assert entity.dxf.radius == pytest.approx(0.75, rel=1e-9)


def test_dxf_empty_writeerror() -> None:
    with pytest.raises(WriteError):
        render_dxf(DxfDrawing())


def test_dxf_holes_decompose() -> None:
    d = DxfDrawing()
    d.layer("P").add(rectangle((0, 0), (1, 1)).with_hole(circle((0.5, 0.5), 0.2)))
    text = render_dxf(d)
    assert text.count("LWPOLYLINE") == 1
    assert text.count("CIRCLE") == 1


def test_dxf_golden() -> None:
    golden = (Path(__file__).parent / "goldens" / "smoke.dxf").read_text(encoding="ascii")
    assert render_dxf(smoke_drawing()) == golden
