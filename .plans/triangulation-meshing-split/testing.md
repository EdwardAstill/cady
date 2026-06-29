# Testing Strategy

## Narrow Tests

Triangulation:

```bash
.venv/bin/pytest -q tests/operations/test_triangulation.py
```

Polyline and curve meshing:

```bash
.venv/bin/pytest -q tests/geometry/test_geometry_curves2.py tests/geometry/test_curves3.py
```

Region, surface, and extrusion meshing:

```bash
.venv/bin/pytest -q tests/geometry/test_region3.py tests/geometry/test_body3.py
```

Mesh clipping and closure:

```bash
.venv/bin/pytest -q tests/operations/test_mesh_cut.py tests/geometry/test_mesh_close.py
```

Wireframe and loft behavior:

```bash
.venv/bin/pytest -q tests/geometry/test_wireframe3.py tests/geometry/test_linesplan_meshing.py
```

## Convention Tests

Run after import or public API changes:

```bash
.venv/bin/pytest -q tests/conventions/test_import_boundaries.py tests/conventions/test_stdlib_only.py tests/conventions/test_public_api_removed.py tests/test_smoke_import.py
```

## Static Checks

Run on touched files during each phase:

```bash
.venv/bin/ruff check <touched files>
.venv/bin/pyright <touched files>
```

Run globally before finishing:

```bash
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
```

## Completion Gates

The implementation is complete only when:

```bash
.venv/bin/pytest -q
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
git diff --check
git status --short
```

passes or any failure is documented as unrelated pre-existing worktree state.
