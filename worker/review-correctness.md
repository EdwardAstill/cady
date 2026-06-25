## Review

- Correct: `Wireframe3D` is a frozen, slotted dataclass with only `vertices` and `edges`; there is no `faces` field (`src/cady/geometry3d/wireframe.py:19-24`). Construction normalizes vertices/edges and rejects negative, out-of-range, and edge-without-vertex cases (`src/cady/geometry3d/wireframe.py:26-37`).
- Correct: `Wireframe3D.to_array()` returns an `ArrayMesh3` with populated vertices/edges and an empty `(0, 3)` faces array (`src/cady/geometry3d/wireframe.py:63-71`).
- Correct: `Mesh3D.from_dxf` has been removed from `Mesh3D`; DXF wire import is now via `dxf.read_wireframe()` (`src/cady/geometry3d/mesh.py:51-69`, `src/cady/files/dxf/__init__.py:66-81`). `Mesh3D.to_wireframe()` extracts unique face edges into a `Wireframe3D` (`src/cady/geometry3d/mesh.py:186-194`).
- Correct: Existing Mesh3D close tests are passing. `PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/test_mesh.py tests/geometry3d/test_wireframe.py tests/geometry3d/test_mesh_close.py` passed with `43 passed`.

- Blocker [High]: `Wireframe3D.close_planar()` can cap open edge chains as if they were closed loops. It trusts `stitch_segments()` (`src/cady/geometry3d/wireframe.py:115-123`), but `stitch_segments()` appends any walked path with `len(loop) >= 3` even when it did not return to the start (`src/cady/ops/mesh_cut.py:237-255`). Repro: an open three-edge chain `0-1-2-3` on the plane returned two faces instead of raising (`faces ((3, 1, 0), (1, 3, 2))`). This violates the stated loop-triangulation behavior and can silently create invalid caps.
- Blocker [High]: The planned end-to-end `examples/linesplan/close-mirror-mesh.py --no-view` currently fails inside `Wireframe3D.close_planar()` with `ValueError: Could not triangulate cap loop; try cap=False` at `src/cady/geometry3d/wireframe.py:122`. This is likely another manifestation of insufficient loop validation/segmentation in `close_planar()` for real wire data.
- Major [Medium]: `Wireframe3D.triangulate_loops()` only reliably handles disjoint components; it can miss closed cycles in the same connected component. The DFS uses one global `visited` set and breaks after finding one cycle in a component (`src/cady/geometry3d/wireframe.py:154-179`). Repro with two squares connected by a bridge returned 2 faces for one square, not 4 faces for both loops. This violates the method docstring/plan claim that it detects closed edge cycles and triangulates each into faces.
- Note [Low]: Empty `Wireframe3D` is valid, but `Wireframe3D((), ()).transformed(...)` raises `ValueError: points must have rank 2`; `mirror()` has the same issue because it delegates to `transformed()` (`src/cady/geometry3d/wireframe.py:39-45`). If empty wireframes are supported values, transforms should probably return an empty wireframe.
- Note [Low]: `Wireframe3D.view()` will not be classified as wire-only by the default style helper because `_is_wire_only()` requires both `faces` and `edges` attributes (`src/cady/view/open_view.py:101-106`), and `Wireframe3D` intentionally has no `faces`. VisPy still draws edges, but the default mode/color resolution is not wireframe-specific.

## Validation commands

- `git diff -- src/cady/geometry3d/wireframe.py src/cady/geometry3d/mesh.py tests/geometry3d/test_wireframe.py tests/geometry3d/test_mesh.py` — inspected current diff; note that `wireframe.py` and `test_wireframe.py` are untracked, so they were read directly.
- `PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/test_mesh.py tests/geometry3d/test_wireframe.py tests/geometry3d/test_mesh_close.py` — passed, `43 passed in 0.10s`.
- `PYTHONPATH=src .venv/bin/pytest -q tests/files/test_new_file_facades.py tests/test_smoke_import.py tests/examples/test_visualise_3d.py` — passed, `20 passed in 0.82s`.
- `.venv/bin/pyright src/cady` — passed, `0 errors`.
- `.venv/bin/ruff check src/cady tests` — passed.
- `PYTHONPATH=src .venv/bin/python examples/linesplan/close-mirror-mesh.py --no-view` — failed with `ValueError: Could not triangulate cap loop; try cap=False`.
- `git diff --check` — passed.

## Residual risks

- `plan.md` and `progress.md` requested by the task do not exist at the repository root; I reviewed `.plans/wireframe-type/plan.md` instead.
- I did not run the full test suite; I ran focused geometry, DXF facade/smoke/example tests plus pyright and ruff.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Concrete findings with severity and file:line references are listed under Blocker/Major/Note, including close_planar open-chain capping, example failure, triangulate_loops missed cycles, and empty-transform behavior."
    }
  ],
  "changedFiles": [],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "git diff -- src/cady/geometry3d/wireframe.py src/cady/geometry3d/mesh.py tests/geometry3d/test_wireframe.py tests/geometry3d/test_mesh.py",
      "result": "passed",
      "summary": "Inspected current tracked diff; untracked files were read directly."
    },
    {
      "command": "PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/test_mesh.py tests/geometry3d/test_wireframe.py tests/geometry3d/test_mesh_close.py",
      "result": "passed",
      "summary": "43 passed."
    },
    {
      "command": "PYTHONPATH=src .venv/bin/pytest -q tests/files/test_new_file_facades.py tests/test_smoke_import.py tests/examples/test_visualise_3d.py",
      "result": "passed",
      "summary": "20 passed."
    },
    {
      "command": ".venv/bin/pyright src/cady",
      "result": "passed",
      "summary": "0 errors, 0 warnings."
    },
    {
      "command": ".venv/bin/ruff check src/cady tests",
      "result": "passed",
      "summary": "All checks passed."
    },
    {
      "command": "PYTHONPATH=src .venv/bin/python examples/linesplan/close-mirror-mesh.py --no-view",
      "result": "failed",
      "summary": "Failed in Wireframe3D.close_planar with ValueError: Could not triangulate cap loop; try cap=False."
    },
    {
      "command": "git diff --check",
      "result": "passed",
      "summary": "No whitespace errors in tracked diff."
    }
  ],
  "validationOutput": [
    "review-findings: 2 high-severity blockers, 1 medium-severity major finding, 2 low-severity notes",
    "residual-risks: full suite not run; requested root plan.md/progress.md were missing"
  ],
  "residualRisks": [
    "Full test suite was not run.",
    "Root plan.md and progress.md were missing; reviewed .plans/wireframe-type/plan.md instead."
  ],
  "noStagedFiles": true,
  "notes": "No project/source files were modified; only the requested worker review report was written."
}
```
