from __future__ import annotations

import math

import pytest

from cady.utils import finite, loop_edges, positive, positive_tolerance


def test_finite_positive_and_tolerance_validation() -> None:
    assert finite(1.5, "value") == 1.5
    assert positive(2, "length") == 2.0
    assert positive_tolerance(1e-3) == 1e-3

    with pytest.raises(ValueError, match="value must be finite"):
        finite(math.inf, "value")
    with pytest.raises(ValueError, match="length must be positive"):
        positive(0.0, "length")
    with pytest.raises(ValueError, match="tolerance must be positive"):
        positive_tolerance(-1.0)


def test_loop_edges_returns_closed_index_loop() -> None:
    assert loop_edges(4) == ((0, 1), (1, 2), (2, 3), (3, 0))
