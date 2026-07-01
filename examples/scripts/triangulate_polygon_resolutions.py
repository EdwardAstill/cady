"""Compare cady polygon triangulation at different mesh sizes.

Run from the repository root:

    PYTHONPATH=src .venv/bin/python examples/scripts/triangulate_polygon_resolutions.py
"""

from __future__ import annotations

from collections.abc import Iterable
from math import isfinite

from cady import Camera, DisplayStyle, Mesh3, Polyline3, Scene
from cady.operations import Transform3, TriangulationGuide, triangulate_curve3

Point3 = tuple[float, float, float]
EdgeIndex = tuple[int, int]

TOLERANCE = 1e-6
MAX_EDGE_LENGTHS = (None, 0.75, 0.35, 0.18)
POLYGON_POINTS: tuple[Point3, ...] = (
    (-1.65, -0.25, 0.0),
    (-1.05, -0.9, 0.0),
    (-0.2, -0.82, 0.0),
    (0.35, -1.18, 0.0),
    (1.35, -0.6, 0.0),
    (1.7, 0.18, 0.0),
    (0.85, 0.5, 0.0),
    (0.55, 1.1, 0.0),
    (-0.28, 0.68, 0.0),
    (-1.18, 0.96, 0.0),
    (-1.58, 0.35, 0.0),
)

MESH_STYLES = (
    DisplayStyle(color=(0.52, 0.64, 0.74), opacity=0.82),
    DisplayStyle(color=(0.35, 0.66, 0.58), opacity=0.82),
    DisplayStyle(color=(0.84, 0.57, 0.34), opacity=0.82),
    DisplayStyle(color=(0.73, 0.48, 0.70), opacity=0.82),
)


def example_polyline() -> Polyline3:
    return Polyline3(POLYGON_POINTS, closed=True)


def triangulate_polygon(
    polyline: Polyline3,
    *,
    max_edge_length: float | None = None,
    tolerance: float = TOLERANCE,
) -> Mesh3:
    if not isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    if max_edge_length is not None and (not isfinite(max_edge_length) or max_edge_length <= 0.0):
        raise ValueError("max_edge_length must be positive")

    guide = None if max_edge_length is None else TriangulationGuide(max_edge_length=max_edge_length)
    mesh = triangulate_curve3(polyline, tolerance=tolerance, guide=guide)
    return Mesh3(mesh.vertices, mesh.faces, _face_edges(mesh.faces))


def triangulate_resolutions(
    polyline: Polyline3,
    *,
    max_edge_lengths: Iterable[float | None] = MAX_EDGE_LENGTHS,
    tolerance: float = TOLERANCE,
) -> tuple[tuple[float | None, Mesh3], ...]:
    return tuple(
        (
            max_edge_length,
            triangulate_polygon(
                polyline,
                max_edge_length=max_edge_length,
                tolerance=tolerance,
            ),
        )
        for max_edge_length in max_edge_lengths
    )


def build_scene(cases: tuple[tuple[float | None, Mesh3], ...]) -> Scene:
    spacing = 4.25
    centre = (len(cases) - 1) / 2.0
    scene = Scene(
        "polygon_triangulation_sizes",
        camera=Camera.orthographic(
            position=(0.0, 0.0, 11.0),
            target=(0.0, 0.0, 0.0),
            up=(0.0, 1.0, 0.0),
            scale=10.5,
        ),
    )
    for index, (max_edge_length, mesh) in enumerate(cases):
        offset = (index - centre) * spacing
        scene = scene.add(
            mesh.transformed(Transform3().translate(offset, 0.0, 0.0)),
            name=_case_name(max_edge_length),
            style=MESH_STYLES[index % len(MESH_STYLES)],
        )
    return scene


def mesh_summary(cases: tuple[tuple[float | None, Mesh3], ...]) -> str:
    lines = ["cady polygon triangulation size comparison"]
    for max_edge_length, mesh in cases:
        lines.append(
            f"{_case_name(max_edge_length)}: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces"
        )
    return "\n".join(lines)


def main() -> None:
    cases = triangulate_resolutions(example_polyline())
    print(mesh_summary(cases))
    build_scene(cases).view(
        tolerance=TOLERANCE,
        title="polygon triangulation sizes",
    )


def _face_edges(faces: Iterable[tuple[int, ...]]) -> tuple[EdgeIndex, ...]:
    edges: set[EdgeIndex] = set()
    for face in faces:
        if len(face) != 3:
            raise ValueError("triangulation faces must be triangles")
        a, b, c = face
        for start, end in ((a, b), (b, c), (c, a)):
            edges.add((min(start, end), max(start, end)))
    return tuple(sorted(edges))


def _case_name(max_edge_length: float | None) -> str:
    if max_edge_length is None:
        return "original boundary"
    return f"max edge {max_edge_length:g}"


if __name__ == "__main__":
    main()
