from __future__ import annotations

from math import pi

import numpy as np

from cady.numeric.transform import Pose3, Transform2, Transform3


def test_transform2_rotation_origin_and_centre() -> None:
    rotated = Transform2.rotation(pi / 2).apply_points([[1.0, 0.0]])
    np.testing.assert_allclose(rotated, [[0.0, 1.0]], atol=1e-12)

    around_centre = Transform2.rotation(pi / 2, centre=(1.0, 1.0)).apply_points([[2.0, 1.0]])
    np.testing.assert_allclose(around_centre, [[1.0, 2.0]], atol=1e-12)


def test_transform2_compose_applies_other_then_self() -> None:
    transform = Transform2.translation(1.0, 0.0).compose(Transform2.rotation(pi / 2))

    np.testing.assert_allclose(transform.apply_points([[1.0, 0.0]]), [[1.0, 1.0]], atol=1e-12)


def test_transform2_inverse_round_trip_and_mirror() -> None:
    points = np.array([[1.0, 2.0], [3.0, 4.0]])
    transform = Transform2.translation(2.0, -1.0).compose(Transform2.scale(2.0))

    np.testing.assert_allclose(
        transform.inverse().apply_points(transform.apply_points(points)),
        points,
    )
    np.testing.assert_allclose(
        Transform2.mirror((0.0, 0.0), (0.0, 1.0)).apply_points([[2.0, 0.0]]),
        [[-2.0, 0.0]],
    )


def test_transform3_rotation_arbitrary_axis() -> None:
    transform = Transform3.rotation((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), pi / 2)

    np.testing.assert_allclose(
        transform.apply_points([[2.0, 0.0, 0.0]]),
        [[1.0, 1.0, 0.0]],
        atol=1e-12,
    )


def test_transform3_scale_mirror_and_inverse_round_trip() -> None:
    points = np.array([[1.0, 2.0, 3.0], [2.0, 4.0, 6.0]])
    transform = Transform3.translation(1.0, 2.0, 3.0).compose(
        Transform3.scale(2.0, 3.0, 4.0, centre=(1.0, 1.0, 1.0))
    )

    np.testing.assert_allclose(
        transform.inverse().apply_points(transform.apply_points(points)),
        points,
    )
    np.testing.assert_allclose(
        Transform3.mirror((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)).apply_points([[1.0, 2.0, 3.0]]),
        [[-1.0, 2.0, 3.0]],
    )


def test_pose3_and_vectorised_large_transform() -> None:
    points = np.column_stack(
        [
            np.arange(1000, dtype=np.float64),
            np.ones(1000, dtype=np.float64),
            np.zeros(1000, dtype=np.float64),
        ]
    )
    pose = Pose3(np.eye(3), np.array([1.0, 2.0, 3.0]))

    transformed = pose.apply_points(points)

    assert transformed.shape == (1000, 3)
    np.testing.assert_allclose(transformed[0], [1.0, 3.0, 3.0])
    np.testing.assert_allclose(pose.to_transform3().apply_points(points), transformed)
