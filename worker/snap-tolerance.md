# Mesh3D close_planar snap_tolerance implementation

## Summary

Added `snap_tolerance` parameter to `close_planar_cap` (ops) and
`Mesh3D.close_planar` (domain). When set, boundary vertices within
`snap_tolerance` of the plane (but outside `tolerance`) are projected onto
the plane. The cap uses projected copies while originals stay connected to the
body, creating thin gaps that `close_boundary` can fill.

## Changed files

| File | Change |
|------|--------|
| `src/cady/ops/mesh_cut.py` | +41 lines. `close_planar_cap` now accepts `snap_tolerance: float | None`. Added`_snapped_index` helper. |
| `src/cady/geometry3d/mesh.py` | +11 lines. `Mesh3D.close_planar` accepts and passes through `snap_tolerance`. |
| `tests/geometry3d/test_mesh_close.py` | +77 lines. 4 new tests. |

## Tests added

4 new tests in `tests/geometry3d/test_mesh_close.py`:

- `test_close_planar_snap_projects_nearby_boundary` — displaced boundary vertices get projected, cap faces added, originals preserved
- `test_close_planar_snap_creates_gaps_for_close_boundary` — snap-cap then `close_boundary` fills the resulting gaps without error
- `test_close_planar_snap_noop_when_all_on_plane` — snap_tolerance doesn't change behavior when boundary is already planar
- `test_close_planar_snap_rejects_negative` — ValueError for zero/negative snap_tolerance

All 15 test_mesh_close tests pass + 45 total geometry3d/numeric tests pass.

## Validation

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/test_mesh_close.py -v
# 15 passed

PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/ tests/numeric/test_mesh_cut.py -v
# 45 passed, no regressions

.venv/bin/pyright src/cady
# 0 errors, 0 warnings

.venv/bin/ruff check src/cady tests
# All checks passed
```

## Residual risks

- The gap loops created by snap-cap + close_boundary can produce non-manifold
  edges when the original boundary and projected cap boundary form two separate
  loops that `close_boundary` fills independently. This is a pre-existing
  limitation of `close_boundary` (no nested-loop support), not introduced by
  the snap feature.
- `_snapped_index` creates exactly one projected copy per original vertex.
  This is correct for simple boundaries but could theoretically produce wrong
  results if the same original boundary vertex needs different projections
  for different cap planes (not applicable — only one plane per call).

## Non-goals preserved

- No automatic two-step combined method
- No snap behavior on any other method
- `snap_tolerance` is cleanly separated from `tolerance`

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Added snap_tolerance parameter to close_planar_cap and Mesh3D.close_planar only. No scope creep. 4 new tests, 3 source files changed (ops, domain, tests)."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "15 tests pass, pyright 0 errors, ruff clean. Changed files: mesh_cut.py, mesh.py, test_mesh_close.py. Commands and results documented."
    }
  ],
  "changedFiles": [
    "src/cady/ops/mesh_cut.py",
    "src/cady/geometry3d/mesh.py",
    "tests/geometry3d/test_mesh_close.py"
  ],
  "testsAddedOrUpdated": [
    "tests/geometry3d/test_mesh_close.py (+4 tests: test_close_planar_snap_projects_nearby_boundary, test_close_planar_snap_creates_gaps_for_close_boundary, test_close_planar_snap_noop_when_all_on_plane, test_close_planar_snap_rejects_negative)"
  ],
  "commandsRun": [
    {
      "command": "PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/test_mesh_close.py -v",
      "result": "passed",
      "summary": "15 passed"
    },
    {
      "command": "PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/ tests/numeric/test_mesh_cut.py -v",
      "result": "passed",
      "summary": "45 passed, no regressions"
    },
    {
      "command": ".venv/bin/pyright src/cady",
      "result": "passed",
      "summary": "0 errors, 0 warnings"
    },
    {
      "command": ".venv/bin/ruff check src/cady tests",
      "result": "passed",
      "summary": "All checks passed"
    }
  ],
  "validationOutput": [],
  "residualRisks": [
    "close_boundary fills both the projected-cap loop and the original-boundary loop independently, which can produce non-manifold edges at thin gap strips. This is a pre-existing close_boundary limitation, not a snap_tolerance bug.",
    "One projected copy per original vertex — correct for single-plane usage but may need generalization if multi-plane snapping is added later."
  ],
  "noStagedFiles": true,
  "notes": "Two-step workflow works: close_planar(..., snap_tolerance=0.05) followed by close_boundary(tolerance=0.03) produces a closed mesh from a roughly-planar boundary. The combined result has a single non-manifold edge from nested-loop filling, which is a pre-existing close_boundary limitation."
}
```
