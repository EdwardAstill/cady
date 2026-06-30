# Tasks

## 1. Confirm Current View Boundary

Audit the current view modules and tests before editing. Record any deviation
from this plan in `spec.md` before implementation.

Files to inspect:

- `src/cady/view/scene.py`
- `src/cady/view/preparation.py`
- `src/cady/view/draw_batches.py`
- `src/cady/view/overlay.py`
- `src/cady/view/overlay_renderers.py`
- `src/cady/view/interaction.py`
- `src/cady/view/vispy_viewer.py`
- `src/cady/view/open_view.py`
- `src/cady/view/__init__.py`
- `src/cady/__init__.py`
- `tests/view/*`
- `tests/test_smoke_import.py`
- `tests/conventions/*`

Verification:

```bash
rg -n "PreparedScene|RenderScene|_make_canvas|class _Canvas|ScaleBarOverlay|LocalAxes" \
  src/cady/view tests/view tests/test_smoke_import.py notes/viewing.md
```

## 2. Rename Prepared Render Data To `RenderScene`

Create `src/cady/view/render_scene.py` from the current preparation module.
Rename:

- `PreparedScene` -> `RenderScene`

Keep:

- `prepare_scene(...)`
- `SceneMesh`
- `SceneLine`
- `LineVertices`
- `prepare_polyline(...)`
- `transform_from_pose(...)`

Update imports in:

- `draw_batches.py`
- `vispy_viewer.py`
- `open_view.py` if needed
- `cady.view.__init__`
- tests
- notes

Remove `src/cady/view/preparation.py` unless compatibility is explicitly
required before this task starts.

Verification:

```bash
rg -n "PreparedScene|view.preparation|from cady.view.preparation|import cady.view.preparation" \
  src/cady tests notes || true
.venv/bin/pytest -q tests/view/test_vispy_viewer.py tests/test_smoke_import.py
.venv/bin/pyright src/cady/view
```

## 3. Extract Internal `VispyCanvas`

Move the nested canvas implementation out of `vispy_viewer.py` into
`src/cady/view/vispy_canvas.py`.

Target shape:

```python
def _make_vispy_canvas(render_scene: RenderScene, *, title: str | None = None) -> object:
    ...

class VispyCanvas(...):
    ...
```

Keep `VispyCanvas` internal. Do not export it from `cady.view`.

`vispy_viewer.py` should retain the public viewer functions and call
`_make_vispy_canvas(...)`.

Verification:

```bash
rg -n "class _Canvas|def _make_canvas|def _make_vispy_canvas|class VispyCanvas" src/cady/view
.venv/bin/pytest -q tests/view/test_vispy_viewer.py
.venv/bin/pyright src/cady/view
.venv/bin/ruff check src/cady/view tests/view
```

## 4. Make Local Axes An Overlay Model

Add `LocalAxesOverlay` to `src/cady/view/overlay.py`.

Update:

- `SceneOverlay` type alias
- scene overlay validation
- default scene overlays
- overlay renderer dispatch
- tests for default overlays and custom overlay tuples

Expected default:

```python
Scene(overlays=(ScaleBarOverlay(), LocalAxesOverlay()))
```

If the implementation shows that default local axes would be too disruptive,
record the reason in `spec.md` and keep `LocalAxesOverlay` available but not
default.

Verification:

```bash
.venv/bin/pytest -q tests/view/test_scene.py tests/view/test_vispy_viewer.py
.venv/bin/pyright src/cady/view
.venv/bin/ruff check src/cady/view tests/view
```

## 5. Reconcile Public Exports And Docs

Update public exports:

- `cady.view.RenderScene`
- remove `cady.view.PreparedScene`
- `cady.view.LocalAxesOverlay`
- top-level `cady.LocalAxesOverlay` if overlays are top-level public values

Update:

- `tests/test_smoke_import.py`
- `notes/viewing.md`
- `AGENTS.md` public API section if it has become stale

Verification:

```bash
.venv/bin/pytest -q tests/test_smoke_import.py tests/conventions/test_public_api_removed.py
rg -n "PreparedScene|RenderScene|VispyCanvas|LocalAxesOverlay" notes/viewing.md AGENTS.md src/cady tests
git diff --check
```

## 6. Re-run Import Boundary Gates

Verify that the refactor did not introduce eager GUI imports or forbidden
runtime dependencies.

Verification:

```bash
.venv/bin/pytest -q \
  tests/conventions/test_import_boundaries.py \
  tests/conventions/test_stdlib_only.py \
  tests/conventions/test_public_api_removed.py
```

## 7. Final View-Layer Gate

Run the focused final gate.

Verification:

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

The status output may include unrelated dirty files. Confirm expected changes
for this plan are limited to view-layer source, view tests, public export tests,
and notes/docs.
