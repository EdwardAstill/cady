# Fix algorithmic bugs in Wireframe3D

## Bug 1: close_planar caps open edge chains

**Root cause:** `stitch_segments()` returns any walked path with `len >= 3`
even when it didn't close back to start. An open 3-edge chain like `0-1-2-3`
would be returned as loop `[0, 1, 2, 3]` and triangulated into invalid cap
faces.

**Fix:** After `stitch_segments()`, validate each loop by checking the
closing edge `(loop[-1], loop[0])` exists in the original `plane_edges` set.
Only triangulate closed loops. Added `closed_loops` filter and new
`GeometryError("no closed planar edge loops found")` when no valid closed
loops remain.

**Test:** `test_close_planar_rejects_open_chain` — 4-vertex open chain
raises `GeometryError`.

## Bug 2: triangulate_loops misses cycles in connected components

**Root cause:** Global `visited` set prevented DFS from finding cycles that
share vertices with previously found cycles. Example: two triangles sharing
vertex 2 — after finding triangle `[0,1,2]`, vertex 2 was marked visited and
triangle `[2,3,4]` could not be found.

**Fix:** Replaced global `visited` set with per-search `visited` set. Added
`used_cycle_edges` set to track edges already consumed by found cycles. After
a cycle is found, its edges are marked used so subsequent DFS searches skip
them, preventing duplicate cycles while allowing multiple cycles in the same
component.

**Test:** `test_triangulate_loops_two_connected_squares` — two squares
joined by a bridge edge. Previously found 2 faces (one square), now finds
4 faces (both squares).

## Changed files

| File | Change |
|------|--------|
| `src/cady/geometry3d/wireframe.py` | close_planar: +8 lines closed-loop validation. triangulate_loops: rewritten DFS with edge-based cycle tracking. |
| `tests/geometry3d/test_wireframe.py` | +2 tests. Renamed `test_wireframe_triangulate_loops_multiple_cycles` to `test_triangulate_loops_multiple_disjoint_cycles`. |

## Validation

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/test_wireframe.py -v
# 19 passed (17 existing + 2 new)

PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/ -x
# 61 passed

.venv/bin/pyright src/cady
# 0 errors, 0 warnings

.venv/bin/ruff check src/cady tests
# All checks passed
```

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Only wireframe.py close_planar and triangulate_loops changed, plus 2 new tests. No import structure changes, no stitch_segments changes, no linesplan example fix. Scope matches task exactly."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Changed files: wireframe.py (+16 lines), test_wireframe.py (+2 tests). 61 geometry3d tests pass. pyright 0 errors, ruff clean. Both bug reproducers pass as tests."
    }
  ],
  "changedFiles": [
    "src/cady/geometry3d/wireframe.py",
    "tests/geometry3d/test_wireframe.py"
  ],
  "testsAddedOrUpdated": [
    "test_close_planar_rejects_open_chain",
    "test_triangulate_loops_two_connected_squares",
    "test_wireframe_triangulate_loops_multiple_cycles renamed to test_triangulate_loops_multiple_disjoint_cycles"
  ],
  "commandsRun": [
    {
      "command": "PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/test_wireframe.py -v",
      "result": "passed",
      "summary": "19 passed in 0.09s"
    },
    {
      "command": "PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/ -x",
      "result": "passed",
      "summary": "61 passed in 0.12s"
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
    "close-mirror-mesh.py still fails on linesplan DXF — separate data complexity issue, not touched here",
    "edge-based cycle tracking assumes simple cycles; self-intersecting edges within a component may produce unpredictable results"
  ],
  "noStagedFiles": true,
  "notes": "Bug 1 was a missing closed-loop validation. Bug 2 was a global-visited-set preventing multi-cycle detection. Both fixed with minimal changes."
}
```
