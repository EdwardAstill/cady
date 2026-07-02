"""Coordinate the linesplan station processing and hull-closing pipeline."""

from __future__ import annotations

from clean_mesh import TOLERANCE, clean_mesh, merge_coplanar_faces
from close_hull import close_linesplan_hull
from load_stations import load_station_polylines
from loft_patches import loft_station_groups
from process_stations import process_stations
from visualise import (
    print_summary,
    view_cleaned_mesh,
    view_decimated_mesh,
    view_full_walkthrough,
    view_merged_coplanar_mesh,
)

from cady import Mesh3

DECIMATED_TARGET_FACES = 3000 


def main() -> Mesh3:
    """Run the example from DXF input through to the closed hull mesh."""
    station_lines = load_station_polylines()
    processed = process_stations(station_lines)
    lofted_patches = loft_station_groups(
        (processed.yellow_top_lines, processed.red_top_lines),
        processed.station_end_points,
    )
    hull = close_linesplan_hull(lofted_patches)
    final_mesh = hull.closed_mesh or hull.combined_mesh
    merged_coplanar_mesh = merge_coplanar_faces(final_mesh)
    try:
        cleaned_mesh = clean_mesh(final_mesh)
    except ValueError as exc:
        print_summary(processed, hull, merged_coplanar_mesh)
        print(f"cleaned mesh: failed - {exc}", flush=True)
        view_full_walkthrough(station_lines, processed, hull)
        view_merged_coplanar_mesh(merged_coplanar_mesh)
        raise
    decimated_mesh = cleaned_mesh.decimate(DECIMATED_TARGET_FACES, tolerance=TOLERANCE)

    print_summary(processed, hull, merged_coplanar_mesh, cleaned_mesh, decimated_mesh)
    view_full_walkthrough(station_lines, processed, hull)
    view_merged_coplanar_mesh(merged_coplanar_mesh)
    view_cleaned_mesh(cleaned_mesh)
    view_decimated_mesh(decimated_mesh)
    print("done")
    return decimated_mesh

if __name__ == "__main__":
    main()
