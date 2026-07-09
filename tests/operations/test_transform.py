from __future__ import annotations

from math import pi

import numpy as np
import pytest

from cady.operations.transforms import Transform2, Transform3


def test_transform2_chains_sequential_operations() -> None:
    points = (
        Transform2([[1.0, 0.0]])
        .rotate(pi / 2)
        .scale(2.0)
        .translate(1.0, 0.0)
        .array
    )

    np.testing.assert_allclose(points, [[1.0, 2.0]], atol=1e-12)


def test_transform2_center_mirror_and_linear_transform() -> None:
    around_center = Transform2([[2.0, 1.0]]).rotate(pi / 2, center=(1.0, 1.0)).array
    np.testing.assert_allclose(around_center, [[1.0, 2.0]], atol=1e-12)

    mirrored = Transform2([[2.0, 0.0]]).mirror((0.0, 0.0), (0.0, 1.0)).array
    np.testing.assert_allclose(mirrored, [[-2.0, 0.0]], atol=1e-12)

    sheared = Transform2([[1.0, 2.0]]).transform([[1.0, 2.0], [0.0, 1.0]]).array
    np.testing.assert_allclose(sheared, [[5.0, 2.0]])


def test_transform2_can_apply_delayed_transform_to_points() -> None:
    transform = Transform2().translate(1.0, 2.0).rotate(pi / 2)

    np.testing.assert_allclose(
        transform.apply_points([[1.0, 0.0]]),
        [[-2.0, 2.0]],
        atol=1e-12,
    )


def test_transform3_chains_sequential_operations() -> None:
    points = (
        Transform3([[2.0, 0.0, 0.0]])
        .rotate(axis_dir=(0.0, 0.0, 1.0), angle=pi / 2, axis_origin=(1.0, 0.0, 0.0))
        .translate(0.0, 0.0, 3.0)
        .array
    )

    np.testing.assert_allclose(points, [[1.0, 1.0, 3.0]], atol=1e-12)


def test_transform3_scale_mirror_and_linear_transform() -> None:
    scaled = Transform3([[2.0, 3.0, 4.0]]).scale(
        2.0,
        3.0,
        4.0,
        center=(1.0, 1.0, 1.0),
    ).array
    np.testing.assert_allclose(scaled, [[3.0, 7.0, 13.0]])

    mirrored = Transform3([[1.0, 2.0, 3.0]]).mirror(
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
    ).array
    np.testing.assert_allclose(mirrored, [[-1.0, 2.0, 3.0]])

    flipped = Transform3([[1.0, 2.0, 3.0]]).transform(
        np.diag([-1.0, 1.0, 1.0])
    ).array
    np.testing.assert_allclose(flipped, [[-1.0, 2.0, 3.0]])


def test_transform3_applies_and_composes_delayed_transforms() -> None:
    points = np.array([[1.0, 2.0, 3.0], [2.0, 4.0, 6.0]])
    transform = Transform3().translate(1.0, 2.0, 3.0).compose(
        Transform3().scale(2.0, 3.0, 4.0).translate(-1.0, -2.0, -3.0)
    )

    transformed = transform.apply_points(points)

    np.testing.assert_allclose(transform.inverse().apply_points(transformed), points)
    np.testing.assert_allclose(transform.with_points(points).array, transformed)


def test_transform3_coerce_accepts_none_transform_matrix_and_translation() -> None:
    transform = Transform3().translate(1.0, 2.0, 3.0)

    np.testing.assert_allclose(
        Transform3.coerce(None, allow_none=True).matrix,
        Transform3().matrix,
    )
    np.testing.assert_allclose(Transform3.coerce(transform).matrix, transform.matrix)
    np.testing.assert_allclose(Transform3.coerce(transform.matrix).matrix, transform.matrix)
    np.testing.assert_allclose(
        Transform3.coerce((4.0, 5.0, 6.0)).matrix,
        Transform3().translate(4.0, 5.0, 6.0).matrix,
    )


def test_transform3_coerce_rejects_invalid_values() -> None:
    with pytest.raises(TypeError, match="value must not be None"):
        Transform3.coerce(None)

    with pytest.raises(TypeError, match="value must be Transform3-like or a 3D translation"):
        Transform3.coerce((1.0, 2.0))


def test_transform_rejects_invalid_axes_and_missing_points() -> None:
    with pytest.raises(ValueError, match="axis_dir must be non-zero"):
        Transform3([[1.0, 0.0, 0.0]]).rotate(
            axis_dir=(0.0, 0.0, 0.0),
            angle=pi / 2,
        )

    with pytest.raises(ValueError, match="Transform2 has no points"):
        _points = Transform2().array
