# Files API Tasks

## 1. Add `cady.files` Package

Create:

- `src/cady/files/__init__.py`
- `src/cady/files/dxf.py`
- `src/cady/files/stl.py`
- `src/cady/files/step.py`

Expected exports:

- `cady.files.dxf.write_drawing`
- `cady.files.dxf.write_model`
- `cady.files.stl.write_mesh`
- `cady.files.stl.write_model`
- `cady.files.step.write_model`
- `cady.files.step.read_faces`
- `cady.files.step.read_members`

Verification:

```bash
PYTHONPATH=src python - <<'PY'
from cady.files import dxf, step, stl
assert dxf.write_drawing
assert dxf.write_model
assert stl.write_mesh
assert stl.write_model
assert step.write_model
assert step.read_faces
assert step.read_members
PY
```

## 2. Route Facade Functions to Existing Implementations

Implement the facade as thin wrappers around current code:

- DXF drawing writes should call the existing DXF section writer.
- DXF model writes should reuse the current `Model.write_dxf` merge behavior
  or extract that behavior into a shared helper if needed.
- STL mesh writes should call existing ASCII/binary STL writers through
  `StlMesh.write(...)`.
- STL model writes should reuse the current model mesh aggregation behavior.
- STEP model writes should call existing STEP rendering.
- STEP reads should call existing `read_step` and member extraction helpers.

Verification:

```bash
PYTHONPATH=src pytest tests/model tests/write tests/read
```

## 3. Clean Up Object Write Method Names

Keep these methods:

- `Model.write_dxf(path)`
- `Model.write_stl(path, *, ascii=False, tolerance=1e-3)`
- `Model.write_step(path)`
- `StlMesh.write(path, ascii=False)`

Add or normalize these methods:

- `Drawing2D.write_dxf(path)`
- optionally keep `DxfDrawing.write(path)` as the lower-level internal
  equivalent.

Do not add `to_dxf(path)`.

Verification:

```bash
PYTHONPATH=src pytest tests/model/test_model_dxf.py tests/model/test_model_stl.py tests/model/test_model_step.py
```

## 4. Add Facade Tests

Create focused tests under `tests/files/`:

- `test_dxf_files.py`
- `test_stl_files.py`
- `test_step_files.py`

Cover:

- facade write functions create files;
- facade write output matches existing object-level writes for simple cases;
- `step.read_faces(...)` returns faces;
- `step.read_members(...)` returns reconstructed members where supported;
- `cady.files.step` does not expose vague `read(...)` unless intentionally
  added with a canonical return type.

Verification:

```bash
PYTHONPATH=src pytest tests/files
```

## 5. Update Public Imports and Docs

Update:

- `src/cady/__init__.py` only if top-level aliases are desired;
- `README.md`;
- `examples/README.md`;
- examples that currently mention direct exporter/importer imports.

Preferred docs should show:

```python
from cady.files import step

faces = step.read_faces("member.step")
```

and object writes:

```python
model.write_dxf("plate.dxf")
model.write_step("plate.step")
```

Verification:

```bash
PYTHONPATH=src pytest tests/examples tests/test_smoke_import.py
```

## 6. Strengthen Boundary Tests

Extend convention tests so:

- `cady.files` does not import `cady.visualisation`;
- `cady.files` remains a facade and does not introduce `numpy` as a required
  module-scope import;
- no new `ops` module imports domain objects.

Verification:

```bash
PYTHONPATH=src pytest tests/conventions
```

## 7. Full Regression

Run the full suite after the migration.

Verification:

```bash
PYTHONPATH=src pytest
```
