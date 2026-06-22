# Plotting and Visualisation Tasks

## 1. Create `cady.plotting`

Create a new optional leaf package:

- `src/cady/plotting/__init__.py`
- `src/cady/plotting/plot2d.py`
- `src/cady/plotting/plot3d.py`
- `src/cady/plotting/styles.py` if style constants remain shared by plotting

Move plot-oriented functions from `cady.visualisation` into `cady.plotting`.

Verification:

```bash
PYTHONPATH=src python - <<'PY'
from cady.plotting import plot_shape2d, plot_array_mesh3
assert plot_shape2d
assert plot_array_mesh3
PY
```

## 2. Preserve Temporary Compatibility Imports

Keep existing imports working during the migration:

```python
from cady.visualisation import plot_shape2d, plot_array_mesh3
```

Those names should delegate to or re-export `cady.plotting` functions with a
clear internal TODO/deprecation note.

Verification:

```bash
PYTHONPATH=src pytest tests/visualisation/test_imports.py
```

## 3. Refocus `cady.visualisation` on Interactive Viewers

Keep or create viewer functions under `src/cady/visualisation/`:

- `view_shape3d(...)`
- `view_part(...)`
- `view_model(...)`
- `visualise(value, ...)`

The implementation should consume `to_array(...)` outputs and dispatch based
on semantic object type only at the boundary.

Do not keep Matplotlib static plot code as the primary implementation in this
package once `cady.plotting` exists.

Verification:

```bash
PYTHONPATH=src pytest tests/visualisation
```

## 4. Add VisPy Viewer Backend

Add VisPy as the intended interactive backend for native viewing windows.

Expected first pass:

- convert `ArrayMesh3.vertices` and `ArrayMesh3.faces` into a VisPy mesh;
- render multiple meshes for `Part` and `Model`;
- support default camera controls for orbit, pan, and zoom;
- keep imports lazy so VisPy is required only when the viewer is used;
- raise a clear install error when VisPy is missing.

Suggested public default:

```python
view_shape3d(solid, backend="vispy")
```

Verification should include import-level tests that do not require an active
display, plus at least one backend smoke test that is skipped when VisPy is not
installed.

## 5. Decide Object Convenience Methods

Add object methods only after the package split is stable.

Candidate methods:

- `Shape2D.plot(...)`
- `Drawing2D.plot(...)`
- `Shape3D.plot(...)` for static 3D plots if useful;
- `Shape3D.visualise(...)`
- `Part.visualise(...)`
- `Model.visualise(...)`

Methods must be thin lazy delegates into `cady.plotting` or
`cady.visualisation`. They must not import either package at module scope.

Verification:

```bash
PYTHONPATH=src pytest tests/conventions
```

## 6. Update Dependencies and Extras

Revise optional dependencies to match the split.

Possible shape:

```toml
[project.optional-dependencies]
plotting = [
    "matplotlib>=3.10",
]
visualisation = [
    "vispy>=0.15",
]
all = [
    "cady[plotting,visualisation]",
]
```

Keep compatibility with the current `visualisation` extra if needed during the
migration.

Verification:

```bash
uv lock
PYTHONPATH=src pytest tests/conventions/test_stdlib_only.py
```

## 7. Update Docs and Examples

Update:

- `README.md`
- `docs/visualisation.md`, or split into `docs/plotting.md` and
  `docs/visualisation.md`
- `examples/README.md`
- `examples/scripts/visualise_plate.py`, possibly renamed or split

Docs should use:

```python
from cady.plotting import plot_shape2d
from cady.visualisation import view_shape3d
```

Verification:

```bash
PYTHONPATH=src pytest tests/examples
```

## 8. Full Regression

Run focused checks first, then the full suite.

```bash
PYTHONPATH=src pytest tests/plotting tests/visualisation tests/conventions
PYTHONPATH=src pytest
```
