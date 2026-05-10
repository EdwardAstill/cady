from __future__ import annotations

import subprocess
import sys


def test_model_plate_example(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, "examples/model_plate.py", "--out", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""
    assert (tmp_path / "model_plate.dxf").stat().st_size > 0
    assert (tmp_path / "model_plate.stl").stat().st_size > 0
