# Files API File Plan

## New Files

### `src/cady/files/__init__.py`

Purpose: public namespace for file format facades.

Suggested contents:

```python
from cady.files import dxf, step, stl

__all__ = ["dxf", "step", "stl"]
```

### `src/cady/files/dxf.py`

Purpose: public DXF file facade.

Suggested functions:

```python
def write_drawing(drawing: Drawing2D | DxfDrawing, path: str | Path) -> object: ...
def write_model(model: Model, path: str | Path) -> Model: ...
def render_drawing(drawing: Drawing2D | DxfDrawing) -> str: ...
```

Do not add `read_drawing(...)` until DXF reading is actually supported.

### `src/cady/files/stl.py`

Purpose: public STL file facade.

Suggested functions:

```python
def write_mesh(mesh: StlMesh, path: str | Path, *, ascii: bool = False) -> StlMesh: ...
def write_model(
    model: Model,
    path: str | Path,
    *,
    ascii: bool = False,
    tolerance: float = 1e-3,
) -> Model: ...
```

### `src/cady/files/step.py`

Purpose: public STEP file facade.

Suggested functions:

```python
def write_model(model: Model, path: str | Path) -> Model: ...
def read_faces(path: str | Path) -> list[StepFace]: ...
def read_members(path: str | Path) -> list[ExtrudedMember]: ...
```

Do not add `read_model(...)` until STEP reconstruction into `Model` is
actually implemented.

## Existing Files To Touch

### `src/cady/domain/model.py`

Keep public object methods. Either leave current implementations in place or
make them thin delegates to `cady.files`.

If delegating, avoid circular imports by importing inside methods:

```python
def write_step(self, path: str | Path) -> Model:
    from cady.files.step import write_model

    write_model(self, path)
    return self
```

Add `Drawing2D.write_dxf(path)` if users should write named drawings directly.

### `src/cady/domain/drawing.py`

Keep `DxfDrawing.write(path)` for lower-level compatibility.

### `src/cady/domain/mesh.py`

Leave `StlMesh.write(...)` intact or route through `cady.files.stl.write_mesh`.

### `src/cady/__init__.py`

Optional: expose `files` at top-level only if the project wants
`from cady import files`.

Do not re-export every file helper at top-level unless there is a clear
ergonomic reason.

### `README.md`

Update architecture text:

- `cady.files`: public file namespace and implementation package.

### `tests/conventions/test_import_boundaries.py`

Add boundary checks for `cady.files`.

## Implementation Move

Implementation modules moved from:

- `src/cady/exporters/dxf/*`
- `src/cady/exporters/stl/*`
- `src/cady/exporters/step/*`
- `src/cady/importers/step/*`

to:

- `src/cady/files/dxf/*`
- `src/cady/files/stl/*`
- `src/cady/files/step/*`

The old `exporters` and `importers` packages are deleted.
