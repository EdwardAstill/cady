# Linesplan mesh pipeline

Reads a DXF linesplan, cleans station curves, lofts them into a half-hull
quad-strip mesh, mirrors it, caps the ends, closes holes, and triangulates.

## Pipeline steps

### 1. Read DXF — `wireframe.py`

Loads station polyline curves from a DXF file via `cady.files.dxf.read()`.
Produces `STATION_POLYLINES` — a tuple of `Polyline3` curves used by the rest
of the pipeline.

### 2. Process polylines — `process_polylines.py`

- **Snap & join** — snaps close endpoints (`SNAP_TOLERANCE = 1000 mm`) and
  joins collinear fragments into continuous station curves.
- **Clean** — removes short fragments below `MIN_STATION_FRAGMENT_LENGTH`,
  deduplicates consecutive points.
- **Classify** — splits stations into two groups based on the station top
  y-coordinate pattern:
  - **Yellow group** — stations with tops in positive-y (bow half).
  - **Red group** — stations with tops approaching or at y=0 (stern keel).
- Each group is sorted by x-coordinate (bow-to-stern).

Produces `POLYLINE_GROUPS = (yellow_group, red_group)`.

### 3. Loft polylines — `loft_polylines.py`

- Resamples each polyline to a uniform number of nodes (`nodes_on_polyline`)
  based on the median polyline length and `TARGET_NODE_SPACING`.
- Constructs a quad-strip mesh grid: adjacent rows of equal-length node arrays
  are stitched into quad faces (`get_node_array` → `mesh_node_array`).
- One `Mesh3` patch per polyline group.

Produces `LOFTED_MESH_PATCHES`.

### 4. Mark boundary nodes — `main.py`

Identifies mesh boundary nodes on each lofted patch:

- **Yellow nodes** — the first column of the yellow group mesh (bow boundary,
  group index 0).
- **Green nodes** — the last column of each row where the polyline endpoint
  matches a known station end point (keel-joining boundary).

Returns annotated `LoftedMeshPatch` records.

### 5. Boundary extensions — `main.py`

For each chain of consecutive boundary nodes, creates quad faces that extend
the boundary edges down to y=0 (the centerline plane). Vertices with y ≈ 0
map directly; others are projected to `(x, 0, z)`.

Produces `BOUNDARY_EXTENSION_MESHES`, merged into `HALF_MESHES`.

### 6. Mirror — `main.py`

Mirrors each half-hull mesh across the centerline plane `y=0` using
`Mesh3.mirror()`. Produces a full-hull set of mesh patches.

Produces `MESH_PATCHES = (*HALF_MESHES, *MIRRORED_MESHES)`.

### 7. Keel end cap — `main.py`

Creates closing faces at the bow and stern keel boundaries by taking the
first and last keel boundary rows, mirroring them, and forming polygon faces
that bridge the gap.

Produces `KEEL_CAP_MESH`.

### 8. Combine — `main.py`

Merges all mesh patches and the keel cap into one mesh via `Mesh3.merged()`,
then welds coincident vertices within `TOLERANCE` (snaps y ≈ 0 to exactly 0,
deduplicates by tolerance-grid keying, removes degenerate faces).

Produces `COMBINED_MESH`.

### 9. Close — `main.py`

Attempts `mesh.close_mesh(tolerance=TOLERANCE)` to fill remaining holes.
Falls back to the combined mesh if closing fails.

Produces `CLOSED_MESH` (or `COMBINED_MESH` on failure).

### 10. Pizza triangulate — `pizza_triangulate.py` (last step)

Converts every non-triangular face in the final mesh to triangles:

- **Quads** (4 vertices) → split along the shorter diagonal into 2 triangles.
- **N-gons** (5+ vertices) → add a vertex at the face centroid, then fan
  triangles from the centroid to each edge.

Display edges are **recomputed from the new triangle faces** so every edge
(including the diagonal splits) is visible in the viewer.

Produces `TRIANGULATED_MESH` — an all-triangle mesh ready for export or
further processing.

## File map

| File | Role |
|---|---|
| `main.py` | Pipeline orchestrator — wires all steps, prints stats, handles viewing |
| `wireframe.py` | DXF loading and station classification |
| `process_polylines.py` | Station curve cleaning, snapping, splitting into groups |
| `loft_polylines.py` | Uniform resampling and quad-strip lofting |
| `pizza_triangulate.py` | Quad/n-gon to triangle conversion (pizza/centroid fan) |
| `remesh.py` | Standalone isotropic remeshing utilities (split, collapse, flip, smooth) |
| `close_mesh.py` | Quick viewer for the closed mesh |
| `steps.md` | This file — pipeline documentation |
