# pyseas-cad Stage 6 v1 Product Hardening Plan

> **For agentic workers:** Refine this draft with `writing-plans` after Stage 5
> STEP MVP is implemented.

**Goal:** Prepare pyseas-cad v1 for real adoption.

**Status:** draft

## Draft Task Headings

1. Audit README, examples, gallery files, and planning docs for stale guidance.
2. Add or update gallery regeneration workflow.
3. Build the viewer/checker compatibility matrix.
4. Review packaging metadata, versioning, and runtime dependency guarantees.
5. Add pyseas-yard integration notes or adapter sketch.
6. Split post-v1 backlog into explicit candidate specs.
7. Run full gates and fill Stage 6 post-implementation review.

## Draft Acceptance Commands

- `.venv/bin/pytest -q`
- `.venv/bin/pyright src/cad`
- `.venv/bin/ruff check src/cad tests examples/scripts`
- `.venv/bin/python -c "import importlib.metadata as m; assert (m.distribution('pyseas-cad').requires or []) == []"`
