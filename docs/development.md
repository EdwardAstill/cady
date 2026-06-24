# Development

## Overview

Keep changes aligned with cady's boundaries: semantic domain objects,
primitive ops functions, validated numeric arrays, and small file writers.

## Details

## Environment

```bash
python -m venv .venv
.venv/bin/pip install -e . -r requirements-dev.txt
```

Optional extras:

```bash
.venv/bin/pip install -e '.[plotting]'
.venv/bin/pip install -e '.[visualisation]'
```

## Gates

```bash
.venv/bin/pytest -q
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
```

## Layout

```text
src/cady/build         factories
src/cady/domain        semantic objects
src/cady/ops           geometry algorithms
src/cady/numeric       evaluated geometry
src/cady/files         DXF/STL/STEP I/O
src/cady/plotting      optional static plotting
src/cady/visualisation optional interactive viewing
tests                  regression and convention tests
docs                   user and contributor docs
```

## Adding Features

For a 2D shape, add the frozen domain dataclass, implement
`bounds()`, `points()`, `close()`, `_transform2()`, and
`to_array(tolerance=...)`, then add public exports and tests.

For a 3D shape, add the frozen domain dataclass, implement `bounds()`,
`_transform3()`, and `to_array(tolerance=...)`, then add tessellation, public
exports, and tests. Add STEP support only when semantic STEP export is needed.

For ops functions, accept primitive values only. Do not import domain objects
from core ops modules.

For numeric types, validate arrays in `__post_init__` with
`cady.numeric.validation` helpers.

For file I/O, preserve semantic entities where the target format supports
them and tessellate only where the format requires evaluated geometry.

## Common Checks

Import-boundary failures usually mean a module-scope dependency crossed the
domain/numeric/ops/files boundary.

Cracked curved meshes usually mean caps and side walls do not share boundary
vertices, hole loops are wound incorrectly, or closed-solid edges are not
owned by exactly two triangles.

