"""Simplify a triangle mesh with Mesh3.decimate.

Usage:
    PYTHONPATH=src .venv/bin/python examples/scripts/mesh_decimate.py --no-view
    PYTHONPATH=src .venv/bin/python examples/scripts/mesh_decimate.py --target-faces 80
"""

from __future__ import annotations

import argparse
from math import cos, sin

from cady import Camera, DirectionalLight, DisplayStyle, Mesh3, Scene
from cady.operations import Transform3

Point3 = tuple[float, float, float]

SOURCE_STYLE = DisplayStyle(color=(0.72, 0.76, 0.80), opacity=0.62, render_mode="shaded")
DECIMATED_STYLE = DisplayStyle(color=(0.26, 0.57, 0.84), opacity=0.9, render_mode="shaded")
LIGHT = DirectionalLight(direction=(-0.35, -0.55, -0.76), intensity=1.35)


def build_source_mesh(*, columns: int = 19, rows: int = 13) -> Mesh3:
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


def mesh_with_face_edges(mesh: Mesh3) -> Mesh3:
    return Mesh3(mesh.vertices, mesh.faces, _face_edges(mesh.faces))


def build_scene(source: Mesh3, decimated: Mesh3) -> Scene:
    return (
        Scene(
            "mesh_decimation",
            camera=Camera.orthographic(
                position=(0.0, -5.0, 3.0),
                target=(0.0, 0.0, 0.0),
                scale=4.2,
            ),
            lights=(LIGHT,),
        )
        .add(
            source.transformed(Transform3().translate(-1.9, 0.0, 0.0)),
            name="source_mesh",
            style=SOURCE_STYLE,
        )
        .add(
            decimated.transformed(Transform3().translate(1.9, 0.0, 0.0)),
            name="decimated_mesh",
            style=DECIMATED_STYLE,
        )
    )


def mesh_summary(label: str, mesh: Mesh3) -> str:
    lower, upper = mesh.bounds()
    return (
        f"{label}: {len(mesh.vertices)} vertices, {len(mesh.edges)} edges, "
        f"{len(mesh.faces)} faces, "
        f"bounds={_format_point(lower)} to {_format_point(upper)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Demonstrate Mesh3.decimate on a generated mesh")
    parser.add_argument("--target-faces", type=int, default=120)
    parser.add_argument("--columns", type=int, default=19)
    parser.add_argument("--rows", type=int, default=13)
    parser.add_argument("--tolerance", type=float, default=1e-9)
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Print summaries without opening the VisPy viewer",
    )
    args = parser.parse_args()

    source = build_source_mesh(columns=args.columns, rows=args.rows)
    decimated = mesh_with_face_edges(source.decimate(args.target_faces, tolerance=args.tolerance))

    print("cady mesh decimation demo")
    print(mesh_summary("source", source))
    print(mesh_summary("decimated", decimated))
    print(f"target faces: {args.target_faces}")
    print(f"removed faces: {len(source.faces) - len(decimated.faces)}")

    if args.no_view:
        print("VisPy viewer skipped.")
        print("Done.")
        return

    from cady.view import view_scene

    view_scene(build_scene(source, decimated), tolerance=args.tolerance, title="mesh decimation")
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


def _format_point(point: Point3) -> str:
    return "(" + ", ".join(f"{coordinate:.3g}" for coordinate in point) + ")"


if __name__ == "__main__":
    main()
