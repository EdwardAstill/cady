# Testing Plan

## Narrow Gates

Run after render-scene naming changes:

```bash
.venv/bin/pytest -q tests/view/test_vispy_viewer.py tests/test_smoke_import.py
.venv/bin/pyright src/cady/view
.venv/bin/ruff check src/cady/view tests/view tests/test_smoke_import.py
```

Run after canvas extraction:

```bash
.venv/bin/pytest -q tests/view/test_vispy_viewer.py
.venv/bin/pyright src/cady/view
.venv/bin/ruff check src/cady/view tests/view
```

Run after overlay model changes:

```bash
.venv/bin/pytest -q tests/view/test_scene.py tests/view/test_vispy_viewer.py
.venv/bin/pyright src/cady/view
```

Run after public export changes:

```bash
.venv/bin/pytest -q tests/test_smoke_import.py tests/conventions/test_public_api_removed.py
```

## Architecture Gates

Run after any import or package layout change:

```bash
.venv/bin/pytest -q \
  tests/conventions/test_import_boundaries.py \
  tests/conventions/test_stdlib_only.py \
  tests/conventions/test_public_api_removed.py
```

## Final Gates

Run before claiming implementation complete:

```bash
.venv/bin/pytest -q tests/view tests/document/test_document.py tests/test_smoke_import.py \
  tests/conventions/test_import_boundaries.py \
  tests/conventions/test_stdlib_only.py \
  tests/conventions/test_public_api_removed.py

.venv/bin/pyright src/cady/view
.venv/bin/ruff check src/cady/view src/cady/__init__.py tests/view tests/test_smoke_import.py
git diff --check
git status --short
```

Use the full project gates if the implementation touches product, geometry,
files, operations, or public top-level exports outside the view layer.

## Test Expectations

Tests should pin behavior:

- `Scene` stores default camera, lights, and overlays as real objects.
- `Scene.view(...)` calls the public lazy viewer path.
- `prepare_scene(...)` returns `RenderScene`.
- Render preparation carries overlays through unchanged.
- VisPy is not imported by `import cady` or `import cady.view`.
- The canvas factory can be exercised through fake VisPy modules or focused
  helpers without requiring a real GUI session.

Avoid tests that lock in incidental private structure unless they are defending
the lazy import boundary.
