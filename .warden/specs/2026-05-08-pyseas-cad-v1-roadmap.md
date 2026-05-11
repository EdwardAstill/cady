# pyseas-cad v1 Roadmap

**Status:** roadmap contract.
**Date:** 2026-05-08.
**Purpose:** Keep implementation pointed at the best end goal: a useful,
domain-blind CAD output library that pyseas-yard can use to generate 2D
drawings, 3D previews, and basic interchange files from one source model.

## End Goal

pyseas-cad v1 is complete when a caller can build one domain-neutral CAD model
and export the useful manufacturing/review artifacts from it:

```python
from cad import Model, rectangle, circle

plate = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))

model = Model("padeye_plate")
model.drawing("front").layer("PLATE").add(plate)
model.part("plate").add(plate.extrude("+z", 0.04))

model.write_dxf("padeye_plate.dxf")
model.write_stl("padeye_plate.stl")
model.write_step("padeye_plate.step")
```

v1 does not need to be a full CAD kernel. It needs to be reliable for
pyseas-yard-style parts: plates, holes, cheeks, pins, bolts, weld symbols,
dimensions, basic extrusions/revolutions, and viewer-loadable 3D output.

## Product Principles

- **One source model, many exporters.** DXF, STL, STEP, and future SVG should
  export from the same organized model instead of each writer inventing its own
  scene structure.
- **Keep `geom` immutable and format-blind.** The model layer organizes names,
  parts, drawings, layers, assemblies, metadata, and output intent; it does not
  replace the primitive geometry layer.
- **Domain-blind core.** pyseas-cad never learns `Padeye`, `Shackle`, or other
  lifting-gear vocabulary. Recipes live in pyseas-yard or examples.
- **Pure-stdlib runtime.** Dev/test tools may use external packages; shipped
  runtime code does not.
- **Write-only.** No DXF/STL/STEP parser in v1.
- **Viewer-proven output.** Every export format gets at least one smoke example
  that loads in a common viewer or validating library.
- **Documentation is part of each stage.** A stage is not complete until docs
  and downstream plans are updated.

## Stage Plan

### Stage 1 — Foundation: Geometry, DXF Basics, STL

**Status:** implemented.

Delivered:

- Immutable 2D/3D geometry families.
- DXF writer for `LINE`, `LWPOLYLINE`, `CIRCLE`, `ARC`, `MTEXT`.
- STL binary and ASCII writer.
- End-to-end plate-with-hole example.
- Acceptance tests and post-implementation review.

### Stage 2 — Model Layer

**Goal:** Add the organizing layer that makes later exporters coherent.

Deliverables:

- `cad.model` package.
- `Model`, `Drawing2D`, `Part`, `Assembly` or equivalent names.
- Named drawings with layers.
- Named 3D parts containing `Shape3D` values.
- Metadata: name, units, author/source, creation timestamp override for stable
  tests.
- Export facade methods: `write_dxf`, `write_stl`, future-reserved
  `write_step`.
- JSON debug/export representation if it helps tests, but not as a primary
  public file format unless separately specified.

Why this stage comes before more DXF or STEP:

- DXF needs drawings/layers/blocks.
- STEP needs product/part/assembly names.
- STL needs solids grouped by part.
- pyseas-yard should build one model, not three separate output scenes.

Acceptance:

- Existing Stage 1 `DxfDrawing` and `StlMesh` APIs continue to work.
- `Model(...).drawing(...).layer(...).add(shape2d).write_dxf(path)` emits the
  same valid DXF as the direct scene API.
- `Model(...).part(...).add(shape3d).write_stl(path)` emits the same valid STL
  as the direct scene API.
- `pytest`, `pyright`, and `ruff` pass.
- README and `IDEAS.md` are updated with the model-first API.
- Stage 3 spec/plan are updated from what Stage 2 actually shipped.

### Stage 3 — Production DXF

**Goal:** Make 2D drawings useful for pyseas-yard manufacturing/review output.

Deliverables:

- `HATCH`, with ANSI31 minimum.
- `BLOCK` definitions and `INSERT` references.
- Linetype support beyond `CONTINUOUS` where needed for hidden/center lines.
- Symbol examples: weld marker, bolt/shackle placeholder, reusable detail.
- DXF output from `Model` drawings.

Deferred out of Stage 3:

- Full dimension engine if it threatens schedule. Dimensions may become Stage 4
  if needed, but the roadmap should not let STEP start before drawing usability
  is addressed.

Acceptance:

- DXF smoke file opens in `ezdxf` and contains expected HATCH/BLOCK/INSERT
  entities.
- Golden tests cover a minimal drawing with hatch and inserted symbol.
- README examples include a production-style drawing.
- `IDEAS.md`, preference locks, and next-stage spec/plan are updated.

### Stage 4 — Dimensions and Drawing Helpers

**Status:** implemented 2026-05-11.

**Goal:** Add enough dimension output and construction helpers for practical 2D
engineering drawings.

Deliverables:

- Linear, aligned, radial/diameter, and angular dimensions, or a documented
  subset if viewer compatibility forces a smaller first pass.
- Decision: self-rendered dimension blocks versus anonymous CAD-regenerated
  dimensions.
- Helper functions that dimensions and recipes need: midpoint, perpendicular,
  offset basics where justified.
- Example drawing with outline, holes, hatching, symbols, text, and dimensions.

Acceptance:

- Dimension examples open in at least `ezdxf` and one visual viewer when
  available.
- pyseas-yard-style 2D drawing recipe can be expressed without raw DXF calls.
- Docs explain dimension compatibility limitations honestly.
- Stage 5 STEP spec/plan are updated.

### Stage 5 — STEP MVP and v1 Hardening

**Goal:** Produce viewer-loadable 3D interchange files from the model layer and
package pyseas-cad v1 as a usable library.

Deliverables:

- `cad.write.step` package.
- STEP writer for basic solids from `Model` parts:
  - prisms/boxes,
  - simple extrusions,
  - cylinders or revolutions where bounded,
  - named product/part structure.
- Initial holes strategy:
  - either analytic pre-cut topology for common circular holes in extruded
    plates,
  - or documented multi-body/visual-review-only output if analytic holes are
    too expensive.
- Viewer smoke files under `examples/` or `artifacts/`.
- Final README/API docs.
- Compatibility matrix for DXF/STL/STEP viewers tested.

Out of v1 unless separately approved:

- General boolean kernel.
- Fillets/blends.
- Sweep solids.
- NURBS surfaces.
- STEP GD&T.
- STEP parser.

Acceptance:

- `Model(...).write_step(path)` creates a `.step` file that loads in at least
  one accessible STEP viewer.
- Stage 1 STL and DXF examples still pass.
- Full test/type/lint suite passes.
- README documents install, quickstart, examples, and limitations.
- `IDEAS.md` no longer contains stale stage guidance.
- Post-v1 backlog is explicit and separated from v1 scope.

## Mandatory End-Of-Stage Gate

Every implementation stage must end with all of the following:

1. Run format-specific acceptance examples.
2. Run full `pytest -q`.
3. Run `pyright` in strict mode as configured by `pyproject.toml`.
4. Run `ruff check`.
5. Update `README.md`.
6. Update `IDEAS.md` if roadmap/product direction changed.
7. Update `.warden/preference-lock.json` if architecture decisions changed.
8. Fill the stage spec `Post-Implementation Review`.
9. Update or create the next stage spec.
10. Update or create the next stage plan.
11. Commit the implementation and documentation together.

## Architecture Decision

The optimal route is **model-first from Stage 2 onward**.

Rejected route: continue adding exporters directly to independent scene types
only (`DxfDrawing`, `StlMesh`, later `StepDocument`). That is quicker for one
format, but it makes pyseas-yard build multiple disconnected outputs and loses
part/assembly metadata that STEP needs.

Chosen route: keep direct scene APIs for simple use, but introduce `Model` as
the preferred v1 API and make exporters consume it.

## Post-v1 Backlog

- General boolean operations.
- TRIM/split/intersection editing tools.
- Sweep solids.
- Fillets/chamfers/blends.
- Sheet/title-block composition.
- SVG writer.
- R12 DXF fallback.
- STEP AP203 fallback or richer AP242 metadata.
