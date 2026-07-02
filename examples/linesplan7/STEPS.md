# 1 Read And Classify The DXF Station Curves

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
endpoint-to-segment snaps match within `SNAP_TOLERANCE` (1000.0). Filter out
duplicate rows by checking all-point proximity.

## 2.2 Sort The Connected Polylines

Sort the connected station polylines by median `x`.

## 2.3 Prepare Each Station

Convert each station to points at `tolerance=1e-3`, deduplicate neighbouring
points, trim after the highest positive-`y` point, then orient so the row start
has the larger `z` value.

## 2.4 Split Each Station At The Keel Discontinuity

Find the highest discontinuity using `KEEL_DISCONTINUITY_ANGLE_DEGREES` (60°).
Rows before the split become the yellow top group. Rows after the split become
the red keel-top group.

## 2.5 Record The Debug Points

Record top positive-`y` points, top discontinuity points, and station end points
for later boundary marking and visual checks.

# 3 Loft The Station Groups Into Open Quad Mesh Patches

## 3.1 Choose A Shared Node Count For Each Group

Use each group's median polyline length and `TARGET_NODE_SPACING` (400.0) to
choose the number of nodes to sample on every station in that group.

## 3.2 Sample Each Station At Even Arc-Length Intervals

Walk along each station row and place nodes at even distances from the row
start to the row end.

## 3.3 Normalise Each Station Row To One X Plane

Set every node in a row to that row's median `x` coordinate so each station
section stays planar in the length direction.

## 3.4 Build Quad Mesh Patches From The Node Rows

Connect neighbouring nodes along each row and matching nodes between adjacent
rows to create open quad mesh patches. Result: one patch per group.

## 3.5 Mark The Centreline Boundary Nodes

Mark the first node in the yellow-group (group 0) rows as a yellow
centreline-closing boundary.

## 3.6 Mark The Prepared Station End Boundaries

Mark the final node in a row as a green boundary when the source polyline end
matches a prepared station end point within `1e-3`.

# 4 Close The Half Hull

## 4.1 Build Centreline Extension Strips

Turn contiguous yellow and green boundary-node chains into strip meshes
projected to `y = 0`.

## 4.2 Attach The Extension Strips To The Half Hull

Merge the centreline extension strips into the positive-`y` half-hull meshes.

## 4.3 Mirror The Half Hull

Mirror the positive-`y` half hull across the centreline plane `(y=0)` to create
the negative-`y` half hull.

## 4.4 Build The Keel End Caps

Take the first and last red keel boundary rows and join each row to its
mirrored row to form end cap faces.

## 4.5 Merge And Weld The Mesh Patches

Merge the half meshes, mirrored meshes, and keel end cap, then weld matching
vertices at `tolerance=1e-3`.

## 4.6 Close The Remaining Boundary Loops

Close the planar boundary loops with `Mesh3.close_mesh(...)`. If mesh closure
fails, report the error and fall back to the combined open mesh for display.

# 5 Report And Visualise The Results

## 5.1 Print The Mesh Summary

Print the station group counts, mesh patch count, combined mesh size, and
closed mesh status (size or failure).

## 5.2 Show The Intermediate Geometry

Open viewer windows for the source stations, processed stations, split station
groups, and mesh patches (yellow half, red half, mirrored yellow, mirrored red).

## 5.3 Show The Final Geometry

Open a viewer window for the closed hull mesh, falling back to the combined
mesh if closure failed.

# 6 Check The Current Result

## 6.1 Run The Example With The Default DXF

Run the linesplan7 example from the repository root:

```bash
PYTHONPATH=src .venv/bin/python examples/linesplan7/main.py
```

## 6.2 Compare The Summary Output

Check that the process reports:

```text
polyline groups: yellow=65, red=4
mesh patches: 4
combined mesh: <vertex count> vertices, <face count> faces
closed mesh: <vertex count> vertices, <face count> faces
```

## 6.3 Check The Result Visually

Check that the closed hull mesh is watertight (no visible gaps at the centreline
mirror, keel, or end caps) and that the surface is smooth across station
sections.
