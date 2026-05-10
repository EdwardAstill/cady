# pyseas-cad Stage 4 - Dimensions and Drawing Helpers

**Status:** draft.
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
- Dimension output opens through `ezdxf.readfile()` and audits without errors or
  has explicit documented viewer limitations.
- Existing Stage 1, Stage 2, and Stage 3 tests keep passing.
- README documents dimension support and limitations.

## Non-Goals

- STEP output.
- Full GD&T.
- Sheet/title-block layout.
- General TRIM/split/intersection editing unless required for dimension helper
  placement.
