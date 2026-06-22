from __future__ import annotations

from collections.abc import Iterable

from cady.domain.base import Shape2D, Shape3D
from cady.domain.model import Drawing2D, Model, Part


def shape2d_arrays(shape: Shape2D, *, tolerance: float) -> list[object]:
    return [shape.to_array(tolerance=tolerance)]


def drawing2d_arrays(drawing: Drawing2D, *, tolerance: float) -> list[object]:
    return drawing.to_array(tolerance=tolerance)


def shape3d_array(shape: Shape3D, *, tolerance: float) -> object:
    return shape.to_array(tolerance=tolerance)


def mesh_arrays(value: Shape3D | Part | Model | object, *, tolerance: float) -> list[object]:
    if isinstance(value, Shape3D):
        return [value.to_array(tolerance=tolerance)]
    if isinstance(value, Part | Model):
        return value.to_array(tolerance=tolerance)
    return [value]


def flattened(values: Iterable[object]) -> list[object]:
    return list(values)
