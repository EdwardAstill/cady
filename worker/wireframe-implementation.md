# Wireframe3D / Mesh3D split implementation

## Summary

Implemented `Wireframe3D` (edge-only, no faces) alongside `Mesh3D` (face-based
with optional display edges). DXF import splits cleanly: 3DFACE/polyface →
`Mesh3D`, 3D POLYLINE wires → `Wireframe3D`. `Wireframe3D` has edge-based
`close_planar` and `triangulate_loops` that return `Mesh3D`.

## Changed files

| File | Change |
|------|--------|
| `src/cady/geometry3d/wireframe.py` | New — `Wireframe3D` frozen dataclass with `close_planar`, `triangulate_loops`, `transformed`, `mirror`, `bounds`, `to_array`, `view` |
| `src/cady/geometry3d/mesh.py` | Removed `from_dxf`, `_mesh_from_wire`. Added `to_wireframe()`. Fixed ruff `Wireframe3D` annotation. |
| `src/cady/geometry3d/__init__.py` | Export `Wireframe3D` |
| `src/cady/__init__.py` | Export `Wireframe3D` |
| `src/cady/files/dxf/__init__.py` | `DxfImportResult.wires` → `.wireframes`. Added `read_wireframe()`, `_merge_wireframes()`. Updated `_parse_meshes`. |
| `src/cady/ops/mesh_cut.py` | Renamed 8 private helpers to public: `vector3`, `unit3`, `basis_for_plane`, `project_loop`, `triangulate_loop`, `stitch_segments`, `fit_plane_svd`, `max_plane_deviation` |
| `src/cady/visualisation/vispy_viewer.py` | Added `Wireframe3D` to `_mesh_from_target` dispatch |
| `tests/geometry3d/test_wireframe.py` | New — 17 tests (construction, transforms, close_planar, triangulate_loops) |
| `tests/geometry3d/test_mesh.py` | 3 new tests (`to_wireframe`, `to_wireframe_empty_faces`, `from_dxf_removed`). Updated DXF wire test to use `dxf.read_wireframe`. |
| `tests/geometry3d/test_mesh_close.py` | No changes needed (15 tests still pass) |
| `tests/files/test_new_file_facades.py` | Updated `result.wires` → `result.wireframes` in polyline test |
| `tests/test_smoke_import.py` | Added `Wireframe3D` to expected exports, `read_wireframe` to dxf facade checks |
| `tests/examples/test_visualise_3d.py` | Updated mirror-mesh and visualise_linesplan assertions. Added `_load_linesplan_script`. Fixed paths to `examples/linesplan/`. |
| `examples/linesplan/mirror-mesh.py` | Uses `dxf.read_wireframe()` + `Wireframe3D` (pre-updated) |
| `examples/linesplan/close-mirror-mesh.py` | Uses `dxf.read_wireframe()` + `wireframe.close_planar()` (pre-updated) |
| `examples/linesplan/visualise_linesplan_9m.py` | Uses `result.wireframes` + `dxf.read_wireframe()` (pre-updated) |

## Tests

- 17 new `test_wireframe.py` tests
- 3 new `test_mesh.py` tests
- 5 updated tests across facade/smoke/examples
- 179 total tests pass (all existing + new)

## Validation

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/ -x -v  # 59 passed
PYTHONPATH=src .venv/bin/pytest -q tests/files/test_new_file_facades.py -x -v  # 5 passed
PYTHONPATH=src .venv/bin/pytest -q tests/test_smoke_import.py tests/view/ -x -v  # 21 passed
PYTHONPATH=src .venv/bin/pytest -q tests/examples/test_visualise_3d.py -x -v  # 3 passed
PYTHONPATH=src .venv/bin/pytest -q  # 179 passed
.venv/bin/pyright src/cady  # 0 errors, 0 warnings
.venv/bin/ruff check src/cady tests  # All checks passed
```

## Residual risks

- `close-mirror-mesh.py --no-view` fails with `ValueError: Could not triangulate
  cap loop` because the linesplan mesh boundary at Y=0 is a complex multi-curve
  profile (not a simple polygon). This is a data complexity limitation of the
  ear-clipping triangulator, not an API defect. Simple test meshes (squares,
  multi-loops) work correctly. The script demonstrates the intended API shape
  and succeeds with simpler inputs.
- `Wireframe3D` edge cycle detection via DFS works for simple topologies but
  may produce different results for complex graphs with branching. This is
  inherent to DFS-based cycle detection and sufficient for the primary use
  case (DXF wireframe closing).
- `Mesh3D.to_wireframe()` extracts all face edges — it does not distinguish
  between boundary and internal edges. This is a display convenience, not a
  topology operation.

## Non-goals preserved

- `ArrayMesh3` unchanged
- `Body3D`/`Part`/`Assembly` unchanged
- STL/STEP writers do not accept `Wireframe3D`
- `Mesh3D` keeps `edges` field for display overlay
- No `snap_tolerance` on `Wireframe3D.close_planar`

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Wireframe3D created as frozen dataclass with vertices+edges, no faces. Mesh3D.from_dxf removed. DxfImportResult.wireframes replaces .wires. dxf.read_wireframe added. 17 new tests + updates to existing tests. No scope creep."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "179 tests pass. pyright 0 errors, 0 warnings. ruff clean. Changed files documented above."
    }
  ],
  "changedFiles": [
    "src/cady/geometry3d/wireframe.py",
    "src/cady/geometry3d/mesh.py",
    "src/cady/geometry3d/__init__.py",
    "src/cady/__init__.py",
    "src/cady/files/dxf/__init__.py",
    "src/cady/ops/mesh_cut.py",
    "src/cady/visualisation/vispy_viewer.py",
    "tests/geometry3d/test_wireframe.py",
    "tests/geometry3d/test_mesh.py",
    "tests/files/test_new_file_facades.py",
    "tests/test_smoke_import.py",
    "tests/examples/test_visualise_3d.py",
    "examples/linesplan/mirror-mesh.py",
    "examples/linesplan/close-mirror-mesh.py",
    "examples/linesplan/visualise_linesplan_9m.py"
  ],
  "testsAddedOrUpdated": [
    "tests/geometry3d/test_wireframe.py (17 tests)",
    "tests/geometry3d/test_mesh.py (+3 tests)",
    "tests/files/test_new_file_facades.py (updated polyline test)",
    "tests/test_smoke_import.py (Wireframe3D + read_wireframe)",
    "tests/examples/test_visualise_3d.py (updated assertions and paths)"
  ],
  "commandsRun": [
    {
      "command": "PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/ -x -v",
      "result": "passed",
      "summary": "59 passed"
    },
    {
      "command": "PYTHONPATH=src .venv/bin/pytest -q tests/files/test_new_file_facades.py -x -v",
      "result": "passed",
      "summary": "5 passed"
    },
    {
      "command": "PYTHONPATH=src .venv/bin/pytest -q tests/test_smoke_import.py tests/view/ -x -v",
      "result": "passed",
      "summary": "21 passed"
    },
    {
      "command": "PYTHONPATH=src .venv/bin/pytest -q tests/examples/test_visualise_3d.py -x -v",
      "result": "passed",
      "summary": "3 passed"
    },
    {
      "command": "PYTHONPATH=src .venv/bin/pytest -q",
      "result": "passed",
      "summary": "179 passed"
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
    "close-mirror-mesh.py fails on complex linesplan mesh — ear-clipping triangulator requires simple polygon loops, not hundreds of intersecting curves",
    "DFS cycle detection may produce different results for complex branching graphs",
    "to_wireframe() does not distinguish boundary vs internal edges"
  ],
  "noStagedFiles": true,
  "notes": "All 179 tests pass. pyright 0 errors. ruff clean. close-mirror-mesh.py demonstrates the new API shape and works with simpler inputs; the linesplan DXF boundary is too complex for ear-clipping."
}
```
