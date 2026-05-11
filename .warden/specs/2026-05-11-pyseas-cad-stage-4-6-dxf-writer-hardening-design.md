# pyseas-cad Stage 4.6 - DXF Writer Hardening

**Status:** draft.
**Date:** 2026-05-11.
**Purpose:** Stabilize DXF writer orchestration before STEP work starts.

## Goal

Make shared DXF writer state explicit and deterministic without changing the
public scene/model API.

## Scope

- Introduce a render plan/context for one DXF document render.
- Allocate native-dimension anonymous block names once in that plan.
- Pass the plan into `TABLES`, `BLOCKS`, and `ENTITIES` emitters where shared
  state is required.
- Keep direct `DxfDrawing` and model-first `Model.write_dxf` APIs unchanged.
- Preserve existing output behavior unless tests intentionally update a golden
  or gallery artifact.

## Non-Goals

- No STEP implementation.
- No universal writer abstraction across DXF/STL/STEP.
- No public API rename.
- No visual redesign of examples.

## Acceptance Draft

- A test proves every native DXF `DIMENSION` block reference exists in the
  `BLOCKS` section.
- `examples/gallery/production_plate.dxf` still audits with zero ezdxf errors
  and contains four native dimensions.
- `.venv/bin/pytest -q` passes.
- `.venv/bin/pyright src/cad` passes.
- `.venv/bin/ruff check src/cad tests examples/scripts` passes.

## Design Contract

The writer builds a single immutable render plan before emitting sections:

```python
@dataclass(frozen=True)
class DxfRenderPlan:
    layers: tuple[Layer, ...]
    dimension_block_names: tuple[str, ...]
    uses_dimstyle: bool
```

Section emitters consume that plan instead of recomputing shared names.
