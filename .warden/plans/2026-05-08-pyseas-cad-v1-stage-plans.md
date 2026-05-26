# cady v1 Stage Plans

> **For agentic workers:** This is the cross-stage execution map for the v1
> roadmap. Do not execute it as a single implementation plan. For each stage,
> first create or refine that stage's design spec, then create a dedicated
> TDD implementation plan under `.warden/plans/`.

**Goal:** Reach cady v1: one domain-neutral model that exports practical
DXF drawings, STL previews, and basic viewer-loadable STEP files.

**Architecture:** Stage 2 introduces the model layer that all later exporters
consume. Stages 3-4 complete practical DXF. Stage 4.6 hardens DXF writer
orchestration before Stage 5 adds STEP. Stage 6 turns the result into a v1
product.

**Tech Stack:** Python 3.11+, stdlib runtime, pytest, pyright strict via
`pyproject.toml`, ruff, ezdxf for DXF verification.

**Recommended Skills:** system-designing, writing-plans, test-driven-development,
python, reviewer, verification-before-completion, writing, git

**Recommended MCPs:** none

**Status:** draft
**Refinement passes:** 0

## Controlling Documents

- Roadmap: `.warden/specs/2026-05-08-cady-v1-roadmap.md`
- Implemented Stage 1 spec:
  `.warden/specs/2026-05-08-cady-stage-1-design.md`
- Existing Stage 1 plan:
  `.warden/plans/2026-05-08-cady-stage-1.md`

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
`.warden/specs/2026-05-08-cady-stage-2-model-design.md`.

**Design Spec To Create:**

- `.warden/specs/2026-05-08-cady-stage-2-model-design.md`

**Implementation Plan To Create After Spec Approval:**

- `.warden/plans/2026-05-08-cady-stage-2-model.md`

**Major Work Units:**

1. Design `cady.model` API contract:
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
- `pyright src/cady`
- `ruff check src/cady tests`
- `python -c "import importlib.metadata as m; assert (m.distribution('cady').requires or []) == []"`

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
`.warden/specs/2026-05-08-cady-stage-3-dxf-production-design.md`.

**Design Spec To Create:**

- `.warden/specs/2026-05-08-cady-stage-3-dxf-production-design.md`

**Implementation Plan To Create After Spec Approval:**

- `.warden/plans/2026-05-08-cady-stage-3-dxf-production.md`

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
- `pyright src/cady`
- `ruff check src/cady tests`

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

**Status:** implemented 2026-05-11. Linear, aligned, radius, and diameter
dimensions now emit native editable DXF `DIMENSION` entities; angular dimensions
are deferred.

**Purpose:** Add the drawing features that make generated DXF useful as an
engineering drawing rather than just geometry.

**Design Spec To Create:**

- `.warden/specs/2026-05-08-cady-stage-4-dimensions-design.md`

**Implementation Plan To Create After Spec Approval:**

- `.warden/plans/2026-05-08-cady-stage-4-dimensions.md`

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
- `pyright src/cady`
- `ruff check src/cady tests`

**End Gate:**

- Update README with dimension example and compatibility notes.
- Update `IDEAS.md` with dimension strategy decision.
- Update preference locks for dimension strategy and helper APIs.
- Fill Stage 4 post-implementation review.
- Create/refine Stage 4.6 DXF writer hardening spec and plan.

**Exit Criteria:**

- A pyseas-yard-style 2D drawing can be expressed through model APIs without raw
  DXF calls.
- Dimension limitations are explicit and tested.

## Stage 4.6 Plan — DXF Writer Hardening

**Purpose:** Make DXF writer shared state explicit before STEP work starts.

**Design Spec To Create:**

- `.warden/specs/2026-05-11-cady-stage-4-6-dxf-writer-hardening-design.md`

**Implementation Plan To Create After Spec Approval:**

- `.warden/plans/2026-05-11-cady-stage-4-6-dxf-writer-hardening.md`

**Major Work Units:**

1. Test native dimension block reference consistency.
2. Add a small `DxfRenderPlan`/context.
3. Pass that plan into DXF section emitters that need shared state.
4. Preserve public APIs and gallery behavior.
5. Run full gates.

**Exit Criteria:**

- DXF output remains valid and native dimensions remain editable.
- Shared writer state is allocated once per render.

## Stage 5 Plan — STEP MVP

**Purpose:** Produce basic viewer-loadable STEP from model parts. Do not bundle
general product polish into this stage.

**Design Spec To Create:**

- `.warden/specs/2026-05-08-cady-stage-5-step-v1-design.md`

**Implementation Plan To Create After Spec Approval:**

- `.warden/plans/2026-05-08-cady-stage-5-step-v1.md`

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
7. Add one gallery STEP artifact.
8. Record initial viewer/checker notes.
9. Update Stage 6 hardening plan from what actually shipped.

**Acceptance Commands:**

- `pytest tests/write -q -k step`
- `pytest tests/examples -q`
- `pytest -q`
- `pyright src/cady`
- `ruff check src/cady tests`
- Manual or scripted viewer smoke check recorded in spec post-implementation
  review.

**End Gate:**

- Update README with STEP MVP support and limitations.
- Update preference locks for STEP scope and limitations.
- Fill Stage 5 post-implementation review.
- Refine Stage 6 v1 product-hardening spec/plan.

**Exit Criteria:**

- A user can call `Model(...).write_step(path)` and load the result in at
  least one accessible STEP viewer.
- DXF and STL examples still pass.
- STEP MVP limitations are honest and visible.

## Stage 6 Plan — v1 Product Hardening

**Purpose:** Make cady adoptable after the core exporters exist.

**Design Spec To Create:**

- `.warden/specs/2026-05-11-cady-stage-6-v1-product-hardening-design.md`

**Implementation Plan To Create After Spec Approval:**

- `.warden/plans/2026-05-11-cady-stage-6-v1-product-hardening.md`

**Major Work Units:**

1. Audit and update README/API docs.
2. Add a gallery index and regeneration workflow.
3. Build DXF/STL/STEP compatibility matrix.
4. Review package metadata, versioning, and dependency guarantees.
5. Add pyseas-yard integration notes.
6. Split the post-v1 backlog into clear candidate specs.

**Exit Criteria:**

- A fresh user can install, run examples, inspect artifacts, and understand
  limitations from README and examples alone.
- v1 is ready to tag/release or consciously defer.

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
