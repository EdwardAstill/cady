from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_production_dxf_example(tmp_path) -> None:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "examples/scripts/production_dxf.py", "--out", str(tmp_path)],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""
    text = (tmp_path / "production_plate.dxf").read_text(encoding="ascii")
    assert "DIA 0.24" in text
    assert "R0.12" in text
    assert text.count("\n0\nHATCH\n") == 1
    assert text.count("\n0\nDIMENSION\n") == 4


def test_production_dxf_gallery_uses_native_dimensions() -> None:
    ezdxf = pytest.importorskip("ezdxf")
    doc = ezdxf.readfile(ROOT / "examples" / "gallery" / "production_plate.dxf")
    audit = doc.audit()
    dimensions = list(doc.modelspace().query("DIMENSION"))

    assert not audit.errors
    assert len(dimensions) == 4
