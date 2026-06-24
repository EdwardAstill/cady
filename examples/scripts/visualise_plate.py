from __future__ import annotations

import argparse
import importlib.util
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

from model_plate import build_model

GALLERY_DIR = Path(__file__).resolve().parents[1] / "gallery"


class ArrayMesh3Class(Protocol):
    @classmethod
    def merged(cls, meshes: object) -> object: ...


PlotArrayMesh3 = Callable[..., object]
PlotDrawing2D = Callable[..., object]


def _load_visualisation() -> tuple[type[ArrayMesh3Class], PlotArrayMesh3, PlotDrawing2D] | str:
    for module in ("numpy", "matplotlib"):
        if importlib.util.find_spec(module) is None:
            return module
    try:
        from cady.numeric import ArrayMesh3
        from cady.plotting import plot_array_mesh3, plot_drawing2d
    except ImportError as exc:
        return str(exc)
    return cast(type[ArrayMesh3Class], ArrayMesh3), plot_array_mesh3, plot_drawing2d


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=GALLERY_DIR)
    parser.add_argument("--tolerance", type=float, default=1e-3)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    visualisation = _load_visualisation()
    if isinstance(visualisation, str):
        print(f"cady visualisation prerequisites are not available: {visualisation}")
        return

    ArrayMesh3, plot_array_mesh3, plot_drawing2d = visualisation
    model = build_model()

    plot_drawing2d(
        model.drawing("front"),
        tolerance=args.tolerance,
        save_path=args.out / "visualise_plate_2d.png",
        show=args.show,
    )

    meshes = model.to_array(tolerance=args.tolerance)
    mesh = meshes[0] if len(meshes) == 1 else ArrayMesh3.merged(meshes)
    plot_array_mesh3(
        mesh,
        save_path=args.out / "visualise_plate_3d.png",
        show=args.show,
    )


if __name__ == "__main__":
    main()
