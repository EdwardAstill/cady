"""Organise the linesplan station cleaning, lofting, mirroring, and closing."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from dataclasses import dataclass
from math import dist
from typing import TypeAlias

import numpy as np
from loft_polylines import get_node_array, mesh_node_array
from pizza_triangulate import pizza_triangulate_mesh
from process_polylines import (
    SNAP_TOLERANCE,
    prepare_station_lines,
    process_station_lines,
    split_station_lines,
    station_end_points,
    station_top_discontinuity_points,
    station_top_positive_y_points,
    view_original_station_lines,
    view_processed_station_lines,
)
from remesh import isotropic_remesh
from wireframe import STATION_POLYLINES

from cady import DisplayStyle, Mesh3, PointCloud3, Polyline3, Scene

Point3: TypeAlias = tuple[float, float, float]
Face: TypeAlias = tuple[int, ...]
Edge: TypeAlias = tuple[int, int]
PolylineGroup: TypeAlias = tuple[Polyline3, ...]
NodeArray: TypeAlias = tuple[tuple[Point3, ...], ...]

TOLERANCE = 1e-3
NODE_SPACING = 1000.0
MIRROR_PLANE_ORIGIN: Point3 = (0.0, 0.0, 0.0)
MIRROR_PLANE_NORMAL: Point3 = (0.0, 1.0, 0.0)

YELLOW_TOP_STYLE = DisplayStyle(color=(0.95, 0.82, 0.12), render_mode="wireframe")
RED_TOP_STYLE = DisplayStyle(color=(0.95, 0.22, 0.12), render_mode="wireframe")
MIRRORED_YELLOW_STYLE = DisplayStyle(color=(0.35, 0.62, 0.9), render_mode="wireframe")
MIRRORED_RED_STYLE = DisplayStyle(color=(0.45, 0.78, 0.5), render_mode="wireframe")
START_POINT_STYLE = DisplayStyle(color=(0.95, 0.95, 0.12), point_size=8.0)
END_POINT_STYLE = DisplayStyle(color=(0.1, 0.82, 0.24), point_size=8.0)
PIZZA_STYLE = DisplayStyle(color=(0.9, 0.4, 0.2), render_mode="wireframe")
REMESH_STYLE = DisplayStyle(color=(0.2, 0.6, 0.9), render_mode="wireframe")


@dataclass(frozen=True, slots=True)
class LoftedMeshPatch:
    group_index: int
    polylines: PolylineGroup
    nodes: NodeArray
    mesh: Mesh3
    yellow_nodes: tuple[BoundaryNode, ...] = ()
    green_nodes: tuple[BoundaryNode, ...] = ()


@dataclass(frozen=True, slots=True)
class BoundaryNode:
    row_index: int
    point: Point3


@dataclass(frozen=True, slots=True)
class KeelBoundaryPair:
    red: Point3
    green: Point3


def loft_polyline_groups(
    polyline_groups: Iterable[PolylineGroup],
    *,
    node_spacing: float = NODE_SPACING,
) -> tuple[LoftedMeshPatch, ...]:
    patches: list[LoftedMeshPatch] = []
    for group_index, polyline_group in enumerate(polyline_groups):
        if polyline_group:
            nodes = get_node_array(polyline_group, node_spacing=node_spacing)
            patches.append(
                LoftedMeshPatch(
                    group_index=group_index,
                    polylines=polyline_group,
                    nodes=nodes,
                    mesh=mesh_node_array(nodes),
                )
            )
    return tuple(patches)


def mark_mesh_boundary_nodes(
    patch: LoftedMeshPatch,
    green_points: Iterable[Point3],
) -> LoftedMeshPatch:
    green_points = tuple(green_points)
    end_column = len(patch.nodes[0]) - 1
    yellow_nodes: tuple[BoundaryNode, ...] = ()
    if patch.group_index == 0:
        yellow_nodes = tuple(
            BoundaryNode(row_index, row[0]) for row_index, row in enumerate(patch.nodes)
        )

    green_nodes = tuple(
        BoundaryNode(row_index, patch.nodes[row_index][end_column])
        for row_index, polyline in enumerate(patch.polylines)
        if _matches_any_point(polyline.end, green_points)
    )
    return LoftedMeshPatch(
        group_index=patch.group_index,
        polylines=patch.polylines,
        nodes=patch.nodes,
        mesh=patch.mesh,
        yellow_nodes=yellow_nodes,
        green_nodes=green_nodes,
    )


def boundary_extension_meshes(nodes: Iterable[BoundaryNode]) -> tuple[Mesh3, ...]:
    meshes: list[Mesh3] = []
    chain: list[BoundaryNode] = []
    for node in sorted(nodes, key=lambda item: item.row_index):
        if chain and node.row_index != chain[-1].row_index + 1:
            meshes.append(boundary_extension_mesh(boundary_node.point for boundary_node in chain))
            chain = []
        chain.append(node)

    if chain:
        meshes.append(boundary_extension_mesh(boundary_node.point for boundary_node in chain))
    return tuple(mesh for mesh in meshes if mesh.vertices)


def boundary_extension_mesh(points: Iterable[Point3]) -> Mesh3:
    points = tuple(points)
    if len(points) < 2:
        return Mesh3((), ())

    vertices = list(points)
    projected_indices: list[int] = []
    edges: set[Edge] = set()
    faces: list[Face] = []

    for index, point in enumerate(points):
        if abs(point[1]) <= TOLERANCE:
            projected_indices.append(index)
            continue

        projected_indices.append(len(vertices))
        vertices.append((point[0], 0.0, point[2]))
        edges.add(_edge_key(index, projected_indices[-1]))

    for index in range(len(points) - 1):
        next_index = index + 1
        edges.add(_edge_key(index, next_index))
        edges.add(_edge_key(projected_indices[index], projected_indices[next_index]))
        face = _clean_face(
            (index, next_index, projected_indices[next_index], projected_indices[index])
        )
        if len(face) >= 3:
            faces.append(face)

    return Mesh3(tuple(vertices), tuple(faces), tuple(sorted(edges)))


def merge_boundary_extensions(
    patches: Iterable[LoftedMeshPatch],
    extensions: Iterable[Mesh3],
) -> tuple[Mesh3, ...]:
    meshes = [patch.mesh for patch in patches]
    extension_meshes = tuple(mesh for mesh in extensions if mesh.vertices)
    if meshes and extension_meshes:
        meshes[0] = Mesh3.merged((meshes[0], *extension_meshes))
    return tuple(meshes)


def keel_boundary_pairs(patches: Iterable[LoftedMeshPatch]) -> tuple[KeelBoundaryPair, ...]:
    pairs: list[KeelBoundaryPair] = []
    for patch in patches:
        if patch.group_index != 1:
            continue
        for row in patch.nodes:
            pairs.append(KeelBoundaryPair(red=row[0], green=row[-1]))
    return tuple(sorted(pairs, key=lambda pair: pair.red[0]))


def keel_boundary_rows(patches: Iterable[LoftedMeshPatch]) -> tuple[tuple[Point3, ...], ...]:
    rows: list[tuple[Point3, ...]] = []
    for patch in patches:
        if patch.group_index == 1:
            rows.extend(patch.nodes)
    return tuple(sorted(rows, key=lambda row: row[0][0]))


def keel_end_pairs(pairs: Iterable[KeelBoundaryPair]) -> tuple[KeelBoundaryPair, ...]:
    pairs = tuple(pairs)
    if len(pairs) <= 2:
        return pairs
    return (pairs[0], pairs[-1])


def keel_end_rows(rows: Iterable[tuple[Point3, ...]]) -> tuple[tuple[Point3, ...], ...]:
    rows = tuple(rows)
    if len(rows) <= 2:
        return rows
    return (rows[0], rows[-1])


def keel_end_cap_mesh(rows: Iterable[tuple[Point3, ...]]) -> Mesh3:
    vertices: list[Point3] = []
    faces: list[Face] = []
    edges: set[Edge] = set()

    for row in rows:
        start = len(vertices)
        vertices.extend((*row, *(_mirror_point(point) for point in reversed(row))))
        face = tuple(range(start, len(vertices)))
        faces.append(face)
        for edge in zip(face, face[1:] + face[:1], strict=True):
            edges.add(_edge_key(*edge))

    return Mesh3(tuple(vertices), tuple(faces), tuple(sorted(edges)))


def mirror_meshes(meshes: Iterable[Mesh3]) -> tuple[Mesh3, ...]:
    return tuple(mesh.mirror(MIRROR_PLANE_ORIGIN, MIRROR_PLANE_NORMAL) for mesh in meshes)


def combine_meshes(meshes: Iterable[Mesh3]) -> Mesh3:
    return weld_mesh(Mesh3.merged(meshes), tolerance=TOLERANCE)


def close_mesh(mesh: Mesh3) -> Mesh3:
    return mesh.close_mesh(tolerance=TOLERANCE)


def try_close_mesh(mesh: Mesh3) -> tuple[Mesh3 | None, Exception | None]:
    try:
        return close_mesh(mesh), None
    except ValueError as exc:
        return None, exc


def weld_mesh(mesh: Mesh3, *, tolerance: float) -> Mesh3:
    index_by_point: dict[tuple[int, int, int], int] = {}
    vertices: list[Point3] = []
    remap: list[int] = []

    for x, y, z in mesh.vertices:
        if abs(y) <= tolerance:
            y = 0.0
        key = (round(x / tolerance), round(y / tolerance), round(z / tolerance))
        if key not in index_by_point:
            index_by_point[key] = len(vertices)
            vertices.append((x, y, z))
        remap.append(index_by_point[key])

    faces: list[Face] = []
    for face in mesh.faces:
        mapped: list[int] = []
        for index in face:
            new_index = remap[index]
            if not mapped or mapped[-1] != new_index:
                mapped.append(new_index)
        if len(mapped) > 1 and mapped[0] == mapped[-1]:
            mapped.pop()

        unique: list[int] = []
        for index in mapped:
            if index not in unique:
                unique.append(index)
        if len(unique) >= 3:
            faces.append(tuple(unique))

    edges: set[Edge] = set()
    for a, b in mesh.edges:
        start, end = remap[a], remap[b]
        if start != end:
            edges.add((min(start, end), max(start, end)))

    return Mesh3(tuple(vertices), tuple(faces), tuple(sorted(edges)))


def _matches_any_point(point: Point3, targets: Iterable[Point3]) -> bool:
    return any(dist(point, target) <= TOLERANCE for target in targets)


def _edge_key(start: int, end: int) -> Edge:
    return (min(start, end), max(start, end))


def _mirror_point(point: Point3) -> Point3:
    return (point[0], -point[1], point[2])


def _clean_face(indices: Iterable[int]) -> Face:
    face: list[int] = []
    for index in indices:
        if not face or face[-1] != index:
            face.append(index)
    if len(face) > 1 and face[0] == face[-1]:
        face.pop()
    return tuple(face)


def build_patch_scene(meshes: tuple[Mesh3, ...]) -> Scene:
    styles = (YELLOW_TOP_STYLE, RED_TOP_STYLE, MIRRORED_YELLOW_STYLE, MIRRORED_RED_STYLE)
    scene = Scene(name="linesplan_mesh_patches")
    for index, mesh in enumerate(meshes):
        scene = scene.add(mesh, name=f"mesh_patch_{index:02d}", style=styles[index % len(styles)])
    return scene


def build_split_polyline_scene(polyline_groups: tuple[PolylineGroup, PolylineGroup]) -> Scene:
    scene = Scene(name="linesplan_split_polylines")
    styles = (YELLOW_TOP_STYLE, RED_TOP_STYLE)
    names = ("yellow_top", "red_top")
    for group_index, group in enumerate(polyline_groups):
        for polyline_index, polyline in enumerate(group):
            scene = scene.add(
                polyline.points(),
                name=f"{names[group_index]}_{polyline_index:02d}",
                style=styles[group_index],
            )

        if group:
            scene = scene.add(
                PointCloud3(tuple(polyline.start for polyline in group)),
                name=f"{names[group_index]}_starts",
                style=START_POINT_STYLE,
            )
            scene = scene.add(
                PointCloud3(tuple(polyline.end for polyline in group)),
                name=f"{names[group_index]}_ends",
                style=END_POINT_STYLE,
            )
    return scene


def build_comparison_scene(before: Mesh3, after: Mesh3) -> Scene:
    return (
        Scene(name="linesplan_remesh_comparison")
        .add(before, name="pizza_triangulated", style=PIZZA_STYLE)
        .add(after, name="isotropic_remesh", style=REMESH_STYLE)
    )


def view_intermediate_objects() -> None:
    view_original_station_lines(STATION_POLYLINES)
    view_processed_station_lines(
        PREPARED_STATION_POLYLINES,
        station_top_positive_y_points(PREPARED_STATION_POLYLINES),
        station_top_discontinuity_points(PREPARED_STATION_POLYLINES),
        station_end_points(PREPARED_STATION_POLYLINES),
    )
    build_split_polyline_scene(POLYLINE_GROUPS).view(title="split station polylines")
    build_patch_scene(MESH_PATCHES).view(title="linesplan mesh patches")


PROCESSED_STATION_POLYLINES = process_station_lines(STATION_POLYLINES, SNAP_TOLERANCE)
PREPARED_STATION_POLYLINES = prepare_station_lines(PROCESSED_STATION_POLYLINES)
POLYLINE_GROUPS = split_station_lines(PREPARED_STATION_POLYLINES)
YELLOW_TOP_POLYLINES = POLYLINE_GROUPS[0]
RED_TOP_POLYLINES = POLYLINE_GROUPS[1]
STATION_GREEN_POINTS = station_end_points(PREPARED_STATION_POLYLINES)
LOFTED_MESH_PATCHES = tuple(
    mark_mesh_boundary_nodes(patch, STATION_GREEN_POINTS)
    for patch in loft_polyline_groups(POLYLINE_GROUPS, node_spacing=NODE_SPACING)
)
YELLOW_MESH_NODES = tuple(node for patch in LOFTED_MESH_PATCHES for node in patch.yellow_nodes)
GREEN_MESH_NODES = tuple(node for patch in LOFTED_MESH_PATCHES for node in patch.green_nodes)
BOUNDARY_EXTENSION_MESHES = tuple(
    mesh
    for patch in LOFTED_MESH_PATCHES
    for nodes in (patch.yellow_nodes, patch.green_nodes)
    for mesh in boundary_extension_meshes(nodes)
)
HALF_MESHES = merge_boundary_extensions(LOFTED_MESH_PATCHES, BOUNDARY_EXTENSION_MESHES)
MIRRORED_MESHES = mirror_meshes(HALF_MESHES)
MESH_PATCHES = (*HALF_MESHES, *MIRRORED_MESHES)
KEEL_BOUNDARY_PAIRS = keel_boundary_pairs(LOFTED_MESH_PATCHES)
KEEL_END_PAIRS = keel_end_pairs(KEEL_BOUNDARY_PAIRS)
KEEL_BOUNDARY_ROWS = keel_boundary_rows(LOFTED_MESH_PATCHES)
KEEL_END_ROWS = keel_end_rows(KEEL_BOUNDARY_ROWS)
KEEL_CAP_MESH = keel_end_cap_mesh(KEEL_END_ROWS)
COMBINED_MESH = combine_meshes((*MESH_PATCHES, KEEL_CAP_MESH))
CLOSED_MESH, CLOSE_ERROR = try_close_mesh(COMBINED_MESH)
FINAL_MESH = CLOSED_MESH if CLOSED_MESH is not None else COMBINED_MESH
TRIANGULATED_MESH = pizza_triangulate_mesh(FINAL_MESH)

TRI_V = np.array(TRIANGULATED_MESH.vertices, dtype=np.float64)
TRI_F = np.array(TRIANGULATED_MESH.faces, dtype=np.int64)
REMESHED_V, REMESHED_F = isotropic_remesh(
    TRI_V,
    TRI_F,
    target_edge_length=None,
    iterations=6,
    feature_angle_degrees=None,
    protect_boundary=True,
    project=False,
    verbose=True,
)
REMESHED_MESH = Mesh3(
    tuple(tuple(v) for v in REMESHED_V),  # type: ignore[arg-type]
    tuple(tuple(int(i) for i in f) for f in REMESHED_F),  # type: ignore[arg-type]
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean, split, loft, mirror, combine, and close linesplan stations.",
    )
    parser.add_argument(
        "--no-view",
        action="store_true",
        help="Print mesh summaries without opening a viewer.",
    )
    parser.add_argument(
        "--patches",
        action="store_true",
        help="View only the open mesh patches.",
    )
    parser.add_argument(
        "--final-only",
        action="store_true",
        help="View only the final remeshed mesh.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Show pizza-triangulated (before) and remeshed (after) overlaid.",
    )
    args = parser.parse_args()

    print(f"polyline groups: yellow={len(YELLOW_TOP_POLYLINES)}, red={len(RED_TOP_POLYLINES)}")
    print(f"mesh patches: {len(MESH_PATCHES)}")
    print(
        f"combined mesh: {len(COMBINED_MESH.vertices)} vertices, {len(COMBINED_MESH.faces)} faces"
    )
    if CLOSED_MESH is None:
        print(f"closed mesh: failed - {CLOSE_ERROR}")
    else:
        print(f"closed mesh: {len(CLOSED_MESH.vertices)} vertices, {len(CLOSED_MESH.faces)} faces")
    print(
        f"triangulated mesh: {len(TRIANGULATED_MESH.vertices)} vertices, "
        f"{len(TRIANGULATED_MESH.faces)} faces"
    )
    print(
        f"remeshed mesh: {len(REMESHED_MESH.vertices)} vertices, {len(REMESHED_MESH.faces)} faces"
    )

    if args.no_view:
        return

    if args.patches:
        build_patch_scene(MESH_PATCHES).view(title="linesplan mesh patches")
    elif args.compare:
        build_comparison_scene(TRIANGULATED_MESH, REMESHED_MESH).view(
            title="linesplan remesh: pizza (orange) vs isotropic (blue)"
        )
    elif args.final_only:
        REMESHED_MESH.view(title="remeshed linesplan mesh")
    else:
        view_intermediate_objects()
        TRIANGULATED_MESH.view(title="triangulated linesplan mesh (before)")
        REMESHED_MESH.view(title="remeshed linesplan mesh (after)")


if __name__ == "__main__":
    main()
