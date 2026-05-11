# pyseas-cad Stage 4 Dimensions Implementation Plan

> **For agentic workers:** This draft must be refined with `writing-plans` after the Stage 4 design spec is approved.

**Goal:** Add model-first DXF dimensions and helper geometry for practical engineering drawings.

**Architecture:** Build dimensions on top of the Stage 3 drawing model: layers, linetypes, hatch, blocks, and inserts. Keep geometry helpers format-blind in `cad.geom` only when they are useful outside DXF.

**Tech Stack:** Python 3.11+, pure-stdlib runtime, pytest, pyright, ruff, ezdxf.

**Recommended Skills:** system-designing, writing-plans, test-driven-development, python, reviewer, verification-before-completion

**Recommended MCPs:** none

**Status:** implemented
**Refinement passes:** 1

## Draft Task Headings

1. Decide dimension strategy and compatibility contract.
2. Add helper geometry tests and implementation for midpoint/perpendicular.
3. Add linear dimension scene API.
4. Emit linear dimension DXF through the chosen strategy.
5. Add aligned dimension support.
6. Add radial or diameter dimension support.
7. Add hatch holes/islands for profiles with `inner_loops`.
8. Add model-first dimension example.
9. Update README, preference locks, and Stage 4.6 DXF hardening planning artifacts.

## Implementation Result

- Implemented linear, aligned, radius, and diameter dimensions. Stage 4.5 then
  replaced the primitive renderer with native editable DXF `DIMENSION` output.
- Implemented one-level HATCH holes/islands for shapes with `inner_loops`.
- Added small geometry helpers for midpoint, perpendicular normal, and
  perpendicular offset points.
- Updated the production DXF example and regenerated the gallery DXF.
- Deferred angular dimensions.

## Draft Acceptance Commands

- `.venv/bin/pytest tests/write -q -k dimension`
- `.venv/bin/pytest tests/geom -q -k helpers`
- `.venv/bin/pytest tests/examples -q`
- `.venv/bin/pytest -q`
- `.venv/bin/pyright src/cad`
- `.venv/bin/ruff check src/cad tests`
