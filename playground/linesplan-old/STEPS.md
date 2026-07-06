# 1 Load And Classify The DXF Station Curves

## 1.1 Read The DXF Curves

Read `examples/inputs/linesplan_9m.dxf` with
`cady.files.dxf.read_curves(...)`.

## 1.2 Classify The Linesplan Network

Pass the DXF curves to `classify_linesplan_curves(...)` so the source network is
split into named line types.

## 1.3 Keep The Station Sections

Keep only the classified station sections. These are the hull cross-sections
used by the downstream pipeline.

## 1.4 Store The Stations As Polylines

Store each station section as a `Polyline3`.

# 2 Process The Station Polylines

## 2.1 Snap And Connect Close Station Fragments

Snap near-centreline points to `y = 0`, remove repeated neighbouring points,
drop fragments shorter than `1.0`, and join fragments whose endpoints or
endpoint-to-segment snaps match within `SNAP_TOLERANCE`.

## 2.2 Orient The Connected Polylines

Sort the connected station polylines by median `x`, then orient each polyline so
the row starts at the larger `z` value.

## 2.3 Convert Each Oriented Station To Points

Convert each oriented station to points at `tolerance=1e-3` and remove repeated
neighbouring points.

## 2.4 Trim Each Station After The Highest Positive-Y Point

Find the highest station point whose `y` value is greater than `TOLERANCE`, then
discard later points on that row.

## 2.5 Split Each Station At The Keel Discontinuity

Find the highest top discontinuity using `KEEL_DISCONTINUITY_ANGLE_DEGREES`.
Rows before the split become the yellow top group. Rows after the split become
the red keel-top group.

## 2.6 Record The Debug And Boundary Points

Record top positive-`y` points, top discontinuity points, and station end points
for later boundary marking and visual checks.

# 3 Loft The Station Groups Into Open Mesh Patches

## 3.1 Choose A Shared Node Count For Each Group

Use each group's median polyline length and `TARGET_NODE_SPACING` to choose the
number of nodes to sample on every station in that group.

## 3.2 Sample Each Station At Even Arc-Length Intervals

Walk along each station row and place nodes at even distances from the row
start to the row end.

## 3.3 Normalise Each Station Row To One X Plane

Set every node in a row to that row's median `x` coordinate so each station
section stays planar in the length direction.

## 3.4 Build Quad Mesh Patches From The Node Rows

Connect neighbouring nodes along each row and matching nodes between adjacent
rows to create open quad mesh patches.

## 3.5 Mark The Centreline Boundary Nodes

Mark the first yellow-group node in each row as a yellow centreline-closing
boundary.

## 3.6 Mark The Prepared Station End Boundaries

Mark the final node in a row as a green boundary when the source polyline end
matches a prepared station end point.

# 4 Close The Half Hull

## 4.1 Build Centreline Extension Strips

Turn contiguous yellow and green boundary-node chains into strip meshes
projected to `y = 0`.

## 4.2 Attach The Extension Strips To The Half Hull

Merge the centreline extension strips into the positive-`y` half-hull meshes.

## 4.3 Mirror The Half Hull

Mirror the positive-`y` half hull across the centreline plane to create the
negative-`y` half hull.

## 4.4 Build The Keel End Caps

Take the first and last red keel rows and join each row to its mirrored row.

## 4.5 Merge And Weld The Mesh Patches

Merge the half meshes, mirrored meshes, and keel caps, then weld matching
vertices at `tolerance=1e-3`.

## 4.6 Close The Remaining Boundary Loops

Close the planar boundary loops with `Mesh3.close_mesh(...)`. This adds polygon
cap faces without triangulating them. If mesh closure fails, raise the error and
do not treat the combined open mesh as a usable final hull.

# 5 Merge, Triangulate, And Decimate The Mesh

## 5.1 Use The Closed Mesh As The Final Hull Source

Use `hull.closed_mesh` from the hull-closing stage. Do not fall back to the
combined open mesh.

## 5.2 Split Non-Planar Loft Quads

Find any quad face whose four vertices are not planar within `TOLERANCE`, then
split that quad into two triangles. Leave planar quads and larger planar
polygon faces unchanged.

## 5.3 Merge Connected Coplanar Faces

Run `merge_coplanar_faces(...)` before triangulation so connected faces on the
same plane become larger polygon faces.

## 5.4 Copy Existing Triangle Faces

Keep existing triangle faces as triangles during cleanup.

## 5.5 Triangulate Non-Triangle Polygon Faces

Send every non-triangular polygon face through the local
`triangulate_polygon.py` helper. The main pipeline requests
`min_angle_degrees=20.0` for both the full cleaned mesh and the extracted top
face.

## 5.6 Stop If Cleanup Fails

If cleaning fails, print the summary, show the walkthrough and merged coplanar
mesh, report the triangulation failure, and re-raise the error.

# 6 Report And Visualise The Results

## 6.1 Print The Mesh Summary

Print the station group counts, patch count, combined mesh size, closed mesh
size, merged coplanar mesh size, cleaned mesh size, and cleaned top face size.

## 6.2 Show The Intermediate Geometry

Open viewer windows for the source stations, processed stations, split station
groups, mesh patches, the combined mesh before boundary closure, and the merged
coplanar mesh.

## 6.3 Show The Final Geometry

Open viewer windows for the closed hull mesh, cleaned mesh, and cleaned top face.

# 7 Check The Current Result

## 7.1 Run The Example With The Default DXF

Run the refactored linesplan example from the repository root:

```bash
PYTHONPATH=src .venv/bin/python examples/linesplan-refactored/main.py
```

## 7.2 Compare The Summary Output

Check that the process reports:

```text
polyline groups: yellow=65, red=4
mesh patches: 4
combined mesh: 8882 vertices, 8740 faces
closed mesh: 8882 vertices, 8746 faces
merged coplanar mesh: 4995 vertices, 9308 faces
cleaned mesh: <vertex count> vertices, <face count> faces
```

## 7.3 Verify Cleaned Mesh Quality

Check that `cleaned mesh` and `cleaned top face` report vertex and face counts
(not a triangulation failure) and that all faces are triangles satisfying the
20° minimum angle constraint.
