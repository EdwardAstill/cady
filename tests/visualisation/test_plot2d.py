from __future__ import annotations

import pytest

from cady import circle, rectangle

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

from cady.visualisation import plot_shape2d  # noqa: E402


def test_plot_shape2d_saves_png(tmp_path) -> None:
    path = tmp_path / "profile.png"
    profile = rectangle((0, 0), (1, 1)).with_hole(circle((0.5, 0.5), 0.2))

    fig, ax = plot_shape2d(profile, tolerance=1e-2, save_path=path)

    assert fig
    assert ax
    assert path.exists()
    assert path.stat().st_size > 0
