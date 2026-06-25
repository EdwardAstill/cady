## Review

- Correct [severity: none]: `src/cady/geometry3d/wireframe.py` does not import `matplotlib`, `pyvista`, or `cady.visualisation` at module scope. The only view-related imports are under `TYPE_CHECKING` (`src/cady/geometry3d/wireframe.py:13-16`) and a local runtime import inside `view()` (`src/cady/geometry3d/wireframe.py:218`).
- Correct [severity: none]: `src/cady/ops/mesh_cut.py` does not import `cady.geometry3d`; module-scope imports are stdlib, `numpy`, `numpy.typing`, and `cady.numeric.mesh3d` only (`src/cady/ops/mesh_cut.py:3-10`). Public helper renames did not add an ops -> geometry3d dependency.
- Blocker [severity: high]: `Wireframe3D` imports NumPy at module scope (`src/cady/geometry3d/wireframe.py:6`) and uses it in the domain/authoring class (`src/cady/geometry3d/wireframe.py:65-71`, `src/cady/geometry3d/wireframe.py:102-108`, `src/cady/geometry3d/wireframe.py:184-189`). This violates the requested domain import boundary check for `cady.geometry3d.wireframe`.
- Blocker [severity: high]: `cady.files.dxf` imports `cady.geometry3d` at module scope (`src/cady/files/dxf/__init__.py:12`) for `Mesh3D`/`Wireframe3D` types and construction (`src/cady/files/dxf/__init__.py:26-30`, `src/cady/files/dxf/__init__.py:73-81`, `src/cady/files/dxf/__init__.py:285-308`). Importing `cady.files.dxf` currently loads both `cady.geometry3d` and `numpy` indirectly; verified with `PYTHONPATH=src .venv/bin/python - <<'PY' ... import cady.files.dxf ...`. This is not caught by the current AST-only files convention test because it only checks direct imports (`tests/conventions/test_import_boundaries.py:81-88`).
- Note [severity: low]: The requested `src/cady/files/dxf/reader.py` file does not exist in this checkout; DXF reading/parsing is in `src/cady/files/dxf/__init__.py`.
- Note [severity: low]: Current convention tests pass, but they do not enforce the `geometry3d`/domain NumPy restriction and do not detect indirect NumPy loading through `cady.files.dxf` (`tests/conventions/test_import_boundaries.py:81-88`, `tests/conventions/test_stdlib_only.py:17-34`). Residual risk remains unless tests are expanded or imports are made lazy/type-checking-only.

## Validation

- `PYTHONPATH=src .venv/bin/pytest -q tests/conventions/test_import_boundaries.py tests/conventions/test_stdlib_only.py` — passed, 7 tests.
- `PYTHONPATH=src .venv/bin/python - <<'PY' ... import cady.files.dxf ...` — confirmed `numpy_loaded=True`, `geometry3d_loaded=True`, `wireframe_loaded=True`, and no `cady.visualisation`/`matplotlib`/`pyvista` loaded.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Concrete findings are listed with severity and file:line references, including high-severity module-scope NumPy import in src/cady/geometry3d/wireframe.py:6 and high-severity cady.files.dxf -> cady.geometry3d module-scope import in src/cady/files/dxf/__init__.py:12."
    }
  ],
  "changedFiles": [],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "git diff -- src/cady/geometry3d/wireframe.py src/cady/geometry3d/mesh.py src/cady/files/dxf/__init__.py src/cady/files/dxf/reader.py src/cady/ops/mesh_cut.py tests/conventions/test_import_boundaries.py tests/conventions/test_stdlib_only.py",
      "result": "passed",
      "summary": "Inspected current diff for requested files; reader.py is absent."
    },
    {
      "command": "PYTHONPATH=src .venv/bin/pytest -q tests/conventions/test_import_boundaries.py tests/conventions/test_stdlib_only.py",
      "result": "passed",
      "summary": "7 passed in 0.11s."
    },
    {
      "command": "PYTHONPATH=src .venv/bin/python - <<'PY' ... import cady.files.dxf ...",
      "result": "passed",
      "summary": "Confirmed importing cady.files.dxf loads numpy, cady.geometry3d, and cady.geometry3d.wireframe; did not load visualisation/matplotlib/pyvista."
    },
    {
      "command": "git diff --cached --name-only",
      "result": "passed",
      "summary": "No staged files."
    }
  ],
  "validationOutput": [
    "7 passed in 0.11s",
    "numpy_loaded= True; geometry3d_loaded= True; wireframe_loaded= True; visualisation_loaded= False; matplotlib_loaded= False; pyvista_loaded= False"
  ],
  "residualRisks": [
    "tests/conventions/test_import_boundaries.py checks direct file imports only, so it does not catch cady.files.dxf indirectly loading numpy through cady.geometry3d.",
    "No top-level plan.md or progress.md existed at the requested paths; reviewed .plans/wireframe-type/plan.md as the available relevant plan."
  ],
  "noStagedFiles": true,
  "notes": "Review-only task; no project/source files were modified."
}
```
