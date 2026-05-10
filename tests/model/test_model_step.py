from __future__ import annotations

import pytest

from cad import Model


def test_write_step_is_reserved_for_stage_5(tmp_path) -> None:
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    with pytest.raises(NotImplementedError, match="Stage 5"):
        model.write_step(tmp_path / "demo.step")
