from __future__ import annotations

import pytest

from cady import prism

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

from cady.visualisation import view_shape3d  # noqa: E402


def test_view_shape3d_saves_png(tmp_path) -> None:
    path = tmp_path / "solid.png"

    fig = view_shape3d(
        prism((0, 0, 0), (1, 1, 1)),
        backend="matplotlib",
        show=False,
        save_path=path,
    )

    assert fig
    assert path.exists()
    assert path.stat().st_size > 0
