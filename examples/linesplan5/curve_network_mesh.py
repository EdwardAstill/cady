"""Build a linesplan mesh while keeping DXF intersection nodes visible.

Usage:
    PYTHONPATH=src .venv/bin/python examples/linesplan5/curve_network_mesh.py --no-view
    PYTHONPATH=src .venv/bin/python examples/linesplan5/curve_network_mesh.py
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from math import dist, floor, isfinite
from pathlib import Path

from pc_from_dxf import (
    DEFAULT_INTERSECTION_TOLERANCE,
    DEFAULT_REPEAT_DISTANCE,
    LINESPLAN_DXF,
    DxfIntersectionPointCloud,
    IntersectionPoint,
    dxf_intersection_pointcloud,
    pointcloud_from_intersections,
    read_polyline_curves,
    wireframe_from_curves,
)

from cady import (
    Camera,
    DirectionalLight,
    DisplayStyle,
    Mesh3,
    PointCloud3,
    Scene,
    Wireframe3,
)
from cady.operations.meshes import (
    LinesplanNetwork,
    classify_linesplan_curves,
)

VIEW_ASPECT = 900.0 / 700.0
FIT_PADDING = 1.08
MESH_STYLE = DisplayStyle(color=(0.38, 0.58, 0.36), opacity=0.52, render_mode="shaded")
WIRE_STYLE = DisplayStyle(color=(0.04, 0.20, 0.44), render_mode="wireframe", line_width=1.0)
POINT_STYLE = DisplayStyle(color=(0.88, 0.45, 0.12), render_mode="points", point_size=7.0)
LIGHT = DirectionalLight(direction=(0.0, -1.0, -1.0), intensity=1.2)

Point3 = tuple[float, float, float]
PointKey3 = tuple[int, int, int]
EdgeIndex = tuple[int, int]
FaceIndex = tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CurveNode:
    measure: float
    node_index: int


@dataclass(frozen=True, slots=True)
class CurveIntersectionRef:
    measure: float
    node_index: int
    other_curve_index: int


@dataclass(frozen=True, slots=True)
class CurveNetworkMesh:
    source: Wireframe3
    intersection_wireframe: Wireframe3
    cloud: PointCloud3
    mesh: Mesh3
    node_result: DxfIntersectionPointCloud
    network: LinesplanNetwork
    tolerance: float


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build an intersection-bounded linesplan patch mesh.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=LINESPLAN_DXF,
        help="DXF file to read.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1e-3,
        help="Geometry tolerance used by classification and meshing.",
    )
    parser.add_argument(
        "--intersection-tolerance",
        "--snap-tolerance",
        dest="intersection_tolerance",
        type=float,
        default=DEFAULT_INTERSECTION_TOLERANCE,
        help="Maximum gap between two polylines that counts as an intersection node.",
    )
    parser.add_argument(
        "--repeat-distance",
        "--min-repeat-distance",
        "--min-node-distance",
        "--exclusion-distance",
        dest="repeat_distance",
        type=float,
        default=DEFAULT_REPEAT_DISTANCE,
        help="Minimum distance before the same two polylines can intersect again.",
    )
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Print summaries without opening a VisPy window.",
    )
    args = parser.parse_args()

    _validate_positive(args.tolerance, "tolerance")
    _validate_positive(args.intersection_tolerance, "intersection_tolerance")
    _validate_positive(args.repeat_distance, "repeat_distance")

    result = curve_network_mesh_from_dxf(
        args.input,
        tolerance=args.tolerance,
        intersection_tolerance=args.intersection_tolerance,
        repeat_distance=args.repeat_distance,
    )

    print("cady linesplan5 curve-network mesh demo")
    print(f"input: {args.input}")
    print("steps: DXF curves -> intersection incidence -> quad patch mesh")
    print("overlay: intersection nodes -> intersection-node wireframe")
    print_wireframe_summary("source wireframe", result.source)
    print_wireframe_summary("intersection-node wireframe", result.intersection_wireframe)
    print_mesh_summary("intersection patch mesh", result.mesh)
    print(f"polyline curves: {result.node_result.curve_count}")
    print(f"intersecting polyline pairs: {result.node_result.intersecting_pair_count}")
    print(f"raw pair intersections: {result.node_result.raw_intersection_count}")
    print(f"intersection nodes: {len(result.cloud.vertices)}")
    print(f"intersection tolerance: {result.node_result.intersection_tolerance:g}")
    print(f"repeat distance: {result.node_result.repeat_distance:g}")
    print(f"mesh uses only intersection nodes: {mesh_uses_only_intersection_nodes(result)}")
    print(
        "classified curves: "
        f"{len(result.network.sections)} sections, "
        f"{len(result.network.buttocks)} buttocks, "
        f"{len(result.network.waterlines)} waterlines, "
        f"{len(result.network.knuckles)} knuckles, "
        f"{len(result.network.rejected)} rejected"
    )
    if result.network.compatibility_report.issues:
        print(f"network compatibility issues: {len(result.network.compatibility_report.issues)}")
        for issue in result.network.compatibility_report.issues[:5]:
            print(f"  - {issue}")
        if len(result.network.compatibility_report.issues) > 5:
            print("  - ...")

    if args.no_view:
        print("VisPy viewer skipped.")
        return

    from cady.view import view_scene

    view_scene(
        build_scene(result),
        tolerance=args.tolerance,
        title="linesplan5 curve-network mesh",
    )


def curve_network_mesh_from_dxf(
    path: str | Path,
    *,
    tolerance: float = 1e-3,
    intersection_tolerance: float = DEFAULT_INTERSECTION_TOLERANCE,
    repeat_distance: float = DEFAULT_REPEAT_DISTANCE,
) -> CurveNetworkMesh:
    _validate_positive(tolerance, "tolerance")

    curves = read_polyline_curves(Path(path))
    source = wireframe_from_curves(curves)
    node_result = pointcloud_from_intersections(
        curves,
        source=source,
        tolerance=tolerance,
        intersection_tolerance=intersection_tolerance,
        repeat_distance=repeat_distance,
    )
    curve_nodes = intersection_curve_nodes(
        node_result.cloud,
        node_result.intersections,
        node_tolerance=intersection_tolerance,
    )
    intersection_wireframe = intersection_node_wireframe_from_curve_nodes(
        node_result.cloud,
        curve_nodes,
    )
    network = classify_linesplan_curves(curves, tolerance=tolerance)
    mesh = intersection_patch_mesh_from_intersections(
        node_result.cloud,
        node_result.intersections,
        node_tolerance=intersection_tolerance,
        tolerance=tolerance,
    )

    return CurveNetworkMesh(
        source=source,
        intersection_wireframe=intersection_wireframe,
        cloud=node_result.cloud,
        mesh=mesh,
        node_result=node_result,
        network=network,
        tolerance=tolerance,
    )


def intersection_node_wireframe_from_dxf(
    path: str | Path,
    *,
    tolerance: float = 1e-3,
    intersection_tolerance: float = DEFAULT_INTERSECTION_TOLERANCE,
    repeat_distance: float = DEFAULT_REPEAT_DISTANCE,
) -> Wireframe3:
    node_result = dxf_intersection_pointcloud(
        path,
        tolerance=tolerance,
        intersection_tolerance=intersection_tolerance,
        repeat_distance=repeat_distance,
    )
    curve_nodes = intersection_curve_nodes(
        node_result.cloud,
        node_result.intersections,
        node_tolerance=intersection_tolerance,
    )
    return intersection_node_wireframe_from_curve_nodes(node_result.cloud, curve_nodes)


def intersection_curve_nodes(
    cloud: PointCloud3,
    intersections: tuple[IntersectionPoint, ...],
    *,
    node_tolerance: float,
) -> dict[int, tuple[CurveNode, ...]]:
    canonical_nodes = _canonical_node_index_lookup(cloud.vertices, tolerance=node_tolerance)
    curve_nodes: dict[int, list[CurveNode]] = {}
    for intersection in intersections:
        node_index = _nearest_canonical_node_index(
            intersection.point,
            canonical_nodes,
            tolerance=node_tolerance,
        )
        curve_nodes.setdefault(intersection.left_curve_index, []).append(
            CurveNode(intersection.left_measure, node_index)
        )
        curve_nodes.setdefault(intersection.right_curve_index, []).append(
            CurveNode(intersection.right_measure, node_index)
        )
    return {index: tuple(nodes) for index, nodes in curve_nodes.items()}


def intersection_node_wireframe_from_curve_nodes(
    cloud: PointCloud3,
    curve_nodes: dict[int, tuple[CurveNode, ...]],
) -> Wireframe3:
    return Wireframe3.from_edges(cloud.vertices, _curve_node_edges(curve_nodes))


def intersection_patch_mesh_from_intersections(
    cloud: PointCloud3,
    intersections: tuple[IntersectionPoint, ...],
    *,
    node_tolerance: float,
    tolerance: float,
) -> Mesh3:
    """Build quad patches whose corners and sides come from curve intersections."""
    refs = intersection_curve_intersection_refs(
        cloud,
        intersections,
        node_tolerance=node_tolerance,
    )
    curve_orders = _curve_node_orders_from_refs(refs)
    incident_curves = _incident_curves_from_refs(refs)
    faces = _intersection_quad_patch_faces(
        curve_orders,
        incident_curves,
        tolerance=tolerance,
        vertices=cloud.vertices,
    )
    if not faces:
        raise ValueError("no intersection-bounded quad patches were found")

    curve_edges = _curve_node_edges_from_orders(curve_orders)
    edges: set[EdgeIndex] = set()
    edges.update(curve_edges)
    edges.update(_face_edges(faces))
    return Mesh3(cloud.vertices, tuple(faces), tuple(sorted(edges)))


def intersection_curve_intersection_refs(
    cloud: PointCloud3,
    intersections: tuple[IntersectionPoint, ...],
    *,
    node_tolerance: float,
) -> dict[int, tuple[CurveIntersectionRef, ...]]:
    canonical_nodes = _canonical_node_index_lookup(cloud.vertices, tolerance=node_tolerance)
    refs: dict[int, list[CurveIntersectionRef]] = {}

    for intersection in intersections:
        node_index = _nearest_canonical_node_index(
            intersection.point,
            canonical_nodes,
            tolerance=node_tolerance,
        )
        refs.setdefault(intersection.left_curve_index, []).append(
            CurveIntersectionRef(
                measure=intersection.left_measure,
                node_index=node_index,
                other_curve_index=intersection.right_curve_index,
            )
        )
        refs.setdefault(intersection.right_curve_index, []).append(
            CurveIntersectionRef(
                measure=intersection.right_measure,
                node_index=node_index,
                other_curve_index=intersection.left_curve_index,
            )
        )

    return {
        curve_index: tuple(
            sorted(items, key=lambda item: (item.measure, item.node_index, item.other_curve_index))
        )
        for curve_index, items in refs.items()
    }


def mesh_uses_only_intersection_nodes(result: CurveNetworkMesh) -> bool:
    return set(result.mesh.vertices).issubset(result.cloud.vertices)


def build_scene(result: CurveNetworkMesh) -> Scene:
    lower, upper = result.source.bounds()
    camera = _fit_profile_camera(lower, upper)
    centre = _bounds_centre(lower, upper)

    return (
        Scene(name="linesplan5_curve_network_mesh")
        .add(result.mesh, name="intersection_patch_mesh", style=MESH_STYLE)
        .add(result.intersection_wireframe, name="intersection_node_wireframe", style=WIRE_STYLE)
        .add(result.cloud, name="intersection_nodes", style=POINT_STYLE)
        .with_camera(camera, name="profile")
        .with_light(LIGHT)
        .with_metadata(target=_format_point(centre))
    )


def print_wireframe_summary(label: str, wireframe: Wireframe3) -> None:
    lower, upper = wireframe.bounds()
    print(
        f"{label}: {len(wireframe.vertices)} vertices, {len(wireframe.edges)} edges, "
        f"bounds={_format_point(lower)} to {_format_point(upper)}"
    )


def print_mesh_summary(label: str, mesh: Mesh3) -> None:
    lower, upper = mesh.bounds()
    print(
        f"{label}: {len(mesh.vertices)} vertices, {len(mesh.edges)} edges, "
        f"{len(mesh.faces)} faces, bounds={_format_point(lower)} to {_format_point(upper)}"
    )


def _canonical_node_index_lookup(
    nodes: tuple[Point3, ...],
    *,
    tolerance: float,
) -> dict[PointKey3, list[tuple[int, Point3]]]:
    buckets: dict[PointKey3, list[tuple[int, Point3]]] = {}
    for index, node in enumerate(nodes):
        buckets.setdefault(_point_key(node, tolerance=tolerance), []).append((index, node))
    return buckets


def _nearest_canonical_node_index(
    point: Point3,
    buckets: dict[PointKey3, list[tuple[int, Point3]]],
    *,
    tolerance: float,
) -> int:
    key = _point_key(point, tolerance=tolerance)
    best: tuple[float, int] | None = None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for index, candidate in buckets.get(
                    (key[0] + dx, key[1] + dy, key[2] + dz),
                    (),
                ):
                    gap = dist(point, candidate)
                    if best is None or gap < best[0]:
                        best = (gap, index)
    if best is None or best[0] > tolerance:
        raise ValueError("intersection point could not be matched to a cloud node")
    return best[1]


def _curve_node_edges(curve_nodes: dict[int, tuple[CurveNode, ...]]) -> tuple[EdgeIndex, ...]:
    edges: set[EdgeIndex] = set()
    for nodes in curve_nodes.values():
        ordered = _ordered_unique_node_indices(nodes)
        for start, end in zip(ordered, ordered[1:], strict=False):
            if start != end:
                edges.add((min(start, end), max(start, end)))
    return tuple(sorted(edges))


def _ordered_unique_node_indices(nodes: tuple[CurveNode, ...]) -> tuple[int, ...]:
    ordered: list[int] = []
    seen: set[int] = set()
    for node in sorted(nodes, key=lambda item: (item.measure, item.node_index)):
        if node.node_index in seen:
            continue
        seen.add(node.node_index)
        ordered.append(node.node_index)
    return tuple(ordered)


def _curve_node_orders_from_refs(
    refs: dict[int, tuple[CurveIntersectionRef, ...]],
) -> dict[int, tuple[int, ...]]:
    orders: dict[int, tuple[int, ...]] = {}
    for curve_index, curve_refs in refs.items():
        ordered: list[int] = []
        seen: set[int] = set()
        for ref in curve_refs:
            if ref.node_index in seen:
                continue
            seen.add(ref.node_index)
            ordered.append(ref.node_index)
        if len(ordered) >= 2:
            orders[curve_index] = tuple(ordered)
    return orders


def _incident_curves_from_refs(
    refs: dict[int, tuple[CurveIntersectionRef, ...]],
) -> dict[tuple[int, int], set[int]]:
    incident: dict[tuple[int, int], set[int]] = {}
    for curve_index, curve_refs in refs.items():
        for ref in curve_refs:
            incident.setdefault((curve_index, ref.node_index), set()).add(ref.other_curve_index)
    return incident


def _curve_node_edges_from_orders(
    curve_orders: dict[int, tuple[int, ...]],
) -> tuple[EdgeIndex, ...]:
    edges: set[EdgeIndex] = set()
    for order in curve_orders.values():
        for start, end in zip(order, order[1:], strict=False):
            if start != end:
                edges.add((min(start, end), max(start, end)))
    return tuple(sorted(edges))


def _intersection_quad_patch_faces(
    curve_orders: dict[int, tuple[int, ...]],
    incident_curves: dict[tuple[int, int], set[int]],
    *,
    tolerance: float,
    vertices: tuple[Point3, ...],
) -> tuple[FaceIndex, ...]:
    position = _curve_node_positions(curve_orders)
    faces: list[FaceIndex] = []
    seen: set[FaceIndex] = set()

    for curve_a, order_a in curve_orders.items():
        for n00, n10 in zip(order_a, order_a[1:], strict=False):
            curves_at_n00 = incident_curves.get((curve_a, n00), set())
            curves_at_n10 = incident_curves.get((curve_a, n10), set())
            for curve_c in curves_at_n00:
                if curve_c == curve_a:
                    continue
                for n01 in _adjacent_nodes_on_curve(curve_c, n00, curve_orders, position):
                    if n01 in (n00, n10):
                        continue
                    for curve_b in incident_curves.get((curve_c, n01), set()):
                        if curve_b in (curve_a, curve_c):
                            continue
                        for n11 in _adjacent_nodes_on_curve(
                            curve_b,
                            n01,
                            curve_orders,
                            position,
                        ):
                            if len({n00, n10, n11, n01}) != 4:
                                continue
                            for curve_d in incident_curves.get((curve_b, n11), set()):
                                if curve_d in (curve_a, curve_b, curve_c):
                                    continue
                                if curve_d not in curves_at_n10:
                                    continue
                                if not _nodes_are_adjacent_on_curve(curve_d, n10, n11, position):
                                    continue

                                face = (n00, n10, n11, n01)
                                if _face_is_degenerate_3d(vertices, face, tolerance=tolerance):
                                    continue
                                key = _canonical_face_key(face)
                                if key in seen:
                                    continue
                                seen.add(key)
                                faces.append(face)
    return tuple(faces)


def _curve_node_positions(
    curve_orders: dict[int, tuple[int, ...]],
) -> dict[int, dict[int, int]]:
    return {
        curve_index: {node_index: offset for offset, node_index in enumerate(order)}
        for curve_index, order in curve_orders.items()
    }


def _adjacent_nodes_on_curve(
    curve_index: int,
    node_index: int,
    curve_orders: dict[int, tuple[int, ...]],
    position: dict[int, dict[int, int]],
) -> tuple[int, ...]:
    curve_position = position.get(curve_index)
    order = curve_orders.get(curve_index)
    if curve_position is None or order is None:
        return ()

    offset = curve_position.get(node_index)
    if offset is None:
        return ()

    adjacent: list[int] = []
    if offset > 0:
        adjacent.append(order[offset - 1])
    if offset + 1 < len(order):
        adjacent.append(order[offset + 1])
    return tuple(adjacent)


def _nodes_are_adjacent_on_curve(
    curve_index: int,
    left: int,
    right: int,
    position: dict[int, dict[int, int]],
) -> bool:
    curve_position = position.get(curve_index)
    if curve_position is None:
        return False

    left_position = curve_position.get(left)
    right_position = curve_position.get(right)
    if left_position is None or right_position is None:
        return False
    return abs(left_position - right_position) == 1


def _face_is_degenerate_3d(
    vertices: tuple[Point3, ...],
    face: FaceIndex,
    *,
    tolerance: float,
) -> bool:
    if len(face) < 3:
        return True

    normal = _newell_normal(vertices, face)
    normal_length_sq = normal[0] * normal[0] + normal[1] * normal[1] + normal[2] * normal[2]
    return normal_length_sq <= tolerance * tolerance * tolerance * tolerance


def _newell_normal(
    vertices: tuple[Point3, ...],
    face: FaceIndex,
) -> Point3:
    nx = 0.0
    ny = 0.0
    nz = 0.0
    for index, current_index in enumerate(face):
        next_index = face[(index + 1) % len(face)]
        current = vertices[current_index]
        following = vertices[next_index]
        nx += (current[1] - following[1]) * (current[2] + following[2])
        ny += (current[2] - following[2]) * (current[0] + following[0])
        nz += (current[0] - following[0]) * (current[1] + following[1])
    return (nx, ny, nz)


def _canonical_face_key(face: FaceIndex) -> FaceIndex:
    rotations: list[FaceIndex] = []
    forward = tuple(face)
    backward = tuple(reversed(face))
    for sequence in (forward, backward):
        for offset in range(len(sequence)):
            rotations.append(sequence[offset:] + sequence[:offset])
    return min(rotations)


def _face_edges(faces: tuple[FaceIndex, ...]) -> tuple[EdgeIndex, ...]:
    edges: set[EdgeIndex] = set()
    for face in faces:
        for start, end in zip(face, face[1:] + face[:1], strict=True):
            edges.add((min(start, end), max(start, end)))
    return tuple(sorted(edges))


def _point_key(point: Point3, *, tolerance: float) -> PointKey3:
    return (
        floor(point[0] / tolerance),
        floor(point[1] / tolerance),
        floor(point[2] / tolerance),
    )


def _validate_positive(value: float, name: str) -> None:
    if value <= 0.0 or not isfinite(value):
        raise ValueError(f"{name} must be positive")


def _fit_profile_camera(lower: Point3, upper: Point3) -> Camera:
    centre = _bounds_centre(lower, upper)
    span = (upper[0] - lower[0], upper[1] - lower[1], upper[2] - lower[2])
    profile_scale = max(span[2], span[0] / VIEW_ASPECT, 1.0) * FIT_PADDING
    distance = max(span) * 1.5 or 1.0
    return Camera.orthographic(
        position=(centre[0], centre[1] - distance, centre[2]),
        target=centre,
        scale=profile_scale,
    )


def _bounds_centre(lower: Point3, upper: Point3) -> Point3:
    return (
        (lower[0] + upper[0]) / 2.0,
        (lower[1] + upper[1]) / 2.0,
        (lower[2] + upper[2]) / 2.0,
    )


def _format_point(point: Point3) -> str:
    return f"({point[0]:g}, {point[1]:g}, {point[2]:g})"


if __name__ == "__main__":
    main()
