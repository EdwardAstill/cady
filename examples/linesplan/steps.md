# Linesplan mesh pipeline

Reads a DXF linesplan, extracts station curves, cleans and splits them, lofts
the station groups into half-hull patches, projects boundary chains to the
centreline, mirrors the half hull, caps and closes it, triangulates every face,
then snaps close nodes in the final triangle mesh.

The pipeline resolves four tolerance-style settings from the station-line
`x` span. If a setting is left as `None`, it is scaled from the 9 m reference
linesplan values:

- `STATION_GEOMETRY_TOLERANCE = 1e-3` is the fine DXF station cleanup tolerance.
- `DXF_SNAP_TOLERANCE` joins source DXF station fragments during
  station-line cleanup.
- `MESH_GEOMETRY_TOLERANCE` is the fine mesh welding and closure tolerance.
- `MESH_SNAP_TOLERANCE` merges close final mesh vertices after
  triangulation.
- `NODE_SPACING` controls loft and boundary projection sampling density.

## Pipeline steps

### 1. Read DXF - `wireframe.py`

`station_polylines(...)` reads the selected DXF with `cady.files.dxf.read_curves(...)`,
classifies the linesplan network with `classify_linesplan_curves(...)`, and returns
the station sections as immutable `Polyline3` values.

Produces `LinesplanMeshBuild.station_polylines`.

### 2. Process station polylines - `process_polylines.py`

- Snaps points close to the centreline onto `y = 0`.
- Drops fragments shorter than `MIN_STATION_FRAGMENT_LENGTH`.
- Deduplicates neighbouring points at `STATION_GEOMETRY_TOLERANCE = 1e-3`.
- Joins station fragments when endpoints, reversed endpoints, or
  endpoint-to-segment snap points match within the resolved `DXF_SNAP_TOLERANCE`.
- Filters duplicate rows and sorts the connected station rows by median `x`.
- Trims each station after its highest positive-`y` top point and orients it so
  the higher-`z` end is first.
- Splits rows at the highest discontinuity above
  `KEEL_DISCONTINUITY_ANGLE_DEGREES = 60.0`.

The split result is `LinesplanMeshBuild.polyline_groups`, with yellow top
polylines first and red top polylines second. Rows without a qualifying
discontinuity stay in the yellow group. Rows with a qualifying discontinuity
contribute a yellow section up to the break and a red section from the break to
the station end.

### 3. Loft station groups - `loft_polylines.py`

`main.py` calls `loft_polyline_groups(...)` with the resolved `NODE_SPACING`.

For each group, `get_node_array(...)`:

- Chooses one shared row width from the group's median polyline length.
- Samples every station at even arc-length positions.
- Projects every sampled row back onto one median-`x` station plane.

`mesh_node_array(...)` then stitches neighbouring rows into quad-strip
`Mesh3` patches and keeps row and column display edges.

Produces `LinesplanMeshBuild.lofted_mesh_patches`.

### 4. Mark boundary nodes - `main.py`

Each `LoftedMeshPatch` is annotated with boundary nodes:

- Yellow nodes are the first sampled node in every row of group 0.
- Green nodes are the final sampled node in rows whose source polyline end
  matches a prepared station end point.

Stores yellow and green boundary nodes on each `LoftedMeshPatch`.

### 5. Project boundary chains to the centreline - `main.py`

`boundary_extension_meshes(...)` splits marked nodes into consecutive row-index
chains. Each chain is projected down to `y = 0` and converted into an extension
mesh.

For each boundary point, `_projection_segment_count(...)` decides how many
segments the projected column should have:

- Short projections below `SHORT_PROJECTION_RATIO = 0.3` of the longest
  projection in the chain use one direct boundary-to-centreline segment.
- Longer projections get intermediate nodes spaced by `NODE_SPACING`.

Neighbouring projected columns can have different node counts. `_append_projection_faces(...)`
walks both columns by relative height and emits quads when the next step lines
up, otherwise triangles. The result is a mixed triangle/quad extension strip
instead of a forced rectangular grid.

Extension meshes are welded at `MESH_GEOMETRY_TOLERANCE` and merged into the
first half-hull patch.

Produces boundary extension meshes that are merged into the half-hull meshes.

### 6. Mirror the half hull - `main.py`

Every half-hull mesh is mirrored across the centreline plane `y = 0` with
`Mesh3.mirror(...)`.

Produces `LinesplanMeshBuild.mesh_patches`.

### 7. Cap the keel ends - `main.py`

The red keel rows are sorted by `x`. The first and last rows are mirrored and
wrapped into polygon faces that bridge each red row to its mirrored copy.

Produces `KEEL_CAP_MESH`.

### 8. Combine, weld, and close - `main.py`

`combine_meshes(...)` merges all hull patches and the keel cap, then
`weld_mesh(...)`:

- Snaps vertices within `MESH_GEOMETRY_TOLERANCE` of `y = 0` exactly onto the
  centreline.
- Deduplicates vertices by tolerance-grid key.
- Removes degenerate faces and collapsed display edges.

`try_close_mesh(...)` then calls
`mesh.close_mesh(tolerance=MESH_GEOMETRY_TOLERANCE)` to fill remaining boundary
loops. If closure fails, the pipeline keeps the combined mesh for later steps.

Produces `LinesplanMeshBuild.combined_mesh` and, when closure succeeds,
`LinesplanMeshBuild.closed_mesh`.

### 9. Triangulate faces - `pizza_triangulate.py`

`pizza_triangulate_mesh(...)` converts the closed mesh, or the combined mesh if
closure failed, to an all-triangle mesh:

- Triangles pass through unchanged.
- Quads split along the shorter diagonal.
- N-gons first try a centroid fan.
- If the centroid fan misses `PIZZA_MIN_ANGLE_DEGREES = 15.0`, the triangulator
  tries up to three reduced inner polygon rings.
- If the ring strategy still misses the angle target, it recursively splits the
  polygon across the best valid internal chord.

Display edges are recomputed from the new triangle faces, so diagonal splits and
inserted ring/centroid edges are visible.

Produces `LinesplanMeshBuild.triangulated_mesh`.

### 10. Snap close final nodes - `snap_close_nodes.py`

`snap_close_nodes(build.triangulated_mesh, tolerance=...)` runs after
triangulation with the resolved `MESH_SNAP_TOLERANCE`.

The snapper uses a tolerance-sized spatial grid to find the nearest existing
vertex within tolerance, remaps close vertices onto that shared vertex, removes
collapsed faces, drops duplicate faces, and cleans collapsed display edges.

Produces `LinesplanMeshBuild.snapped_mesh`, the mesh shown by `main.py` when
`main(..., final_only=True)` is used.

## Run and check

Run from the repository root:

```bash
PYTHONPATH=src:examples/linesplan .venv/bin/python -c "from main import DXF_FILE, main; main(DXF_FILE, show_view=False)"
```

Current summary output:

```text
input: /home/eastill/projects/cady/examples/inputs/3d_lp.dxf
polyline groups: yellow=23, red=0
mesh patches: 2
combined mesh: 1228 vertices, 1334 faces
closed mesh: 1228 vertices, 1336 faces
triangulated mesh: 1273 vertices, 2542 faces
snapped mesh: 1263 vertices, 2521 faces, 3782 edges
```

Call `main(DXF_FILE, patches=True)` to view only the open and mirrored patches,
or `main(DXF_FILE, final_only=True)` to view only the snapped triangulated mesh.

## File map

| File | Role |
|---|---|
| `main.py` | Pipeline orchestrator; wires all steps, prints stats, handles viewing |
| `wireframe.py` | DXF reading and station section extraction |
| `process_polylines.py` | Station cleaning, snapping, joining, trimming, and splitting |
| `loft_polylines.py` | Uniform station resampling and quad-strip lofting |
| `pizza_triangulate.py` | Triangle conversion for triangles, quads, and n-gons |
| `snap_close_nodes.py` | Final tolerance-based node snapping and topology cleanup |
| `close_mesh.py` | Quick viewer for the closed mesh result |
| `steps.md` | This pipeline documentation |
