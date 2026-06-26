# Operations Refactor

## Goal

Split `src/cady/operations` into responsibility-focused modules while keeping
the existing public `cady.operations` import surface stable.

## Non-goals

- No behaviour changes to mesh clipping, cap closing, linesplan meshing, or
  geometry constructors.
- No dependency changes.

## Acceptance Criteria

- `cady.operations` still re-exports the existing public names.
- Mesh cutting, cap closing, boundary stitching, plane helpers, mesh primitive
  builders, constructors, and 2D sampling live in separate modules.
- Old broad compatibility wrapper modules are removed.
- Existing internal imports use the new module names where appropriate.
- Relevant tests pass.
- `git diff --check` passes.

## Target Structure

- `constructors.py`: public geometry factory wrappers.
- `sampling2d.py`: 2D curve sampling helpers.
- `mesh_primitives.py`: primitive and feature triangle builders.
- `mesh_clipping.py`: plane clipping entry point.
- `mesh_boundaries.py`: boundary edge and loop helpers.
- `mesh_caps.py`: planar cap and boundary closing entry points.
- `planes.py`: vector coercion, basis, projection, and plane fitting helpers.
- `transforms.py`, `polygons2d.py`, `triangulation.py`, `linesplan.py`: kept
  unless a direct responsibility split is needed.

## Verification

- `.venv/bin/pytest -q tests/operations/test_mesh_cut.py tests/geometry3d/test_mesh_close.py tests/geometry3d/test_linesplan_meshing.py tests/geometry3d/test_linesplan_network.py tests/geometry2d/test_constructors.py tests/geometry2d/test_profiles.py tests/test_smoke_import.py`
- `.venv/bin/pytest -q tests/conventions/test_import_boundaries.py`
- `git diff --check`
