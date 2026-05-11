from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_production_step_example(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "examples/scripts/production_step.py", "--out", str(tmp_path)],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""
    text = (tmp_path / "production_plate.step").read_text(encoding="ascii")
    assert "ISO-10303-21" in text
    assert "AUTOMOTIVE_DESIGN" in text
    assert text.count("MANIFOLD_SOLID_BREP") == 2


def test_production_step_gallery_artifact_exists() -> None:
    artifact = ROOT / "examples" / "gallery" / "production_plate.step"
    assert artifact.exists(), "run production_step.py to regenerate gallery artifact"
    text = artifact.read_text(encoding="ascii")
    assert "ISO-10303-21" in text
    assert text.count("MANIFOLD_SOLID_BREP") == 2
