from __future__ import annotations

import importlib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol, cast

from cady.plotting import styles

Point3Like = Sequence[float]


class FigureLike(Protocol):
    def add_subplot(self, *args: object, projection: str) -> object: ...

    def savefig(self, fname: str | Path) -> object: ...


class Axis3DLike(Protocol):
    figure: FigureLike

    def add_collection3d(self, collection: object) -> object: ...

    def set_xlim(self, left: float, right: float) -> object: ...

    def set_ylim(self, left: float, right: float) -> object: ...

    def set_zlim(self, left: float, right: float) -> object: ...


class PyplotLike(Protocol):
    def figure(self) -> FigureLike: ...

    def show(self) -> object: ...


class ArrayMesh3Like(Protocol):
    vertices: Sequence[Point3Like]
    faces: Sequence[Sequence[int]]
    triangles: Sequence[Sequence[Point3Like]]


def _import_pyplot() -> PyplotLike:
    try:
        pyplot = importlib.import_module("matplotlib.pyplot")
    except ImportError as exc:
        raise ImportError("3D plotting requires matplotlib; install cady[plotting]") from exc
    return cast(PyplotLike, pyplot)


def _figure_axis(ax: object | None) -> tuple[FigureLike, Axis3DLike]:
    if ax is not None:
        axis = cast(Axis3DLike, ax)
        return axis.figure, axis
    pyplot = _import_pyplot()
    fig = pyplot.figure()
    return fig, cast(Axis3DLike, fig.add_subplot(111, projection="3d"))


def _set_equal_axes(ax: Axis3DLike, vertices: Sequence[Point3Like]) -> None:
    xs = [float(point[0]) for point in vertices]
    ys = [float(point[1]) for point in vertices]
    zs = [float(point[2]) for point in vertices]
    if not xs:
        return
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    cz = (min(zs) + max(zs)) / 2
    radius = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1e-9) / 2
    ax.set_xlim(cx - radius, cx + radius)
    ax.set_ylim(cy - radius, cy + radius)
    ax.set_zlim(cz - radius, cz + radius)


def _finish(fig: FigureLike, *, show: bool, save_path: str | Path | None) -> FigureLike:
    if save_path is not None:
        fig.savefig(Path(save_path))
    if show:
        pyplot = _import_pyplot()
        pyplot.show()
    return fig


def plot_array_mesh3(
    mesh: ArrayMesh3Like,
    *,
    ax: object | None = None,
    show: bool = False,
    save_path: str | Path | None = None,
    wireframe: bool = True,
    face_opacity: float = styles.FACE_ALPHA,
) -> tuple[FigureLike, Axis3DLike]:
    try:
        art3d = importlib.import_module("mpl_toolkits.mplot3d.art3d")
    except ImportError as exc:
        raise ImportError("3D plotting requires matplotlib; install cady[plotting]") from exc
    poly3d_collection = cast(
        Callable[..., object],
        getattr(art3d, "Poly3DCollection"),  # noqa: B009
    )

    fig, axis = _figure_axis(ax)
    collection = poly3d_collection(
        mesh.triangles,
        alpha=face_opacity,
        facecolor=styles.MESH_COLOR,
        edgecolor=styles.MESH_EDGE_COLOR if wireframe else styles.MESH_COLOR,
        linewidth=0.4 if wireframe else 0.0,
    )
    axis.add_collection3d(collection)
    _set_equal_axes(axis, mesh.vertices)
    _finish(fig, show=show, save_path=save_path)
    return fig, axis
