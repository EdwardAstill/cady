"""Coordinate the linesplan station processing and hull-closing pipeline."""

from __future__ import annotations

from clean_mesh import (
    clean_mesh,
    merge_coplanar_faces,
    top_face_mesh,
    triangulate_non_planar_quads,
)
from close_hull import close_linesplan_hull
from load_stations import load_station_polylines
from loft_patches import loft_station_groups
from process_stations import process_stations
from visualise import (
    print_summary,
    view_cleaned_mesh,
    view_cleaned_top_face,
    view_full_walkthrough,
    view_merged_coplanar_mesh,
)

from cady import Mesh3

MIN_TRIANGLE_ANGLE_DEGREES = 5.0


def main() -> Mesh3:
    """Run the example from DXF input through to the closed hull mesh."""
    station_lines = load_station_polylines()
    processed = process_stations(station_lines)
    lofted_patches = loft_station_groups(
        (processed.yellow_top_lines, processed.red_top_lines),
        processed.station_end_points,
    )
    hull = close_linesplan_hull(lofted_patches)
    final_mesh = hull.closed_mesh
    quad_triangular_mesh = triangulate_non_planar_quads(final_mesh)
    merged_coplanar_mesh = merge_coplanar_faces(quad_triangular_mesh)
    top_face = top_face_mesh(merged_coplanar_mesh)
    try:
        cleaned_mesh = clean_mesh(
            merged_coplanar_mesh,
            min_angle_degrees=MIN_TRIANGLE_ANGLE_DEGREES,
        )
        cleaned_top_face = clean_mesh(
            top_face,
            min_angle_degrees=MIN_TRIANGLE_ANGLE_DEGREES,
        )
    except ValueError as exc:
        print_summary(processed, hull, merged_coplanar_mesh)
        print(f"cleaned mesh: failed - {exc}", flush=True)
        view_full_walkthrough(station_lines, processed, hull)
        view_merged_coplanar_mesh(merged_coplanar_mesh)
        raise

    print_summary(
        processed,
        hull,
        merged_coplanar_mesh=merged_coplanar_mesh,
        cleaned_mesh=cleaned_mesh,
        cleaned_top_face=cleaned_top_face,
    )
    view_full_walkthrough(station_lines, processed, hull)
    view_merged_coplanar_mesh(merged_coplanar_mesh)
    view_cleaned_mesh(cleaned_mesh)
    view_cleaned_top_face(cleaned_top_face)
    print("done")
    return cleaned_mesh


if __name__ == "__main__":
    main()
