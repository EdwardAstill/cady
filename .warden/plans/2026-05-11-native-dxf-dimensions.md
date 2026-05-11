# Native DXF Dimensions Plan

**Status:** implemented.
**Date:** 2026-05-11.

## Goal

Replace Stage 4 self-rendered dimensions with native editable DXF `DIMENSION`
entities while preserving the existing scene/model dimension API.

## Plan

1. Generate local ezdxf reference DXFs for linear, aligned, radius, and diameter
   dimensions.
2. Test-drive native output expectations:
   - writer emits `DIMENSION` records and `DIMSTYLE`,
   - ezdxf round-trip sees four dimension entities,
   - production gallery uses native dimensions.
3. Implement native dimension serialization in the pure-stdlib DXF writer.
4. Regenerate `examples/gallery/production_plate.dxf`.
5. Update docs and preference locks.
6. Run full gates and merge.

## Strategy

Emit compact native `DIMENSION` entities with anonymous `*D...` geometry blocks.
The blocks are intentionally empty; they satisfy DXF audit requirements while
leaving visual regeneration to CAD viewers. The old primitive `LINE`/`MTEXT`
dimension rendering is removed from the default writer path.

## Verification

- `PYTHONPATH=src .venv/bin/pytest -q` -> 102 passed, 70 dependency warnings.
- `PYTHONPATH=src .venv/bin/ruff check src/cad tests examples/scripts` -> pass.
- `PYTHONPATH=src .venv/bin/pyright src/cad` -> 0 errors, 0 warnings.
- `PYTHONPATH=src .venv/bin/python -c "import importlib.metadata as m; assert (m.distribution('pyseas-cad').requires or []) == []"` -> pass.
