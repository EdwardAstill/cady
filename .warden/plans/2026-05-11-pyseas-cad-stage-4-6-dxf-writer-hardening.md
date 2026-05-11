# pyseas-cad Stage 4.6 DXF Writer Hardening Plan

> **For agentic workers:** Refine this draft with `writing-plans` before
> execution.

**Goal:** Make DXF writer shared state explicit before STEP MVP work.

**Architecture:** Add a small DXF render plan/context local to `cad.write.dxf`.
Do not introduce a cross-format writer framework.

**Status:** draft

## Draft Task Headings

1. Add a failing test for dimension block reference consistency.
2. Add `DxfRenderPlan` with dimension block name allocation.
3. Update `document.py`, `blocks.py`, `tables.py`, and `dimensions.py` to
   consume the plan where needed.
4. Regenerate any changed DXF gallery/golden artifacts.
5. Update docs/preference lock if the internal writer contract changes.
6. Run full gates and fill the Stage 4.6 post-implementation review.

## Draft Acceptance Commands

- `.venv/bin/pytest tests/write -q -k dimension`
- `.venv/bin/pytest tests/examples/test_production_dxf.py -q`
- `.venv/bin/pytest -q`
- `.venv/bin/pyright src/cad`
- `.venv/bin/ruff check src/cad tests examples/scripts`
