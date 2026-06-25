"""Demo: close a simple wireframe to a plane using close_to_plane.

Builds a 3D square wireframe elevated above the XY plane, visualises it,
then projects the boundary edges to Z=0 and creates wall faces.

Usage:
    PYTHONPATH=src .venv/bin/python examples/linesplan/demo_close_to_plane.py
"""

from __future__ import annotations

from cady import DisplayStyle, Mesh3D, Vec3, Wireframe3D

SQUARE_STYLE = DisplayStyle(color=(0.05, 0.23, 0.55), render_mode="wireframe")
CLOSED_STYLE = DisplayStyle(color=(0.72, 0.25, 0.12))
HIGHLIGHT_STYLE = DisplayStyle(color=(0.12, 0.72, 0.25))


def build_upright_square() -> Wireframe3D:
    """Build a square standing on the XY plane, 2x2, offset 1 unit above Z=0."""
    vertices = (
        Vec3(0, 0, 1),
        Vec3(2, 0, 1),
        Vec3(2, 2, 1),
        Vec3(0, 2, 1),
    )
    edges = ((0, 1), (1, 2), (2, 3), (3, 0))
    return Wireframe3D(vertices, edges)


def build_cube_wireframe() -> Wireframe3D:
    """Build a wireframe cube 2x2x2 with bottom at Z=0."""
    vertices = (
        Vec3(0, 0, 0),
        Vec3(2, 0, 0),
        Vec3(2, 2, 0),
        Vec3(0, 2, 0),  # bottom
        Vec3(0, 0, 2),
        Vec3(2, 0, 2),
        Vec3(2, 2, 2),
        Vec3(0, 2, 2),  # top
    )
    edges = (
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),  # bottom
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),  # top
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),  # verticals
    )
    return Wireframe3D(vertices, edges)


def print_summary(label: str, wf: Wireframe3D, mesh: Mesh3D | None = None) -> None:
    print(f"--- {label} ---")
    print(f"  wireframe: {len(wf.vertices)} vertices, {len(wf.edges)} edges")
    if mesh is not None:
        print(f"  mesh:      {len(mesh.vertices)} vertices, {len(mesh.faces)} faces")


def main() -> None:
    # --- Before ---
    square = build_upright_square()
    print_summary("Upright square (before)", square)
    square.view(title="Wireframe square — before close_to_plane", style=SQUARE_STYLE)

    # Close to Z=0 plane
    closed_square = square.close_to_plane(
        plane_origin=(0, 0, 0),
        plane_normal=(0, 0, 1),
        tolerance=1e-3,
        max_distance=2.0,
    )
    print_summary("Upright square (after)", square, closed_square)
    closed_square.view(title="Wireframe square — after close_to_plane", style=CLOSED_STYLE)

    # --- Cube demo ---
    cube = build_cube_wireframe()
    print_summary("Cube (before)", cube)
    cube.view(title="Wireframe cube — before close_to_plane", style=SQUARE_STYLE)

    # Close bottom to Z=0 (already there, should be no-op or minimal)
    closed_cube = cube.close_to_plane(
        plane_origin=(0, 0, 0),
        plane_normal=(0, 0, 1),
        tolerance=1e-3,
        max_distance=0.1,
    )
    print_summary("Cube bottom (after)", cube, closed_cube)
    closed_cube.view(title="Wireframe cube — bottom to Z=0", style=CLOSED_STYLE)

    # Close top to Z=2
    closed_cube_top = cube.close_to_plane(
        plane_origin=(0, 0, 2),
        plane_normal=(0, 0, 1),
        tolerance=1e-3,
        max_distance=2.0,
    )
    print_summary("Cube top (after)", cube, closed_cube_top)
    closed_cube_top.view(title="Wireframe cube — top to Z=2", style=HIGHLIGHT_STYLE)


if __name__ == "__main__":
    main()
