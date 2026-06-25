# Linesplan Wireframe Meshing Spec

**Date:** 2026-06-25
**Status:** first native implementation complete

## Problem

`dxf.read_mesh(...)` currently parses DXF line geometry, invents a mesh from a
subset of section-like curves, and then appends the original DXF wireframe
vertices/edges onto the returned `Mesh3D` as display edges.

This creates a false topology: the viewer shows wireframe edges that are not
edges of any mesh face, and the mesh surface can fail to cover source lines that
were not selected by the hidden loft heuristic.

## Decision

Remove the hidden DXF-to-mesh responsibility from the DXF facade. DXF import
should produce drawing, mesh entities that are actually mesh entities, and
wire/curve entities. Linesplan surface generation should be an explicit
wireframe/curve-network operation.

Target data flow:

```text
DXF file
  -> dxf.read_wireframe(...) / dxf.read_curves(...)
  -> LinesplanCurveNetwork
  -> mesh_linesplan_curve_network(...)
  -> Mesh3D
```

## Algorithm

Use Gordon surface / curve-network interpolation as the target algorithm family.

Implementation should proceed in two levels:

1. **Native sampled network mesher:** classify curves, find intersections,
   build a compatible U/V parameter grid, evaluate a sampled surface, and
   triangulate the sampled grid. This can be done with existing NumPy support
   and keeps cady's core dependency surface small.
2. **Optional reference backend spike:** test `occ_gordon` or `geomdl` outside
   the core runtime path. `occ_gordon` is closest to full Gordon interpolation
   but depends on OpenCASCADE/pythonocc. `geomdl` is pure Python and useful for
   B-spline fitting/evaluation once a grid exists, but does not solve network
   classification by itself.

## Expected Behaviour

- `dxf.read_wireframe(path)` remains the file-format import path for DXF line
  geometry.
- A new explicit operation converts source wire/curve data into a mesh.
- Source wireframes can be rendered as a separate scene object, not embedded in
  `Mesh3D.edges`.
- `Mesh3D.edges`, when present, must refer to edges that are actually meaningful
  for the mesh being displayed. Source overlay edges must not be mixed into the
  mesh topology.
- The linesplan example should show the generated surface covering the relevant
  source curves; any non-meshed source curve should be visibly separate and
  explainable by classification, not silently drawn as part of the mesh.

## Non-Goals

- Do not add OpenCASCADE, Gmsh, VTK, SciPy, or geomdl as default runtime
  dependencies without explicit approval.
- Do not try to solve arbitrary unorganized 3D curve-network reconstruction in
  the first pass.
- Do not preserve the existing `dxf.read_mesh(... mirror_origin=...)` behaviour
  as a hidden compatibility path without deprecation or a compatibility wrapper.

## Proposed API Shape

Names are provisional:

```python
from cady.files import dxf
from cady.ops.linesplan import classify_linesplan_curves, mesh_linesplan_network

wireframe = dxf.read_wireframe(path)
network = classify_linesplan_curves(wireframe, tolerance=1e-3)
mesh = mesh_linesplan_network(network, tolerance=1e-3)
```

For rendering:

```python
scene = Scene().add(mesh, name="surface").add(wireframe, name="source_wires")
```

## Done Criteria

- DXF import tests show DXF line geometry imports as wire/curve data, not hidden
  generated mesh data.
- Existing mesh import of real `3DFACE` entities still works.
- Linesplan conversion is called explicitly from a wireframe/curve-network API.
- The linesplan mesh has no source-wire-only edges inside `Mesh3D.edges`.
- Tests verify that classified sections, waterlines, buttocks, and knuckles are
  either used as surface constraints or reported as rejected with reasons.
- `examples/linesplan/mesh-boundary.py` is replaced or rewritten so its name and
  data flow match the new API.

## Implementation Notes

- The first native mesher is a conservative sampled section loft over classified
  `SECTIONS`.
- `BUTTOCKS`, `WATERLINES`, and `Knuckle` curves are classified and reported in
  compatibility diagnostics, but are not yet enforced as Gordon-style surface
  constraints.
- No new runtime dependency was added.
