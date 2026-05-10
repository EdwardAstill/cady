from __future__ import annotations

import subprocess
import sys


def test_production_dxf_example(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, "examples/production_dxf.py", "--out", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""
    assert (tmp_path / "production_plate.dxf").stat().st_size > 0
