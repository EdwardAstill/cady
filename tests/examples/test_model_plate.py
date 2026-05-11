from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_model_plate_example(tmp_path) -> None:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(
        [sys.executable, "examples/scripts/model_plate.py", "--out", str(tmp_path)],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""
    assert (tmp_path / "model_plate.dxf").stat().st_size > 0
    assert (tmp_path / "model_plate.stl").stat().st_size > 0
