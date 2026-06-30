"""Triangulate and visualise a closed 2D polyline.

Run from the repository root:

    PYTHONPATH=src .venv/bin/python examples/scripts/triangulate_polyline2.py

Edit ``POLYLINE_POINTS`` or import ``triangulate_closed_polyline`` to try a
different closed ``Polyline2``.
"""

from __future__ import annotations

from math import isfinite

from cady import Camera, DisplayStyle, Mesh2, Mesh3, Polyline2, Scene, Wireframe3

Point2 = tuple[float, float]
FaceIndex = tuple[int, int, int]
EdgeIndex = tuple[int, int]

TOLERANCE = 1e-6
POLYLINE_POINTS: tuple[Point2, ...] = (
    (0.0, 0.0),
    (2.0, 0.0),
    (2.0, 1.0),
    (1.0, 0.45),
    (0.0, 1.0),
)

TRIANGLE_STYLE = DisplayStyle(color=(0.46, 0.62, 0.78))
BOUNDARY_STYLE = DisplayStyle(color=(0.95, 0.16, 0.22), render_mode="wireframe")


def example_polyline() -> Polyline2:
    return Polyline2(POLYLINE_POINTS, closed=True)


def triangulate_closed_polyline(
    polyline: Polyline2,
    *,
    tolerance: float = TOLERANCE,
) -> Mesh2:
    if not isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    return polyline.to_mesh(tolerance=tolerance)


def build_scene(polyline: Polyline2, mesh: Mesh2) -> Scene:
    lower, upper = mesh.bounds()
    return (
        Scene("polyline2_triangulation")
        .add(_mesh2_to_flat_mesh3(mesh), name="triangulation", style=TRIANGLE_STYLE)
        .add(_boundary_wire(polyline), name="closed_polyline", style=BOUNDARY_STYLE)
        .with_camera(_fit_camera(lower, upper), name="top")
    )


def mesh_summary(mesh: Mesh2) -> str:
    lines = [
        "cady closed Polyline2 triangulation demo",
        (
            f"mesh: {len(mesh.vertices)} vertices, {len(mesh.edges)} boundary edges, "
            f"{len(mesh.faces)} faces, area={mesh.area:.6g}"
        ),
        "",
        "faces:",
    ]
    for index, face in enumerate(mesh.faces):
        triangle = tuple(mesh.vertices[vertex_index] for vertex_index in face)
        lines.append(
            f"  {index}: {face} -> "
            + ", ".join(_format_point(point) for point in triangle)
        )
    return "\n".join(lines)


def main() -> None:
    polyline = example_polyline()
    mesh = triangulate_closed_polyline(polyline, tolerance=TOLERANCE)
    print(mesh_summary(mesh))

    from cady.view import view_scene

    view_scene(
        build_scene(polyline, mesh),
        tolerance=TOLERANCE,
        title="closed Polyline2 triangulation",
    )


def _mesh2_to_flat_mesh3(mesh: Mesh2) -> Mesh3:
    vertices = tuple((x, y, 0.0) for x, y in mesh.vertices)
    return Mesh3(vertices, mesh.faces, _triangle_edges(mesh.faces))


def _boundary_wire(polyline: Polyline2) -> Wireframe3:
    points = polyline.vertices
    vertices = tuple((x, y, 0.02) for x, y in points)
    edges = tuple((index, (index + 1) % len(vertices)) for index in range(len(vertices)))
    return Wireframe3(vertices, edges)


def _triangle_edges(faces: tuple[FaceIndex, ...]) -> tuple[EdgeIndex, ...]:
    edges: set[EdgeIndex] = set()
    for a, b, c in faces:
        for start, end in ((a, b), (b, c), (c, a)):
            edges.add((min(start, end), max(start, end)))
    return tuple(sorted(edges))


def _fit_camera(lower: Point2, upper: Point2) -> Camera:
    centre = (
        (lower[0] + upper[0]) / 2.0,
        (lower[1] + upper[1]) / 2.0,
        0.0,
    )
    span = max(upper[0] - lower[0], upper[1] - lower[1], 1.0)
    return Camera.orthographic(
        position=(centre[0], centre[1], span * 2.0),
        target=centre,
        up=(0.0, 1.0, 0.0),
        scale=span * 1.25,
    )


def _format_point(point: Point2) -> str:
    return "(" + ", ".join(f"{coordinate:.6g}" for coordinate in point) + ")"


if __name__ == "__main__":
    main()
