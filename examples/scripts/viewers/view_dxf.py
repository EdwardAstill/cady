from collections.abc import Callable
from pathlib import Path
from typing import cast

import numpy as np
from numpy.typing import NDArray

from cady.drawing import Drawing2
from cady.errors import ReadError
from cady.files import dxf

DXF_FILE = Path(__file__).resolve().parents[2] / "files/padeye.dxf"


def view_format(
    drawing: bool = True,
    mesh: bool = False,
    wireframe: bool = True,
    tolerance: float = 1e-3,
) -> None:
    if mesh:
        try:
            dxf.read_mesh(DXF_FILE).view(tolerance=tolerance, title="DXF mesh")
        except ReadError as exc:
            print(f"Skipping mesh view: {exc}")
    if wireframe:
        try:
            dxf.read_wireframe(DXF_FILE).view(tolerance=tolerance, title="DXF wireframe")
        except ReadError as exc:
            print(f"Skipping wireframe view: {exc}")
    if drawing:
        try:
            _view_drawing(dxf.read_drawing(DXF_FILE), tolerance=tolerance)
        except ReadError as exc:
            print(f"Skipping drawing view: {exc}")


def _view_drawing(drawing: Drawing2, *, tolerance: float) -> None:
    from cady.view import view_lines

    lines = _drawing_lines(drawing, tolerance=tolerance)
    if lines:
        view_lines(lines, title="DXF drawing")


def _drawing_lines(drawing: Drawing2, *, tolerance: float) -> tuple[NDArray[np.float64], ...]:
    lines: list[NDArray[np.float64]] = []
    for entity in drawing.entities:
        geometry = getattr(entity, "geometry", None)
        if geometry is None:
            continue

        loops = cast(Callable[..., object] | None, getattr(geometry, "loops", None))
        if callable(loops):
            for loop in cast(tuple[object, ...], loops(tolerance=tolerance)):
                lines.append(_line3(loop, closed=True))
            continue

        to_array = cast(Callable[..., object] | None, getattr(geometry, "to_array", None))
        if callable(to_array):
            lines.append(
                _line3(
                    to_array(tolerance=tolerance),
                    closed=bool(getattr(geometry, "closed", False)),
                )
            )
    return tuple(lines)


def _line3(points: object, *, closed: bool) -> NDArray[np.float64]:
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError("drawing geometry must convert to an (N, 2) array")
    if closed and len(array) > 0 and not np.array_equal(array[0], array[-1]):
        array = np.vstack((array, array[0]))
    z = np.zeros((len(array), 1), dtype=np.float64)
    return np.column_stack((array, z))


if __name__ == "__main__":
    view_format()
