"""Interactive 3D visualisation demo.

Opens a VisPy window with orbit/pan/zoom controls for each shape.

Usage:
    PYTHONPATH=src python examples/scripts/visualise_3d.py
    PYTHONPATH=src python examples/scripts/visualise_3d.py --shape plate
    PYTHONPATH=src python examples/scripts/visualise_3d.py --shape model
    PYTHONPATH=src python examples/scripts/visualise_3d.py --shape sphere

Controls:
    Left-drag   → orbit (rotate around object)
    Middle-drag → pan (slide the view)
    Scroll      → zoom in/out
    Close window → move to next shape (or exit if it was the last)
"""

from __future__ import annotations

import argparse

from cady import Model, circle, prism, rectangle, sphere


def build_plate():
    """A plate with a circular hole, extruded."""
    profile = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))
    return profile.extrude("+z", 0.04)


def build_model():
    """A model with two parts: a plate and a prism stud."""
    plate = rectangle((0, 0), (1.0, 0.6))
    hole = circle((0.5, 0.3), 0.12)
    profile = plate.with_hole(hole)

    model = Model("demo_model")
    model.part("plate").add(profile.extrude("+z", 0.04))
    model.part("stud").add(prism((0.3, 0.15, 0.04), (0.4, 0.3, 0.06)))
    return model


SHAPES: dict[str, str] = {
    "plate": "Extruded plate with hole",
    "prism": "Plain prism",
    "sphere": "Sphere",
    "model": "Two-part model (plate + stud)",
    "all": "All shapes, one after another",
}


def _try_visualise(label: str, obj: object, *, tolerance: float) -> None:  # noqa: B027 — obj used via .visualise()
    print(f"\n  → {label}")
    print("    Opening window… (close it to continue)")
    try:
        obj.visualise(tolerance=tolerance)  # type: ignore[attr-defined]
    except ImportError:
        print("    (vispy not installed — skipping interactive viewer)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Interactive 3D visualisation demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Controls: left-drag=orbit, middle-drag=pan, scroll=zoom, close=next/exit",
    )
    parser.add_argument(
        "--shape",
        choices=list(SHAPES),
        default="all",
        help="Which shape to visualise (default: all)",
    )
    parser.add_argument("--tolerance", type=float, default=1e-3)
    args = parser.parse_args()

    tolerance = args.tolerance
    choice = args.shape

    print("cady interactive 3D viewer")
    print("  backend: vispy")
    print(f"  tolerance: {tolerance}")
    print(f"  shape: {choice}")

    if choice in ("plate", "all"):
        _try_visualise(SHAPES["plate"], build_plate(), tolerance=tolerance)

    if choice in ("prism", "all"):
        _try_visualise(SHAPES["prism"], prism((0, 0, 0), (1.0, 0.6, 0.4)), tolerance=tolerance)

    if choice in ("sphere", "all"):
        _try_visualise(SHAPES["sphere"], sphere((0, 0, 0), 0.5), tolerance=tolerance)

    if choice in ("model", "all"):
        _try_visualise(SHAPES["model"], build_model(), tolerance=tolerance)

    print("\nDone.")


if __name__ == "__main__":
    main()
