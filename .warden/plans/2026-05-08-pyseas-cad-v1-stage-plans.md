# pyseas-cad v1 Stage Plans

> **For agentic workers:** This is the cross-stage execution map for the v1
> roadmap. Do not execute it as a single implementation plan. For each stage,
> first create or refine that stage's design spec, then create a dedicated
> TDD implementation plan under `.warden/plans/`.

**Goal:** Reach pyseas-cad v1: one domain-neutral model that exports practical
DXF drawings, STL previews, and basic viewer-loadable STEP files.

**Architecture:** Stage 2 introduces the model layer that all later exporters
consume. Stages 3-5 build output capability on that model instead of growing
separate writer-specific scene APIs.

**Tech Stack:** Python 3.11+, stdlib runtime, pytest, pyright strict via
`pyproject.toml`, ruff, ezdxf for DXF verification.

**Recommended Skills:** system-designing, writing-plans, test-driven-development,
python, reviewer, verification-before-completion, writing, git

**Recommended MCPs:** none

**Status:** draft
**Refinement passes:** 0

## Controlling Documents

- Roadmap: `.warden/specs/2026-05-08-pyseas-cad-v1-roadmap.md`
- Implemented Stage 1 spec:
  `.warden/specs/2026-05-08-pyseas-cad-stage-1-design.md`
- Existing Stage 1 plan:
  `.warden/plans/2026-05-08-pyseas-cad-stage-1.md`

## Global Assumptions

- `A1` — v1 should optimize for pyseas-yard-style plate/pin/bolt/weld drawing
  and review workflows, not a general CAD kernel.
  Type: design
  Source: v1 roadmap end goal
  Check: stage specs reject general booleans, fillets, sweeps, NURBS, and STEP
  parsing unless separately approved.
  If false: rewrite roadmap before Stage 2.
  Owner: every stage spec.

- `A2` — runtime remains pure stdlib.
  Type: policy
  Source: Stage 1 acceptance and v1 roadmap product principles
  Check: `pytest tests/conventions/test_stdlib_only.py -q` and package metadata
  dependency check.
  If false: record explicit decision in preference lock and README.
  Owner: every implementation plan.

- `A3` — the model layer is the preferred v1 API, while direct `DxfDrawing`
  and `StlMesh` APIs remain supported for simple use.
  Type: architectural
  Source: v1 roadmap architecture decision
  Check: Stage 2 tests prove both direct and model facade APIs work.
  If false: re-plan Stage 3-5 around writer-specific scenes.
  Owner: Stage 2.

---

## Stage 2 Plan — Model Layer

**Purpose:** Create the single source model that future DXF/STL/STEP exporters
consume.

**Status:** implemented on branch `stage-2-model`; see
`.warden/specs/2026-05-08-pyseas-cad-stage-2-model-design.md`.

**Design Spec To Create:**

- `.warden/specs/2026-05-08-pyseas-cad-stage-2-model-design.md`

**Implementation Plan To Create After Spec Approval:**

- `.warden/plans/2026-05-08-pyseas-cad-stage-2-model.md`

**Major Work Units:**

1. Design `cad.model` API contract:
   - `Model`
   - `Drawing2D`
   - model `Layer` or wrapper around existing scene layer
   - `Part`
   - `Assembly` if needed
   - metadata and stable timestamp handling
2. Add tests for model construction and shape ownership.
3. Implement model drawing layer facade over existing `DxfDrawing`.
4. Implement model part facade over existing `StlMesh`.
5. Add `Model.write_dxf(path)` and `Model.write_stl(path)`.
6. Add a reserved `Model.write_step(path)` failure mode or placeholder that
   clearly states STEP arrives in Stage 5.
7. Update examples to show the model-first API.
8. Keep direct Stage 1 APIs working.

**Acceptance Commands:**

- `pytest tests/model tests/examples tests/write tests/scene -q`
- `pytest -q`
- `pyright src/cad`
- `ruff check src/cad tests`
- `python -c "import importlib.metadata as m; assert (m.distribution('pyseas-cad').requires or []) == []"`

**End Gate:**

- Update `README.md` with model-first quickstart.
- Update `IDEAS.md` if API direction changes.
- Update `.warden/preference-lock.json` with model API decisions.
- Fill Stage 2 post-implementation review.
- Create/refine Stage 3 DXF spec and plan.

**Exit Criteria:**

- A user can build one `Model` and write valid DXF and STL from it.
- Existing direct `DxfDrawing` and `StlMesh` code still works.

## Stage 3 Plan — Production DXF

**Purpose:** Make 2D drawings rich enough for practical review/manufacturing
outputs before tackling dimensions or STEP.

**Status:** implemented on branch `stage-3-dxf-plan`; see
`.warden/specs/2026-05-08-pyseas-cad-stage-3-dxf-production-design.md`.

**Design Spec To Create:**

- `.warden/specs/2026-05-08-pyseas-cad-stage-3-dxf-production-design.md`

**Implementation Plan To Create After Spec Approval:**

- `.warden/plans/2026-05-08-pyseas-cad-stage-3-dxf-production.md`

**Major Work Units:**

1. Decide public API for hatches:
   - scene-level versus layer-level call
   - hatch tied to a closed `Shape2D`
   - ANSI31 minimum pattern
2. Implement DXF `HATCH` entity emission.
3. Add model-first hatch examples.
4. Decide block API:
   - block definition ownership
   - insertion point
   - scale/rotation
   - layer behavior
5. Implement DXF `BLOCKS` section with named block definitions.
6. Implement `INSERT` entity emission.
7. Add linetype table support where needed.
8. Add reusable symbol examples.
9. Add golden and ezdxf behavioral tests.

**Acceptance Commands:**

- `pytest tests/write -q -k dxf`
- `pytest tests/model tests/examples -q`
- `pytest -q`
- `pyright src/cad`
- `ruff check src/cad tests`

**End Gate:**

- Update README with production DXF example.
- Update `IDEAS.md` to mark Stage 3 direction complete/current.
- Update preference locks for HATCH/BLOCK/INSERT API decisions.
- Fill Stage 3 post-implementation review.
- Create/refine Stage 4 dimensions spec and plan.

**Exit Criteria:**

- A model-first example emits DXF containing outline, text, hatch, and inserted
  reusable symbol.
- Output opens through `ezdxf.readfile()` and passes audit checks.

## Stage 4 Plan — Dimensions and Drawing Helpers

**Purpose:** Add the drawing features that make generated DXF useful as an
engineering drawing rather than just geometry.

**Design Spec To Create:**

- `.warden/specs/2026-05-08-pyseas-cad-stage-4-dimensions-design.md`

**Implementation Plan To Create After Spec Approval:**

- `.warden/plans/2026-05-08-pyseas-cad-stage-4-dimensions.md`

**Major Work Units:**

1. Decide dimension strategy:
   - self-rendered dimension blocks
   - anonymous/regenerated dimensions
   - explicit compatibility limitations
2. Implement linear dimensions.
3. Implement aligned dimensions.
4. Implement radial/diameter dimensions.
5. Implement angular dimensions if still inside v1 scope.
6. Add geometry helpers dimensions need:
   - midpoint
   - perpendicular
   - offset basics only if justified
7. Add model-first drawing example with dimensions.
8. Add visual/viewer smoke instructions.

**Acceptance Commands:**

- `pytest tests/write -q -k dimension`
- `pytest tests/geom -q -k helpers`
- `pytest tests/examples -q`
- `pytest -q`
- `pyright src/cad`
- `ruff check src/cad tests`

**End Gate:**

- Update README with dimension example and compatibility notes.
- Update `IDEAS.md` with dimension strategy decision.
- Update preference locks for dimension strategy and helper APIs.
- Fill Stage 4 post-implementation review.
- Create/refine Stage 5 STEP spec and plan.

**Exit Criteria:**

- A pyseas-yard-style 2D drawing can be expressed through model APIs without raw
  DXF calls.
- Dimension limitations are explicit and tested.

## Stage 5 Plan — STEP MVP and v1 Hardening

**Purpose:** Produce basic viewer-loadable STEP from model parts and finish v1
as a usable product.

**Design Spec To Create:**

- `.warden/specs/2026-05-08-pyseas-cad-stage-5-step-v1-design.md`

**Implementation Plan To Create After Spec Approval:**

- `.warden/plans/2026-05-08-pyseas-cad-stage-5-step-v1.md`

**Major Work Units:**

1. Decide STEP schema target:
   - AP242 preferred if feasible
   - AP214/AP203 fallback if viewer compatibility is better
2. Define internal STEP entity builder:
   - stable ID allocation
   - header metadata
   - product/part naming from `Model`
   - unit context
3. Implement STEP for rectangular prisms/boxes.
4. Implement STEP for simple extrusions.
5. Implement cylinders/revolutions if bounded enough for v1.
6. Decide and implement first hole strategy:
   - analytic circular-hole topology for common extruded plate case, or
   - documented multi-body/visual review limitation.
7. Add viewer smoke artifacts/examples.
8. Build compatibility matrix:
   - online STEP viewer
   - local viewer if available
   - parser/viewer notes
9. Harden packaging/docs for v1.

**Acceptance Commands:**

- `pytest tests/write -q -k step`
- `pytest tests/examples -q`
- `pytest -q`
- `pyright src/cad`
- `ruff check src/cad tests`
- Manual or scripted viewer smoke check recorded in spec post-implementation
  review.

**End Gate:**

- Update README as v1 documentation.
- Remove stale roadmap guidance from `IDEAS.md`.
- Update preference locks for STEP scope and limitations.
- Fill Stage 5 post-implementation review.
- Create post-v1 backlog spec if needed.

**Exit Criteria:**

- A user can call `Model(...).write_step(path)` and load the result in at
  least one accessible STEP viewer.
- DXF and STL examples still pass.
- v1 limitations are honest and visible.

## Cross-Stage Documentation Rule

No stage may be marked done until the next stage's design and plan have been
reviewed against what actually shipped. This prevents later plans from drifting
away from the real code.

At the end of each stage:

- If shipped API differs from the prior plan, update all downstream stage
  plans that mention that API.
- If a scope item is deferred, move it into the post-v1 backlog or the next
  stage explicitly.
- If a viewer/parser assumption failed, record it in the completed spec's
  Known Limitations and revise the next stage acceptance checks.
