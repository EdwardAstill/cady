"""Organise the linesplan station cleaning, lofting, mirroring, and closing."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import ceil, dist
from pathlib import Path
from typing import TypeAlias

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
from snap_close_nodes import snap_close_nodes
from wireframe import LINESPLAN_DXF, station_polylines

from cady import DisplayStyle, Mesh3, PointCloud3, Polyline3, Scene

Point3: TypeAlias = tuple[float, float, float]
Face: TypeAlias = tuple[int, ...]
Edge: TypeAlias = tuple[int, int]
PolylineGroup: TypeAlias = tuple[Polyline3, ...]
NodeArray: TypeAlias = tuple[tuple[Point3, ...], ...]

TOLERANCE = 1e-3
SNAP_CLOSE_TOLERANCE = 500
NODE_SPACING = 2000.0
SHORT_PROJECTION_RATIO = 0.3
MIRROR_PLANE_ORIGIN: Point3 = (0.0, 0.0, 0.0)
MIRROR_PLANE_NORMAL: Point3 = (0.0, 1.0, 0.0)

YELLOW_TOP_STYLE = DisplayStyle(color=(0.95, 0.82, 0.12), render_mode="wireframe")
RED_TOP_STYLE = DisplayStyle(color=(0.95, 0.22, 0.12), render_mode="wireframe")
MIRRORED_YELLOW_STYLE = DisplayStyle(color=(0.35, 0.62, 0.9), render_mode="wireframe")
MIRRORED_RED_STYLE = DisplayStyle(color=(0.45, 0.78, 0.5), render_mode="wireframe")
START_POINT_STYLE = DisplayStyle(color=(0.95, 0.95, 0.12), point_size=8.0)
END_POINT_STYLE = DisplayStyle(color=(0.1, 0.82, 0.24), point_size=8.0)


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


@dataclass(frozen=True, slots=True)
class LinesplanMeshBuild:
    input_path: Path
    station_polylines: tuple[Polyline3, ...]
    prepared_station_polylines: tuple[Polyline3, ...]
    polyline_groups: tuple[PolylineGroup, PolylineGroup]
    lofted_mesh_patches: tuple[LoftedMeshPatch, ...]
    mesh_patches: tuple[Mesh3, ...]
    combined_mesh: Mesh3
    closed_mesh: Mesh3 | None
    close_error: Exception | None
    triangulated_mesh: Mesh3
    snapped_mesh: Mesh3


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


def boundary_extension_meshes(
    nodes: Iterable[BoundaryNode],
    *,
    node_spacing: float = NODE_SPACING,
) -> tuple[Mesh3, ...]:
    meshes: list[Mesh3] = []
    chain: list[BoundaryNode] = []
    for node in sorted(nodes, key=lambda item: item.row_index):
        if chain and node.row_index != chain[-1].row_index + 1:
            meshes.append(
                boundary_extension_mesh(
                    (boundary_node.point for boundary_node in chain),
                    node_spacing=node_spacing,
                )
            )
            chain = []
        chain.append(node)

    if chain:
        meshes.append(
            boundary_extension_mesh(
                (boundary_node.point for boundary_node in chain),
                node_spacing=node_spacing,
            )
        )
    return tuple(mesh for mesh in meshes if mesh.vertices)


def boundary_extension_mesh(
    points: Iterable[Point3],
    *,
    node_spacing: float = NODE_SPACING,
) -> Mesh3:
    points = tuple(points)
    if len(points) < 2:
        return Mesh3((), ())
    if node_spacing <= 0.0:
        raise ValueError("node_spacing must be positive")

    longest_projection = max(abs(point[1]) for point in points)
    short_projection_limit = longest_projection * SHORT_PROJECTION_RATIO
    vertices: list[Point3] = []
    columns: list[tuple[int, ...]] = []
    for point in points:
        segment_count = _projection_segment_count(
            point,
            node_spacing=node_spacing,
            short_projection_limit=short_projection_limit,
        )
        column: list[int] = []
        for segment_index in range(segment_count + 1):
            ratio = segment_index / segment_count
            column.append(len(vertices))
            vertices.append(
                (
                    point[0],
                    0.0 if segment_index == segment_count else point[1] * (1.0 - ratio),
                    point[2],
                )
            )
        columns.append(tuple(column))

    faces: list[Face] = []
    edges: set[Edge] = set()
    for column in columns:
        for edge in zip(column, column[1:], strict=False):
            edges.add(_edge_key(*edge))
    for left_column, right_column in zip(columns, columns[1:], strict=False):
        _append_projection_faces(left_column, right_column, faces, edges)

    return weld_mesh(
        Mesh3(tuple(vertices), tuple(faces), tuple(sorted(edges))),
        tolerance=TOLERANCE,
    )


def _projection_segment_count(
    point: Point3,
    *,
    node_spacing: float,
    short_projection_limit: float,
) -> int:
    projection_distance = abs(point[1])
    if projection_distance < short_projection_limit:
        return 1
    return max(1, ceil(projection_distance / node_spacing))


def _append_projection_faces(
    left_column: tuple[int, ...],
    right_column: tuple[int, ...],
    faces: list[Face],
    edges: set[Edge],
) -> None:
    left_segments = len(left_column) - 1
    right_segments = len(right_column) - 1
    left_index = 0
    right_index = 0

    while left_index < left_segments or right_index < right_segments:
        next_left = (
            (left_index + 1) / left_segments
            if left_index < left_segments
            else float("inf")
        )
        next_right = (
            (right_index + 1) / right_segments
            if right_index < right_segments
            else float("inf")
        )
        if abs(next_left - next_right) <= 1e-12:
            face = _clean_face(
                (
                    left_column[left_index],
                    left_column[left_index + 1],
                    right_column[right_index + 1],
                    right_column[right_index],
                )
            )
            left_index += 1
            right_index += 1
        elif next_left < next_right:
            face = _clean_face(
                (
                    left_column[left_index],
                    left_column[left_index + 1],
                    right_column[right_index],
                )
            )
            left_index += 1
        else:
            face = _clean_face(
                (
                    left_column[left_index],
                    right_column[right_index + 1],
                    right_column[right_index],
                )
            )
            right_index += 1

        if len(face) >= 3:
            faces.append(face)
            for edge in zip(face, face[1:] + face[:1], strict=True):
                edges.add(_edge_key(*edge))


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


def build_linesplan_mesh(path: str | Path = LINESPLAN_DXF) -> LinesplanMeshBuild:
    input_path = Path(path)
    station_lines = station_polylines(input_path)
    processed_station_polylines = process_station_lines(station_lines, SNAP_TOLERANCE)
    prepared_station_polylines = prepare_station_lines(processed_station_polylines)
    polyline_groups = split_station_lines(prepared_station_polylines)
    station_green_points = station_end_points(prepared_station_polylines)
    lofted_mesh_patches = tuple(
        mark_mesh_boundary_nodes(patch, station_green_points)
        for patch in loft_polyline_groups(polyline_groups, node_spacing=NODE_SPACING)
    )
    boundary_extension_meshes_ = tuple(
        mesh
        for patch in lofted_mesh_patches
        for nodes in (patch.yellow_nodes, patch.green_nodes)
        for mesh in boundary_extension_meshes(nodes)
    )
    half_meshes = merge_boundary_extensions(lofted_mesh_patches, boundary_extension_meshes_)
    mirrored_meshes = mirror_meshes(half_meshes)
    mesh_patches = (*half_meshes, *mirrored_meshes)
    keel_boundary_rows_ = keel_boundary_rows(lofted_mesh_patches)
    keel_end_rows_ = keel_end_rows(keel_boundary_rows_)
    keel_cap_mesh = keel_end_cap_mesh(keel_end_rows_)
    combined_mesh = combine_meshes((*mesh_patches, keel_cap_mesh))
    closed_mesh, close_error = try_close_mesh(combined_mesh)
    final_mesh = closed_mesh if closed_mesh is not None else combined_mesh
    triangulated_mesh = pizza_triangulate_mesh(final_mesh)
    snapped_mesh = snap_close_nodes(triangulated_mesh, tolerance=SNAP_CLOSE_TOLERANCE)
    return LinesplanMeshBuild(
        input_path=input_path,
        station_polylines=station_lines,
        prepared_station_polylines=prepared_station_polylines,
        polyline_groups=polyline_groups,
        lofted_mesh_patches=lofted_mesh_patches,
        mesh_patches=mesh_patches,
        combined_mesh=combined_mesh,
        closed_mesh=closed_mesh,
        close_error=close_error,
        triangulated_mesh=triangulated_mesh,
        snapped_mesh=snapped_mesh,
    )


def view_intermediate_objects(build: LinesplanMeshBuild) -> None:
    view_original_station_lines(build.station_polylines)
    view_processed_station_lines(
        build.prepared_station_polylines,
        station_top_positive_y_points(build.prepared_station_polylines),
        station_top_discontinuity_points(build.prepared_station_polylines),
        station_end_points(build.prepared_station_polylines),
    )
    build_split_polyline_scene(build.polyline_groups).view(title="split station polylines")
    build_patch_scene(build.mesh_patches).view(title="linesplan mesh patches")


def main(
    dxf_file_path: str | Path = LINESPLAN_DXF,
    *,
    show_view: bool = True,
    patches: bool = False,
    final_only: bool = False,
) -> LinesplanMeshBuild:
    build = build_linesplan_mesh(dxf_file_path)
    yellow_top_polylines, red_top_polylines = build.polyline_groups

    print(f"input: {build.input_path}")
    print(f"polyline groups: yellow={len(yellow_top_polylines)}, red={len(red_top_polylines)}")
    print(f"mesh patches: {len(build.mesh_patches)}")
    print(
        f"combined mesh: {len(build.combined_mesh.vertices)} vertices, "
        f"{len(build.combined_mesh.faces)} faces"
    )
    if build.closed_mesh is None:
        print(f"closed mesh: failed - {build.close_error}")
    else:
        print(
            f"closed mesh: {len(build.closed_mesh.vertices)} vertices, "
            f"{len(build.closed_mesh.faces)} faces"
        )
    print(
        f"triangulated mesh: {len(build.triangulated_mesh.vertices)} vertices, "
        f"{len(build.triangulated_mesh.faces)} faces"
    )
    print(
        f"snapped mesh: {len(build.snapped_mesh.vertices)} vertices, "
        f"{len(build.snapped_mesh.faces)} faces, {len(build.snapped_mesh.edges)} edges"
    )

    if not show_view:
        return build

    if patches:
        build_patch_scene(build.mesh_patches).view(title="linesplan mesh patches")
    elif final_only:
        build.snapped_mesh.view(title="snapped triangulated linesplan mesh")
    else:
        view_intermediate_objects(build)
        build.snapped_mesh.view(title="snapped triangulated linesplan mesh")
    return build


if __name__ == "__main__":
    main()
