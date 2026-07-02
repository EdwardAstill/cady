"""Reporting and visualisation helpers for the linesplan pipeline."""

from __future__ import annotations

from collections.abc import Iterable
from colorsys import hsv_to_rgb

from close_hull import LinesplanHull
from process_stations import ProcessedStations

from cady import DisplayStyle, Mesh3, PointCloud3, Polyline3, Scene, Wireframe3

YELLOW_TOP_STYLE = DisplayStyle(color=(0.95, 0.82, 0.12), render_mode="wireframe")
RED_TOP_STYLE = DisplayStyle(color=(0.95, 0.22, 0.12), render_mode="wireframe")
MIRRORED_YELLOW_STYLE = DisplayStyle(color=(0.35, 0.62, 0.9), render_mode="wireframe")
MIRRORED_RED_STYLE = DisplayStyle(color=(0.45, 0.78, 0.5), render_mode="wireframe")
START_POINT_STYLE = DisplayStyle(color=(0.95, 0.95, 0.12), point_size=8.0)
END_POINT_STYLE = DisplayStyle(color=(0.1, 0.82, 0.24), point_size=8.0)
TOP_POSITIVE_Y_STYLE = DisplayStyle(color=(1.0, 0.95, 0.05), point_size=10.0)
DISCONTINUITY_STYLE = DisplayStyle(color=(1.0, 0.18, 0.05), point_size=12.0)
SOURCE_STATION_STYLE = DisplayStyle(color=(0.05, 0.23, 0.55), render_mode="wireframe")


def print_summary(
    processed: ProcessedStations,
    hull: LinesplanHull,
    merged_coplanar_mesh: Mesh3 | None = None,
    cleaned_mesh: Mesh3 | None = None,
    cleaned_top_face: Mesh3 | None = None,
) -> None:
    """Print the stable summary used to verify the example."""
    print(
        "polyline groups: "
        f"yellow={len(processed.yellow_top_lines)}, red={len(processed.red_top_lines)}",
        flush=True,
    )
    print(f"mesh patches: {len(hull.mesh_patches)}", flush=True)
    print(
        f"combined mesh: {len(hull.combined_mesh.vertices)} vertices, "
        f"{len(hull.combined_mesh.faces)} faces",
        flush=True,
    )
    print(
        f"closed mesh: {len(hull.closed_mesh.vertices)} vertices, "
        f"{len(hull.closed_mesh.faces)} faces",
        flush=True,
    )
    if merged_coplanar_mesh is not None:
        print(
            f"merged coplanar mesh: {len(merged_coplanar_mesh.vertices)} vertices, "
            f"{len(merged_coplanar_mesh.faces)} faces",
            flush=True,
        )
    if cleaned_mesh is not None:
        print(
            f"cleaned mesh: {len(cleaned_mesh.vertices)} vertices, "
            f"{len(cleaned_mesh.faces)} faces",
            flush=True,
        )
    if cleaned_top_face is not None:
        print(
            f"cleaned top face: {len(cleaned_top_face.vertices)} vertices, "
            f"{len(cleaned_top_face.faces)} faces",
            flush=True,
        )


def view_final_mesh(hull: LinesplanHull) -> None:
    """Display the closed hull mesh."""
    hull.closed_mesh.view(title="closed linesplan mesh")


def view_combined_mesh(hull: LinesplanHull) -> None:
    """Display the welded mesh immediately before boundary closure."""
    hull.combined_mesh.view(title="combined linesplan mesh before boundary closure")


def view_cleaned_mesh(mesh: Mesh3) -> None:
    """Display the cleaned triangular hull mesh."""
    mesh.view(title="cleaned triangular linesplan mesh")


def view_cleaned_top_face(mesh: Mesh3) -> None:
    """Display the cleaned triangular top face."""
    mesh.view(title="cleaned triangular linesplan top face")


def view_merged_coplanar_mesh(mesh: Mesh3) -> None:
    """Display the merged connected-coplanar-face mesh before retriangulation."""
    mesh.view(title="merged coplanar linesplan mesh")


def view_full_walkthrough(
    source_stations: Iterable[Polyline3],
    processed: ProcessedStations,
    hull: LinesplanHull,
) -> None:
    """Display the intermediate scenes followed by the final mesh."""
    view_intermediate_objects(source_stations, processed, hull)
    view_combined_mesh(hull)
    view_final_mesh(hull)


def view_intermediate_objects(
    source_stations: Iterable[Polyline3],
    processed: ProcessedStations,
    hull: LinesplanHull,
) -> None:
    """Show the source, cleaned, split, and lofted intermediate objects."""
    view_original_station_lines(source_stations)
    view_processed_station_lines(processed)
    build_split_polyline_scene(processed).view(title="split station polylines")
    build_patch_scene(hull.mesh_patches).view(title="linesplan mesh patches")


def view_original_station_lines(polylines: Iterable[Polyline3]) -> None:
    """Display the raw station lines before cleanup."""
    wireframe = Wireframe3.from_polylines(polylines)
    wireframe.view(title="original station polylines", style=SOURCE_STATION_STYLE)


def view_processed_station_lines(processed: ProcessedStations) -> None:
    """Display prepared station lines and the key split/debug points."""
    polylines = processed.prepared_lines
    scene = Scene(name="processed_station_polylines")
    for index, polyline in enumerate(polylines):
        scene = scene.add(
            polyline.points(),
            name=f"station_{index:02d}",
            style=DisplayStyle(color=hsv_to_rgb(index / max(len(polylines), 1), 0.72, 0.92)),
        )

    if processed.top_positive_y_points:
        scene = scene.add(
            PointCloud3(processed.top_positive_y_points),
            name="station_top_positive_y_points",
            style=TOP_POSITIVE_Y_STYLE,
        )

    if processed.top_discontinuity_points:
        scene = scene.add(
            PointCloud3(processed.top_discontinuity_points),
            name="station_top_discontinuities",
            style=DISCONTINUITY_STYLE,
        )

    if processed.station_end_points:
        scene = scene.add(
            PointCloud3(processed.station_end_points),
            name="station_end_points",
            style=END_POINT_STYLE,
        )
    scene.view(title="processed station polylines")


def build_split_polyline_scene(processed: ProcessedStations) -> Scene:
    """Build a scene showing the two station groups used for lofting."""
    scene = Scene(name="linesplan_split_polylines")
    styles = (YELLOW_TOP_STYLE, RED_TOP_STYLE)
    names = ("yellow_top", "red_top")
    groups = (processed.yellow_top_lines, processed.red_top_lines)
    for group_index, group in enumerate(groups):
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


def build_patch_scene(meshes: tuple[Mesh3, ...]) -> Scene:
    """Build a scene showing the open lofted and mirrored mesh patches."""
    styles = (YELLOW_TOP_STYLE, RED_TOP_STYLE, MIRRORED_YELLOW_STYLE, MIRRORED_RED_STYLE)
    scene = Scene(name="linesplan_mesh_patches")
    for index, mesh in enumerate(meshes):
        scene = scene.add(mesh, name=f"mesh_patch_{index:02d}", style=styles[index % len(styles)])
    return scene
