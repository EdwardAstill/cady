# Migration Tasks

Do not execute these tasks until implementation is explicitly requested.

## Phase 0: Baseline And Stale-State Check

1. Record current status and confirm no unrelated work will be touched.

   Verification:

   ```bash
   git status --short
   ```

2. Resolve the `cady.ops.linesplan` discrepancy before moving packages.

   Verification:

   ```bash
   rg -n "cady\.ops\.linesplan|from cady\.ops import .*linesplan|def classify_linesplan_curves|def mesh_linesplan_network" src tests examples
   ```

3. Run the current baseline tests that cover import boundaries and geometry.

   Verification:

   ```bash
   PYTHONPATH=src .venv/bin/pytest -q tests/conventions tests/geometry2d tests/geometry3d tests/operations
   ```

## Phase 1: Add New Package Shells

1. Add empty/re-exporting package shells:
   - `src/cady/geometry/__init__.py`
   - `src/cady/operations/__init__.py`
   - `src/cady/operations/__init__.py`

2. Do not move implementation yet. Re-export existing names through the new
   package shells.

   Verification:

   ```bash
   PYTHONPATH=src .venv/bin/python -c "from cady.geometry import Line2D, Body3D, Mesh3D; from cady.operations import line2d, box; from cady.operations import cut_mesh_by_plane"
   ```

## Phase 2: Move Operations

1. Move `src/cady/ops` implementation modules to `src/cady/operations`.

2. Rename `point_transforms.py` to `transforms.py`.

3. Update internal imports from `cady.ops...` to `cady.operations...`.

4. Keep `src/cady/ops` as a compatibility shim that re-exports from
   `cady.operations`.

5. Update convention tests so `operations` must not import authoring packages.

   Verification:

   ```bash
   PYTHONPATH=src .venv/bin/pytest -q tests/conventions/test_import_boundaries.py tests/operations/test_mesh_cut.py tests/geometry3d/test_mesh_close.py
   ```

   Compatibility verification:

   ```bash
   PYTHONPATH=src .venv/bin/python -c "from cady.ops import cut_mesh_by_plane; from cady.operations import cut_mesh_by_plane as new_cut; assert cut_mesh_by_plane is new_cut"
   ```

## Phase 3: Move 2D Geometry Objects

1. Split `geometry2d/curves.py` into:
   - `geometry/curves2d.py`
   - `geometry/line2d.py`
   - `geometry/arc2d.py`
   - `geometry/spline2d.py`
   - `geometry/polyline2d.py`
   - `geometry/conic2d.py`

2. Move `geometry2d/profile.py` to `geometry/profile2d.py`.

3. Move `geometry2d/mesh.py` to `geometry/mesh2d.py`.

4. Update imports in first-party code to use `cady.geometry`.

5. Keep `geometry2d` modules as compatibility shims.

   Verification:

   ```bash
   PYTHONPATH=src .venv/bin/pytest -q tests/geometry2d tests/drawing tests/files
   ```

   Import verification:

   ```bash
   PYTHONPATH=src .venv/bin/python -c "from cady.geometry import Line2D, Arc2D, Spline2D, Polyline2D, ClosedPolyline2D, Circle2D, Ellipse2D, Profile2D, Mesh2D"
   ```

## Phase 4: Move 3D Geometry Objects

1. Move:
   - `geometry3d/frame.py` to `geometry/frame3d.py`
   - `geometry3d/face.py` to `geometry/face3d.py`
   - `geometry3d/body.py` to `geometry/body3d.py`
   - `geometry3d/mesh.py` to `geometry/mesh3d.py`
   - `geometry3d/wireframe.py` to `geometry/wireframe3d.py`
   - `geometry3d/curves.py` to `geometry/polyline3d.py`
   - `geometry3d/features.py` to `geometry/features.py`

2. Keep `geometry/_mesh_builders.py` private during the first move if it still
   imports semantic geometry objects.

3. Extract only object-free algorithms from `_mesh_builders.py` into focused
   operations modules such as `operations.mesh_primitives`.

4. Update imports in files, product, visualisation, and tests.

5. Keep `geometry3d` modules as compatibility shims.

   Verification:

   ```bash
   PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d tests/product tests/view tests/files
   ```

   Import verification:

   ```bash
   PYTHONPATH=src .venv/bin/python -c "from cady.geometry import Frame3D, Face3D, Body3D, Mesh3D, Wireframe3D, Polyline3D, ClosedPolyline3D"
   ```

## Phase 5: Move Constructor Helpers

1. Move 2D constructor helpers:
   - `line2d`, `arc2d`, `circle2d`, `polyline2d` to
     `operations/curves2d.py`
   - `profile_rectangle`, `profile_circle` to `operations/profiles.py`

2. Move 3D primitive constructor helpers:
   - `box`, `cylinder`, `sphere` to `operations/meshes3d.py`

3. Re-export all constructor helpers from `cady.operations` and top-level `cady`.

4. Keep old geometry package constructor imports as compatibility shims.

   Verification:

   ```bash
   PYTHONPATH=src .venv/bin/pytest -q tests/geometry2d/test_constructor helpers.py tests/geometry3d/test_body.py tests/test_smoke_import.py
   ```

   Import verification:

   ```bash
   PYTHONPATH=src .venv/bin/python -c "from cady.operations import line2d, arc2d, circle2d, polyline2d, profile_rectangle, profile_circle, box, cylinder, sphere"
   ```

## Phase 6: Public API And Compatibility Tests

1. Update `src/cady/__init__.py` to import semantic geometry from
   `cady.geometry` and constructor helpers from `cady.operations`.

2. Add explicit tests for:
   - top-level `cady` imports
   - new `cady.geometry` imports
   - new `cady.operations` imports
   - new `cady.operations` imports
   - old `geometry2d`, `geometry3d`, and `ops` compatibility imports

3. Update docs and examples to prefer new package names.

   Verification:

   ```bash
   PYTHONPATH=src .venv/bin/pytest -q tests/test_smoke_import.py tests/conventions
   ```

## Phase 7: Final Gates

1. Run the full test suite.

   Verification:

   ```bash
   PYTHONPATH=src .venv/bin/pytest -q
   ```

2. Run type checking.

   Verification:

   ```bash
   PYTHONPATH=src .venv/bin/pyright src/cady
   ```

3. Run linting.

   Verification:

   ```bash
   .venv/bin/ruff check src/cady tests
   ```

4. Run diff and status gates.

   Verification:

   ```bash
   git diff --check
   git status --short
   ```
