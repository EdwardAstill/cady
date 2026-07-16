"""Polyline discontinuity and curve-discretization algorithms."""

from collections.abc import Sequence
from math import acos, degrees, dist, isfinite
from typing import TypeAlias

Point2: TypeAlias = Sequence[float]
Point3: TypeAlias = Sequence[float]


def polyline2_discontinuities(
    points: tuple[Point2, ...],
    *,
    closed: bool,
    min_angle_degrees: float,
    min_segment_length: float,
) -> tuple[Point2, ...]:
    """Return 2D points whose adjacent segments meet above a minimum angle."""
    min_angle = _validated_min_angle_degrees(min_angle_degrees)
    min_length = _validated_min_segment_length(min_segment_length)
    if len(points) < 3:
        return ()

    discontinuities: list[Point2] = []
    if closed:
        point_triples = (
            (
                points[(index - 1) % len(points)],
                points[index],
                points[(index + 1) % len(points)],
            )
            for index in range(len(points))
        )
    else:
        point_triples = (
            (points[index - 1], points[index], points[index + 1])
            for index in range(1, len(points) - 1)
        )

    for previous, current, following in point_triples:
        angle = _turn_angle_degrees2(
            previous,
            current,
            following,
            min_segment_length=min_length,
        )
        if angle is not None and angle >= min_angle:
            discontinuities.append(current)
    return tuple(discontinuities)


def polyline3_discontinuities(
    points: tuple[Point3, ...],
    *,
    closed: bool,
    min_angle_degrees: float,
    min_segment_length: float,
) -> tuple[Point3, ...]:
    """Return 3D points whose adjacent segments meet above a minimum angle."""
    min_angle = _validated_min_angle_degrees(min_angle_degrees)
    min_length = _validated_min_segment_length(min_segment_length)
    if len(points) < 3:
        return ()

    discontinuities: list[Point3] = []
    if closed:
        point_triples = (
            (
                points[(index - 1) % len(points)],
                points[index],
                points[(index + 1) % len(points)],
            )
            for index in range(len(points))
        )
    else:
        point_triples = (
            (points[index - 1], points[index], points[index + 1])
            for index in range(1, len(points) - 1)
        )

    for previous, current, following in point_triples:
        angle = _turn_angle_degrees3(
            previous,
            current,
            following,
            min_segment_length=min_length,
        )
        if angle is not None and angle >= min_angle:
            discontinuities.append(current)
    return tuple(discontinuities)


def _turn_angle_degrees2(
    previous: Point2,
    current: Point2,
    following: Point2,
    *,
    min_segment_length: float,
) -> float | None:
    incoming = (current[0] - previous[0], current[1] - previous[1])
    outgoing = (following[0] - current[0], following[1] - current[1])
    incoming_length = dist(previous, current)
    outgoing_length = dist(current, following)
    if incoming_length <= min_segment_length or outgoing_length <= min_segment_length:
        return None
    dot_product = incoming[0] * outgoing[0] + incoming[1] * outgoing[1]
    return _angle_degrees(dot_product, incoming_length, outgoing_length)


def _turn_angle_degrees3(
    previous: Point3,
    current: Point3,
    following: Point3,
    *,
    min_segment_length: float,
) -> float | None:
    incoming = (
        current[0] - previous[0],
        current[1] - previous[1],
        current[2] - previous[2],
    )
    outgoing = (
        following[0] - current[0],
        following[1] - current[1],
        following[2] - current[2],
    )
    incoming_length = dist(previous, current)
    outgoing_length = dist(current, following)
    if incoming_length <= min_segment_length or outgoing_length <= min_segment_length:
        return None
    dot_product = (
        incoming[0] * outgoing[0]
        + incoming[1] * outgoing[1]
        + incoming[2] * outgoing[2]
    )
    return _angle_degrees(dot_product, incoming_length, outgoing_length)


def _angle_degrees(dot_product: float, first_length: float, second_length: float) -> float:
    cosine = dot_product / (first_length * second_length)
    return degrees(acos(max(-1.0, min(1.0, cosine))))


def _validated_min_angle_degrees(value: float) -> float:
    angle = float(value)
    if not isfinite(angle) or angle <= 0.0 or angle > 180.0:
        raise ValueError("min_angle_degrees must be greater than 0 and at most 180")
    return angle


def _validated_min_segment_length(value: float) -> float:
    length = float(value)
    if not isfinite(length) or length < 0.0:
        raise ValueError("min_segment_length must be finite and non-negative")
    return length


__all__ = [
    "polyline2_discontinuities",
    "polyline3_discontinuities",
]
