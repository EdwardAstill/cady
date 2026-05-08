from __future__ import annotations

import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_plate_with_hole_example(tmp_path) -> None:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    subprocess.run(
        [sys.executable, "examples/plate_with_hole.py", "--out", str(tmp_path)],
        cwd=ROOT,
        env=env,
        check=True,
    )
    dxf = tmp_path / "plate.dxf"
    stl = tmp_path / "plate.stl"
    assert dxf.exists()
    assert stl.exists()
    ezdxf = pytest.importorskip("ezdxf")
    types = [entity.dxftype() for entity in ezdxf.readfile(dxf).modelspace()]
    assert "LWPOLYLINE" in types
    assert "CIRCLE" in types
    data = stl.read_bytes()
    assert struct.unpack("<I", data[80:84])[0] > 0


def test_example_uses_public_factories() -> None:
    text = (ROOT / "examples" / "plate_with_hole.py").read_text(encoding="utf-8")
    for forbidden in ("Polyline(", "Circle(", "Vec2(", "Vec3("):
        assert forbidden not in text
