# pyseas-cad Stage 3 - Production DXF

**Status:** draft.
**Date:** 2026-05-11.
**Purpose:** Design the next DXF capability layer after Stage 2 `Model`.

## Goal

Make generated 2D drawings useful for pyseas-yard-style review and fabrication
output by adding production DXF entities to the existing model-first API.

Stage 3 builds on:

```python
model = Model("drawing")
front = model.drawing("front")
front.layer("PLATE").add(profile)
model.write_dxf("drawing.dxf")
```

## Scope

- `HATCH`, with ANSI31 minimum.
- `BLOCK` definitions and `INSERT` references.
- Linetype table support beyond `CONTINUOUS` where needed for hidden and center
  lines.
- Model-first examples for hatching and inserted reusable symbols.
- Golden and `ezdxf` audit tests.

## Deferred

- Full dimension engine remains Stage 4 unless Stage 3 design proves a small
  self-rendered subset is necessary for symbol work.
- STEP remains Stage 5.
- Sheet/title-block composition remains outside core unless separately approved.

## Design Questions

- Hatch API location: `Drawing2D.hatch(...)`, `ModelLayer.hatch(...)`, or
  lower-level `DxfDrawing` first with model facade delegation.
- Hatch boundary representation: closed `Shape2D` only, or explicit boundary
  loops.
- Block ownership: model-wide, drawing-wide, or direct `DxfDrawing` ownership.
- Insert layer behavior: insertion layer only, definition layer preservation, or
  both.
- Linetype API: layer attribute update versus explicit table registration.

## Acceptance Draft

- `Model(...).drawing(...).hatch(...)` or chosen equivalent emits readable DXF
  with expected `HATCH` entity.
- A reusable symbol can be defined once and inserted at least twice.
- `ezdxf.readfile(path).audit()` reports no errors on hatch/block smoke files.
- Existing Stage 1 direct scene APIs and Stage 2 `Model` APIs keep passing.
- README shows one production-style drawing example.

## Post-Design Notes

To be filled when Stage 3 design is approved.
