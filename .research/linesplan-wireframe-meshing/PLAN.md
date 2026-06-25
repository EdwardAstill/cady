# Research Plan: Linesplan Wireframe Meshing

**Goal:** Choose a defensible algorithm and implementation plan for converting
DXF linesplan wireframes into meshes without hiding format parsing inside mesh
generation.
**Pattern:** focused single-lane investigation
**Date:** 2026-06-25

## Phase 1: Algorithm Selection
**Stop when:** at least three credible sources identify the right algorithm
family or rule out nearby alternatives, and the local DXF structure is mapped
well enough to drive a repo plan.
**Dispatch:** local investigation, no subagents

### Lane: Curve-Network Surfacing For Linesplans
- **Where:** CAD/surfacing references for Gordon surfaces, curve-network
  interpolation, ruled surfaces, NURBS fitting, and mesh/surface generation
  tools.
- **What to find:** whether a linesplan with sections, buttocks, waterlines,
  and knuckles should be meshed as a loft, a ruled surface, a constrained
  triangulation, a point-cloud reconstruction, or a curve-network interpolation
  problem.

## Phase 2: Repo Plan
**Stop when:** `.plans/linesplan-wireframe-meshing/` contains a spec and
ordered task list with verification commands.

