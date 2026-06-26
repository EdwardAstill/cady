# Operations Refactor Tasks

## 1. Baseline

- Run targeted operations tests before editing.
- Failure signal: baseline tests fail in unrelated ways; record before
  continuing.

Verification:

```bash
.venv/bin/pytest -q tests/operations/test_mesh_cut.py tests/geometry3d/test_mesh_close.py tests/geometry3d/test_linesplan_meshing.py tests/geometry3d/test_linesplan_network.py tests/geometry2d/test_constructors.py tests/geometry2d/test_profiles.py tests/test_smoke_import.py
```

## 2. Split Modules

- Move constructor wrappers to `operations/constructors.py`.
- Move curve sampling helpers to `operations/sampling2d.py`.
- Move 3D triangle primitive builders to `operations/mesh_primitives.py`.
- Split `mesh_cut.py` into clipping, caps, boundaries, and plane helpers.

Verification:

```bash
PYTHONPATH=src python - <<'PY'
from cady.operations import box, cut_mesh_by_plane, line2d, profile_rectangle
from cady.operations.mesh_caps import close_boundary, close_planar_cap
from cady.operations.mesh_clipping import cut_mesh_by_plane as cut
assert cut is cut_mesh_by_plane
assert callable(box) and callable(line2d) and callable(profile_rectangle)
assert callable(close_boundary) and callable(close_planar_cap)
PY
```

## 3. Update Imports

- Update geometry and operations imports from old modules to new modules.
- Delete old compatibility modules after confirming there are no source/test
  references.

Verification:

```bash
rg -n "operations\\.mesh_cut|operations\\.meshes3d|operations\\.curves2d" src/cady tests
```

## 4. Final Checks

- Run targeted tests.
- Run import boundary tests.
- Run diff whitespace check.

Verification:

```bash
.venv/bin/pytest -q tests/operations/test_mesh_cut.py tests/geometry3d/test_mesh_close.py tests/geometry3d/test_linesplan_meshing.py tests/geometry3d/test_linesplan_network.py tests/geometry2d/test_constructors.py tests/geometry2d/test_profiles.py tests/test_smoke_import.py
.venv/bin/pytest -q tests/conventions/test_import_boundaries.py
git diff --check
```
