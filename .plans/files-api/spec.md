# Files API Plan

## Problem

The current public API exposes CAD file work through a mix of object methods
and implementation package names:

- object-level writes such as `Model.write_dxf(...)`, `Model.write_stl(...)`,
  `Model.write_step(...)`, and `DxfDrawing.write(...)`;
- direct imports from old implementation package names:
  `cady.exporters.*` and `cady.importers.*`;
- STEP import helpers whose names do not make the return target obvious at the
  top-level API.

The desired API should feel like "files/formats" to users, while preserving
the existing clean boundary where semantic CAD objects stay mostly
format-blind and format code remains in leaf modules.

## Decision

Use `cady.files` as the public file namespace and the home for format-specific
implementation modules.

Remove the old `cady.exporters` and `cady.importers` packages. Examples and
top-level public docs should use `cady.files`.

Use asymmetric read/write design:

- writes are owned by objects when the object determines the valid output;
- reads are owned by format modules and must name the target representation.

## Target API

### Write API

Object convenience methods stay public:

```python
model.write_dxf("plate.dxf")
model.write_stl("plate.stl")
model.write_step("plate.step")
drawing.write_dxf("drawing.dxf")
mesh.write("mesh.stl")
```

Format facade functions are also public for users who prefer explicit file
modules:

```python
from cady.files import dxf, step, stl

dxf.write_drawing(drawing, "drawing.dxf")
dxf.write_model(model, "model.dxf")
stl.write_model(model, "model.stl", tolerance=1e-3)
step.write_model(model, "model.step")
```

Avoid `obj.to_dxf(path)`. A `to_*` method should return a value, not write a
path. If added later, `to_dxf()` should return DXF text or a serializable
document value.

### Read API

Reads live on format modules and name the return target:

```python
from cady.files import step

faces = step.read_faces("member.step")
members = step.read_members("member.step")
```

Add broader reads only when the library truly supports that target:

```python
drawing = dxf.read_drawing("drawing.dxf")
model = step.read_model("assembly.step")
```

Do not add vague `read(path)` functions unless a format has exactly one
canonical return type.

## Module Boundaries

Target dependency direction:

```text
domain objects -> cady.files format modules
cady.files format modules -> domain/numeric/ops as needed
numeric -> no domain dependency
ops -> no new domain dependency
visualisation -> domain/numeric
```

Domain object write methods should remain thin and use lazy imports so normal
domain imports do not eagerly load all file format implementation code.

`cady.files` package `__init__` files expose stable public names. Format
submodules hold the DXF/STEP/STL rendering and parsing logic.

## Naming

Use:

- `write_model`, `write_drawing`, `write_mesh` for path-writing side effects;
- `render_*` for string/bytes generation;
- `read_faces`, `read_members`, `read_drawing`, `read_model` for imports;
- `to_*` only for in-memory conversion with a returned value.

Avoid:

- monkeypatching methods from `cady.files` onto domain objects;
- format modules with vague `read(...)` return types;
- reintroducing `cady.exporters` or `cady.importers` compatibility packages.

## Compatibility

This migration removes the old package names:

- keep existing `Model.write_*` behavior working;
- keep useful internal helpers importable from `cady.files.*`;
- add `Drawing2D.write_dxf(...)` if user-facing drawing writes should mirror
  `Model.write_dxf(...)`;
- update docs/examples to prefer `cady.files`;
- ensure `cady.exporters` and `cady.importers` no longer import.

## Done Criteria

- `cady.files` exists with `dxf`, `stl`, and `step` submodules.
- Public read functions name their target return type.
- Object write methods delegate through `cady.files` or remain equally thin.
- Existing tests continue to pass.
- New tests cover the facade functions and the absence of vague read APIs.
- README examples use the new public file API where relevant.
