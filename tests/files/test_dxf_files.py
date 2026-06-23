from __future__ import annotations

import math

import pytest

from cady import Model, rectangle
from cady.domain import Arc, Circle, DxfDrawing, Line, Polyline
from cady.errors import ReadError
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


def test_read_drawing_imports_basic_entities_from_cady_dxf(tmp_path) -> None:
    path = tmp_path / "drawing.dxf"
    drawing = DxfDrawing()
    drawing.layer("PLATE", color=3, linetype="CENTER").add(rectangle((0, 0), (2, 1)))
    drawing.layer("CUTS", color=1).add(Circle((1, 0.5), 0.2))
    drawing.layer("GEOM").add(Line((0, 0), (1, 1))).add(Arc((1, 1), 0.5, 0.0, math.pi / 2))
    drawing.add_text("LABEL", (0.25, 0.25), 0.1, "TEXT")
    drawing.write(path)

    imported = dxf.read_drawing(path)

    assert imported.layers["PLATE"].color == 3
    assert imported.layers["PLATE"].linetype == "CENTER"
    assert isinstance(imported.layers["PLATE"].entities[0], Polyline)
    assert imported.layers["PLATE"].entities[0].closed is True
    assert isinstance(imported.layers["CUTS"].entities[0], Circle)
    assert isinstance(imported.layers["GEOM"].entities[0], Line)
    assert isinstance(imported.layers["GEOM"].entities[1], Arc)
    assert imported.texts[0].text == "LABEL"
    assert imported.texts[0].layer == "TEXT"


def test_read_drawing_imports_minimal_external_dxf(tmp_path) -> None:
    path = tmp_path / "minimal.dxf"
    path.write_text(
        "\n".join(
            (
                "0",
                "SECTION",
                "2",
                "ENTITIES",
                "0",
                "LINE",
                "8",
                "0",
                "10",
                "0",
                "20",
                "0",
                "11",
                "2.5",
                "21",
                "1.5",
                "0",
                "ENDSEC",
                "0",
                "EOF",
                "",
            )
        ),
        encoding="ascii",
    )

    imported = dxf.read_drawing(path)
    line = imported.layers["0"].entities[0]

    assert isinstance(line, Line)
    assert line.b.x == pytest.approx(2.5)
    assert line.b.y == pytest.approx(1.5)


def test_parse_dxf_rejects_malformed_group_pairs() -> None:
    with pytest.raises(ReadError, match="line pairs"):
        dxf.parse_dxf("0\nSECTION\n2")


def test_parse_dxf_rejects_bad_lwpolyline_count() -> None:
    text = "\n".join(
        (
            "0",
            "SECTION",
            "2",
            "ENTITIES",
            "0",
            "LWPOLYLINE",
            "90",
            "2",
            "70",
            "0",
            "10",
            "0",
            "20",
            "0",
            "0",
            "ENDSEC",
            "0",
            "EOF",
            "",
        )
    )

    with pytest.raises(ReadError, match="expected 2 vertices"):
        dxf.parse_dxf(text)
