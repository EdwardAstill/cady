# cady Stage 4 - Dimensions and Drawing Helpers

**Status:** implemented.
**Date:** 2026-05-11.
**Purpose:** Design dimension output and helper geometry after Stage 3 production
DXF support.

## Goal

Add enough dimension output and construction helpers for practical 2D
engineering drawings through the model-first API.

## Scope

- Dimension strategy decision: self-rendered dimension blocks versus
  CAD-regenerated dimension entities.
- Linear and aligned dimensions.
- Radial or diameter dimensions.
- Angular dimensions if the chosen strategy remains small enough.
- Hatch holes/islands for profiles with `inner_loops`, so section hatching does
  not run through holes in production drawings.
- Helper geometry needed by dimensions: midpoint, perpendicular, and offset
  basics where justified.
- Example drawing combining outline, holes, hatch, reusable symbols, text, and
  dimensions.

## Inputs From Stage 3

- `Drawing2D.layer(...).hatch(...)` emits ANSI31 HATCH.
- `Drawing2D.block(...)` and `Drawing2D.insert(...)` support reusable symbols.
- Built-in `CENTER` and `HIDDEN` linetypes are available.
- `Model.write_dxf` aggregates named drawings into one DXF modelspace.

## Acceptance Draft

- A model-first drawing can express at least one linear dimension and one radial
  or diameter dimension without raw DXF calls.
- Dimension output opens through `ezdxf.readfile()` and audits without errors.
- HATCH output preserves one-level profile holes/islands.
- Existing Stage 1, Stage 2, and Stage 3 tests keep passing.
- README documents dimension support and limitations.

## Non-Goals

- STEP output.
- Full GD&T.
- Sheet/title-block layout.
- General TRIM/split/intersection editing unless required for dimension helper
  placement.
- Angular dimensions.

## Post-Implementation Review

Filled 2026-05-11.

- Shipped API:
  - `DxfDrawing.linear_dimension(...)` and `Drawing2D.linear_dimension(...)`.
  - `DxfDrawing.aligned_dimension(...)` and `Drawing2D.aligned_dimension(...)`.
  - `DxfDrawing.radius_dimension(...)` / `diameter_dimension(...)` plus model
    equivalents.
  - `cady.geom.helpers.midpoint`, `perpendicular`, and `offset_point`.
- Strategy decision:
  - Stage 4 initially used self-rendered `LINE`/`MTEXT` dimensions.
  - Stage 4.5 replaced that renderer with native DXF `DIMENSION` entities and
    compact anonymous geometry blocks.
- Scope update from the original draft:
  - Added hatch holes/islands because the Stage 3 production plate visual showed
    hatching through holes.
  - Angular dimensions remain deferred.
- Verification results:
  - Focused Stage 4 tests:
    `tests/geom/test_helpers.py`, `tests/write/test_dxf_dimensions.py`, hatch
    hole test, model dimension preservation test, and production example test.
  - `PYTHONPATH=src .venv/bin/pytest -q` -> 102 passed, 70 dependency warnings
    after the native-dimension follow-up.
  - `PYTHONPATH=src .venv/bin/ruff check src/cady tests examples/scripts` -> pass.
  - `PYTHONPATH=src .venv/bin/pyright src/cady` -> 0 errors, 0 warnings.
  - `PYTHONPATH=src .venv/bin/python -c "import importlib.metadata as m; assert (m.distribution('cady').requires or []) == []"` -> pass.
