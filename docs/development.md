# Development

Keep changes aligned with cady's package boundaries: immutable authoring
values, primitive ops functions, validated numeric arrays, and small file
facades.

## Environment

```bash
python -m venv .venv
.venv/bin/pip install --group dev -e .
```

Optional extras:

```bash
.venv/bin/pip install -e '.[plotting]'
.venv/bin/pip install -e '.[visualisation]'
.venv/bin/pip install -e '.[all]'
```

## Gates

```bash
.venv/bin/pytest -q
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
```

## Layout

```text
src/cady/geometry2d
src/cady/geometry3d
src/cady/drawing
src/cady/product
src/cady/view
src/cady/document.py
src/cady/numeric
src/cady/ops
src/cady/files
src/cady/visualisation
tests
docs
examples
```

## Adding 2D geometry

Add the frozen value object under `cady.geometry2d`, implement:

- `bounds()`
- `points()`
- `to_array(tolerance=...)`

Add a factory only when construction is common enough to justify one. Re-export
the public name from `cady.geometry2d.__init__` and `cady.__init__`, then add
tests under `tests/geometry2d`.

## Adding 3D geometry

Prefer features on `Body3D` or dedicated values under `cady.geometry3d`.
Meshable objects should expose:

- `to_mesh(tolerance=...)` when they are 3D authoring objects;
- `to_array(tolerance=...)` when they are already semantic mesh values.

Add tests under `tests/geometry3d`, `tests/product`, and `tests/files` when the
new behavior affects export.

## Adding ops functions

Ops functions must accept primitive values: arrays, tuples/lists, and scalars.
They should not import `cady.geometry2d`, `cady.geometry3d`, `cady.drawing`,
`cady.product`, or `cady.view`.

## Adding numeric types

Numeric types are frozen dataclasses with NumPy array fields. Validate arrays in
`__post_init__` with `cady.numeric.validation` helpers and provide
`.transformed(...)` where transforms make sense.

## Adding file I/O

Keep file modules import-light. Prefer public methods such as
`to_array(tolerance=...)` and `to_mesh(tolerance=...)` rather than inspecting
internal authoring state. Preserve semantic file entities where the format has
one, and sample only when the file format requires evaluated geometry.

## Common checks

Import-boundary failures usually mean a module-scope dependency crossed from
numeric/ops/files into an authoring or viewer package.

Mesh failures usually mean cap triangulation, side wall winding, or transform
composition changed. Add a small regression test around bounds and face counts
before widening the implementation.
