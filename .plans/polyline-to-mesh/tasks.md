# Polyline To Mesh Tasks

**Date:** 2026-06-26
**Status:** implemented

## Task 1: Add The 2D Mesh Data Types

**Status:** complete

Add `ArrayMesh2` in `cady.operations` and `Mesh2D` in `cady.geometry2d`.

Expected behaviour:

- `ArrayMesh2` validates 2D vertices, triangular faces, and optional edges.
- `Mesh2D.from_array(...)`, `Mesh2D.to_array(...)`, `Mesh2D.merged(...)`,
  `Mesh2D.triangles`, `Mesh2D.bounds()`, and `Mesh2D.transformed(...)` follow
  the existing `Mesh3D` conventions where applicable.
- No authoring package imports optional visualisation/runtime-heavy modules.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/operations/test_array_mesh2d.py tests/geometry2d/test_geometry_mesh2d.py
```

## Task 2: Add `ClosedPolyline2D.to_mesh(...)`

**Status:** complete

Use the existing 2D polygon triangulation path to convert a closed 2D boundary
into `Mesh2D`.

Expected behaviour:

- `ClosedPolyline2D.to_mesh(tolerance=...)` returns `Mesh2D`.
- `Polyline2D` remains an open curve type with no `to_mesh(...)`.
- Boundary points are not duplicated in the mesh vertex list.
- Generated explicit edges preserve the source boundary loop.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/geometry2d/test_curves.py tests/geometry2d/test_geometry_mesh2d.py
```

## Task 3: Decide And Add The 3D Polyline Surface

**Status:** complete

Choose the smallest API surface for 3D closed polylines:

- preferred: add domain `Polyline3D` and `ClosedPolyline3D`;
- smaller first pass: add `ArrayPolyline3.to_mesh(...) -> ArrayMesh3` and defer
  domain 3D polylines.

Expected behaviour:

- Only closed 3D loops mesh to faces.
- Planar loops return `Mesh3D` or `ArrayMesh3`, depending on the chosen API.
- Non-planar loops fail with `GeometryError`.
- Face winding is deterministic for a world-XY square.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/geometry3d/test_curves3d.py tests/operations/test_mesh3d.py
```

## Task 4: Wire Public Exports

**Status:** complete

Expose the selected public types through package `__init__` files.

Expected behaviour:

- `Mesh2D` is importable from `cady` and `cady.geometry2d`.
- `ArrayMesh2` is importable from `cady.operations`.
- If domain 3D polylines are added, they are importable from `cady` and
  `cady.geometry3d`.
- Removed legacy API tests remain unchanged unless a new explicit export list
  assertion is needed.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q tests/test_smoke_import.py tests/conventions
```

## Task 5: Update Documentation And Examples Where Needed

**Status:** complete

Update only docs or examples that describe the public geometry conversion
surface.

Expected behaviour:

- Public API documentation mentions `Mesh2D` and closed-polyline meshing.
- Existing examples are left alone unless they naturally use this new API.
- No generated artifacts are edited without checking their source.

Verification:

```bash
rg -n "Mesh2D|ClosedPolyline3D|to_mesh\\(" README.md docs src tests examples
```

## Task 6: Run Final Gates

**Status:** complete

Run the project verification gates after implementation.

Verification:

```bash
PYTHONPATH=src .venv/bin/pytest -q
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
git diff --check
git status --short
```
