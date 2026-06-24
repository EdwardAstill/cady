from __future__ import annotations

import importlib
from pathlib import Path
from typing import cast

from cady.domain.base import Shape3D
from cady.domain.model import Model, Part
from cady.plotting.plot3d import ArrayMesh3Like, PyplotLike, plot_array_mesh3


def _show_matplotlib() -> None:
    try:
        pyplot = importlib.import_module("matplotlib.pyplot")
    except ImportError as exc:
        raise ImportError("3D plotting requires matplotlib; install cady[plotting]") from exc
    cast(PyplotLike, pyplot).show()


def view_shape3d(
    shape: Shape3D | object,
    *,
    tolerance: float = 1e-3,
    backend: str = "matplotlib",
    show: bool = True,
    save_path: str | Path | None = None,
) -> object:
    mesh = cast(
        ArrayMesh3Like,
        shape.to_array(tolerance=tolerance) if isinstance(shape, Shape3D) else shape,
    )
    if backend == "matplotlib":
        return plot_array_mesh3(mesh, show=show, save_path=save_path)[0]
    raise ValueError(f"unknown 3D visualisation backend {backend!r}")


def view_model(
    model: Model | Part,
    *,
    tolerance: float = 1e-3,
    backend: str = "matplotlib",
    show: bool = True,
    save_path: str | Path | None = None,
) -> object:
    if backend != "matplotlib":
        raise ValueError(f"unknown 3D visualisation backend {backend!r}")

    meshes = [cast(ArrayMesh3Like, mesh) for mesh in model.to_array(tolerance=tolerance)]
    if not meshes:
        raise ValueError("cannot visualise an empty model")

    fig, axis = plot_array_mesh3(meshes[0], show=False)
    for mesh in meshes:
        if mesh is not meshes[0]:
            plot_array_mesh3(mesh, ax=axis, show=False)
    if save_path is not None:
        fig.savefig(Path(save_path))
    if show:
        _show_matplotlib()
    return fig


def view_part(
    part: Part,
    *,
    tolerance: float = 1e-3,
    backend: str = "matplotlib",
    show: bool = True,
    save_path: str | Path | None = None,
) -> object:
    return view_model(part, tolerance=tolerance, backend=backend, show=show, save_path=save_path)


def visualise(
    value: Shape3D | Model | Part | object,
    *,
    tolerance: float = 1e-3,
    backend: str = "matplotlib",
    show: bool = True,
    save_path: str | Path | None = None,
) -> object:
    if isinstance(value, Shape3D):
        return view_shape3d(
            value,
            tolerance=tolerance,
            backend=backend,
            show=show,
            save_path=save_path,
        )
    if isinstance(value, (Model, Part)):
        return view_model(
            value,
            tolerance=tolerance,
            backend=backend,
            show=show,
            save_path=save_path,
        )
    return view_shape3d(
        value,
        tolerance=tolerance,
        backend=backend,
        show=show,
        save_path=save_path,
    )
