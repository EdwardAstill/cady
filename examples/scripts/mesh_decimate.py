"""Simplify several meshes with Mesh3.decimate.

Usage:
    PYTHONPATH=src .venv/bin/python examples/scripts/mesh_decimate.py --no-view
    PYTHONPATH=src .venv/bin/python examples/scripts/mesh_decimate.py --case closed-cylinder
    PYTHONPATH=src .venv/bin/python examples/scripts/mesh_decimate.py --case linesplan-dxf
"""

from __future__ import annotations

import argparse
from math import cos, sin
from pathlib import Path
from typing import NamedTuple

from cady import Camera, DirectionalLight, DisplayStyle, Mesh3, Scene, box, cylinder
from cady.errors import GeometryError
from cady.operations import Transform3

Point3 = tuple[float, float, float]

ROOT = Path(__file__).resolve().parents[2]
LINESPLAN_DXF = ROOT / "examples" / "inputs" / "linesplan_9m.dxf"
CASE_KEYS = ("surface", "closed-box", "closed-cylinder", "linesplan-dxf")

SOURCE_STYLE = DisplayStyle(color=(0.72, 0.76, 0.80), opacity=0.62, render_mode="shaded")
DECIMATED_STYLE = DisplayStyle(color=(0.26, 0.57, 0.84), opacity=0.9, render_mode="shaded")
LIGHT = DirectionalLight(direction=(-0.35, -0.55, -0.76), intensity=1.35)


class DecimationCase(NamedTuple):
    key: str
    label: str
    source: Mesh3
    target_faces: int


class DecimationResult(NamedTuple):
    key: str
    label: str
    source: Mesh3
    decimated: Mesh3
    target_faces: int


def build_source_mesh(*, columns: int = 19, rows: int = 13) -> Mesh3:
    """Build an open wavy height-field mesh."""
    _validate_grid(columns=columns, rows=rows)
    vertices: list[Point3] = []
    for row in range(rows):
        y = -1.0 + 2.0 * row / (rows - 1)
        for column in range(columns):
            x = -1.5 + 3.0 * column / (columns - 1)
            z = 0.18 * sin(3.0 * x) * cos(2.0 * y)
            vertices.append((x, y, z))

    faces: list[tuple[int, int, int]] = []
    for row in range(rows - 1):
        for column in range(columns - 1):
            lower_left = row * columns + column
            lower_right = lower_left + 1
            upper_left = (row + 1) * columns + column
            upper_right = upper_left + 1
            faces.append((lower_left, lower_right, upper_right))
            faces.append((lower_left, upper_right, upper_left))

    return mesh_with_face_edges(Mesh3(tuple(vertices), tuple(faces)))


def build_case(
    key: str,
    *,
    target_faces: int | None = None,
    columns: int = 19,
    rows: int = 13,
    linesplan_nodes: int = 12,
    linesplan_dxf: Path = LINESPLAN_DXF,
    linesplan_tolerance: float = 1e-3,
) -> DecimationCase:
    if key == "surface":
        return DecimationCase(
            key,
            "open height-field mesh",
            build_source_mesh(columns=columns, rows=rows),
            target_faces or 120,
        )
    if key == "closed-box":
        mesh = box(1.2, 1.0, 0.8).to_mesh(tolerance=1e-3)
        return DecimationCase(
            key,
            "closed box mesh",
            mesh_with_face_edges(mesh),
            target_faces or 10,
        )
    if key == "closed-cylinder":
        mesh = cylinder(1.0, 1.5).to_mesh(tolerance=0.1)
        return DecimationCase(
            key,
            "closed cylinder mesh",
            mesh_with_face_edges(mesh),
            target_faces or 16,
        )
    if key == "linesplan-dxf":
        from cady.vessels import Linesplan

        mesh = Linesplan.from_dxf(linesplan_dxf, tolerance=linesplan_tolerance).to_mesh(
            nodes_per_station=linesplan_nodes,
            tolerance=linesplan_tolerance,
        )
        return DecimationCase(
            key,
            "closed linesplan mesh from DXF",
            mesh_with_face_edges(mesh),
            target_faces or 300,
        )
    raise ValueError(f"unknown case: {key}")


def build_cases(
    selection: str,
    *,
    target_faces: int | None = None,
    columns: int = 19,
    rows: int = 13,
    linesplan_nodes: int = 12,
    linesplan_dxf: Path = LINESPLAN_DXF,
    linesplan_tolerance: float = 1e-3,
) -> tuple[DecimationCase, ...]:
    keys = CASE_KEYS if selection == "all" else (selection,)
    return tuple(
        build_case(
            key,
            target_faces=target_faces,
            columns=columns,
            rows=rows,
            linesplan_nodes=linesplan_nodes,
            linesplan_dxf=linesplan_dxf,
            linesplan_tolerance=linesplan_tolerance,
        )
        for key in keys
    )


def decimate_case(case: DecimationCase, *, tolerance: float = 1e-9) -> DecimationResult:
    decimated = mesh_with_face_edges(case.source.decimate(case.target_faces, tolerance=tolerance))
    return DecimationResult(case.key, case.label, case.source, decimated, case.target_faces)


def mesh_with_face_edges(mesh: Mesh3) -> Mesh3:
    return Mesh3(mesh.vertices, mesh.faces, _face_edges(mesh.faces))


def build_scene(source: Mesh3, decimated: Mesh3, *, name: str = "mesh_decimation") -> Scene:
    source_dx, decimated_dx = _comparison_offsets(source, decimated)
    shifted_source = source.transformed(Transform3().translate(source_dx, 0.0, 0.0))
    shifted_decimated = decimated.transformed(Transform3().translate(decimated_dx, 0.0, 0.0))
    lower, upper = _combined_bounds((shifted_source, shifted_decimated))
    return (
        Scene(
            name,
            camera=_fit_camera(lower, upper),
            lights=(LIGHT,),
        )
        .add(
            shifted_source,
            name="source_mesh",
            style=SOURCE_STYLE,
        )
        .add(
            shifted_decimated,
            name="decimated_mesh",
            style=DECIMATED_STYLE,
        )
    )


def build_result_scene(result: DecimationResult) -> Scene:
    return build_scene(result.source, result.decimated, name=result.key)


def result_summary(result: DecimationResult) -> str:
    return "\n".join(
        (
            result.label,
            f"  source: {mesh_summary(result.source)}",
            f"  decimated: {mesh_summary(result.decimated)}",
            f"  target faces: {result.target_faces}",
            f"  removed faces: {len(result.source.faces) - len(result.decimated.faces)}",
        )
    )


def mesh_summary(mesh: Mesh3) -> str:
    lower, upper = mesh.bounds()
    return (
        f"{len(mesh.vertices)} vertices, {len(mesh.edges)} edges, "
        f"{len(mesh.faces)} faces, closed={_closed_state(mesh)}, "
        f"bounds={_format_point(lower)} to {_format_point(upper)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Demonstrate Mesh3.decimate on several meshes")
    parser.add_argument("--case", choices=(*CASE_KEYS, "all"), default="all")
    parser.add_argument(
        "--target-faces",
        type=int,
        default=None,
        help="Override the target face count for the selected case(s)",
    )
    parser.add_argument("--columns", type=int, default=19)
    parser.add_argument("--rows", type=int, default=13)
    parser.add_argument("--linesplan-nodes", type=int, default=12)
    parser.add_argument("--linesplan-dxf", type=Path, default=LINESPLAN_DXF)
    parser.add_argument("--linesplan-tolerance", type=float, default=1e-3)
    parser.add_argument("--tolerance", type=float, default=1e-9)
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Print summaries without opening the VisPy viewer",
    )
    args = parser.parse_args()

    cases = build_cases(
        args.case,
        target_faces=args.target_faces,
        columns=args.columns,
        rows=args.rows,
        linesplan_nodes=args.linesplan_nodes,
        linesplan_dxf=args.linesplan_dxf,
        linesplan_tolerance=args.linesplan_tolerance,
    )
    results = tuple(decimate_case(case, tolerance=args.tolerance) for case in cases)

    print("cady mesh decimation demo")
    print("views: " + ", ".join(result.key for result in results))
    for result in results:
        print()
        print(result_summary(result))

    if args.no_view:
        print("\nVisPy viewer skipped.")
        print("Done.")
        return

    from cady.view import view_scene

    for result in results:
        view_scene(
            build_result_scene(result),
            tolerance=args.tolerance,
            title=f"mesh decimation - {result.label}",
        )
    print("Done.")


def _validate_grid(*, columns: int, rows: int) -> None:
    if columns < 3:
        raise ValueError("columns must be at least 3")
    if rows < 3:
        raise ValueError("rows must be at least 3")


def _face_edges(faces: tuple[tuple[int, ...], ...]) -> tuple[tuple[int, int], ...]:
    edges: set[tuple[int, int]] = set()
    for face in faces:
        for start, end in zip(face, face[1:] + face[:1], strict=True):
            edges.add((min(start, end), max(start, end)))
    return tuple(sorted(edges))


def _closed_state(mesh: Mesh3) -> str:
    try:
        return "yes" if mesh.boundary_loops == () else "no"
    except GeometryError:
        return "undefined"


def _comparison_offsets(source: Mesh3, decimated: Mesh3) -> tuple[float, float]:
    source_span = _span(*source.bounds())
    decimated_span = _span(*decimated.bounds())
    gap = max(source_span[0], decimated_span[0], 1.0) * 0.42
    return (-(source_span[0] + gap) / 2.0, (decimated_span[0] + gap) / 2.0)


def _fit_camera(lower: Point3, upper: Point3) -> Camera:
    centre = _bounds_centre(lower, upper)
    span = _span(lower, upper)
    scale = max(span[0], span[1], span[2] * 4.0, 1.0) * 1.12
    distance = max(span) * 1.65 or 1.0
    return Camera.orthographic(
        position=(centre[0], centre[1] - distance, centre[2] + distance * 0.55),
        target=centre,
        scale=scale,
    )


def _combined_bounds(meshes: tuple[Mesh3, ...]) -> tuple[Point3, Point3]:
    bounds = tuple(mesh.bounds() for mesh in meshes)
    return (
        (
            min(lower[0] for lower, _upper in bounds),
            min(lower[1] for lower, _upper in bounds),
            min(lower[2] for lower, _upper in bounds),
        ),
        (
            max(upper[0] for _lower, upper in bounds),
            max(upper[1] for _lower, upper in bounds),
            max(upper[2] for _lower, upper in bounds),
        ),
    )


def _bounds_centre(lower: Point3, upper: Point3) -> Point3:
    return (
        (lower[0] + upper[0]) / 2.0,
        (lower[1] + upper[1]) / 2.0,
        (lower[2] + upper[2]) / 2.0,
    )


def _span(lower: Point3, upper: Point3) -> Point3:
    return (upper[0] - lower[0], upper[1] - lower[1], upper[2] - lower[2])


def _format_point(point: Point3) -> str:
    return "(" + ", ".join(f"{coordinate:.3g}" for coordinate in point) + ")"


if __name__ == "__main__":
    main()
