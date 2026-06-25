# Linesplan Wireframe Meshing Tasks

**Date:** 2026-06-25
**Status:** planned, not implemented

## Task 1: Freeze The Current Failure As A Regression

Add a test around `examples/inputs/linesplan_9m.dxf` proving that the old hidden
mesh path returns display edges that are not face edges.

Expected assertion shape:

- `mesh.edges` contains source-wire-only edges today.
- The future explicit mesher must not mix source overlay edges into the mesh.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d tests/files
```

## Task 2: Split DXF Parsing From Linesplan Meshing

Deprecate or remove line-geometry meshing from `dxf.read_mesh(...)`.

Expected behaviour:

- `dxf.read_mesh(path)` reads actual DXF mesh entities such as `3DFACE`.
- DXF `POLYLINE` line geometry is available through `read_wireframe(...)` or a
  new structured curve import API.
- No DXF facade silently converts polylines into hull surfaces.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/files tests/geometry3d/test_mesh.py
```

## Task 3: Preserve Source Curve Metadata

Introduce a structured source-curve representation for imported DXF polylines.

Minimum fields:

- vertices
- edges or ordered point list
- DXF layer
- entity type
- source index
- derived orientation hints: approximately constant `x`, `y`, or `z`

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/files
```

## Task 4: Add Linesplan Curve Classification

Build `classify_linesplan_curves(...)` to classify sections, buttocks,
waterlines, knuckles, boundaries, and rejected curves.

For `linesplan_9m.dxf`, expected starting classification from local inventory:

- 68 `SECTIONS`
- 19 `BUTTOCKS`
- 9 `WATERLINES`
- 4 `Knuckle`
- 5 layer `0` polylines

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/test_linesplan_network.py
```

## Task 5: Build Curve-Network Compatibility

Compute intersections between profile and guide curves within tolerance, sort
curves in each parameter direction, and report missing/ambiguous intersections.

Expected behaviour:

- The operation returns a compatibility report before meshing.
- Bad networks fail with actionable diagnostics rather than a malformed mesh.
- The algorithm never silently drops guide curves.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/test_linesplan_network.py
```

## Task 6: Implement Native Sampled Gordon-Style Meshing

Implement the first native backend:

- Use compatible profile/guide intersections as the parameter grid.
- Resample curves at shared parameter values.
- Construct a surface grid constrained by both directions.
- Triangulate the grid.
- Add mesh edges only from actual grid/face topology.

This does not need to output a NURBS object in the first pass. It only needs to
return a correct `Mesh3D` whose surface covers the classified source curves.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/test_linesplan_meshing.py
```

## Task 7: Add Optional Backend Spike

Create a non-default experiment for `occ_gordon` or `geomdl`.

Rules:

- Do not add a default runtime dependency without approval.
- Keep the spike isolated under examples, experimental tests, or an optional
  extra.
- Use it to validate shape quality and identify gaps in the native backend.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/test_linesplan_meshing.py
```

## Task 8: Rewrite The Linesplan Example

Replace the current `mesh-boundary.py` data flow with explicit stages:

```text
read DXF wireframe -> classify network -> mesh network -> render mesh + source overlay
```

Expected display:

- The shaded mesh is generated from the classified curve network.
- Source wires are a separate overlay object.
- Any source curve not used by the mesh has a printed rejection/classification
  reason.

Verification:

```bash
PYTHONPATH=src .venv/bin/python examples/linesplan/mesh-boundary.py --no-view
PYTHONPATH=src .venv/bin/pytest -q tests/examples/test_visualise_3d.py
```

## Task 9: Run Gates

After implementation:

```bash
PYTHONPATH=src .venv/bin/pytest -q
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
git diff --check
git status --short
```

