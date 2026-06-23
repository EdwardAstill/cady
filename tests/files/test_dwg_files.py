from __future__ import annotations

import sys

import pytest

from cady import Model, rectangle
from cady.errors import WriteError
from cady.files import dwg


def _converter_script(tmp_path) -> str:
    script = tmp_path / "copy_converter.py"
    script.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "source = Path(sys.argv[1])\n"
        "target = Path(sys.argv[2])\n"
        "target.write_bytes(b'DWG' + source.read_bytes())\n",
        encoding="ascii",
    )
    return str(script)


def test_write_drawing_uses_configured_converter(tmp_path) -> None:
    path = tmp_path / "drawing.dwg"
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")
    drawing.layer("PLATE").add(rectangle((0, 0), (1, 1)))
    converter = dwg.DwgConverter.from_command(
        (sys.executable, _converter_script(tmp_path), "{input}", "{output}")
    )

    assert dwg.write_drawing(drawing, path, converter=converter) is drawing
    assert path.read_bytes().startswith(b"DWG0\nSECTION")


def test_write_model_uses_environment_converter(tmp_path, monkeypatch) -> None:
    path = tmp_path / "model.dwg"
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    model.drawing("front").layer("PLATE").add(rectangle((0, 0), (1, 1)))
    monkeypatch.setenv(
        dwg.DWG_CONVERTER_ENV,
        f"{sys.executable} {_converter_script(tmp_path)} {{input}} {{output}}",
    )

    assert dwg.write_model(model, path) is model
    assert b"LWPOLYLINE" in path.read_bytes()


def test_convert_to_dxf_uses_converter(tmp_path) -> None:
    source = tmp_path / "source.dwg"
    target = tmp_path / "target.dxf"
    source.write_bytes(b"dwg bytes")
    converter = dwg.DwgConverter.from_command(
        (sys.executable, _converter_script(tmp_path), "{input}", "{output}")
    )

    assert dwg.convert_to_dxf(source, target, converter=converter) == target
    assert target.read_bytes() == b"DWGdwg bytes"


def test_write_drawing_without_converter_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(dwg.DWG_CONVERTER_ENV, raising=False)
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")

    with pytest.raises(WriteError, match="external converter"):
        dwg.write_drawing(drawing, tmp_path / "drawing.dwg")


def test_converter_failure_raises_write_error(tmp_path) -> None:
    script = tmp_path / "failing_converter.py"
    script.write_text(
        "import sys\n"
        "print('conversion failed', file=sys.stderr)\n"
        "raise SystemExit(12)\n",
        encoding="ascii",
    )
    converter = dwg.DwgConverter.from_command((sys.executable, str(script), "{input}", "{output}"))
    source = tmp_path / "source.dxf"
    source.write_text("0\nEOF\n", encoding="ascii")

    with pytest.raises(WriteError, match="conversion failed"):
        converter.convert(source, tmp_path / "out.dwg")
