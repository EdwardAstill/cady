from __future__ import annotations

import importlib
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, cast

from cady.domain.base import Shape2D
from cady.domain.model import Drawing2D
from cady.visualisation import styles

Point2Like = Sequence[float]


class FigureLike(Protocol):
    def savefig(self, fname: str | Path) -> object: ...


class Axis2DLike(Protocol):
    figure: FigureLike

    def set_aspect(self, aspect: str, *, adjustable: str) -> object: ...

    def autoscale(self) -> object: ...

    def plot(
        self,
        x_values: Sequence[float],
        y_values: Sequence[float],
        *,
        color: str,
        linewidth: float,
    ) -> object: ...

    def fill(
        self,
        x_values: Sequence[float],
        y_values: Sequence[float],
        *,
        facecolor: str,
        edgecolor: str,
        linewidth: float = 1.0,
        alpha: float = 1.0,
    ) -> object: ...


class PyplotLike(Protocol):
    def subplots(self) -> tuple[FigureLike, Axis2DLike]: ...

    def show(self) -> object: ...


class ArrayPolyline2Like(Protocol):
    vertices: Sequence[Point2Like]
    closed: bool


class ArrayPolygon2Like(Protocol):
    outer: Sequence[Point2Like]
    holes: Sequence[Sequence[Point2Like]]


class Sampleable2Like(Protocol):
    def sample(self, *, samples: int) -> ArrayPolyline2Like: ...


def _import_pyplot() -> PyplotLike:
    try:
        pyplot = importlib.import_module("matplotlib.pyplot")
    except ImportError as exc:
        raise ImportError(
            "2D visualisation requires matplotlib; install cady[visualisation]"
        ) from exc
    return cast(PyplotLike, pyplot)


def _figure_axis(ax: object | None) -> tuple[FigureLike, Axis2DLike]:
    pyplot = _import_pyplot()
    if ax is not None:
        axis = cast(Axis2DLike, ax)
        return axis.figure, axis
    return pyplot.subplots()


def _finish(
    fig: FigureLike,
    ax: Axis2DLike,
    *,
    show: bool,
    save_path: str | Path | None,
) -> tuple[FigureLike, Axis2DLike]:
    ax.set_aspect("equal", adjustable="box")
    ax.autoscale()
    if save_path is not None:
        fig.savefig(Path(save_path))
    if show:
        pyplot = _import_pyplot()
        pyplot.show()
    return fig, ax


def plot_array_polyline2(
    polyline: ArrayPolyline2Like,
    *,
    ax: object | None = None,
) -> tuple[FigureLike, Axis2DLike]:
    fig, axis = _figure_axis(ax)
    vertices = polyline.vertices
    if len(vertices) == 0:
        return fig, axis
    points = vertices
    if polyline.closed:
        points = list(vertices) + [vertices[0]]
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    axis.plot(xs, ys, color=styles.LINE_COLOR, linewidth=styles.LINE_WIDTH)
    return fig, axis


def plot_array_polygon2(
    polygon: ArrayPolygon2Like,
    *,
    ax: object | None = None,
) -> tuple[FigureLike, Axis2DLike]:
    fig, axis = _figure_axis(ax)
    outer = polygon.outer
    xs = [float(point[0]) for point in outer] + [float(outer[0][0])]
    ys = [float(point[1]) for point in outer] + [float(outer[0][1])]
    axis.fill(
        xs,
        ys,
        facecolor=styles.FILL_COLOR,
        edgecolor=styles.EDGE_COLOR,
        linewidth=styles.LINE_WIDTH,
        alpha=0.65,
    )
    for hole in polygon.holes:
        hx = [float(point[0]) for point in hole] + [float(hole[0][0])]
        hy = [float(point[1]) for point in hole] + [float(hole[0][1])]
        axis.fill(hx, hy, facecolor="white", edgecolor=styles.EDGE_COLOR)
    return fig, axis


def _plot_array2(value: object, *, ax: object | None = None) -> tuple[FigureLike, Axis2DLike]:
    if hasattr(value, "outer"):
        return plot_array_polygon2(cast(ArrayPolygon2Like, value), ax=ax)
    if hasattr(value, "vertices"):
        return plot_array_polyline2(cast(ArrayPolyline2Like, value), ax=ax)
    if hasattr(value, "sample"):
        sampled = cast(Sampleable2Like, value).sample(samples=48)
        return plot_array_polyline2(sampled, ax=ax)
    raise TypeError(f"unsupported 2D visualisation object {type(value).__name__}")


def plot_shape2d(
    shape: Shape2D,
    *,
    tolerance: float = 1e-3,
    ax: object | None = None,
    show: bool = False,
    save_path: str | Path | None = None,
) -> tuple[FigureLike, Axis2DLike]:
    fig, axis = _plot_array2(shape.to_array(tolerance=tolerance), ax=ax)
    return _finish(fig, axis, show=show, save_path=save_path)


def plot_drawing2d(
    drawing: Drawing2D,
    *,
    tolerance: float = 1e-3,
    ax: object | None = None,
    show: bool = False,
    save_path: str | Path | None = None,
) -> tuple[FigureLike, Axis2DLike]:
    fig, axis = _figure_axis(ax)
    for value in drawing.to_array(tolerance=tolerance):
        _plot_array2(value, ax=axis)
    return _finish(fig, axis, show=show, save_path=save_path)
