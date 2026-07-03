"""Compare cady polygon triangulation at different mesh sizes.

Run from the repository root:

    PYTHONPATH=src .venv/bin/python examples/scripts/triangulate_polygon_resolutions.py
"""

from collections.abc import Iterable, Sequence
from math import acos, ceil, degrees, isfinite, radians, sqrt, tan
from typing import Literal, TypeAlias

from cady import Camera, DisplayStyle, Mesh3, Polyline3, Scene

Point3: TypeAlias = tuple[float, float, float]
EdgeIndex: TypeAlias = tuple[int, int]
FaceIndex: TypeAlias = tuple[int, ...]
ResolutionSpec: TypeAlias = float | Literal["auto"] | None
MinAngleSpec: TypeAlias = float | None

TOLERANCE = 1e-6
MAX_EDGE_LENGTHS: tuple[ResolutionSpec, ...] = (None, "auto", 0.75, 0.35, 0.18)
MIN_ANGLE_DEGREES: tuple[MinAngleSpec, ...] = (None, 5.0, 10.0, 15.0)

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
NARROW_CHANNEL_POINTS: tuple[Point3, ...] = (
    (-2.0, -1.0, 0.0),
    (2.0, -1.0, 0.0),
    (2.0, -0.55, 0.0),
    (-1.15, -0.55, 0.0),
    (-1.15, 0.55, 0.0),
    (2.0, 0.55, 0.0),
    (2.0, 1.0, 0.0),
    (-2.0, 1.0, 0.0),
)
COMB_POINTS: tuple[Point3, ...] = (
    (-2.0, -1.0, 0.0),
    (2.0, -1.0, 0.0),
    (2.0, 1.0, 0.0),
    (1.65, 1.0, 0.0),
    (1.65, 0.15, 0.0),
    (1.25, 0.15, 0.0),
    (1.25, 1.0, 0.0),
    (0.85, 1.0, 0.0),
    (0.85, 0.15, 0.0),
    (0.45, 0.15, 0.0),
    (0.45, 1.0, 0.0),
    (0.05, 1.0, 0.0),
    (0.05, 0.15, 0.0),
    (-0.35, 0.15, 0.0),
    (-0.35, 1.0, 0.0),
    (-0.75, 1.0, 0.0),
    (-0.75, 0.15, 0.0),
    (-1.15, 0.15, 0.0),
    (-1.15, 1.0, 0.0),
    (-2.0, 1.0, 0.0),
)
THIN_NECK_POINTS: tuple[Point3, ...] = (
    (-2.0, -0.9, 0.0),
    (-0.8, -0.9, 0.0),
    (-0.45, -0.25, 0.0),
    (0.45, -0.25, 0.0),
    (0.8, -0.9, 0.0),
    (2.0, -0.9, 0.0),
    (2.0, 0.9, 0.0),
    (0.8, 0.9, 0.0),
    (0.45, 0.25, 0.0),
    (-0.45, 0.25, 0.0),
    (-0.8, 0.9, 0.0),
    (-2.0, 0.9, 0.0),
)
CRESCENT_POINTS: tuple[Point3, ...] = (
    (0.9, -1.15, 0.0),
    (0.15, -1.45, 0.0),
    (-0.75, -1.25, 0.0),
    (-1.35, -0.7, 0.0),
    (-1.55, 0.0, 0.0),
    (-1.35, 0.7, 0.0),
    (-0.75, 1.25, 0.0),
    (0.15, 1.45, 0.0),
    (0.9, 1.15, 0.0),
    (0.45, 0.72, 0.0),
    (0.18, 0.25, 0.0),
    (0.1, -0.25, 0.0),
    (0.35, -0.78, 0.0),
)
LONG_SLIVER_POINTS: tuple[Point3, ...] = (
    (-2.2, -0.04, 0.0),
    (2.2, -0.04, 0.0),
    (2.2, 0.04, 0.0),
    (-2.2, 0.04, 0.0),
)
TAPERED_NEEDLE_POINTS: tuple[Point3, ...] = (
    (-2.2, -0.18, 0.0),
    (1.95, -0.08, 0.0),
    (2.12, -0.02, 0.0),
    (2.12, 0.02, 0.0),
    (1.95, 0.08, 0.0),
    (-2.2, 0.18, 0.0),
)
HAIRLINE_SLOT_POINTS: tuple[Point3, ...] = (
    (-2.2, -0.28, 0.0),
    (2.2, -0.28, 0.0),
    (2.2, -0.18, 0.0),
    (-1.85, -0.18, 0.0),
    (-1.85, -0.14, 0.0),
    (2.2, -0.14, 0.0),
    (2.2, 0.28, 0.0),
    (-2.2, 0.28, 0.0),
)
JAGGED_BAY_POINTS: tuple[Point3, ...] = (
    (-2.0, -0.8, 0.0),
    (-1.6, -1.1, 0.0),
    (-1.1, -0.82, 0.0),
    (-0.65, -1.18, 0.0),
    (-0.2, -0.82, 0.0),
    (0.25, -1.12, 0.0),
    (0.8, -0.78, 0.0),
    (1.4, -1.0, 0.0),
    (1.9, -0.45, 0.0),
    (1.55, 0.05, 0.0),
    (1.9, 0.55, 0.0),
    (1.25, 0.9, 0.0),
    (0.75, 0.55, 0.0),
    (0.35, 1.12, 0.0),
    (-0.1, 0.58, 0.0),
    (-0.55, 1.0, 0.0),
    (-1.0, 0.48, 0.0),
    (-1.55, 0.85, 0.0),
    (-1.9, 0.2, 0.0),
    (-1.45, -0.2, 0.0),
)
POLYGON_CASES: tuple[tuple[str, tuple[Point3, ...]], ...] = (
    ("coastal concave", POLYGON_POINTS),
    ("narrow channel", NARROW_CHANNEL_POINTS),
    ("comb teeth", COMB_POINTS),
    ("thin neck", THIN_NECK_POINTS),
    ("crescent moon", CRESCENT_POINTS),
    ("long sliver", LONG_SLIVER_POINTS),
    ("tapered needle", TAPERED_NEEDLE_POINTS),
    ("hairline slot", HAIRLINE_SLOT_POINTS),
    ("jagged bay", JAGGED_BAY_POINTS),
)

MESH_STYLES = (
    DisplayStyle(color=(0.52, 0.64, 0.74), opacity=0.82),
    DisplayStyle(color=(0.35, 0.66, 0.58), opacity=0.82),
    DisplayStyle(color=(0.84, 0.57, 0.34), opacity=0.82),
    DisplayStyle(color=(0.73, 0.48, 0.70), opacity=0.82),
    DisplayStyle(color=(0.62, 0.58, 0.36), opacity=0.82),
)
HEURISTIC_STYLE = DisplayStyle(color=(0.35, 0.66, 0.58), opacity=0.82)
INPUT_POLYGON_STYLE = DisplayStyle(color=(0.05, 0.18, 0.32), render_mode="wireframe")


def example_polyline() -> Polyline3:
    return Polyline3(POLYGON_POINTS, closed=True)


def polygon_mesh_from_points(points: Sequence[Point3]) -> Mesh3:
    vertices = tuple((float(x), float(y), float(z)) for x, y, z in points)
    face = tuple(range(len(vertices)))
    return Mesh3(vertices, (face,), _polygon_face_edges((face,)))


def polygon_mesh_from_polyline(polyline: Polyline3, *, tolerance: float = TOLERANCE) -> Mesh3:
    return polygon_mesh_from_points(
        tuple((float(x), float(y), float(z)) for x, y, z in polyline.to_array(tolerance=tolerance))
    )


def triangulate3d(
    mesh: Mesh3,
    *,
    tolerance: float = TOLERANCE,
    max_edge_length: float | None = None,
    min_angle_degrees: float | None = None,
) -> Mesh3:
    if not isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("tolerance must be positive")
    if max_edge_length is not None and (not isfinite(max_edge_length) or max_edge_length <= 0.0):
        raise ValueError("max_edge_length must be positive")
    if min_angle_degrees is not None and (
        not isfinite(min_angle_degrees) or min_angle_degrees <= 0.0
    ):
        raise ValueError("min_angle_degrees must be positive")
    if not mesh.faces:
        return Mesh3(mesh.vertices, (), mesh.edges)
    return mesh.triangulate(
        tolerance=tolerance,
        max_edge_length=max_edge_length,
        min_angle_degrees=min_angle_degrees,
    )


def triangulate_polygon(
    polyline: Polyline3,
    *,
    max_edge_length: ResolutionSpec = None,
    tolerance: float = TOLERANCE,
) -> Mesh3:
    if max_edge_length is not None and max_edge_length != "auto" and (
        not isfinite(max_edge_length) or max_edge_length <= 0.0
    ):
        raise ValueError("max_edge_length must be positive")

    polygon = polygon_mesh_from_polyline(polyline, tolerance=tolerance)
    resolved_max_edge_length = (
        _auto_max_edge_length(polygon, tolerance=tolerance)
        if max_edge_length == "auto"
        else max_edge_length
    )
    return triangulate3d(
        polygon,
        tolerance=tolerance,
        max_edge_length=resolved_max_edge_length,
    )


def triangulate_polygon_heuristic(
    polygon: Mesh3,
    *,
    tolerance: float = TOLERANCE,
) -> Mesh3:
    return triangulate3d(
        polygon,
        tolerance=tolerance,
        max_edge_length=_auto_max_edge_length(polygon, tolerance=tolerance),
    )


def _auto_max_edge_length(
    polygon: Mesh3,
    *,
    tolerance: float,
    min_angle_degrees: float | None = None,
) -> float | None:
    lengths = sorted(
        _edge_length(polygon.vertices[start], polygon.vertices[end])
        for start, end in polygon.edges
        if _edge_length(polygon.vertices[start], polygon.vertices[end]) > tolerance
    )
    if not lengths:
        return None

    lower, upper = polygon.bounds()
    span = sqrt(
        (upper[0] - lower[0]) ** 2
        + (upper[1] - lower[1]) ** 2
        + (upper[2] - lower[2]) ** 2
    )
    if span <= tolerance:
        return None

    boundary_feature = lengths[min(len(lengths) - 1, int(0.40 * (len(lengths) - 1)))]
    span_feature = span / 5.0
    max_edge_length = max(tolerance * 8.0, min(boundary_feature, span_feature))
    if min_angle_degrees is not None:
        max_edge_length = min(
            max_edge_length,
            _min_angle_edge_length(lengths[0], min_angle_degrees, tolerance=tolerance),
        )
    return max_edge_length


def _edge_length(start: Point3, end: Point3) -> float:
    return sqrt(
        (end[0] - start[0]) ** 2
        + (end[1] - start[1]) ** 2
        + (end[2] - start[2]) ** 2
    )


def _min_angle_edge_length(
    shortest_feature: float,
    min_angle_degrees: float,
    *,
    tolerance: float,
) -> float:
    tangent = tan(radians(min_angle_degrees))
    if tangent <= 0.0:
        return max(shortest_feature, tolerance * 8.0)
    return max(shortest_feature / tangent, tolerance * 8.0)


def triangulate_resolutions(
    polyline: Polyline3,
    *,
    max_edge_lengths: Iterable[ResolutionSpec] = MAX_EDGE_LENGTHS,
    tolerance: float = TOLERANCE,
) -> tuple[tuple[ResolutionSpec, Mesh3], ...]:
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


def triangulate_shape_cases(
    cases: Iterable[tuple[str, Sequence[Point3]]] = POLYGON_CASES,
    *,
    tolerance: float = TOLERANCE,
) -> tuple[tuple[str, Mesh3, Mesh3], ...]:
    return tuple(
        (
            name,
            polygon,
            triangulate3d(
                polygon,
                tolerance=tolerance,
                max_edge_length=_auto_max_edge_length(polygon, tolerance=tolerance),
            ),
        )
        for name, points in cases
        for polygon in (polygon_mesh_from_points(points),)
    )


def triangulate_min_angle_cases(
    points: Sequence[Point3] = HAIRLINE_SLOT_POINTS,
    *,
    min_angle_degrees: Iterable[MinAngleSpec] = MIN_ANGLE_DEGREES,
    tolerance: float = TOLERANCE,
) -> tuple[tuple[MinAngleSpec, Mesh3, Mesh3], ...]:
    polygon = polygon_mesh_from_points(points)
    return tuple(
        (
            angle,
            polygon,
            triangulate3d(
                polygon,
                tolerance=tolerance,
                max_edge_length=_auto_max_edge_length(
                    polygon,
                    tolerance=tolerance,
                    min_angle_degrees=angle,
                ),
                min_angle_degrees=angle,
            ),
        )
        for angle in min_angle_degrees
    )


def build_scene(cases: tuple[tuple[ResolutionSpec, Mesh3], ...]) -> Scene:
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
            _translated_mesh(mesh, offset, 0.0, 0.0),
            name=_case_name(max_edge_length),
            style=MESH_STYLES[index % len(MESH_STYLES)],
        )
    return scene


def build_shape_scene(cases: tuple[tuple[str, Mesh3, Mesh3], ...]) -> Scene:
    columns = 3
    spacing_x = 5.0
    spacing_y = 3.25
    rows = max(1, ceil(len(cases) / columns))
    scene = Scene(
        "polygon_triangulation_shape_cases",
        camera=Camera.orthographic(
            position=(0.0, 0.0, 15.0),
            target=(0.0, 0.0, 0.0),
            up=(0.0, 1.0, 0.0),
            scale=max(columns * spacing_x, rows * spacing_y) * 1.1,
        ),
    )
    for index, (name, polygon, mesh) in enumerate(cases):
        column = index % columns
        row = index // columns
        x_offset = (column - (columns - 1) / 2.0) * spacing_x
        y_offset = ((rows - 1) / 2.0 - row) * spacing_y
        scene = scene.add(
            _translated_mesh(mesh, x_offset, y_offset, 0.0),
            name=f"{name} heuristic triangles",
            style=MESH_STYLES[index % len(MESH_STYLES)],
        )
        scene = scene.add(
            _translated_mesh(_polygon_boundary_overlay(polygon), x_offset, y_offset, 0.0),
            name=f"{name} input polygon",
            style=INPUT_POLYGON_STYLE,
        )
    return scene


def build_min_angle_scene(cases: tuple[tuple[MinAngleSpec, Mesh3, Mesh3], ...]) -> Scene:
    spacing = 5.0
    centre = (len(cases) - 1) / 2.0
    scene = Scene(
        "polygon_triangulation_min_angles",
        camera=Camera.orthographic(
            position=(0.0, 0.0, 11.0),
            target=(0.0, 0.0, 0.0),
            up=(0.0, 1.0, 0.0),
            scale=max(10.5, len(cases) * spacing),
        ),
    )
    for index, (angle, polygon, mesh) in enumerate(cases):
        offset = (index - centre) * spacing
        case_name = _min_angle_case_name(angle)
        scene = scene.add(
            _translated_mesh(mesh, offset, 0.0, 0.0),
            name=f"{case_name} triangles",
            style=MESH_STYLES[index % len(MESH_STYLES)],
        )
        scene = scene.add(
            _translated_mesh(_polygon_boundary_overlay(polygon), offset, 0.0, 0.0),
            name=f"{case_name} input polygon",
            style=INPUT_POLYGON_STYLE,
        )
    return scene


def build_heuristic_scene(polygon: Mesh3, *, tolerance: float = TOLERANCE) -> Scene:
    lower, upper = polygon.bounds()
    centre = (
        (lower[0] + upper[0]) / 2.0,
        (lower[1] + upper[1]) / 2.0,
        (lower[2] + upper[2]) / 2.0,
    )
    span = max(upper[0] - lower[0], upper[1] - lower[1], upper[2] - lower[2], 1.0)
    return (
        Scene(
            "polygon_triangulation_heuristic",
            camera=Camera.orthographic(
                position=(centre[0], centre[1], centre[2] + span * 2.5),
                target=centre,
                up=(0.0, 1.0, 0.0),
                scale=span * 1.25,
            ),
        )
        .add(
            triangulate_polygon_heuristic(polygon, tolerance=tolerance),
            name="heuristic triangles",
            style=HEURISTIC_STYLE,
        )
        .add(_polygon_boundary_overlay(polygon), name="input polygon", style=INPUT_POLYGON_STYLE)
    )


def mesh_summary(cases: tuple[tuple[ResolutionSpec, Mesh3], ...]) -> str:
    lines = ["cady polygon triangulation size comparison"]
    for max_edge_length, mesh in cases:
        lines.append(
            f"{_case_name(max_edge_length)}: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces"
        )
    return "\n".join(lines)


def heuristic_summary(polygon: Mesh3, mesh: Mesh3) -> str:
    return "\n".join(
        (
            "cady polygon heuristic triangulation",
            f"input polygon: {len(polygon.vertices)} vertices, {len(polygon.faces)} face",
            f"heuristic mesh: {len(mesh.vertices)} vertices, {len(mesh.faces)} faces",
        )
    )


def shape_summary(cases: tuple[tuple[str, Mesh3, Mesh3], ...]) -> str:
    lines = ["cady polygon triangulation shape cases"]
    for name, polygon, mesh in cases:
        lines.append(
            f"{name}: {len(polygon.vertices)} boundary vertices -> "
            f"{len(mesh.vertices)} vertices, {len(mesh.faces)} faces"
        )
    return "\n".join(lines)


def min_angle_summary(cases: tuple[tuple[MinAngleSpec, Mesh3, Mesh3], ...]) -> str:
    lines = ["cady skinny polygon min-angle comparison"]
    for angle, polygon, mesh in cases:
        lines.append(
            f"{_min_angle_case_name(angle)}: {len(polygon.vertices)} boundary vertices -> "
            f"{len(mesh.vertices)} vertices, {len(mesh.faces)} faces, "
            f"worst angle {_mesh_min_angle_degrees(mesh):.3g}"
        )
    return "\n".join(lines)


def main() -> None:
    polyline = example_polyline()
    polygon = polygon_mesh_from_polyline(polyline, tolerance=TOLERANCE)
    heuristic_mesh = triangulate_polygon_heuristic(polygon, tolerance=TOLERANCE)
    cases = triangulate_resolutions(polyline)
    shape_cases = triangulate_shape_cases()
    min_angle_cases = triangulate_min_angle_cases()

    print(mesh_summary(cases))
    build_scene(cases).view(
        tolerance=TOLERANCE,
        title="polygon triangulation sizes",
    )

    print()
    print(heuristic_summary(polygon, heuristic_mesh))
    build_heuristic_scene(polygon, tolerance=TOLERANCE).view(
        tolerance=TOLERANCE,
        title="polygon triangulation auto heuristic",
    )
    print()
    print(shape_summary(shape_cases))
    build_shape_scene(shape_cases).view(
        tolerance=TOLERANCE,
        title="polygon triangulation shape cases",
    )
    print()
    print(min_angle_summary(min_angle_cases))
    build_min_angle_scene(min_angle_cases).view(
        tolerance=TOLERANCE,
        title="skinny polygon min angle comparison",
    )
    print("done")


def _polygon_face_edges(faces: Iterable[FaceIndex]) -> tuple[EdgeIndex, ...]:
    edges: set[EdgeIndex] = set()
    for face in faces:
        for start, end in zip(face, face[1:] + face[:1], strict=True):
            edges.add((min(start, end), max(start, end)))
    return tuple(sorted(edges))


def _polygon_boundary_overlay(polygon: Mesh3) -> Mesh3:
    vertices = tuple((x, y, z + 0.025) for x, y, z in polygon.vertices)
    return Mesh3(vertices, (), _polygon_face_edges(polygon.faces))


def _translated_mesh(mesh: Mesh3, x_offset: float, y_offset: float, z_offset: float) -> Mesh3:
    return Mesh3(
        tuple((x + x_offset, y + y_offset, z + z_offset) for x, y, z in mesh.vertices),
        mesh.faces,
        mesh.edges,
    )


def _case_name(max_edge_length: ResolutionSpec) -> str:
    if max_edge_length is None:
        return "original boundary"
    if max_edge_length == "auto":
        return "auto length"
    return f"max edge {max_edge_length:g}"


def _min_angle_case_name(min_angle_degrees: MinAngleSpec) -> str:
    if min_angle_degrees is None:
        return "auto length"
    return f"min angle {min_angle_degrees:g}"


def _mesh_min_angle_degrees(mesh: Mesh3) -> float:
    return min(
        _triangle_min_angle_degrees(tuple(mesh.vertices[index] for index in face))
        for face in mesh.faces
    )


def _triangle_min_angle_degrees(points: tuple[Point3, Point3, Point3]) -> float:
    a, b, c = points
    ab = _distance3(a, b)
    bc = _distance3(b, c)
    ca = _distance3(c, a)
    return min(
        _angle_degrees(ab, ca, bc),
        _angle_degrees(ab, bc, ca),
        _angle_degrees(bc, ca, ab),
    )


def _angle_degrees(first: float, second: float, opposite: float) -> float:
    denominator = 2.0 * first * second
    if denominator <= 0.0:
        return 0.0
    cosine = (first * first + second * second - opposite * opposite) / denominator
    return degrees(acos(max(-1.0, min(1.0, cosine))))


def _distance3(left: Point3, right: Point3) -> float:
    return sqrt(
        (left[0] - right[0]) * (left[0] - right[0])
        + (left[1] - right[1]) * (left[1] - right[1])
        + (left[2] - right[2]) * (left[2] - right[2])
    )


if __name__ == "__main__":
    main()
