# File Plan

## Source Files

### `src/cady/view/render_scene.py`

Create or rename from the current preparation module.

Owns:

- `RenderScene`
- `SceneMesh`
- `SceneLine`
- `LineVertices`
- `prepare_scene(...)`
- `prepare_polyline(...)`
- `transform_from_pose(...)`
- target-to-mesh, line, point-cloud conversion helpers
- scene lighting resolution

Rules:

- no VisPy imports
- may import NumPy
- may import semantic Cady objects needed at the conversion boundary
- keeps `tolerance` explicit

### `src/cady/view/preparation.py`

Remove after imports are migrated, unless a compatibility decision is made
before implementation.

If compatibility is explicitly required later, keep this as a tiny deprecated
forwarder only:

```python
from cady.view.render_scene import RenderScene, SceneLine, SceneMesh, prepare_scene
```

The preferred plan is no compatibility module.

### `src/cady/view/draw_batches.py`

Update imports from `PreparedScene` to `RenderScene`.

Owns:

- `DrawBatch`
- `CanvasGeometry`
- `SceneBounds`
- conversion from render-scene mesh/line arrays to draw batches
- scene bounds for viewer fitting

Rules:

- no module-scope VisPy imports
- accepts backend objects such as `gloo` as runtime arguments

### `src/cady/view/vispy_canvas.py`

New internal backend module.

Owns:

- `_require_vispy(...)` or equivalent lazy import guard
- shader source strings
- `_make_vispy_canvas(render_scene, title=...)`
- internal `VispyCanvas` class
- event handlers for draw, resize, mouse, wheel, and keyboard input
- wiring between draw batches, interaction state, and overlay renderers

Rules:

- imports VisPy only inside canvas factory or runtime methods
- not exported from `cady.view`
- no CAD target conversion

### `src/cady/view/vispy_viewer.py`

Keep as the public lazy viewer entry module.

Owns:

- `view_scene(...)`
- `view_target(...)`
- `view_mesh(...)`
- `view_meshes(...)`
- `view_lines(...)`
- public viewer `__all__`

Changes:

- import `RenderScene` and `prepare_scene` from `render_scene.py`
- delegate canvas creation to `_make_vispy_canvas(...)`
- avoid retaining a large nested `_Canvas` class

### `src/cady/view/overlay.py`

Extend overlay model values.

Owns:

- `ScaleBarOverlay`
- `LocalAxesOverlay`
- `SceneOverlay` union/type alias

Rules:

- overlay values are immutable dataclasses
- validate public construction inputs
- do not import VisPy

### `src/cady/view/overlay_renderers.py`

Own backend renderer helpers for overlay values.

Changes:

- dispatch from `SceneOverlay` values to renderer objects
- render `ScaleBarOverlay`
- render `LocalAxesOverlay`
- keep screen-space rendering separate from model draw batches

Rules:

- no module-scope VisPy imports
- receive backend objects from `vispy_canvas.py`

### `src/cady/view/scene.py`

Keep scene model responsibilities.

Changes:

- default overlays should be explicit model values, likely
  `(ScaleBarOverlay(), LocalAxesOverlay())`
- validation should accept every `SceneOverlay` value
- no VisPy imports

### `src/cady/view/__init__.py`

Update lazy exports.

Changes:

- expose `RenderScene`
- remove `PreparedScene`, unless compatibility is explicitly required
- expose `LocalAxesOverlay` if it is part of the public overlay model

### `src/cady/__init__.py`

Update top-level exports only for values intended to be top-level API.

Recommended:

- top-level `ScaleBarOverlay`
- top-level `LocalAxesOverlay`
- do not top-level export `RenderScene` unless current API policy already
  top-level exports preparation types

### `src/cady/view/open_view.py`

No major architecture change expected.

Check:

- quick-view path still builds a normal `Scene`
- defaults still produce camera, lights, and overlays through `Scene`
- no direct canvas or VisPy dependency

## Test Files

### `tests/view/test_scene.py`

Update scene overlay defaults and validation tests.

### `tests/view/test_vispy_viewer.py`

Update render-scene naming and canvas extraction expectations.

Tests should verify behavior, not private implementation shape, except where
lazy import boundaries require targeted private checks.

### `tests/view/test_object_view_methods.py`

Confirm object `.view(...)` helpers still call the public viewer path.

### `tests/test_smoke_import.py`

Update public/lazy imports:

- add `RenderScene`
- remove `PreparedScene`
- add `LocalAxesOverlay` if public

### `tests/conventions/test_import_boundaries.py`

Update only if module names or lazy import rules need explicit coverage.

### `tests/conventions/test_stdlib_only.py`

Run as a gate after moving VisPy-related code.

## Notes

### `notes/viewing.md`

Update after implementation so it matches the code:

- `RenderScene` as the real code name
- `VispyCanvas` as the internal live backend object
- overlays include scale bar and local axes
- tree diagram remains accurate

### `AGENTS.md`

Update only if public API lists or package layout guidance become stale.
