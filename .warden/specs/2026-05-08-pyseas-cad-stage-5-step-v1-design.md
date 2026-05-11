# pyseas-cad Stage 5 - STEP MVP and v1 Hardening

**Status:** draft.
**Date:** 2026-05-11.
**Purpose:** Design the first viewer-loadable STEP writer after Stage 4 drawing
usability.

## Goal

Produce basic STEP interchange files from the model layer while keeping the
runtime pure-stdlib and the geometry API domain-blind.

## Scope

- Decide schema target: AP242 preferred, AP214/AP203 fallback if simpler viewer
  compatibility wins.
- Write product/part structure for `Model` and named `Part` solids.
- Support a conservative first solid subset:
  - rectangular/prism solids,
  - simple linear extrusions,
  - bounded revolutions where representation stays manageable.
- Keep STL as the mesh preview/export path; STEP should carry editable CAD
  geometry where feasible.
- Add viewer/audit smoke checks that do not introduce runtime dependencies.

## Inputs From Stage 4

- `Model` is the preferred export facade.
- Drawing output is useful enough for DXF workflows.
- 3D geometry remains descriptive (`Extrusion`, `Revolution`, `Prism`), not a
  full boolean B-rep kernel.

## Acceptance Draft

- `Model.write_step(path)` writes a non-empty STEP file for at least one
  extrusion-based part.
- The generated STEP opens in at least one available local viewer/checker, or
  has an explicit documented verification fallback.
- Existing DXF and STL behavior remains unchanged.
- Runtime package metadata still has no dependencies.

## Non-Goals

- Full boolean kernel.
- Fillets, blends, swept surfaces, and NURBS.
- GD&T/product manufacturing information beyond minimal product structure.
- Replacing STL for mesh workflows.
