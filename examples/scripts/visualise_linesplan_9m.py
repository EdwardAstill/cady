from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import numpy as np

from cady.files import dxf
from cady.visualisation.vispy_viewer import vispy_view_lines

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "examples" / "inputs" / "linesplan_9m.dxf"


class VertexLike(Protocol):
    x: float
    y: float
    z: float


class WireLike(Protocol):
    vertices: Sequence[VertexLike]


def _wire_points(wire: WireLike) -> np.ndarray:
    return np.array(
        [(vertex.x, vertex.y, vertex.z) for vertex in wire.vertices],
        dtype=np.float32,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()

    result = dxf.read_3d(args.input)
    if not result.wires:
        raise SystemExit(f"{args.input} contains no supported DXF wire polylines")

    print(
        f"viewing {len(result.wires)} DXF wire polylines "
        f"({sum(len(wire.vertices) for wire in result.wires)} vertices)"
    )
    if result.skipped:
        print(f"skipped {len(result.skipped)} unsupported 3D DXF entities")

    vispy_view_lines(
        [_wire_points(wire) for wire in result.wires],
        title=f"cady DXF viewer - {args.input.name}",
        color=(0.05, 0.23, 0.55),
    )


if __name__ == "__main__":
    main()
