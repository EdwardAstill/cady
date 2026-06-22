from __future__ import annotations

from cady import Model, rectangle
from cady.domain import DxfDrawing
from cady.files import dxf


def test_write_drawing_accepts_model_drawing(tmp_path) -> None:
    path = tmp_path / "drawing.dxf"
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")
    drawing.layer("PLATE").add(rectangle((0, 0), (1, 1)))

    assert dxf.write_drawing(drawing, path) is drawing
    assert path.read_text(encoding="ascii").startswith("0\nSECTION")


def test_write_drawing_matches_existing_dxf_drawing_write(tmp_path) -> None:
    facade_path = tmp_path / "facade.dxf"
    direct_path = tmp_path / "direct.dxf"

    drawing = DxfDrawing()
    drawing.layer("PLATE").add(rectangle((0, 0), (1, 1)))

    dxf.write_drawing(drawing, facade_path)
    drawing.write(direct_path)

    assert facade_path.read_text(encoding="ascii") == direct_path.read_text(encoding="ascii")


def test_write_model_delegates_to_existing_model_output(tmp_path) -> None:
    facade_path = tmp_path / "facade.dxf"
    direct_path = tmp_path / "direct.dxf"

    facade_model = Model("demo", created_at="2026-05-08T00:00:00Z")
    facade_model.drawing("front").layer("PLATE").add(rectangle((0, 0), (1, 1)))
    direct_model = Model("demo", created_at="2026-05-08T00:00:00Z")
    direct_model.drawing("front").layer("PLATE").add(rectangle((0, 0), (1, 1)))

    assert dxf.write_model(facade_model, facade_path) is facade_model
    direct_model.write_dxf(direct_path)

    assert facade_path.read_text(encoding="ascii") == direct_path.read_text(encoding="ascii")


def test_model_drawing_write_dxf_convenience(tmp_path) -> None:
    path = tmp_path / "drawing.dxf"
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")
    drawing.layer("PLATE").add(rectangle((0, 0), (1, 1)))

    assert drawing.write_dxf(path) is drawing
    assert "LWPOLYLINE" in path.read_text(encoding="ascii")
