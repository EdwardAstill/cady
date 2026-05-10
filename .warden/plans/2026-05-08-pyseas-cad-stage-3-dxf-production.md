# pyseas-cad Stage 3 Production DXF Implementation Plan

> **For agentic workers:** This is a draft stub created at Stage 2 closeout. Refine it with `writing-plans` after the Stage 3 design spec is approved.

**Goal:** Add HATCH, BLOCK, INSERT, and linetype support to DXF output through the model-first API.

**Architecture:** Extend the existing Stage 1 `DxfDrawing`/writer path first, then expose the same capability through `Drawing2D` and `ModelLayer` as appropriate. Keep `Model.write_dxf` as the final export facade.

**Tech Stack:** Python 3.11+, stdlib runtime, pytest, pyright, ruff, ezdxf.

**Recommended Skills:** system-designing, writing-plans, test-driven-development, python, reviewer, verification-before-completion

**Recommended MCPs:** none

**Status:** draft
**Refinement passes:** 0

## Draft Task Headings

1. Design and test hatch API contract.
2. Implement minimal ANSI31 `HATCH` entity emission.
3. Add model-first hatch facade and example.
4. Design and test block definition ownership.
5. Implement `BLOCKS` section emission and `INSERT` entities.
6. Add linetype table support for hidden/center lines.
7. Add reusable symbol examples.
8. Add golden DXF and `ezdxf` audit tests.
9. Update README, preference locks, and Stage 4 dimension spec/plan.

## Draft Acceptance Commands

- `pytest tests/write -q -k dxf`
- `pytest tests/model tests/examples -q`
- `pytest -q`
- `pyright src/cad`
- `ruff check src/cad tests`
