# pyseas-cad Stage 5 STEP MVP Implementation Plan

> **For agentic workers:** Refine this draft with `writing-plans` after the
> Stage 5 design spec is approved.

**Goal:** Implement a conservative pure-stdlib STEP writer for the model layer.

**Architecture:** Add `cad.write.step` alongside the existing DXF/STL writers.
Keep the public entry point as `Model.write_step(path)` and translate the
existing descriptive solids into a limited STEP representation.

**Tech Stack:** Python 3.11+, pure-stdlib runtime, pytest, pyright, ruff, any
viewer/checker tools available locally.

**Status:** draft

## Draft Task Headings

1. Decide exact STEP schema/profile and file structure.
2. Add STEP writer skeleton and product/part header sections.
3. Implement one extrusion/prism path end-to-end.
4. Add model-level STEP aggregation and error handling.
5. Add tests and one gallery STEP product.
6. Document supported/unsupported solids and verification limitations.
7. Refine Stage 6 product-hardening artifacts from what actually shipped.
8. Run full gates and fill the Stage 5 post-implementation review.

## Draft Acceptance Commands

- `.venv/bin/pytest tests/write -q -k step`
- `.venv/bin/pytest tests/model -q -k step`
- `.venv/bin/pytest -q`
- `.venv/bin/pyright src/cad`
- `.venv/bin/ruff check src/cad tests examples/scripts`
- `.venv/bin/python -c "import importlib.metadata as m; assert (m.distribution('pyseas-cad').requires or []) == []"`
