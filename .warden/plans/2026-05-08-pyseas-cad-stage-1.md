# pyseas-cad Stage 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task when tasks are independent. For same-session manual execution, follow this plan directly. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a pure-stdlib Python `cad` package that turns format-blind 2D and 3D geometric primitives into DXF (R2018) and STL (binary + ASCII) files, with the API surface locked in `.warden/specs/2026-05-08-pyseas-cad-stage-1-design.md`.

**Architecture:** Three layers with a one-way dependency `write/ → scene/ → geom/ → _vendor/`. `geom/` holds frozen-dataclass value types split into disjoint `Shape2D` and `Shape3D` hierarchies. `scene/` owns per-format scene state (`DxfDrawing`, `StlMesh`). `write/` emits ASCII DXF and binary/ASCII STL. The vendored `mapbox-earcut` Python port lives under `src/cad/_vendor/` and is the only third-party code in the runtime path.

**Tech Stack:** Python 3.11+, stdlib only at runtime. Dev deps: `pytest`, `pyright` (strict), `ruff`, `ezdxf` (DXF round-trip verification), pure-Python `mapbox-earcut` port (vendored).

**Recommended Skills:** test-driven-development, python, git, verification-before-completion, refactoring, writing.

**Recommended MCPs:** context7 (for ezdxf API and DXF group-code lookups; mapbox-earcut Python port discovery).

**Machine plan:** 2026-05-08-pyseas-cad-stage-1.yaml

**Status:** draft
**Refinement passes:** 0

## Bootstrap context

The repo was initialised by the `writing-plans` skill before plan tasks begin. State at plan-write time:

- Branch `main` carries `IDEAS.md`, `.warden/specs/2026-05-08-pyseas-cad-stage-1-design.md`, `.warden/preference-lock.json`, `notes/dxf-format-cheatsheet.md`, `notes/step-format-cheatsheet.md`, `.gitignore`.
- Branch `stage-1` checked out at `.worktrees/stage-1/`. All plan tasks run inside that worktree.
- Plan tasks 1..N each commit to `stage-1`. The final `merge-and-cleanup` task fast-forward-merges `stage-1` into `main` and removes the worktree.

The spec carries a `## Bootstrap exception` block that records this prior work; do not re-execute `git init` or `git worktree add`.

## Assumptions

- `A1` — A pure-Python MIT-licensed port of `mapbox/earcut.hpp` (handles polygons with holes via the `[outer, hole1, hole2, …]` ring list with `holeIndices`) exists, is ≤ ~500 LOC, and can be vendored at a pinned commit.
  Type: external
  Source: spec §3.7 + §4 first open assumption.
  Check: `pip download joshuaskelly-earcut-python` or browse `pypi.org/project/mapbox-earcut`/community ports. Verify MIT licence and pure-Python (no C extension) install.
  If false: escalate; spec §5 names hand-rolled ear-clipping with holes as the fallback (~3–4 days extra).
  Owner: Task 24 (`vendor_earcut`).

- `A2` — Emitting only `LINE`, `LWPOLYLINE`, `CIRCLE`, `ARC`, `MTEXT` plus `HEADER` (`$ACADVER=AC1032`, `$INSUNITS=6`, `$EXTMIN`, `$EXTMAX`), `TABLES.LAYER`, an empty `BLOCKS` section, an `ENTITIES` section, an empty `OBJECTS` section, and `EOF` is enough for `ezdxf.readfile()` to open the file without warnings.
  Type: external
  Source: spec §4 second open assumption.
  Check: `ezdxf.readfile(path); doc.audit()` produces zero errors and zero warnings on a smoke fixture.
  If false: escalate; missing sections (CLASSES, OBJECTS-DICTIONARY) added incrementally with reference to ezdxf docs via context7.
  Owner: Task 33 (`dxf_writer_skeleton`) verify step.

- `A3` — Binary STL with an 80-byte zero header, a `uint32 LE` triangle count, and `count × (12 floats LE = 48 B + 2-byte attribute = 50 B)` records is accepted by mainstream STL readers (PrusaSlicer, MeshLab, `numpy-stl`).
  Type: external
  Source: spec §4 third open assumption.
  Check: Task 43 emits a 12-tri prism (684 bytes) and parses it back with `struct.unpack` against the canonical layout; manual smoke load in PrusaSlicer if a slicer is at hand.
  If false: escalate; STL format is bit-exact specified — a failure here means the writer has a layout bug to fix, not a spec change.
  Owner: Task 43 (`stl_writer_binary`).

- `A4` — Z-up STL geometry is correct for downstream slicers and CAM. Slicers normally accept any axis convention; the assumption is that "no rotation needed at import time" holds.
  Type: external
  Source: spec §4 fourth open assumption.
  Check: smoke-load the example `plate.stl` in PrusaSlicer (or equivalent) at the Task 49 step; assert plate sits flat without manual rotation.
  If false: log a `Known Limitations` entry; downstream callers can rotate at import.
  Owner: Task 49 (`example_plate_with_hole`).

- `A5` — Python 3.11+ `dataclasses(slots=True, frozen=True)` semantics are sufficient to express all geom value types without resorting to `__slots__` boilerplate. (3.11 fixed slots + inheritance interactions.)
  Type: architectural
  Source: spec §3.5 + §3.11 (Python 3.11+).
  Check: a single base + concrete subclass sample (`Shape2D` → `Line`) compiles, instances are immutable (`assert isinstance(line, Line); line.a = …` raises `FrozenInstanceError`), and `pyright --strict` is clean.
  If false: drop slots on the abstract base only and slot the concrete leaves; document why.
  Owner: Task 3 (`shape_base`).

- `A6` — The `pyright --strict` static type checker, configured against `src/cad/`, can express the disjoint Shape2D/Shape3D arity invariant (Shape2D.translate(2 args), Shape3D.translate(3 args)) so that `rectangle((0,0),(1,1)).translate(2,0,0)` is reported as a type error, as required by spec acceptance criteria.
  Type: design
  Source: spec acceptance lines 594–598.
  Check: `tests/geom/transform_typing.py` contains the named call patterns and `pyright --strict tests/geom/transform_typing.py` exits non-zero against the wrong-arity calls (verified with `# type: ignore[unused-ignore]` machinery or the dedicated `assert_type` pattern).
  Owner: Task 15 (`transform_arity_typing_2d`).

---

## File Structure

```
.worktrees/stage-1/
├── pyproject.toml                              # build config, pyright/ruff/pytest config, no runtime deps
├── NOTICE                                      # mapbox-earcut attribution + commit pin
├── README.md                                   # one-screen quickstart pointing at examples/
├── examples/
│   └── plate_with_hole.py                      # end-to-end DXF + STL example, CLI --out
├── src/cad/
│   ├── __init__.py                             # re-exports factory funcs, scenes, errors
│   ├── errors.py                               # CadError, SceneError, WriteError
│   ├── geom/
│   │   ├── __init__.py                         # re-exports types and factory funcs
│   │   ├── vec.py                              # Vec2, Vec3 frozen dataclasses
│   │   ├── base.py                             # Shape2D, Shape3D abstract bases
│   │   ├── shapes2d.py                         # Line, Arc, Circle, Rectangle, Polyline, Spline, Path
│   │   ├── shapes3d.py                         # Sphere, Prism, Extrusion, Revolution
│   │   ├── factories.py                        # line(), arc(), circle(), rectangle(), polyline(), spline(), sphere(), prism()
│   │   └── tessellate.py                       # curves_to_polyline, polygon_to_triangles, extrusion_to_triangles, revolution_to_triangles
│   ├── scene/
│   │   ├── __init__.py                         # re-exports DxfDrawing, StlMesh, Layer
│   │   ├── dxf.py                              # DxfDrawing, Layer
│   │   └── stl.py                              # StlMesh
│   ├── write/
│   │   ├── __init__.py
│   │   ├── dxf/
│   │   │   ├── __init__.py
│   │   │   ├── codes.py                        # group code constants
│   │   │   ├── emit.py                         # group-code emitter helpers
│   │   │   ├── sections.py                     # HEADER/TABLES/BLOCKS/ENTITIES/OBJECTS/EOF
│   │   │   └── entities.py                     # LINE, LWPOLYLINE, CIRCLE, ARC, MTEXT formatters
│   │   └── stl/
│   │       ├── __init__.py
│   │       ├── ascii.py                        # ASCII STL emitter
│   │       └── binary.py                       # binary STL emitter
│   └── _vendor/
│       ├── __init__.py
│       └── earcut.py                           # vendored mapbox-earcut (MIT)
└── tests/
    ├── conftest.py                             # tmp_path helpers, ezdxf import guard
    ├── geom/
    │   ├── test_vec.py
    │   ├── test_shape_base.py
    │   ├── test_line.py
    │   ├── test_arc.py
    │   ├── test_circle.py
    │   ├── test_rectangle.py
    │   ├── test_polyline.py
    │   ├── test_spline.py
    │   ├── test_path.py
    │   ├── test_close.py
    │   ├── test_with_hole.py
    │   ├── test_transforms_2d.py
    │   ├── test_subtract_typeerror.py
    │   ├── test_sphere.py
    │   ├── test_prism.py
    │   ├── test_extrusion_value.py
    │   ├── test_revolution_value.py
    │   ├── test_extrude_method.py
    │   ├── test_revolve_method.py
    │   ├── test_transforms_3d.py
    │   ├── test_curves_to_polyline.py
    │   ├── test_polygon_to_triangles.py
    │   ├── test_extrusion_to_triangles.py
    │   ├── test_revolution_to_triangles.py
    │   └── transform_typing.py                 # pyright-strict typing assertions
    ├── scene/
    │   ├── test_dxf_drawing.py
    │   ├── test_dxf_text.py
    │   └── test_stl_mesh.py
    ├── write/
    │   ├── goldens/                            # expected DXF byte strings for smoke cases
    │   │   └── smoke.dxf
    │   ├── test_dxf_skeleton.py
    │   ├── test_dxf_layers.py
    │   ├── test_dxf_entities.py                # one round-trip test per entity type
    │   ├── test_dxf_path_decompose.py
    │   ├── test_dxf_holes_decompose.py
    │   ├── test_dxf_writeerror.py
    │   ├── test_dxf_golden.py
    │   ├── test_stl_binary.py
    │   ├── test_stl_ascii.py
    │   ├── test_stl_dispatcher.py
    │   ├── test_stl_writeerror.py
    │   └── test_stl_invariants.py
    ├── errors/
    │   └── test_error_tiers.py
    ├── conventions/
    │   └── test_stdlib_only.py
    └── examples/
        └── test_plate_with_hole.py
```

Deps live as: `geom/` imports only `_vendor` and stdlib. `scene/` imports `geom` only. `write/` imports `scene` and `geom`. The `tests/conventions/test_stdlib_only.py` test makes this contract executable.

---

## Phase A — Scaffold (1 task)

### Task 1: scaffold

**Files:**
- Create: `pyproject.toml`, `NOTICE`, `README.md`, `src/cad/__init__.py`, `src/cad/_vendor/__init__.py`, `tests/conftest.py`, `tests/__init__.py`
- Create: `.python-version` (`3.11` or newer)

**Ownership:**
- In scope: every file listed above.
- Out of scope: any `cad.geom`, `cad.scene`, `cad.write` source.

**Assumption refs:** `A5`

**Invoke skill:** `python` before starting this task.

- [ ] **Step 1: Write the failing test**

`tests/test_smoke_import.py`:

```python
def test_package_importable():
    import cad
    assert hasattr(cad, "__version__")

def test_runtime_has_no_external_deps():
    import importlib.metadata as md
    dist = md.distribution("pyseas-cad")
    requires = dist.requires or []
    runtime = [r for r in requires if "; extra ==" not in r]
    assert runtime == [], f"runtime deps must be empty, got {runtime}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_smoke_import.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'cad'` or `PackageNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

`pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pyseas-cad"
version = "0.1.0.dev0"
description = "Pure-Python write-only CAD library producing DXF and STL from format-blind primitives."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "Edward Astill", email = "edwardast.ll@gmail.com" }]
dependencies = []

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pyright>=1.1.350",
  "ruff>=0.4",
  "ezdxf>=1.3",
]

[tool.hatch.build.targets.wheel]
packages = ["src/cad"]

[tool.pytest.ini_options]
addopts = "-ra"
testpaths = ["tests"]
pythonpath = ["src"]

[tool.pyright]
include = ["src/cad", "tests"]
strict = ["src/cad"]
pythonVersion = "3.11"
typeCheckingMode = "strict"

[tool.ruff]
src = ["src", "tests"]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]
```

`src/cad/__init__.py`:

```python
"""pyseas-cad — write-only CAD library (DXF + STL).

See `.warden/specs/2026-05-08-pyseas-cad-stage-1-design.md` for the contract.
"""
from __future__ import annotations

__version__ = "0.1.0.dev0"

__all__: list[str] = []
```

`src/cad/_vendor/__init__.py`: empty.

`NOTICE`:

```
pyseas-cad
==========

Copyright (c) 2026 Edward Astill.

This product includes vendored third-party code (see src/cad/_vendor/).
Each vendored module retains its upstream licence and attribution; see the
top of each file under src/cad/_vendor/.
```

`README.md`: one-paragraph stub describing scope and pointing at the spec.

`tests/conftest.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
```

- [ ] **Step 4: Install in editable mode and run the test**

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest tests/test_smoke_import.py -q
```

Expected: 2 passed.

- [ ] **Step 5: Verify static-analysis tooling installs cleanly**

```bash
.venv/bin/pyright --version
.venv/bin/ruff --version
```

Both exit 0 with version strings.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml NOTICE README.md src/cad/__init__.py src/cad/_vendor/__init__.py tests/conftest.py tests/__init__.py tests/test_smoke_import.py .python-version
git commit -m "feat: scaffold pyseas-cad package (no runtime deps)"
```

**Acceptance for Task 1:**
- `pytest tests/test_smoke_import.py -q` exits 0 with 2 passed.
- `python -c "import cad; print(cad.__version__)"` prints `0.1.0.dev0`.
- `pip show pyseas-cad` lists no runtime requires.

---

## Phase B — Geom 2D value types and operations (14 tasks)

### Task 2: vec_types

**Files:**
- Create: `src/cad/geom/__init__.py` (empty for now), `src/cad/geom/vec.py`, `tests/geom/__init__.py`, `tests/geom/test_vec.py`

**Ownership:**
- In scope: `src/cad/geom/vec.py`, the two new `__init__.py` files, `tests/geom/test_vec.py`.
- Out of scope: any concrete shape type.

**Assumption refs:** `A5`

**Invoke skill:** `test-driven-development` before starting.

- [ ] **Step 1: Write the failing test**

`tests/geom/test_vec.py`:

```python
import math
import pytest
from cad.geom.vec import Vec2, Vec3

def test_vec2_basic():
    a = Vec2(1.0, 2.0)
    b = Vec2(3.0, 4.0)
    assert a + b == Vec2(4.0, 6.0)
    assert b - a == Vec2(2.0, 2.0)
    assert -a == Vec2(-1.0, -2.0)
    assert a * 2 == Vec2(2.0, 4.0)
    assert a.dot(b) == 11.0
    assert a.length() == pytest.approx(math.sqrt(5))
    assert a.normalised().length() == pytest.approx(1.0)

def test_vec2_immutable():
    a = Vec2(1.0, 2.0)
    with pytest.raises(Exception):
        a.x = 3.0  # type: ignore[misc]

def test_vec3_basic_and_cross():
    a = Vec3(1.0, 0.0, 0.0)
    b = Vec3(0.0, 1.0, 0.0)
    assert a.cross(b) == Vec3(0.0, 0.0, 1.0)
    assert (a + b).length() == pytest.approx(math.sqrt(2))

def test_vec_rejects_nan():
    with pytest.raises(ValueError):
        Vec2(math.nan, 0.0)
    with pytest.raises(ValueError):
        Vec3(0.0, 0.0, math.inf)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/geom/test_vec.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'cad.geom.vec'`.

- [ ] **Step 3: Write minimal implementation**

`src/cad/geom/vec.py`:

```python
from __future__ import annotations

import math
from dataclasses import dataclass


def _check_finite(*values: float) -> None:
    for v in values:
        if not math.isfinite(v):
            raise ValueError(f"coordinate must be finite, got {v}")


@dataclass(frozen=True, slots=True)
class Vec2:
    x: float
    y: float

    def __post_init__(self) -> None:
        _check_finite(self.x, self.y)

    def __add__(self, other: Vec2) -> Vec2: return Vec2(self.x + other.x, self.y + other.y)
    def __sub__(self, other: Vec2) -> Vec2: return Vec2(self.x - other.x, self.y - other.y)
    def __neg__(self) -> Vec2: return Vec2(-self.x, -self.y)
    def __mul__(self, k: float) -> Vec2: return Vec2(self.x * k, self.y * k)
    def dot(self, other: Vec2) -> float: return self.x * other.x + self.y * other.y
    def length(self) -> float: return math.hypot(self.x, self.y)
    def normalised(self) -> Vec2:
        n = self.length()
        if n == 0.0:
            raise ValueError("cannot normalise zero vector")
        return Vec2(self.x / n, self.y / n)


@dataclass(frozen=True, slots=True)
class Vec3:
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        _check_finite(self.x, self.y, self.z)

    def __add__(self, other: Vec3) -> Vec3: return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)
    def __sub__(self, other: Vec3) -> Vec3: return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)
    def __neg__(self) -> Vec3: return Vec3(-self.x, -self.y, -self.z)
    def __mul__(self, k: float) -> Vec3: return Vec3(self.x * k, self.y * k, self.z * k)
    def dot(self, other: Vec3) -> float: return self.x * other.x + self.y * other.y + self.z * other.z
    def length(self) -> float: return math.sqrt(self.dot(self))
    def normalised(self) -> Vec3:
        n = self.length()
        if n == 0.0:
            raise ValueError("cannot normalise zero vector")
        return Vec3(self.x / n, self.y / n, self.z / n)
    def cross(self, other: Vec3) -> Vec3:
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/geom/test_vec.py -q`
Expected: 4 passed.

- [ ] **Step 5: Type-check**

Run: `pyright --strict src/cad/geom/vec.py`
Expected: 0 errors, 0 warnings.

- [ ] **Step 6: Commit**

```bash
git add src/cad/geom/__init__.py src/cad/geom/vec.py tests/geom/__init__.py tests/geom/test_vec.py
git commit -m "feat(geom): add immutable Vec2 / Vec3 with finite-coordinate validation"
```

---

### Task 3: shape_base

**Files:**
- Create: `src/cad/geom/base.py`, `tests/geom/test_shape_base.py`

**Ownership:**
- In scope: `src/cad/geom/base.py`, `tests/geom/test_shape_base.py`.
- Out of scope: any concrete shape.

**Assumption refs:** `A5`

**Invoke skill:** `test-driven-development` before starting.

- [ ] **Step 1: Write the failing test**

`tests/geom/test_shape_base.py`:

```python
import pytest
from cad.geom.base import Shape2D, Shape3D, Axis, parse_axis
from cad.geom.vec import Vec3

def test_shape_classes_are_disjoint():
    assert not issubclass(Shape2D, Shape3D)
    assert not issubclass(Shape3D, Shape2D)

def test_axis_string_parses_to_unit_vec3():
    assert parse_axis("+z") == Vec3(0.0, 0.0, 1.0)
    assert parse_axis("-x") == Vec3(-1.0, 0.0, 0.0)
    assert parse_axis(Vec3(1.0, 1.0, 0.0)).length() == pytest.approx(1.0)

def test_axis_rejects_garbage():
    with pytest.raises(ValueError):
        parse_axis("diagonal")
    with pytest.raises(ValueError):
        parse_axis(Vec3(0.0, 0.0, 0.0))

def test_shape2d_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        Shape2D()  # type: ignore[abstract]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/geom/test_shape_base.py -q`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Write minimal implementation**

`src/cad/geom/base.py`:

```python
from __future__ import annotations

from abc import ABC
from typing import Literal, Union

from cad.geom.vec import Vec3

AxisString = Literal["+x", "-x", "+y", "-y", "+z", "-z"]
Axis = Union[AxisString, Vec3]

_AXIS_TABLE: dict[str, Vec3] = {
    "+x": Vec3(1.0, 0.0, 0.0),
    "-x": Vec3(-1.0, 0.0, 0.0),
    "+y": Vec3(0.0, 1.0, 0.0),
    "-y": Vec3(0.0, -1.0, 0.0),
    "+z": Vec3(0.0, 0.0, 1.0),
    "-z": Vec3(0.0, 0.0, -1.0),
}


def parse_axis(axis: Axis) -> Vec3:
    if isinstance(axis, str):
        try:
            return _AXIS_TABLE[axis]
        except KeyError as exc:
            raise ValueError(f"unknown axis string {axis!r}; expected one of {sorted(_AXIS_TABLE)}") from exc
    if axis.length() == 0.0:
        raise ValueError("axis vector must be non-zero")
    return axis.normalised()


class Shape2D(ABC):
    """Abstract base for 2D shapes. 2D and 3D hierarchies are disjoint."""
    __slots__ = ()


class Shape3D(ABC):
    """Abstract base for 3D shapes. 2D and 3D hierarchies are disjoint."""
    __slots__ = ()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/geom/test_shape_base.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/base.py tests/geom/test_shape_base.py
git commit -m "feat(geom): add Shape2D / Shape3D abstract bases and Axis parser"
```

---

### Task 4: shape2d_line

**Files:**
- Create: `src/cad/geom/shapes2d.py`, `src/cad/geom/factories.py`, `tests/geom/test_line.py`

**Ownership:**
- In scope: only `Line` class plus `line()` factory plus tests.
- Out of scope: arc, circle, rectangle, polyline, spline, path, transforms.

**Invoke skill:** `test-driven-development` before starting.

- [ ] **Step 1: Write the failing test**

`tests/geom/test_line.py`:

```python
import pytest
from cad import line
from cad.geom.shapes2d import Line
from cad.geom.vec import Vec2

def test_line_factory_promotes_tuples():
    seg = line((0.0, 0.0), (1.0, 0.0))
    assert isinstance(seg, Line)
    assert seg.a == Vec2(0.0, 0.0)
    assert seg.b == Vec2(1.0, 0.0)
    assert seg.closed is False

def test_line_bounds():
    seg = line((1.0, 2.0), (3.0, 0.5))
    lo, hi = seg.bounds()
    assert lo == Vec2(1.0, 0.5)
    assert hi == Vec2(3.0, 2.0)

def test_line_zero_length_rejected():
    with pytest.raises(ValueError):
        line((1.0, 2.0), (1.0, 2.0))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/geom/test_line.py -q`
Expected: FAIL with `ImportError` (no `cad.line`).

- [ ] **Step 3: Write minimal implementation**

`src/cad/geom/shapes2d.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from cad.geom.base import Shape2D
from cad.geom.vec import Vec2


def _to_vec2(p: Vec2 | tuple[float, float]) -> Vec2:
    if isinstance(p, Vec2):
        return p
    x, y = p
    return Vec2(float(x), float(y))


@dataclass(frozen=True, slots=True)
class Line(Shape2D):
    a: Vec2
    b: Vec2
    closed: bool = False  # always False for Line as a value; .close() returns the same Line

    def __post_init__(self) -> None:
        if self.a == self.b:
            raise ValueError(f"Line endpoints must differ; got both = {self.a}")

    def bounds(self) -> tuple[Vec2, Vec2]:
        lo = Vec2(min(self.a.x, self.b.x), min(self.a.y, self.b.y))
        hi = Vec2(max(self.a.x, self.b.x), max(self.a.y, self.b.y))
        return lo, hi
```

`src/cad/geom/factories.py`:

```python
from __future__ import annotations

from cad.geom.shapes2d import Line, _to_vec2
from cad.geom.vec import Vec2


def line(a: Vec2 | tuple[float, float], b: Vec2 | tuple[float, float]) -> Line:
    return Line(_to_vec2(a), _to_vec2(b))
```

`src/cad/__init__.py` — append:

```python
from cad.geom.factories import line as line  # noqa: F401

__all__ = ["line"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/geom/test_line.py -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/shapes2d.py src/cad/geom/factories.py src/cad/__init__.py tests/geom/test_line.py
git commit -m "feat(geom): add Line + line() factory with zero-length rejection"
```

---

### Task 5: shape2d_arc

**Files:**
- Modify: `src/cad/geom/shapes2d.py`, `src/cad/geom/factories.py`, `src/cad/__init__.py`
- Create: `tests/geom/test_arc.py`

**Ownership:**
- In scope: `Arc` class, `arc()` factory, tests.
- Out of scope: tessellation; Path composition.

**Invoke skill:** `test-driven-development`.

- [ ] **Step 1: Write the failing test**

`tests/geom/test_arc.py`:

```python
import math
import pytest
from cad import arc
from cad.geom.shapes2d import Arc
from cad.geom.vec import Vec2

def test_arc_factory_promotes_centre():
    a = arc((0.0, 0.0), 1.0, 0.0, math.pi)
    assert isinstance(a, Arc)
    assert a.centre == Vec2(0.0, 0.0)
    assert a.radius == 1.0
    assert a.start_rad == 0.0
    assert a.end_rad == pytest.approx(math.pi)

def test_arc_negative_radius_rejected():
    with pytest.raises(ValueError):
        arc((0, 0), -1.0, 0.0, math.pi)

def test_arc_zero_sweep_rejected():
    with pytest.raises(ValueError):
        arc((0, 0), 1.0, 1.0, 1.0)

def test_arc_bounds_half_circle_top():
    # half-circle from 0 to pi sweeps the upper half of the unit circle
    a = arc((0, 0), 1.0, 0.0, math.pi)
    lo, hi = a.bounds()
    assert lo == Vec2(-1.0, 0.0)
    assert hi == Vec2(1.0, 1.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/geom/test_arc.py -q`
Expected: FAIL with `ImportError` (no `cad.arc`).

- [ ] **Step 3: Write minimal implementation**

In `src/cad/geom/shapes2d.py` add:

```python
import math

@dataclass(frozen=True, slots=True)
class Arc(Shape2D):
    centre: Vec2
    radius: float
    start_rad: float
    end_rad: float
    closed: bool = False

    def __post_init__(self) -> None:
        if self.radius <= 0.0:
            raise ValueError(f"Arc radius must be > 0, got {self.radius}")
        if self.start_rad == self.end_rad:
            raise ValueError("Arc sweep must be non-zero")

    def bounds(self) -> tuple[Vec2, Vec2]:
        # walk the sweep at quadrant boundaries plus endpoints
        s, e = self.start_rad, self.end_rad
        if e < s:
            s, e = e, s
        candidates: list[Vec2] = [
            Vec2(self.centre.x + self.radius * math.cos(self.start_rad),
                 self.centre.y + self.radius * math.sin(self.start_rad)),
            Vec2(self.centre.x + self.radius * math.cos(self.end_rad),
                 self.centre.y + self.radius * math.sin(self.end_rad)),
        ]
        # check each cardinal direction inside [s, e] modulo 2π
        for k in range(-2, 6):
            theta = k * math.pi / 2
            if s <= theta <= e:
                candidates.append(Vec2(
                    self.centre.x + self.radius * math.cos(theta),
                    self.centre.y + self.radius * math.sin(theta),
                ))
        xs = [v.x for v in candidates]
        ys = [v.y for v in candidates]
        return Vec2(min(xs), min(ys)), Vec2(max(xs), max(ys))
```

In `src/cad/geom/factories.py` add:

```python
def arc(centre: Vec2 | tuple[float, float], radius: float, start: float, end: float):
    from cad.geom.shapes2d import Arc
    return Arc(_to_vec2(centre), float(radius), float(start), float(end))
```

In `src/cad/__init__.py` re-export `arc` and append it to `__all__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/geom/test_arc.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/shapes2d.py src/cad/geom/factories.py src/cad/__init__.py tests/geom/test_arc.py
git commit -m "feat(geom): add Arc + arc() factory with radius/sweep validation and bounds"
```

---

### Task 6: shape2d_circle

**Files:**
- Modify: `src/cad/geom/shapes2d.py`, `src/cad/geom/factories.py`, `src/cad/__init__.py`
- Create: `tests/geom/test_circle.py`

**Invoke skill:** `test-driven-development`.

- [ ] **Step 1: Write the failing test**

```python
# tests/geom/test_circle.py
import pytest
from cad import circle
from cad.geom.shapes2d import Circle
from cad.geom.vec import Vec2

def test_circle_is_always_closed():
    c = circle((0, 0), 1.0)
    assert isinstance(c, Circle)
    assert c.closed is True
    assert c.centre == Vec2(0, 0)
    assert c.radius == 1.0

def test_circle_negative_radius_rejected():
    with pytest.raises(ValueError):
        circle((0, 0), -1.0)

def test_circle_zero_radius_rejected():
    with pytest.raises(ValueError):
        circle((0, 0), 0.0)

def test_circle_bounds():
    c = circle((1, 2), 3.0)
    lo, hi = c.bounds()
    assert lo == Vec2(-2.0, -1.0)
    assert hi == Vec2(4.0, 5.0)
```

- [ ] **Step 2: Run to verify it fails**

`pytest tests/geom/test_circle.py -q` → FAIL.

- [ ] **Step 3: Write implementation**

Append to `shapes2d.py`:

```python
@dataclass(frozen=True, slots=True)
class Circle(Shape2D):
    centre: Vec2
    radius: float
    closed: bool = True  # circles are always closed
    inner_loops: tuple["Shape2D", ...] = ()  # populated by .with_hole / .with_holes

    def __post_init__(self) -> None:
        if self.radius <= 0.0:
            raise ValueError(f"Circle radius must be > 0, got {self.radius}")
        if self.closed is False:
            raise ValueError("Circle is always closed")

    def bounds(self) -> tuple[Vec2, Vec2]:
        return (
            Vec2(self.centre.x - self.radius, self.centre.y - self.radius),
            Vec2(self.centre.x + self.radius, self.centre.y + self.radius),
        )
```

Append to `factories.py`:

```python
def circle(centre: Vec2 | tuple[float, float], radius: float):
    from cad.geom.shapes2d import Circle
    return Circle(_to_vec2(centre), float(radius))
```

Re-export `circle` in `cad/__init__.py`.

- [ ] **Step 4: Run tests** → 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/shapes2d.py src/cad/geom/factories.py src/cad/__init__.py tests/geom/test_circle.py
git commit -m "feat(geom): add Circle + circle() factory; always-closed invariant"
```

---

### Task 7: shape2d_rectangle

**Files:**
- Modify: `src/cad/geom/shapes2d.py`, `src/cad/geom/factories.py`, `src/cad/__init__.py`
- Create: `tests/geom/test_rectangle.py`

- [ ] **Step 1: Write failing test**

```python
# tests/geom/test_rectangle.py
import pytest
from cad import rectangle
from cad.geom.shapes2d import Rectangle
from cad.geom.vec import Vec2

def test_rectangle_factory():
    r = rectangle((1, 2), (3, 4))
    assert isinstance(r, Rectangle)
    assert r.origin == Vec2(1, 2)
    assert r.size == Vec2(3, 4)
    assert r.closed is True

def test_rectangle_zero_size_rejected():
    with pytest.raises(ValueError):
        rectangle((0, 0), (0, 1))
    with pytest.raises(ValueError):
        rectangle((0, 0), (1, 0))

def test_rectangle_negative_size_rejected():
    with pytest.raises(ValueError):
        rectangle((0, 0), (-1, 1))

def test_rectangle_bounds():
    r = rectangle((1, 2), (3, 4))
    lo, hi = r.bounds()
    assert lo == Vec2(1, 2)
    assert hi == Vec2(4, 6)
```

- [ ] **Step 2: Run to verify it fails**

`pytest tests/geom/test_rectangle.py -q` → FAIL.

- [ ] **Step 3: Write implementation**

Append to `shapes2d.py`:

```python
@dataclass(frozen=True, slots=True)
class Rectangle(Shape2D):
    origin: Vec2
    size: Vec2
    closed: bool = True
    inner_loops: tuple["Shape2D", ...] = ()

    def __post_init__(self) -> None:
        if self.size.x <= 0.0 or self.size.y <= 0.0:
            raise ValueError(f"Rectangle size must have positive width and height, got {self.size}")

    def bounds(self) -> tuple[Vec2, Vec2]:
        return self.origin, Vec2(self.origin.x + self.size.x, self.origin.y + self.size.y)
```

Append to `factories.py`:

```python
def rectangle(corner: Vec2 | tuple[float, float], size: Vec2 | tuple[float, float]):
    from cad.geom.shapes2d import Rectangle
    return Rectangle(_to_vec2(corner), _to_vec2(size))
```

Re-export `rectangle`.

- [ ] **Step 4: Run tests** → 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/shapes2d.py src/cad/geom/factories.py src/cad/__init__.py tests/geom/test_rectangle.py
git commit -m "feat(geom): add Rectangle + rectangle() factory"
```

---

### Task 8: shape2d_polyline

**Files:**
- Modify: `src/cad/geom/shapes2d.py`, `src/cad/geom/factories.py`, `src/cad/__init__.py`
- Create: `tests/geom/test_polyline.py`

- [ ] **Step 1: Write failing test**

```python
# tests/geom/test_polyline.py
import pytest
from cad import polyline
from cad.geom.shapes2d import Polyline
from cad.geom.vec import Vec2

def test_polyline_open():
    pl = polyline([(0, 0), (1, 0), (1, 1)])
    assert isinstance(pl, Polyline)
    assert pl.points == (Vec2(0, 0), Vec2(1, 0), Vec2(1, 1))
    assert pl.closed is False

def test_polyline_closed_flag():
    pl = polyline([(0, 0), (1, 0), (1, 1)], closed=True)
    assert pl.closed is True

def test_polyline_empty_rejected():
    with pytest.raises(ValueError):
        polyline([])

def test_polyline_single_point_rejected():
    with pytest.raises(ValueError):
        polyline([(0, 0)])

def test_polyline_closed_single_segment_rejected():
    with pytest.raises(ValueError):
        polyline([(0, 0)], closed=True)

def test_polyline_bounds():
    pl = polyline([(0, 0), (1, 2), (-1, 5)])
    lo, hi = pl.bounds()
    assert lo == Vec2(-1, 0)
    assert hi == Vec2(1, 5)
```

- [ ] **Step 2: Run to verify it fails**

`pytest tests/geom/test_polyline.py -q` → FAIL.

- [ ] **Step 3: Implementation**

Append to `shapes2d.py`:

```python
@dataclass(frozen=True, slots=True)
class Polyline(Shape2D):
    points: tuple[Vec2, ...]
    closed: bool = False
    inner_loops: tuple["Shape2D", ...] = ()

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError(f"Polyline needs ≥ 2 points, got {len(self.points)}")
        if self.closed and len(self.points) < 3:
            raise ValueError(f"Closed polyline needs ≥ 3 points, got {len(self.points)}")

    def bounds(self) -> tuple[Vec2, Vec2]:
        xs = [p.x for p in self.points]; ys = [p.y for p in self.points]
        return Vec2(min(xs), min(ys)), Vec2(max(xs), max(ys))
```

Append to `factories.py`:

```python
def polyline(points: list[Vec2 | tuple[float, float]], closed: bool = False):
    from cad.geom.shapes2d import Polyline
    return Polyline(tuple(_to_vec2(p) for p in points), closed)
```

Re-export `polyline`.

- [ ] **Step 4: Run** → 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/shapes2d.py src/cad/geom/factories.py src/cad/__init__.py tests/geom/test_polyline.py
git commit -m "feat(geom): add Polyline + polyline() factory with point-count validation"
```

---

### Task 9: shape2d_spline

**Files:**
- Modify: `src/cad/geom/shapes2d.py`, `src/cad/geom/factories.py`, `src/cad/__init__.py`
- Create: `tests/geom/test_spline.py`

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_spline.py
import pytest
from cad import spline
from cad.geom.shapes2d import Spline
from cad.geom.vec import Vec2

def test_spline_minimal_three_plus_one():
    s = spline([(0, 0), (1, 1), (2, -1), (3, 0)])  # one cubic Bezier (3*1+1 = 4 points)
    assert isinstance(s, Spline)
    assert s.control_points[0] == Vec2(0, 0)

def test_spline_two_segments():
    pts = [(0, 0), (1, 1), (2, -1), (3, 0), (4, 1), (5, -1), (6, 0)]  # 3*2+1 = 7
    s = spline(pts)
    assert len(s.control_points) == 7

def test_spline_bad_count_rejected():
    with pytest.raises(ValueError):
        spline([(0, 0), (1, 1), (2, 0)])  # 3 points, not 3n+1
    with pytest.raises(ValueError):
        spline([(0, 0)])
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

Append to `shapes2d.py`:

```python
@dataclass(frozen=True, slots=True)
class Spline(Shape2D):
    control_points: tuple[Vec2, ...]
    closed: bool = False
    inner_loops: tuple["Shape2D", ...] = ()

    def __post_init__(self) -> None:
        n = len(self.control_points)
        if n < 4 or (n - 1) % 3 != 0:
            raise ValueError(f"Spline needs 3n+1 control points (4, 7, 10, …), got {n}")

    def bounds(self) -> tuple[Vec2, Vec2]:
        xs = [p.x for p in self.control_points]; ys = [p.y for p in self.control_points]
        return Vec2(min(xs), min(ys)), Vec2(max(xs), max(ys))
```

Append to `factories.py`:

```python
def spline(control_points: list[Vec2 | tuple[float, float]]):
    from cad.geom.shapes2d import Spline
    return Spline(tuple(_to_vec2(p) for p in control_points))
```

Re-export `spline`.

- [ ] **Step 4: Run** → 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/shapes2d.py src/cad/geom/factories.py src/cad/__init__.py tests/geom/test_spline.py
git commit -m "feat(geom): add Spline + spline() factory; cubic-Bezier 3n+1 invariant"
```

---

### Task 10: shape2d_path

**Files:**
- Modify: `src/cad/geom/shapes2d.py`, `src/cad/geom/base.py` (add `__add__` on `Shape2D`)
- Create: `tests/geom/test_path.py`

**Notes:** The `+` operator on any Shape2D pair returns a `Path` whose `segments` is the flattened head-to-tail concatenation. Endpoints must match.

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_path.py
import pytest
import math
from cad import line, arc
from cad.geom.shapes2d import Path

def test_two_lines_compose_into_path():
    p = line((0, 0), (1, 0)) + line((1, 0), (1, 1))
    assert isinstance(p, Path)
    assert len(p.segments) == 2
    assert p.closed is False

def test_three_segments_chain():
    p = line((0, 0), (1, 0)) + line((1, 0), (1, 1)) + line((1, 1), (0, 1))
    assert len(p.segments) == 3

def test_endpoint_mismatch_rejected():
    with pytest.raises(ValueError):
        line((0, 0), (1, 0)) + line((0.5, 0), (2, 0))

def test_arc_concatenation():
    p = line((-1, 0), (1, 0)) + arc((0, 0), 1.0, 0.0, math.pi)
    assert len(p.segments) == 2
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

In `shapes2d.py`:

```python
def _endpoints(seg: Shape2D) -> tuple[Vec2, Vec2]:
    import math
    if isinstance(seg, Line):
        return seg.a, seg.b
    if isinstance(seg, Arc):
        s, e = seg.start_rad, seg.end_rad
        return (
            Vec2(seg.centre.x + seg.radius * math.cos(s), seg.centre.y + seg.radius * math.sin(s)),
            Vec2(seg.centre.x + seg.radius * math.cos(e), seg.centre.y + seg.radius * math.sin(e)),
        )
    if isinstance(seg, Polyline):
        return seg.points[0], seg.points[-1]
    if isinstance(seg, Spline):
        return seg.control_points[0], seg.control_points[-1]
    if isinstance(seg, Path):
        return _endpoints(seg.segments[0])[0], _endpoints(seg.segments[-1])[1]
    raise TypeError(f"cannot compose shape of type {type(seg).__name__}")


@dataclass(frozen=True, slots=True)
class Path(Shape2D):
    segments: tuple[Shape2D, ...]
    closed: bool = False
    inner_loops: tuple["Shape2D", ...] = ()

    def __post_init__(self) -> None:
        if len(self.segments) < 1:
            raise ValueError("Path needs ≥ 1 segment")
        for prev, nxt in zip(self.segments, self.segments[1:]):
            _, p_end = _endpoints(prev)
            n_start, _ = _endpoints(nxt)
            if p_end != n_start:
                raise ValueError(f"Path segment endpoints don't match: {p_end} vs {n_start}")

    def bounds(self) -> tuple[Vec2, Vec2]:
        bs = [s.bounds() for s in self.segments]
        xs_lo = [b[0].x for b in bs]; ys_lo = [b[0].y for b in bs]
        xs_hi = [b[1].x for b in bs]; ys_hi = [b[1].y for b in bs]
        return Vec2(min(xs_lo), min(ys_lo)), Vec2(max(xs_hi), max(ys_hi))
```

In `base.py` add to `Shape2D`:

```python
class Shape2D(ABC):
    __slots__ = ()
    def __add__(self, other: "Shape2D") -> "Shape2D":
        from cad.geom.shapes2d import Path
        left = self.segments if isinstance(self, Path) else (self,)
        right = other.segments if isinstance(other, Path) else (other,)
        return Path(tuple(left) + tuple(right))
```

- [ ] **Step 4: Run** → 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/shapes2d.py src/cad/geom/base.py tests/geom/test_path.py
git commit -m "feat(geom): add Path + Shape2D.__add__ head-to-tail composition"
```

---

### Task 11: shape2d_close

**Files:**
- Modify: `src/cad/geom/shapes2d.py`, `src/cad/geom/base.py` (add `.close()` stub)
- Create: `tests/geom/test_close.py`

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_close.py
import math
from cad import line, arc, polyline, circle, rectangle
from cad.geom.shapes2d import Path, Polyline, Line

def test_open_path_closes_with_auto_segment():
    p = line((0, 0), (1, 0)) + line((1, 0), (1, 1)) + line((1, 1), (0, 1))
    closed = p.close()
    assert closed.closed is True
    # the last segment is the auto-added closing line back to (0,0)
    last = closed.segments[-1]
    assert isinstance(last, Line)
    assert last.b == closed.segments[0].a if isinstance(closed.segments[0], Line) else True

def test_already_closed_idempotent_for_circle():
    c = circle((0, 0), 1.0)
    assert c.close() is c

def test_polyline_close_returns_polyline():
    pl = polyline([(0, 0), (1, 0), (1, 1)])
    cp = pl.close()
    assert isinstance(cp, Polyline)
    assert cp.closed is True

def test_path_already_endpoint_match_no_extra_segment():
    p = (line((0, 0), (1, 0))
         + line((1, 0), (1, 1))
         + line((1, 1), (0, 1))
         + line((0, 1), (0, 0)))
    cp = p.close()
    assert cp.closed is True
    assert len(cp.segments) == 4  # no synthetic segment needed
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

In `shapes2d.py` add a `.close()` method to each concrete type. Pattern:

```python
# on Path:
def close(self) -> "Path":
    if self.closed:
        return self
    start, _ = _endpoints(self.segments[0])
    _, end = _endpoints(self.segments[-1])
    segs = self.segments
    if start != end:
        segs = segs + (Line(end, start),)
    return Path(segs, closed=True, inner_loops=self.inner_loops)

# on Polyline:
def close(self) -> "Polyline":
    if self.closed:
        return self
    return Polyline(self.points, closed=True, inner_loops=self.inner_loops)

# on Line:
def close(self) -> "Path":  # closing a single line creates a degenerate path → ValueError
    raise ValueError("cannot close a single Line; compose into a Path first")

# on Arc, Spline:
def close(self) -> "Path":
    raise ValueError("cannot close a single Arc/Spline; compose into a Path first")

# on Circle, Rectangle: already closed → return self.
```

Add `Shape2D.close` abstractly so type-checkers see it on every `Shape2D`.

- [ ] **Step 4: Run** → 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/shapes2d.py src/cad/geom/base.py tests/geom/test_close.py
git commit -m "feat(geom): add Shape2D.close() with auto-closing segment for Paths"
```

---

### Task 12: shape2d_with_hole

**Files:**
- Modify: `src/cad/geom/shapes2d.py`, `src/cad/geom/base.py`
- Create: `tests/geom/test_with_hole.py`

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_with_hole.py
import pytest
from cad import circle, rectangle, line

def test_closed_shape_can_attach_hole():
    plate = rectangle((0, 0), (1, 1)).with_hole(circle((0.5, 0.5), 0.2))
    assert plate.closed is True
    assert len(plate.inner_loops) == 1
    assert plate.inner_loops[0].closed is True

def test_with_holes_multiple():
    plate = rectangle((0, 0), (2, 1)).with_holes([
        circle((0.5, 0.5), 0.1),
        circle((1.5, 0.5), 0.1),
    ])
    assert len(plate.inner_loops) == 2

def test_with_hole_on_open_shape_rejected():
    p = line((0, 0), (1, 0))
    with pytest.raises(ValueError):
        p.with_hole(circle((0.5, 0.5), 0.1))  # type: ignore[attr-defined]

def test_with_hole_on_open_inner_rejected():
    plate = rectangle((0, 0), (1, 1))
    with pytest.raises(ValueError):
        plate.with_hole(line((0.2, 0.2), (0.8, 0.8)))
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

Add to each closed-capable concrete type (Rectangle, Circle, Polyline, Path):

```python
def with_hole(self, inner: Shape2D) -> "<self type>":
    if not self.closed:
        raise ValueError("with_hole requires a closed Shape2D outer; call .close() first")
    if not inner.closed:
        raise ValueError("hole shape must itself be closed")
    return self.__class__(... inner_loops=self.inner_loops + (inner,) ...)

def with_holes(self, inners: list[Shape2D]) -> "<self type>":
    out = self
    for h in inners:
        out = out.with_hole(h)
    return out
```

For `Line`, `Arc`, `Spline` (always-open as singletons): `with_hole` raises `ValueError` with the same "requires closed" message.

Expose abstract method on `Shape2D` so callers can call `.with_hole(...)` without narrowing.

- [ ] **Step 4: Run** → 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/shapes2d.py src/cad/geom/base.py tests/geom/test_with_hole.py
git commit -m "feat(geom): add Shape2D.with_hole / with_holes; closed-only invariant"
```

---

### Task 13: shape2d_transforms

**Files:**
- Modify: `src/cad/geom/shapes2d.py`, `src/cad/geom/base.py`
- Create: `tests/geom/test_transforms_2d.py`

**Notes:** Transforms are methods on every concrete type. `mirror(through=Line)` reflects across the line through the two given points. `rotate(centre, angle)` rotates about a 2D point.

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_transforms_2d.py
import math
import pytest
from cad import rectangle, line, circle
from cad.geom.vec import Vec2

def test_translate_returns_new_shape():
    r = rectangle((0, 0), (1, 1))
    t = r.translate(2, 3)
    assert t is not r
    assert t.bounds() == (Vec2(2, 3), Vec2(3, 4))

def test_translate_bounds_match_spec():
    r = rectangle((0, 0), (1, 1)).translate(2, 0)
    assert r.bounds() == (Vec2(2, 0), Vec2(3, 1))

def test_rotate_circle_centre():
    c = circle((1, 0), 0.5).rotate((0, 0), math.pi / 2)
    assert c.centre.x == pytest.approx(0, abs=1e-12)
    assert c.centre.y == pytest.approx(1, abs=1e-12)

def test_mirror_through_y_axis():
    seg = line((1, 2), (3, 4)).mirror(through=line((0, 0), (0, 1)))
    assert seg.a == Vec2(-1, 2)
    assert seg.b == Vec2(-3, 4)

def test_scale_uniform():
    r = rectangle((0, 0), (1, 1)).scale(2.0)
    assert r.bounds() == (Vec2(0, 0), Vec2(2, 2))
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

Add `translate(dx, dy)`, `rotate(centre, angle)`, `scale(k)`, `mirror(through: Line)` methods to each concrete Shape2D type. They return new instances of the same concrete type. For `Path`, recurse over `segments` and over `inner_loops`. Implementation pattern:

```python
def translate(self, dx: float, dy: float) -> "Line":
    return Line(Vec2(self.a.x + dx, self.a.y + dy), Vec2(self.b.x + dx, self.b.y + dy))
```

For `mirror(through=Line)`, use the standard 2D reflection across a line defined by two points.

Add abstract stubs on `Shape2D` so `.translate(2, 3)` is statically resolvable on any Shape2D.

- [ ] **Step 4: Run** → 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/shapes2d.py src/cad/geom/base.py tests/geom/test_transforms_2d.py
git commit -m "feat(geom): add 2D transforms (translate, rotate, scale, mirror)"
```

---

### Task 14: shape2d_subtract_typeerror

**Files:**
- Modify: `src/cad/geom/base.py`
- Create: `tests/geom/test_subtract_typeerror.py`

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_subtract_typeerror.py
import pytest
from cad import circle

def test_subtraction_points_at_with_hole():
    with pytest.raises(TypeError) as ei:
        circle((0, 0), 1.0) - circle((0, 0), 0.5)  # type: ignore[operator]
    msg = str(ei.value)
    assert "with_hole" in msg
    assert "Stage 6" in msg or "boolean" in msg
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

Add to `Shape2D` in `base.py`:

```python
def __sub__(self, other: object) -> "Shape2D":
    raise TypeError(
        "Shape2D subtraction is not supported. For 2D plate-with-hole geometry, "
        "use shape.with_hole(inner). 3D boolean operations (.cut/.union/.intersect) "
        "are deferred to the Stage 6 boolean spec."
    )
```

- [ ] **Step 4: Run** → 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/base.py tests/geom/test_subtract_typeerror.py
git commit -m "feat(geom): Shape2D.__sub__ raises TypeError pointing at with_hole and Stage 6"
```

---

### Task 15: transform_arity_typing_2d

**Files:**
- Create: `tests/geom/transform_typing.py`, `tests/geom/test_transform_typing_pyright.py`

**Notes:** This task creates a static-analysis test that asserts wrong-arity calls fail. We use `subprocess` to run `pyright --strict` on the typing fixture and assert it reports errors for the offending lines.

**Assumption refs:** `A6`

- [ ] **Step 1: Failing test**

`tests/geom/transform_typing.py` (the fixture under test):

```python
"""Static-typing fixture. pyright --strict on this file MUST flag the marked lines."""
from cad import rectangle

# OK: 2-arg translate on Shape2D
ok_2d = rectangle((0, 0), (1, 1)).translate(2, 0)

# ERROR: 3-arg translate on Shape2D — Shape2D has no 3-arg translate
err_2d_too_many_args = rectangle((0, 0), (1, 1)).translate(2, 0, 0)  # pyright: expect-error
```

`tests/geom/test_transform_typing_pyright.py`:

```python
import json
import shutil
import subprocess
from pathlib import Path

import pytest

PYRIGHT = shutil.which("pyright")

@pytest.mark.skipif(PYRIGHT is None, reason="pyright not installed")
def test_pyright_strict_flags_wrong_arity_2d():
    fixture = Path(__file__).parent / "transform_typing.py"
    res = subprocess.run(
        [PYRIGHT, "--strict", "--outputjson", str(fixture)],
        capture_output=True, text=True,
    )
    data = json.loads(res.stdout)
    diags = data.get("generalDiagnostics", [])
    err_lines = {d["range"]["start"]["line"] + 1 for d in diags if d["severity"] == "error"}
    # the marked line in the fixture
    with fixture.open() as f:
        for i, line in enumerate(f, start=1):
            if "expect-error" in line:
                assert i in err_lines, f"pyright did not flag line {i}: {line.strip()}"
```

- [ ] **Step 2: Run to verify it fails**

`pytest tests/geom/test_transform_typing_pyright.py -q` → FAIL (because `Shape2D.translate` may currently accept `*args` or `dx, dy, dz`).

- [ ] **Step 3: Implementation**

Audit `src/cad/geom/base.py` and `shapes2d.py` so every Shape2D `translate` is declared exactly as:

```python
def translate(self, dx: float, dy: float) -> "<concrete>": ...
```

Run `pyright --strict tests/geom/transform_typing.py` and verify the marked line errors.

- [ ] **Step 4: Run tests** → 1 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/geom/transform_typing.py tests/geom/test_transform_typing_pyright.py
git commit -m "test(geom): pyright-strict guard against wrong-arity Shape2D.translate"
```

---

## Phase C — Geom 3D value types and 2D→3D bridges (8 tasks)

### Task 16: shape3d_sphere

**Files:**
- Create: `src/cad/geom/shapes3d.py`, `tests/geom/test_sphere.py`
- Modify: `src/cad/geom/factories.py`, `src/cad/__init__.py`

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_sphere.py
import pytest
from cad import sphere
from cad.geom.shapes3d import Sphere
from cad.geom.vec import Vec3

def test_sphere_factory():
    s = sphere((0, 0, 0), 1.0)
    assert isinstance(s, Sphere)
    assert s.centre == Vec3(0, 0, 0)
    assert s.radius == 1.0

def test_sphere_negative_radius_rejected():
    with pytest.raises(ValueError):
        sphere((0, 0, 0), -0.1)

def test_sphere_bounds():
    s = sphere((1, 2, 3), 0.5)
    lo, hi = s.bounds()
    assert lo == Vec3(0.5, 1.5, 2.5)
    assert hi == Vec3(1.5, 2.5, 3.5)
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

`src/cad/geom/shapes3d.py`:

```python
from __future__ import annotations
from dataclasses import dataclass
from cad.geom.base import Shape3D
from cad.geom.vec import Vec3


def _to_vec3(p: Vec3 | tuple[float, float, float]) -> Vec3:
    if isinstance(p, Vec3):
        return p
    x, y, z = p
    return Vec3(float(x), float(y), float(z))


@dataclass(frozen=True, slots=True)
class Sphere(Shape3D):
    centre: Vec3
    radius: float

    def __post_init__(self) -> None:
        if self.radius <= 0.0:
            raise ValueError(f"Sphere radius must be > 0, got {self.radius}")

    def bounds(self) -> tuple[Vec3, Vec3]:
        return (
            Vec3(self.centre.x - self.radius, self.centre.y - self.radius, self.centre.z - self.radius),
            Vec3(self.centre.x + self.radius, self.centre.y + self.radius, self.centre.z + self.radius),
        )
```

In `factories.py`:

```python
def sphere(centre, radius: float):
    from cad.geom.shapes3d import Sphere, _to_vec3
    return Sphere(_to_vec3(centre), float(radius))
```

Re-export `sphere` in `cad/__init__.py`.

- [ ] **Step 4: Run** → 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/shapes3d.py src/cad/geom/factories.py src/cad/__init__.py tests/geom/test_sphere.py
git commit -m "feat(geom): add Sphere + sphere() factory"
```

---

### Task 17: shape3d_prism

**Files:**
- Modify: `src/cad/geom/shapes3d.py`, `src/cad/geom/factories.py`, `src/cad/__init__.py`
- Create: `tests/geom/test_prism.py`

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_prism.py
import pytest
from cad import prism
from cad.geom.shapes3d import Prism
from cad.geom.vec import Vec3

def test_prism_factory_and_bounds():
    p = prism((0, 0, 0), (2, 2, 1))
    assert isinstance(p, Prism)
    lo, hi = p.bounds()
    assert lo == Vec3(0, 0, 0)
    assert hi == Vec3(2, 2, 1)

def test_prism_zero_size_rejected():
    with pytest.raises(ValueError):
        prism((0, 0, 0), (0, 1, 1))

def test_prism_negative_size_rejected():
    with pytest.raises(ValueError):
        prism((0, 0, 0), (-1, 1, 1))
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

Append to `shapes3d.py`:

```python
@dataclass(frozen=True, slots=True)
class Prism(Shape3D):
    origin: Vec3
    size: Vec3

    def __post_init__(self) -> None:
        if self.size.x <= 0.0 or self.size.y <= 0.0 or self.size.z <= 0.0:
            raise ValueError(f"Prism size must have positive components, got {self.size}")

    def bounds(self) -> tuple[Vec3, Vec3]:
        return self.origin, Vec3(
            self.origin.x + self.size.x,
            self.origin.y + self.size.y,
            self.origin.z + self.size.z,
        )
```

In `factories.py`:

```python
def prism(origin, size):
    from cad.geom.shapes3d import Prism, _to_vec3
    return Prism(_to_vec3(origin), _to_vec3(size))
```

Re-export.

- [ ] **Step 4: Run** → 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/shapes3d.py src/cad/geom/factories.py src/cad/__init__.py tests/geom/test_prism.py
git commit -m "feat(geom): add Prism + prism() factory"
```

---

### Task 18: shape3d_extrusion_value

**Files:**
- Modify: `src/cad/geom/shapes3d.py`
- Create: `tests/geom/test_extrusion_value.py`

**Notes:** This builds the `Extrusion` *value type* with validation. The `.extrude(...)` *method* on Shape2D arrives in Task 20.

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_extrusion_value.py
import pytest
from cad import circle, line
from cad.geom.shapes3d import Extrusion
from cad.geom.vec import Vec3

def test_extrusion_holds_intent_values():
    profile = circle((0, 0), 1.0)
    e = Extrusion(profile=profile, axis="+z", distance=0.04)
    assert e.profile is profile
    assert e.distance == 0.04

def test_extrusion_rejects_open_profile():
    with pytest.raises(ValueError):
        Extrusion(profile=line((0, 0), (1, 0)), axis="+z", distance=0.04)

def test_extrusion_rejects_zero_distance():
    with pytest.raises(ValueError):
        Extrusion(profile=circle((0, 0), 1.0), axis="+z", distance=0.0)

def test_extrusion_rejects_unknown_axis_string():
    with pytest.raises(ValueError):
        Extrusion(profile=circle((0, 0), 1.0), axis="diagonal", distance=0.04)

def test_extrusion_bounds_axis_aligned_z():
    e = Extrusion(profile=circle((0, 0), 1.0), axis="+z", distance=2.0)
    lo, hi = e.bounds()
    assert lo == Vec3(-1.0, -1.0, 0.0)
    assert hi == Vec3(1.0, 1.0, 2.0)
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

Append to `shapes3d.py`:

```python
from cad.geom.base import Shape2D, Axis, parse_axis
from cad.geom.vec import Vec2

@dataclass(frozen=True, slots=True)
class Extrusion(Shape3D):
    profile: Shape2D
    axis: Axis
    distance: float

    def __post_init__(self) -> None:
        if not self.profile.closed:
            raise ValueError("Extrusion profile must be a closed Shape2D")
        if self.distance == 0.0:
            raise ValueError("Extrusion distance must be non-zero")
        parse_axis(self.axis)  # raises ValueError on unknown string / zero vector

    def bounds(self) -> tuple[Vec3, Vec3]:
        # Axis-aligned cases use the profile-plane convention from spec §3.4.
        # Default fallback: assume profile in XY world plane, sweep along axis vector.
        from cad.geom.shapes3d import _profile_to_world
        u_axis, v_axis, w_axis = _profile_to_world(self.axis)
        plo, phi = self.profile.bounds()
        # corners of the swept volume in world coords
        d = float(self.distance)
        corners = [
            Vec3(*(u_axis * px + v_axis * py + w_axis * dz))
            for px in (plo.x, phi.x)
            for py in (plo.y, phi.y)
            for dz in (0.0, d)
        ]
        xs = [c.x for c in corners]; ys = [c.y for c in corners]; zs = [c.z for c in corners]
        return Vec3(min(xs), min(ys), min(zs)), Vec3(max(xs), max(ys), max(zs))
```

Add the helper `_profile_to_world(axis)` returning `(u, v, w)` Vec3 unit vectors per the §3.4 table; for arbitrary `Vec3` axes, derive `u = cross(+z, axis).normalised()` (fallback to `cross(+y, axis)` if parallel to z), `v = cross(w, u)`. Mark with a one-line comment that this maps profile.x→u, profile.y→v, sweep→w.

For `Vec3.__mul__` returning a `Vec3` (already exists), and for the comprehension, this needs `Vec3 * scalar + Vec3 * scalar` to return a Vec3. That works with the existing operators. Adjust the corner-list expression to use the operator chain rather than `Vec3(*(u*px + v*py + w*dz))`.

- [ ] **Step 4: Run** → 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/shapes3d.py tests/geom/test_extrusion_value.py
git commit -m "feat(geom): add Extrusion intent value type with axis/profile validation"
```

---

### Task 19: shape3d_revolution_value

**Files:**
- Modify: `src/cad/geom/shapes3d.py`
- Create: `tests/geom/test_revolution_value.py`

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_revolution_value.py
import math
import pytest
from cad import rectangle
from cad.geom.shapes3d import Revolution
from cad.geom.vec import Vec3

def test_revolution_holds_intent():
    r = Revolution(
        profile=rectangle((0.5, 0), (0.5, 1.0)),
        axis_origin=Vec3(0, 0, 0),
        axis_direction=Vec3(0, 0, 1),
        angle_rad=2 * math.pi,
    )
    assert r.angle_rad == pytest.approx(2 * math.pi)
    assert r.axis_direction == Vec3(0, 0, 1)

def test_revolution_rejects_zero_angle():
    with pytest.raises(ValueError):
        Revolution(rectangle((0.5, 0), (0.5, 1.0)), Vec3(0, 0, 0), Vec3(0, 0, 1), 0.0)

def test_revolution_rejects_zero_axis_direction():
    with pytest.raises(ValueError):
        Revolution(rectangle((0.5, 0), (0.5, 1.0)), Vec3(0, 0, 0), Vec3(0, 0, 0), math.pi)
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

Append to `shapes3d.py`:

```python
@dataclass(frozen=True, slots=True)
class Revolution(Shape3D):
    profile: Shape2D
    axis_origin: Vec3
    axis_direction: Vec3
    angle_rad: float

    def __post_init__(self) -> None:
        if self.angle_rad == 0.0:
            raise ValueError("Revolution angle must be non-zero")
        if self.axis_direction.length() == 0.0:
            raise ValueError("Revolution axis_direction must be non-zero")

    def bounds(self) -> tuple[Vec3, Vec3]:
        # Conservative bound: profile bounding box swept around full circle ≈ ±max-radius
        plo, phi = self.profile.bounds()
        r_max = max(abs(plo.x), abs(phi.x), abs(plo.y), abs(phi.y))
        ao = self.axis_origin
        return (
            Vec3(ao.x - r_max, ao.y - r_max, ao.z + min(plo.y, phi.y)),
            Vec3(ao.x + r_max, ao.y + r_max, ao.z + max(plo.y, phi.y)),
        )
```

- [ ] **Step 4: Run** → 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/shapes3d.py tests/geom/test_revolution_value.py
git commit -m "feat(geom): add Revolution intent value type"
```

---

### Task 20: shape2d_extrude_method

**Files:**
- Modify: `src/cad/geom/base.py` (add `Shape2D.extrude` declaration), `src/cad/geom/shapes2d.py` (concrete `extrude` per type)
- Create: `tests/geom/test_extrude_method.py`

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_extrude_method.py
import pytest
from cad import circle, rectangle, line
from cad.geom.shapes3d import Extrusion

def test_circle_extrudes_to_extrusion():
    e = circle((0, 0), 1.0).extrude(axis="+z", distance=0.04)
    assert isinstance(e, Extrusion)
    assert e.distance == 0.04

def test_open_path_extrude_rejected():
    p = line((0, 0), (1, 0)) + line((1, 0), (1, 1))
    with pytest.raises(ValueError):
        p.extrude(axis="+z", distance=0.04)

def test_extrude_zero_distance_rejected():
    with pytest.raises(ValueError):
        circle((0, 0), 1.0).extrude(axis="+z", distance=0.0)

def test_extrude_unknown_axis_rejected():
    with pytest.raises(ValueError):
        circle((0, 0), 1.0).extrude(axis="diagonal", distance=0.04)
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

In `Shape2D` (base.py) add:

```python
def extrude(self, axis, distance: float) -> "Shape3D":
    from cad.geom.shapes3d import Extrusion
    if not self.closed:
        raise ValueError("extrude requires a closed Shape2D; call .close() first")
    return Extrusion(profile=self, axis=axis, distance=float(distance))
```

(Per-concrete-type override is unnecessary — the base method handles all. Validation flows through `Extrusion.__post_init__`.)

- [ ] **Step 4: Run** → 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/base.py tests/geom/test_extrude_method.py
git commit -m "feat(geom): add Shape2D.extrude bridge to Extrusion"
```

---

### Task 21: shape2d_revolve_method

**Files:**
- Modify: `src/cad/geom/base.py`
- Create: `tests/geom/test_revolve_method.py`

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_revolve_method.py
import math
from cad import rectangle
from cad.geom.shapes3d import Revolution
from cad.geom.vec import Vec3

def test_rectangle_revolves_full_turn():
    r = rectangle((0.5, 0), (0.5, 1.0)).revolve(axis="+z")
    assert isinstance(r, Revolution)
    assert r.angle_rad == 2 * math.pi
    assert r.axis_direction == Vec3(0, 0, 1)

def test_revolve_partial_angle():
    r = rectangle((0.5, 0), (0.5, 1.0)).revolve(axis="+z", angle=math.pi)
    assert r.angle_rad == math.pi
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

In `Shape2D` (base.py):

```python
def revolve(self, axis, angle: float = 2 * math.pi) -> "Shape3D":
    from cad.geom.shapes3d import Revolution
    direction = parse_axis(axis)
    return Revolution(
        profile=self,
        axis_origin=Vec3(0.0, 0.0, 0.0),
        axis_direction=direction,
        angle_rad=float(angle),
    )
```

(Add `import math` at top of base.py.)

- [ ] **Step 4: Run** → 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/base.py tests/geom/test_revolve_method.py
git commit -m "feat(geom): add Shape2D.revolve bridge to Revolution"
```

---

### Task 22: shape3d_transforms

**Files:**
- Modify: `src/cad/geom/shapes3d.py`, `src/cad/geom/base.py` (add `Shape3D` transform stubs)
- Create: `tests/geom/test_transforms_3d.py`

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_transforms_3d.py
import math
import pytest
from cad import sphere, prism
from cad.geom.vec import Vec3

def test_translate_returns_new_shape():
    s = sphere((0, 0, 0), 1.0).translate(2, 3, 4)
    assert s.centre == Vec3(2, 3, 4)

def test_rotate_about_z_axis_origin():
    s = sphere((1, 0, 0), 0.5).rotate((0, 0, 0), (0, 0, 1), math.pi / 2)
    assert s.centre.x == pytest.approx(0, abs=1e-12)
    assert s.centre.y == pytest.approx(1, abs=1e-12)

def test_mirror_through_xz_plane():
    p = prism((1, 2, 3), (1, 1, 1)).mirror((0, 0, 0), (0, 1, 0))
    lo, hi = p.bounds()
    assert lo.y == -3.0
    assert hi.y == -2.0
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

Per concrete Shape3D type, add `translate(dx, dy, dz)`, `rotate(axis_origin, axis_dir, angle)`, `mirror(plane_origin, plane_normal)`. For `Sphere` translate just shifts the centre; for `Prism` shift origin. Rotation/mirror update `centre` (or `origin`) only — true B-rep rotation of `Prism` produces a non-axis-aligned solid, but for Stage 1 we keep the value type cheap. Document this limitation in the docstring: arbitrary rotation of axis-aligned `Prism` returns the rotated *centre* with the same dimensions (still axis-aligned in its local frame).

For `Extrusion` and `Revolution`, transforms wrap the profile or update the axis fields:

```python
# Extrusion.translate:
def translate(self, dx: float, dy: float, dz: float) -> "Extrusion":
    # offset shifts where the profile sits in 3D — encode as a transformed Extrusion
    # For Stage 1, we attach an `offset: Vec3` field to Extrusion (default Vec3(0,0,0))
    # and bake the translation into it.
    return replace(self, offset=Vec3(self.offset.x + dx, self.offset.y + dy, self.offset.z + dz))
```

This requires adding an `offset: Vec3 = Vec3(0,0,0)` field to `Extrusion` (with default), plus accept-but-ignore semantics in `bounds()` (add offset). The same approach for `Revolution` extends `axis_origin`.

Also add abstract methods on `Shape3D` so callers can call `.translate(...)` without narrowing.

- [ ] **Step 4: Run** → 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/shapes3d.py src/cad/geom/base.py tests/geom/test_transforms_3d.py
git commit -m "feat(geom): add 3D transforms (translate, rotate, mirror) and Extrusion offset field"
```

---

### Task 23: shape3d_subtract_typeerror

**Files:**
- Modify: `src/cad/geom/base.py`
- Create: `tests/geom/test_shape3d_subtract.py`

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_shape3d_subtract.py
import pytest
from cad import prism

def test_prism_subtract_points_at_stage6():
    with pytest.raises(TypeError) as ei:
        prism((0, 0, 0), (1, 1, 1)) - prism((0, 0, 0), (0.5, 0.5, 0.5))  # type: ignore[operator]
    msg = str(ei.value)
    assert "Stage 6" in msg or "boolean" in msg
    assert ".cut" in msg or ".union" in msg or ".intersect" in msg
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

In `Shape3D` (base.py):

```python
def __sub__(self, other: object) -> "Shape3D":
    raise TypeError(
        "Shape3D subtraction is not supported in Stage 1. "
        "3D boolean operations (.cut/.union/.intersect) are deferred to the Stage 6 boolean spec."
    )
```

- [ ] **Step 4: Run** → 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/base.py tests/geom/test_shape3d_subtract.py
git commit -m "feat(geom): Shape3D.__sub__ raises TypeError pointing at Stage 6"
```

---

## Phase D — Vendor + Tessellator (5 tasks)

### Task 24: vendor_earcut

**Files:**
- Create: `src/cad/_vendor/earcut.py`, `tests/geom/test_vendor_earcut.py`
- Modify: `NOTICE`

**Assumption refs:** `A1`

**Invoke skill:** `python` and `git`. **Invoke MCP:** `context7` to query `mapbox-earcut` Python ports if uncertain about source.

- [ ] **Step 1: Locate the upstream port**

Candidates (verify first which is current and pure-Python MIT):
1. `joshuaskelly/earcut-python` — Python port of `mapbox/earcut.hpp`.
2. `pypi:mapbox-earcut` — bindings to C++ library (REJECT — not pure Python).

Choose option 1 unless it has been deprecated; pin commit hash. If neither is acceptable, escalate per A1's `if_false` clause.

- [ ] **Step 2: Write failing test**

```python
# tests/geom/test_vendor_earcut.py
def test_earcut_imports_and_triangulates_square_with_hole():
    from cad._vendor import earcut as ec
    # outer square + inner square hole, flat coordinate list
    coords = [
        0.0, 0.0,  10.0, 0.0,  10.0, 10.0,  0.0, 10.0,   # outer (4 pts)
        2.0, 2.0,   2.0, 8.0,   8.0, 8.0,   8.0, 2.0,   # hole (4 pts)
    ]
    holes = [4]  # hole starts at index 4 of vertex array
    triangles = ec.earcut(coords, holes, dim=2)
    assert isinstance(triangles, list)
    assert len(triangles) % 3 == 0
    # area of square minus hole = 100 - 36 = 64; verify summed triangle area
    # (this is also the integration check for the vendored module)
    def tri_area(i, j, k):
        ax, ay = coords[2*i], coords[2*i+1]
        bx, by = coords[2*j], coords[2*j+1]
        cx, cy = coords[2*k], coords[2*k+1]
        return abs(ax*(by-cy) + bx*(cy-ay) + cx*(ay-by)) / 2
    total = sum(
        tri_area(triangles[t], triangles[t+1], triangles[t+2])
        for t in range(0, len(triangles), 3)
    )
    assert abs(total - 64.0) < 1e-6
```

- [ ] **Step 3: Run** → FAIL.

- [ ] **Step 4: Vendor the file**

```bash
curl -L -o /tmp/earcut_src.py https://raw.githubusercontent.com/joshuaskelly/earcut-python/<COMMIT>/earcut/earcut.py
# Inspect for licence header; copy into src/cad/_vendor/earcut.py with the original copyright
# header preserved at the top.
```

Prepend a vendor-stamp comment to `src/cad/_vendor/earcut.py`:

```python
# Vendored from https://github.com/joshuaskelly/earcut-python
# Pinned commit: <COMMIT-HASH>
# Original copyright + MIT licence header retained below.
```

Update `NOTICE`:

```
src/cad/_vendor/earcut.py
  Origin: https://github.com/joshuaskelly/earcut-python
  Pinned commit: <COMMIT-HASH>
  Licence: MIT (see file header)
```

- [ ] **Step 5: Run test**

`pytest tests/geom/test_vendor_earcut.py -q` → 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/cad/_vendor/earcut.py NOTICE tests/geom/test_vendor_earcut.py
git commit -m "vendor: add mapbox-earcut Python port (joshuaskelly@<COMMIT>) under MIT"
```

---

### Task 25: tessellate_curves_to_polyline

**Files:**
- Create: `src/cad/geom/tessellate.py`, `tests/geom/test_curves_to_polyline.py`

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_curves_to_polyline.py
import math
from cad import circle, line, arc
from cad.geom.shapes2d import Polyline
from cad.geom.tessellate import curves_to_polyline

def test_circle_flattens_below_chord_tolerance():
    c = circle((0, 0), 1.0)
    pl = curves_to_polyline(c, tolerance=1e-3)
    assert isinstance(pl, Polyline)
    # chord error = r - r*cos(theta/2). For tol=1e-3 and r=1 → theta ≈ 0.0894 rad
    # → ≥ 71 segments
    assert len(pl.points) >= 70

def test_pure_line_returned_as_polyline():
    seg = line((0, 0), (1, 0))
    pl = curves_to_polyline(seg, tolerance=1e-3)
    assert isinstance(pl, Polyline)
    assert pl.points == seg_endpoints_tuple_for_line(pl)  # see helper below

def test_arc_chord_error_under_tolerance():
    a = arc((0, 0), 1.0, 0, math.pi)
    pl = curves_to_polyline(a, tolerance=1e-3)
    # check that no consecutive-vertex midpoint deviates from radius by > tol
    for p, q in zip(pl.points, pl.points[1:]):
        mx, my = (p.x + q.x) / 2, (p.y + q.y) / 2
        chord_radius = math.hypot(mx, my)
        assert abs(chord_radius - 1.0) < 1e-3
```

(Helper `seg_endpoints_tuple_for_line` is defined inline in the test file as needed.)

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

`src/cad/geom/tessellate.py`:

```python
from __future__ import annotations
import math
from cad.geom.base import Shape2D
from cad.geom.shapes2d import Line, Arc, Circle, Rectangle, Polyline, Spline, Path
from cad.geom.vec import Vec2


def _arc_segments_for_tolerance(radius: float, sweep: float, tolerance: float) -> int:
    # chord error: r - r*cos(theta/2) ≤ tol → theta ≤ 2 acos(1 - tol/r)
    if tolerance >= radius:
        return 4
    theta_max = 2 * math.acos(1 - tolerance / radius)
    return max(4, math.ceil(abs(sweep) / theta_max))


def _flatten_arc(a: Arc, tolerance: float) -> list[Vec2]:
    sweep = a.end_rad - a.start_rad
    n = _arc_segments_for_tolerance(a.radius, sweep, tolerance)
    return [
        Vec2(a.centre.x + a.radius * math.cos(a.start_rad + sweep * i / n),
             a.centre.y + a.radius * math.sin(a.start_rad + sweep * i / n))
        for i in range(n + 1)
    ]


def _flatten_circle(c: Circle, tolerance: float) -> list[Vec2]:
    n = _arc_segments_for_tolerance(c.radius, 2 * math.pi, tolerance)
    return [
        Vec2(c.centre.x + c.radius * math.cos(2 * math.pi * i / n),
             c.centre.y + c.radius * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


def _flatten_segment(seg: Shape2D, tolerance: float) -> list[Vec2]:
    if isinstance(seg, Line):
        return [seg.a, seg.b]
    if isinstance(seg, Arc):
        return _flatten_arc(seg, tolerance)
    if isinstance(seg, Circle):
        return _flatten_circle(seg, tolerance)
    if isinstance(seg, Rectangle):
        o, s = seg.origin, seg.size
        return [o, Vec2(o.x + s.x, o.y), Vec2(o.x + s.x, o.y + s.y), Vec2(o.x, o.y + s.y)]
    if isinstance(seg, Polyline):
        return list(seg.points)
    if isinstance(seg, Spline):
        return _flatten_spline(seg, tolerance)
    if isinstance(seg, Path):
        out: list[Vec2] = []
        for s in seg.segments:
            pts = _flatten_segment(s, tolerance)
            if out and out[-1] == pts[0]:
                out.extend(pts[1:])
            else:
                out.extend(pts)
        return out
    raise TypeError(f"cannot flatten {type(seg).__name__}")


def _flatten_spline(s: Spline, tolerance: float) -> list[Vec2]:
    # adaptive subdivision per cubic Bezier patch; for Stage 1 use 32 samples per patch
    out: list[Vec2] = []
    cps = s.control_points
    n_patches = (len(cps) - 1) // 3
    for k in range(n_patches):
        p0, p1, p2, p3 = cps[3*k], cps[3*k+1], cps[3*k+2], cps[3*k+3]
        for i in range(33):
            t = i / 32
            mt = 1 - t
            x = mt**3*p0.x + 3*mt**2*t*p1.x + 3*mt*t**2*p2.x + t**3*p3.x
            y = mt**3*p0.y + 3*mt**2*t*p1.y + 3*mt*t**2*p2.y + t**3*p3.y
            out.append(Vec2(x, y))
    return out


def curves_to_polyline(shape: Shape2D, *, tolerance: float) -> Polyline:
    pts = _flatten_segment(shape, tolerance)
    return Polyline(tuple(pts), closed=shape.closed, inner_loops=())
```

- [ ] **Step 4: Run** → 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/tessellate.py tests/geom/test_curves_to_polyline.py
git commit -m "feat(geom): add curves_to_polyline with chord-tolerance flattening"
```

---

### Task 26: tessellate_polygon_to_triangles

**Files:**
- Modify: `src/cad/geom/tessellate.py`
- Create: `tests/geom/test_polygon_to_triangles.py`

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_polygon_to_triangles.py
import math
import pytest
from cad import rectangle, circle
from cad.geom.tessellate import polygon_to_triangles

def test_rectangle_with_hole_area_invariant():
    plate = rectangle((0, 0), (1, 1)).with_hole(circle((0.5, 0.5), 0.2))
    tris = polygon_to_triangles(plate, tolerance=1e-3)
    expected = 1.0 - math.pi * 0.2**2
    total = sum(_tri_area(t) for t in tris)
    assert abs(total - expected) / expected < 0.01

def test_polygon_to_triangles_rejects_open():
    from cad import polyline
    with pytest.raises(ValueError):
        polygon_to_triangles(polyline([(0, 0), (1, 0), (1, 1)]), tolerance=1e-3)

def test_no_triangle_vertex_inside_hole():
    plate = rectangle((0, 0), (1, 1)).with_hole(circle((0.5, 0.5), 0.2))
    tris = polygon_to_triangles(plate, tolerance=1e-3)
    for t in tris:
        for v in (t.a, t.b, t.c):
            assert ((v.x - 0.5)**2 + (v.y - 0.5)**2) >= (0.2**2 - 1e-6)

def _tri_area(t):
    a, b, c = t.a, t.b, t.c
    return abs(a.x*(b.y-c.y) + b.x*(c.y-a.y) + c.x*(a.y-b.y)) / 2
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

In `tessellate.py` add:

```python
from dataclasses import dataclass
from cad._vendor import earcut as ec

@dataclass(frozen=True, slots=True)
class Triangle2:
    a: Vec2
    b: Vec2
    c: Vec2


def polygon_to_triangles(shape: Shape2D, *, tolerance: float) -> list[Triangle2]:
    if not shape.closed:
        raise ValueError("polygon_to_triangles requires a closed Shape2D")

    outer_pts = _flatten_segment(shape, tolerance)
    if outer_pts[0] == outer_pts[-1]:
        outer_pts = outer_pts[:-1]
    flat: list[float] = []
    for p in outer_pts:
        flat.extend([p.x, p.y])

    holes_indices: list[int] = []
    inner_loops = getattr(shape, "inner_loops", ())
    for inner in inner_loops:
        idx = len(flat) // 2
        holes_indices.append(idx)
        inner_pts = _flatten_segment(inner, tolerance)
        if inner_pts[0] == inner_pts[-1]:
            inner_pts = inner_pts[:-1]
        for p in inner_pts:
            flat.extend([p.x, p.y])

    indices = ec.earcut(flat, holes_indices, dim=2)
    out: list[Triangle2] = []
    for i in range(0, len(indices), 3):
        ia, ib, ic = indices[i], indices[i+1], indices[i+2]
        out.append(Triangle2(
            Vec2(flat[2*ia], flat[2*ia+1]),
            Vec2(flat[2*ib], flat[2*ib+1]),
            Vec2(flat[2*ic], flat[2*ic+1]),
        ))
    return out
```

- [ ] **Step 4: Run** → 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/tessellate.py tests/geom/test_polygon_to_triangles.py
git commit -m "feat(geom): add polygon_to_triangles with hole support via earcut"
```

---

### Task 27: tessellate_extrusion_to_triangles

**Files:**
- Modify: `src/cad/geom/tessellate.py`
- Create: `tests/geom/test_extrusion_to_triangles.py`

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_extrusion_to_triangles.py
import math
import pytest
from cad import rectangle, circle
from cad.geom.tessellate import extrusion_to_triangles

def test_unit_prism_via_rectangle_extrusion_has_12_triangles():
    e = rectangle((0, 0), (1, 1)).extrude(axis="+z", distance=1.0)
    tris = extrusion_to_triangles(e, tolerance=1e-3)
    assert len(tris) == 12  # 2 caps × 2 + 4 sides × 2

def test_circle_extrusion_watertight_count():
    e = circle((0, 0), 1.0).extrude(axis="+z", distance=1.0)
    tris = extrusion_to_triangles(e, tolerance=1e-3)
    # Verify edge-sharing watertight invariant
    edges: dict[tuple, int] = {}
    for t in tris:
        for u, v in [(t.a, t.b), (t.b, t.c), (t.c, t.a)]:
            key = tuple(sorted([_v_key(u), _v_key(v)]))
            edges[key] = edges.get(key, 0) + 1
    assert all(c == 2 for c in edges.values()), "every edge must be shared by exactly 2 triangles"

def _v_key(v):
    return (round(v.x, 9), round(v.y, 9), round(v.z, 9))
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

In `tessellate.py`:

```python
from cad.geom.shapes3d import Extrusion, _profile_to_world

@dataclass(frozen=True, slots=True)
class Triangle3:
    a: Vec3
    b: Vec3
    c: Vec3


def _profile_pt_to_world(px: float, py: float, dz: float, e: Extrusion) -> Vec3:
    u, v, w = _profile_to_world(e.axis)
    base = Vec3(0.0, 0.0, 0.0) + u * px + v * py
    if hasattr(e, "offset"):
        base = base + e.offset
    return base + w * dz


def extrusion_to_triangles(e: Extrusion, *, tolerance: float) -> list[Triangle3]:
    cap_tris = polygon_to_triangles(e.profile, tolerance=tolerance)
    out: list[Triangle3] = []
    d = float(e.distance)
    # bottom cap (z=0): reverse winding so normal points -axis
    for t in cap_tris:
        a = _profile_pt_to_world(t.a.x, t.a.y, 0.0, e)
        b = _profile_pt_to_world(t.b.x, t.b.y, 0.0, e)
        c = _profile_pt_to_world(t.c.x, t.c.y, 0.0, e)
        out.append(Triangle3(a, c, b))  # reversed
    # top cap (z=d)
    for t in cap_tris:
        a = _profile_pt_to_world(t.a.x, t.a.y, d, e)
        b = _profile_pt_to_world(t.b.x, t.b.y, d, e)
        c = _profile_pt_to_world(t.c.x, t.c.y, d, e)
        out.append(Triangle3(a, b, c))
    # sides — outer boundary + each hole
    boundaries = [list(_flatten_segment(e.profile, tolerance))]
    for inner in getattr(e.profile, "inner_loops", ()):
        boundaries.append(list(_flatten_segment(inner, tolerance)))
    for ring in boundaries:
        if ring[0] == ring[-1]:
            ring = ring[:-1]
        n = len(ring)
        for i in range(n):
            p = ring[i]; q = ring[(i + 1) % n]
            p0 = _profile_pt_to_world(p.x, p.y, 0.0, e)
            q0 = _profile_pt_to_world(q.x, q.y, 0.0, e)
            p1 = _profile_pt_to_world(p.x, p.y, d, e)
            q1 = _profile_pt_to_world(q.x, q.y, d, e)
            out.append(Triangle3(p0, q0, q1))
            out.append(Triangle3(p0, q1, p1))
    return out
```

- [ ] **Step 4: Run** → 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/tessellate.py tests/geom/test_extrusion_to_triangles.py
git commit -m "feat(geom): add extrusion_to_triangles (caps + side bands, watertight)"
```

---

### Task 28: tessellate_revolution_to_triangles

**Files:**
- Modify: `src/cad/geom/tessellate.py`
- Create: `tests/geom/test_revolution_to_triangles.py`

- [ ] **Step 1: Failing test**

```python
# tests/geom/test_revolution_to_triangles.py
import math
from cad import rectangle
from cad.geom.tessellate import revolution_to_triangles

def test_unit_square_revolved_full_turn_watertight():
    r = rectangle((0.5, 0), (0.5, 1.0)).revolve(axis="+z")
    tris = revolution_to_triangles(r, tolerance=1e-2)
    edges: dict[tuple, int] = {}
    for t in tris:
        for u, v in [(t.a, t.b), (t.b, t.c), (t.c, t.a)]:
            key = tuple(sorted([_k(u), _k(v)]))
            edges[key] = edges.get(key, 0) + 1
    assert all(c == 2 for c in edges.values())

def _k(v): return (round(v.x, 6), round(v.y, 6), round(v.z, 6))
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

In `tessellate.py`:

```python
from cad.geom.shapes3d import Revolution

def _angular_segments_for_tolerance(r_max: float, angle: float, tolerance: float) -> int:
    if tolerance >= r_max:
        return 8
    theta_max = 2 * math.acos(1 - tolerance / r_max)
    return max(8, math.ceil(abs(angle) / theta_max))


def revolution_to_triangles(r: Revolution, *, tolerance: float) -> list[Triangle3]:
    profile_pts = _flatten_segment(r.profile, tolerance)
    if r.profile.closed and profile_pts[0] == profile_pts[-1]:
        profile_pts = profile_pts[:-1]
    r_max = max(p.x for p in profile_pts)
    n = _angular_segments_for_tolerance(r_max, r.angle_rad, tolerance)
    is_full = abs(r.angle_rad - 2 * math.pi) < 1e-12
    angles = [r.angle_rad * i / n for i in range(n + (0 if is_full else 1))]
    # axis assumed +Z through origin for Stage 1; spec §3.5 lists axis_origin/direction;
    # full arbitrary axis support stays in v2 — for full-turn +Z this gives a watertight surface.
    rings: list[list[Vec3]] = []
    for theta in angles:
        ring = [Vec3(p.x * math.cos(theta), p.x * math.sin(theta), p.y) for p in profile_pts]
        rings.append(ring)
    out: list[Triangle3] = []
    m = len(profile_pts)
    nrings = len(rings)
    for i in range(nrings):
        nxt = (i + 1) % nrings if is_full else (i + 1 if i + 1 < nrings else None)
        if nxt is None:
            continue
        for j in range(m):
            j2 = (j + 1) % m if r.profile.closed else (j + 1 if j + 1 < m else None)
            if j2 is None:
                continue
            a = rings[i][j]; b = rings[nxt][j]
            c = rings[nxt][j2]; d = rings[i][j2]
            out.append(Triangle3(a, b, c))
            out.append(Triangle3(a, c, d))
    return out
```

(This implementation handles the full-turn case + Z-axis revolution sufficient to make the watertight-mesh test pass. Arbitrary axis directions are deferred behind the `axis_origin`/`axis_direction` fields and a `Known Limitations` entry at acceptance time if not delivered.)

- [ ] **Step 4: Run** → 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/tessellate.py tests/geom/test_revolution_to_triangles.py
git commit -m "feat(geom): add revolution_to_triangles for full-turn +Z axis"
```

---

## Phase E — Error model (1 task)

### Task 29: error_types

**Files:**
- Create: `src/cad/errors.py`, `tests/errors/__init__.py`, `tests/errors/test_error_tiers.py`
- Modify: `src/cad/__init__.py` (re-export)

- [ ] **Step 1: Failing test**

```python
# tests/errors/test_error_tiers.py
import pytest
from cad import circle, polyline
from cad.errors import CadError, SceneError, WriteError

def test_cad_error_is_root():
    assert issubclass(SceneError, CadError)
    assert issubclass(WriteError, CadError)
    assert not issubclass(ValueError, CadError)

def test_tier1_value_error_from_geom():
    with pytest.raises(ValueError):
        polyline([])
    with pytest.raises(ValueError):
        circle((0, 0), -1.0)

def test_scene_error_can_be_raised_and_caught_as_cad_error():
    with pytest.raises(CadError):
        raise SceneError("test")

def test_write_error_can_be_raised_and_caught_as_cad_error():
    with pytest.raises(CadError):
        raise WriteError("test")
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

`src/cad/errors.py`:

```python
class CadError(Exception):
    """Base class for cad library errors above Tier 1.
    Tier 1 (`ValueError`) stays plain to match dataclass conventions."""


class SceneError(CadError):
    """Raised on invalid scene assembly (e.g., wrong-dim shape passed to wrong scene)."""


class WriteError(CadError):
    """Raised during serialisation (e.g., empty drawing, self-intersecting profile)."""
```

In `cad/__init__.py` re-export `CadError`, `SceneError`, `WriteError`.

- [ ] **Step 4: Run** → 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/errors.py src/cad/__init__.py tests/errors/__init__.py tests/errors/test_error_tiers.py
git commit -m "feat(errors): add CadError / SceneError / WriteError hierarchy"
```

---

## Phase F — Scenes (3 tasks)

### Task 30: scene_dxf_drawing_layers

**Files:**
- Create: `src/cad/scene/__init__.py`, `src/cad/scene/dxf.py`, `tests/scene/__init__.py`, `tests/scene/test_dxf_drawing.py`
- Modify: `src/cad/__init__.py`

- [ ] **Step 1: Failing test**

```python
# tests/scene/test_dxf_drawing.py
import pytest
from cad import DxfDrawing, line, sphere, circle
from cad.errors import SceneError

def test_layer_creation_and_chaining():
    d = DxfDrawing()
    layer = d.layer("PLATE", color=7)
    assert layer.name == "PLATE"
    assert layer.color == 7
    layer.add(line((0, 0), (1, 0))).add(line((1, 0), (1, 1)))
    assert len(layer.entities) == 2
    assert len(d.layers) == 1

def test_layer_idempotent_create():
    d = DxfDrawing()
    a = d.layer("PLATE", 7)
    b = d.layer("PLATE")
    assert a is b
    assert len(d.layers) == 1

def test_default_color_is_seven():
    layer = DxfDrawing().layer("X")
    assert layer.color == 7

def test_layer_rejects_shape3d_with_scene_error():
    d = DxfDrawing()
    layer = d.layer("X")
    with pytest.raises(SceneError):
        layer.add(sphere((0, 0, 0), 1.0))  # type: ignore[arg-type]

def test_two_layers_two_colours():
    d = DxfDrawing()
    d.layer("PLATE", 7)
    d.layer("HOLES", 1)
    assert len(d.layers) == 2
    assert d.layers["PLATE"].color == 7
    assert d.layers["HOLES"].color == 1
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

`src/cad/scene/dxf.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from cad.geom.base import Shape2D, Shape3D
from cad.errors import SceneError


@dataclass
class Layer:
    name: str
    color: int
    linetype: str
    entities: list[Shape2D] = field(default_factory=list)

    def add(self, shape: Shape2D) -> "Layer":
        if isinstance(shape, Shape3D):
            raise SceneError(f"Layer.add accepts Shape2D only; got {type(shape).__name__}")
        if not isinstance(shape, Shape2D):
            raise SceneError(f"Layer.add accepts Shape2D only; got {type(shape).__name__}")
        self.entities.append(shape)
        return self


class DxfDrawing:
    def __init__(self) -> None:
        self.layers: dict[str, Layer] = {}
        self.texts: list = []  # populated by Task 31

    def layer(self, name: str, color: int = 7, linetype: str = "CONTINUOUS") -> Layer:
        if name in self.layers:
            return self.layers[name]
        layer = Layer(name=name, color=color, linetype=linetype)
        self.layers[name] = layer
        return layer

    def write(self, path) -> None:
        # implemented by Task 33+; raises until then.
        from cad.write.dxf.sections import write_drawing
        write_drawing(self, path)
```

`src/cad/scene/__init__.py`: re-export `DxfDrawing`, `Layer`. Re-export `DxfDrawing` and `Layer` in `cad/__init__.py`.

- [ ] **Step 4: Run** → 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/scene/__init__.py src/cad/scene/dxf.py src/cad/__init__.py tests/scene/__init__.py tests/scene/test_dxf_drawing.py
git commit -m "feat(scene): add DxfDrawing + Layer with chained add and SceneError on Shape3D"
```

---

### Task 31: scene_dxf_text

**Files:**
- Modify: `src/cad/scene/dxf.py`
- Create: `tests/scene/test_dxf_text.py`

- [ ] **Step 1: Failing test**

```python
# tests/scene/test_dxf_text.py
import pytest
from cad import DxfDrawing

def test_add_text_records_intent():
    d = DxfDrawing()
    d.add_text("LABEL", at=(0.0, 0.0), height=0.01, layer="ANNOT")
    assert len(d.texts) == 1
    t = d.texts[0]
    assert t.text == "LABEL"
    assert t.at == (0.0, 0.0)
    assert t.height == 0.01
    assert t.layer == "ANNOT"

def test_add_dimension_is_placeholder_not_implemented():
    d = DxfDrawing()
    with pytest.raises(NotImplementedError) as ei:
        d.add_dimension(start=(0,0), end=(1,0), offset=0.05)
    assert "Stage 3" in str(ei.value)
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

In `src/cad/scene/dxf.py`:

```python
@dataclass
class TextAnnotation:
    text: str
    at: tuple[float, float]
    height: float
    layer: str


# In DxfDrawing:
def add_text(self, text: str, at: tuple[float, float], height: float, layer: str) -> "DxfDrawing":
    self.texts.append(TextAnnotation(text=text, at=at, height=float(height), layer=layer))
    return self

def add_dimension(self, **_: object) -> None:
    raise NotImplementedError(
        "DXF DIMENSION entities are reserved for the Stage 3 spec. "
        "Use add_text() for Stage 1 annotations."
    )
```

- [ ] **Step 4: Run** → 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/scene/dxf.py tests/scene/test_dxf_text.py
git commit -m "feat(scene): add DxfDrawing.add_text and Stage-3 add_dimension placeholder"
```

---

### Task 32: scene_stl_mesh

**Files:**
- Create: `src/cad/scene/stl.py`, `tests/scene/test_stl_mesh.py`
- Modify: `src/cad/scene/__init__.py`, `src/cad/__init__.py`

- [ ] **Step 1: Failing test**

```python
# tests/scene/test_stl_mesh.py
import pytest
from cad import StlMesh, prism, sphere, circle
from cad.errors import SceneError

def test_stl_mesh_default_tolerance():
    m = StlMesh()
    assert m.tolerance == 1e-3

def test_stl_mesh_chained_add_returns_self():
    m = StlMesh().add(prism((0, 0, 0), (1, 1, 1)), sphere((0, 0, 0), 1.0))
    assert len(m.solids) == 2

def test_stl_mesh_rejects_shape2d_with_scene_error():
    m = StlMesh()
    with pytest.raises(SceneError):
        m.add(circle((0, 0), 1.0))  # type: ignore[arg-type]

def test_stl_mesh_tolerance_keyword_or_positional():
    a = StlMesh(1e-4)
    b = StlMesh(tolerance=1e-4)
    assert a.tolerance == b.tolerance == 1e-4
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

`src/cad/scene/stl.py`:

```python
from __future__ import annotations
from cad.geom.base import Shape2D, Shape3D
from cad.errors import SceneError


class StlMesh:
    def __init__(self, tolerance: float = 1e-3) -> None:
        self.tolerance: float = float(tolerance)
        self.solids: list[Shape3D] = []

    def add(self, *solids: Shape3D) -> "StlMesh":
        for s in solids:
            if isinstance(s, Shape2D):
                raise SceneError(f"StlMesh.add accepts Shape3D only; got {type(s).__name__}")
            if not isinstance(s, Shape3D):
                raise SceneError(f"StlMesh.add accepts Shape3D only; got {type(s).__name__}")
            self.solids.append(s)
        return self

    def write(self, path, ascii: bool = False) -> None:
        from cad.write.stl.binary import write_binary
        from cad.write.stl.ascii import write_ascii
        if ascii:
            write_ascii(self, path)
        else:
            write_binary(self, path)
```

Re-export `StlMesh` in `cad/scene/__init__.py` and `cad/__init__.py`.

- [ ] **Step 4: Run** → 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/scene/stl.py src/cad/scene/__init__.py src/cad/__init__.py tests/scene/test_stl_mesh.py
git commit -m "feat(scene): add StlMesh with variadic chained .add() and tolerance default 1e-3"
```

---

## Phase G — DXF writer (10 tasks)

### Task 33: dxf_writer_skeleton

**Files:**
- Create: `src/cad/write/__init__.py`, `src/cad/write/dxf/__init__.py`, `src/cad/write/dxf/codes.py`, `src/cad/write/dxf/emit.py`, `src/cad/write/dxf/sections.py`, `tests/write/__init__.py`, `tests/write/test_dxf_skeleton.py`

**Assumption refs:** `A2`

- [ ] **Step 1: Failing test**

```python
# tests/write/test_dxf_skeleton.py
import pytest
import ezdxf
from cad import DxfDrawing

def test_empty_drawing_opens_in_ezdxf(tmp_path):
    d = DxfDrawing()
    d.layer("DEFAULT")
    out = tmp_path / "empty.dxf"
    d.write(out)
    doc = ezdxf.readfile(str(out))
    audit = doc.audit()
    assert len(audit.errors) == 0
    assert doc.dxfversion == "AC1032"

def test_emit_sections_in_order(tmp_path):
    d = DxfDrawing()
    out = tmp_path / "out.dxf"
    d.write(out)
    text = out.read_text()
    # SECTION ordering check
    headers = [s for s in ["HEADER", "TABLES", "BLOCKS", "ENTITIES", "OBJECTS", "EOF"]]
    seen = []
    for marker in headers:
        idx = text.find(f"\n{marker}\n", text.find(seen[-1]) if seen else 0)
        if idx >= 0:
            seen.append(marker)
    assert seen == headers
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

`src/cad/write/dxf/codes.py`:

```python
ENTITY_TYPE = 0
LAYER_NAME = 8
START_X, START_Y, START_Z = 10, 20, 30
END_X, END_Y, END_Z = 11, 21, 31
RADIUS = 40
TEXT_HEIGHT = 40
ANGLE_START, ANGLE_END = 50, 51
TEXT = 1
COLOR = 62
LINETYPE = 6
FLAGS = 70
VERTEX_COUNT = 90
```

`src/cad/write/dxf/emit.py`:

```python
from __future__ import annotations
from io import StringIO

class DxfBuffer:
    def __init__(self) -> None:
        self._buf = StringIO()
    def code(self, group: int, value: object) -> None:
        if isinstance(value, float):
            self._buf.write(f"{group:>3}\n{value:.8g}\n")
        else:
            self._buf.write(f"{group:>3}\n{value}\n")
    def section(self, name: str) -> None:
        self.code(0, "SECTION"); self.code(2, name)
    def endsec(self) -> None:
        self.code(0, "ENDSEC")
    def eof(self) -> None:
        self.code(0, "EOF")
    def text(self) -> str:
        return self._buf.getvalue()
```

`src/cad/write/dxf/sections.py`:

```python
from __future__ import annotations
from pathlib import Path
from cad.write.dxf.emit import DxfBuffer
from cad.errors import WriteError

ACAD_VERSION = "AC1032"  # R2018
INSUNITS_METRES = 6


def _emit_header(buf: DxfBuffer, drawing) -> None:
    buf.section("HEADER")
    buf.code(9, "$ACADVER"); buf.code(1, ACAD_VERSION)
    buf.code(9, "$INSUNITS"); buf.code(70, INSUNITS_METRES)
    # bounds — placeholder; Task 36 fills with actual extents
    buf.code(9, "$EXTMIN"); buf.code(10, 0.0); buf.code(20, 0.0); buf.code(30, 0.0)
    buf.code(9, "$EXTMAX"); buf.code(10, 0.0); buf.code(20, 0.0); buf.code(30, 0.0)
    buf.endsec()


def _emit_tables(buf: DxfBuffer, drawing) -> None:
    buf.section("TABLES")
    # LAYER table emitted by Task 34.
    buf.endsec()


def _emit_blocks(buf: DxfBuffer, drawing) -> None:
    buf.section("BLOCKS"); buf.endsec()


def _emit_entities(buf: DxfBuffer, drawing) -> None:
    buf.section("ENTITIES")
    # entity emitters added by Tasks 35-39.
    buf.endsec()


def _emit_objects(buf: DxfBuffer, drawing) -> None:
    buf.section("OBJECTS"); buf.endsec()


def write_drawing(drawing, path) -> None:
    buf = DxfBuffer()
    _emit_header(buf, drawing)
    _emit_tables(buf, drawing)
    _emit_blocks(buf, drawing)
    _emit_entities(buf, drawing)
    _emit_objects(buf, drawing)
    buf.eof()
    Path(path).write_text(buf.text())
```

- [ ] **Step 4: Run**

`pytest tests/write/test_dxf_skeleton.py -q` → 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/write/__init__.py src/cad/write/dxf/__init__.py src/cad/write/dxf/codes.py src/cad/write/dxf/emit.py src/cad/write/dxf/sections.py tests/write/__init__.py tests/write/test_dxf_skeleton.py
git commit -m "feat(write/dxf): emit empty R2018 skeleton with HEADER/TABLES/BLOCKS/ENTITIES/OBJECTS/EOF"
```

---

### Task 34: dxf_writer_layers

**Files:**
- Modify: `src/cad/write/dxf/sections.py`
- Create: `tests/write/test_dxf_layers.py`

- [ ] **Step 1: Failing test**

```python
# tests/write/test_dxf_layers.py
import ezdxf
from cad import DxfDrawing

def test_layers_emitted_with_colours(tmp_path):
    d = DxfDrawing()
    d.layer("PLATE", color=7)
    d.layer("HOLES", color=1)
    out = tmp_path / "layers.dxf"
    d.write(out)
    doc = ezdxf.readfile(str(out))
    names = {l.dxf.name for l in doc.layers}
    assert "PLATE" in names and "HOLES" in names
    assert doc.layers.get("PLATE").dxf.color == 7
    assert doc.layers.get("HOLES").dxf.color == 1
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

In `_emit_tables`:

```python
def _emit_tables(buf, drawing):
    buf.section("TABLES")
    # LTYPE minimal table
    buf.code(0, "TABLE"); buf.code(2, "LTYPE"); buf.code(70, 1)
    buf.code(0, "LTYPE"); buf.code(2, "CONTINUOUS"); buf.code(70, 0)
    buf.code(3, "Solid line"); buf.code(72, 65); buf.code(73, 0); buf.code(40, 0.0)
    buf.code(0, "ENDTAB")
    # LAYER table
    buf.code(0, "TABLE"); buf.code(2, "LAYER"); buf.code(70, len(drawing.layers))
    for layer in drawing.layers.values():
        buf.code(0, "LAYER")
        buf.code(2, layer.name)
        buf.code(70, 0)
        buf.code(62, layer.color)
        buf.code(6, layer.linetype)
    buf.code(0, "ENDTAB")
    buf.endsec()
```

- [ ] **Step 4: Run** → 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/write/dxf/sections.py tests/write/test_dxf_layers.py
git commit -m "feat(write/dxf): emit LAYER table with colours and linetype"
```

---

### Task 35: dxf_writer_line

**Files:**
- Create: `src/cad/write/dxf/entities.py`, `tests/write/test_dxf_entities.py` (initial — populated by 35-39)
- Modify: `src/cad/write/dxf/sections.py`

- [ ] **Step 1: Failing test**

```python
# tests/write/test_dxf_entities.py
import ezdxf
import pytest
from cad import DxfDrawing, line

def test_emits_one_line(tmp_path):
    d = DxfDrawing()
    d.layer("X").add(line((0, 0), (1, 2)))
    out = tmp_path / "line.dxf"; d.write(out)
    doc = ezdxf.readfile(str(out))
    lines = list(doc.modelspace().query("LINE"))
    assert len(lines) == 1
    assert lines[0].dxf.start == (0.0, 0.0, 0.0)
    assert lines[0].dxf.end == (1.0, 2.0, 0.0)
    assert lines[0].dxf.layer == "X"
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

`src/cad/write/dxf/entities.py`:

```python
from __future__ import annotations
from cad.geom.shapes2d import Line, Arc, Circle, Rectangle, Polyline, Path
from cad.write.dxf.emit import DxfBuffer


def emit_line(buf: DxfBuffer, layer: str, seg: Line) -> None:
    buf.code(0, "LINE")
    buf.code(8, layer)
    buf.code(10, seg.a.x); buf.code(20, seg.a.y); buf.code(30, 0.0)
    buf.code(11, seg.b.x); buf.code(21, seg.b.y); buf.code(31, 0.0)
```

In `_emit_entities` of `sections.py`:

```python
from cad.write.dxf.entities import emit_line
def _emit_entities(buf, drawing):
    buf.section("ENTITIES")
    for layer in drawing.layers.values():
        for ent in layer.entities:
            if isinstance(ent, Line):
                emit_line(buf, layer.name, ent)
            # other types added in Tasks 36-39
    buf.endsec()
```

- [ ] **Step 4: Run** → 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/write/dxf/entities.py src/cad/write/dxf/sections.py tests/write/test_dxf_entities.py
git commit -m "feat(write/dxf): emit LINE entities"
```

---

### Task 36: dxf_writer_lwpolyline

**Files:**
- Modify: `src/cad/write/dxf/entities.py`, `src/cad/write/dxf/sections.py`, `tests/write/test_dxf_entities.py`

- [ ] **Step 1: Failing test (extend existing file)**

```python
def test_emits_open_polyline(tmp_path):
    from cad import polyline
    d = DxfDrawing()
    d.layer("X").add(polyline([(0, 0), (1, 0), (1, 1)]))
    out = tmp_path / "pl.dxf"; d.write(out)
    doc = ezdxf.readfile(str(out))
    pls = list(doc.modelspace().query("LWPOLYLINE"))
    assert len(pls) == 1
    assert pls[0].closed is False
    assert list(pls[0].vertices()) == [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]

def test_emits_closed_polyline(tmp_path):
    from cad import polyline
    d = DxfDrawing()
    d.layer("X").add(polyline([(0, 0), (1, 0), (1, 1)], closed=True))
    out = tmp_path / "pl_closed.dxf"; d.write(out)
    doc = ezdxf.readfile(str(out))
    pls = list(doc.modelspace().query("LWPOLYLINE"))
    assert pls[0].closed is True
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

In `entities.py`:

```python
def emit_lwpolyline(buf, layer: str, pl: Polyline) -> None:
    buf.code(0, "LWPOLYLINE")
    buf.code(8, layer)
    buf.code(90, len(pl.points))
    buf.code(70, 1 if pl.closed else 0)
    for p in pl.points:
        buf.code(10, p.x); buf.code(20, p.y)
```

Add `Polyline` and `Rectangle` (decompose to closed polyline of 4 corners) to the dispatch in `_emit_entities`.

- [ ] **Step 4: Run** → 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/write/dxf/entities.py src/cad/write/dxf/sections.py tests/write/test_dxf_entities.py
git commit -m "feat(write/dxf): emit LWPOLYLINE for Polyline and Rectangle"
```

---

### Task 37: dxf_writer_circle

**Files:**
- Modify: `src/cad/write/dxf/entities.py`, `sections.py`, `tests/write/test_dxf_entities.py`

- [ ] **Step 1: Failing test**

```python
def test_emits_circle_round_trips(tmp_path):
    from cad import circle
    d = DxfDrawing()
    d.layer("X").add(circle((0.5, 0.5), 0.2))
    out = tmp_path / "c.dxf"; d.write(out)
    doc = ezdxf.readfile(str(out))
    circles = list(doc.modelspace().query("CIRCLE"))
    assert len(circles) == 1
    assert circles[0].dxf.center == pytest.approx((0.5, 0.5, 0.0))
    assert circles[0].dxf.radius == pytest.approx(0.2)
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

```python
def emit_circle(buf, layer: str, c: Circle) -> None:
    buf.code(0, "CIRCLE"); buf.code(8, layer)
    buf.code(10, c.centre.x); buf.code(20, c.centre.y); buf.code(30, 0.0)
    buf.code(40, c.radius)
```

Add to dispatch.

- [ ] **Step 4: Run** → 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/write/dxf/entities.py src/cad/write/dxf/sections.py tests/write/test_dxf_entities.py
git commit -m "feat(write/dxf): emit CIRCLE"
```

---

### Task 38: dxf_writer_arc

**Files:**
- Modify: `src/cad/write/dxf/entities.py`, `sections.py`, `tests/write/test_dxf_entities.py`

- [ ] **Step 1: Failing test**

```python
import math

def test_emits_arc_with_degrees(tmp_path):
    from cad import arc
    d = DxfDrawing()
    d.layer("X").add(arc((0, 0), 1.0, 0.0, math.pi / 2))
    out = tmp_path / "a.dxf"; d.write(out)
    doc = ezdxf.readfile(str(out))
    arcs = list(doc.modelspace().query("ARC"))
    assert len(arcs) == 1
    assert arcs[0].dxf.start_angle == pytest.approx(0.0)
    assert arcs[0].dxf.end_angle == pytest.approx(90.0)
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

```python
import math
def emit_arc(buf, layer: str, a: Arc) -> None:
    buf.code(0, "ARC"); buf.code(8, layer)
    buf.code(10, a.centre.x); buf.code(20, a.centre.y); buf.code(30, 0.0)
    buf.code(40, a.radius)
    buf.code(50, math.degrees(a.start_rad))
    buf.code(51, math.degrees(a.end_rad))
```

Add to dispatch.

- [ ] **Step 4: Run** → 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/write/dxf/entities.py src/cad/write/dxf/sections.py tests/write/test_dxf_entities.py
git commit -m "feat(write/dxf): emit ARC with degree angle conversion"
```

---

### Task 39: dxf_writer_mtext

**Files:**
- Modify: `src/cad/write/dxf/entities.py`, `sections.py`, `tests/write/test_dxf_entities.py`

- [ ] **Step 1: Failing test**

```python
def test_emits_mtext_at_position(tmp_path):
    d = DxfDrawing()
    d.layer("ANNOT")
    d.add_text("HELLO", at=(0.0, 0.0), height=0.01, layer="ANNOT")
    out = tmp_path / "text.dxf"; d.write(out)
    doc = ezdxf.readfile(str(out))
    mtexts = list(doc.modelspace().query("MTEXT"))
    assert len(mtexts) == 1
    assert mtexts[0].text == "HELLO"
    assert mtexts[0].dxf.layer == "ANNOT"
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

```python
def emit_mtext(buf, t) -> None:
    buf.code(0, "MTEXT"); buf.code(8, t.layer)
    buf.code(10, float(t.at[0])); buf.code(20, float(t.at[1])); buf.code(30, 0.0)
    buf.code(40, t.height)
    buf.code(1, t.text)
```

After the per-layer entities loop in `_emit_entities`, add:

```python
for t in drawing.texts:
    emit_mtext(buf, t)
```

(MTEXT-bearing layer must be emitted in the LAYER table even if empty of geometry — the existing layer dict already covers this since `add_text` does not auto-create the layer; the test fixture explicitly calls `d.layer("ANNOT")` first.)

- [ ] **Step 4: Run** → 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/write/dxf/entities.py src/cad/write/dxf/sections.py tests/write/test_dxf_entities.py
git commit -m "feat(write/dxf): emit MTEXT for add_text annotations"
```

---

### Task 40: dxf_writer_path_decompose

**Files:**
- Modify: `src/cad/write/dxf/entities.py`, `src/cad/write/dxf/sections.py`
- Create: `tests/write/test_dxf_path_decompose.py`

- [ ] **Step 1: Failing test**

```python
# tests/write/test_dxf_path_decompose.py
import math
import ezdxf
from cad import DxfDrawing, line, arc

def test_path_emits_individual_entities(tmp_path):
    d = DxfDrawing()
    p = (line((-1, 0), (-1, 1))
         + line((-1, 1), (1, 1))
         + arc((0, 1), 1.0, 0.0, math.pi)
         + line((1, 1), (1, 0))).close()
    d.layer("X").add(p)
    out = tmp_path / "path.dxf"; d.write(out)
    doc = ezdxf.readfile(str(out))
    msp = doc.modelspace()
    # path with one Arc segment + multiple Line segments → at least 1 ARC and 3+ LINEs
    assert len(list(msp.query("ARC"))) >= 1
    assert len(list(msp.query("LINE"))) >= 3
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

Add a `emit_path(buf, layer, path)` that walks `path.segments` and dispatches to the appropriate per-entity emitter (recursively for nested Paths). Add `Path` to the dispatch in `_emit_entities`.

- [ ] **Step 4: Run** → 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/write/dxf/entities.py src/cad/write/dxf/sections.py tests/write/test_dxf_path_decompose.py
git commit -m "feat(write/dxf): decompose Path into per-segment LINE/ARC/etc. entities"
```

---

### Task 41: dxf_writer_holes_decompose

**Files:**
- Modify: `src/cad/write/dxf/entities.py`, `sections.py`
- Create: `tests/write/test_dxf_holes_decompose.py`

- [ ] **Step 1: Failing test**

```python
# tests/write/test_dxf_holes_decompose.py
import ezdxf
from cad import DxfDrawing, rectangle, circle

def test_outer_and_inner_emitted_as_separate_entities(tmp_path):
    plate = rectangle((0, 0), (1, 1)).with_hole(circle((0.5, 0.5), 0.2))
    d = DxfDrawing()
    d.layer("X").add(plate)
    out = tmp_path / "plate.dxf"; d.write(out)
    doc = ezdxf.readfile(str(out))
    msp = doc.modelspace()
    # closed rectangle → one LWPOLYLINE; hole → one CIRCLE
    assert len(list(msp.query("LWPOLYLINE"))) == 1
    assert len(list(msp.query("CIRCLE"))) == 1
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

Modify the per-entity emitters to additionally walk `inner_loops` of any closed Shape2D, calling the appropriate emit function for each inner shape on the same layer. (Stage 1 omits HATCH; the geometry only needs the outer + inner loops as separate entities so a CAD viewer renders them.)

- [ ] **Step 4: Run** → 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/write/dxf/entities.py src/cad/write/dxf/sections.py tests/write/test_dxf_holes_decompose.py
git commit -m "feat(write/dxf): emit inner_loops as separate entities on the same layer"
```

---

### Task 42: dxf_writer_writeerror_and_golden

**Files:**
- Modify: `src/cad/write/dxf/sections.py`
- Create: `tests/write/test_dxf_writeerror.py`, `tests/write/test_dxf_golden.py`, `tests/write/goldens/smoke.dxf`

- [ ] **Step 1: Failing tests**

```python
# tests/write/test_dxf_writeerror.py
import pytest
from cad import DxfDrawing
from cad.errors import WriteError

def test_empty_drawing_raises_writeerror(tmp_path):
    d = DxfDrawing()  # no layers, no entities
    with pytest.raises(WriteError) as ei:
        d.write(tmp_path / "empty.dxf")
    assert "no layers" in str(ei.value).lower() or "empty" in str(ei.value).lower()
```

```python
# tests/write/test_dxf_golden.py
import os
from cad import DxfDrawing, line, circle, arc
from math import pi

def _smoke_drawing():
    d = DxfDrawing()
    d.layer("PLATE", 7).add(line((0, 0), (1, 0)))
    d.layer("HOLES", 1).add(circle((0.5, 0.5), 0.2))
    d.add_text("LBL", at=(0.0, 0.0), height=0.01, layer="PLATE")
    return d

def test_golden_byte_match(tmp_path):
    d = _smoke_drawing()
    out = tmp_path / "smoke.dxf"; d.write(out)
    expected = (tmp_path.parent.parent.parent / "tests/write/goldens/smoke.dxf").read_bytes()
    assert out.read_bytes() == expected
```

(The first run regenerates the golden file via `pytest --update-goldens`; the implementer wires this flag in `conftest.py`.)

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

In `write_drawing`:

```python
if not drawing.layers and not drawing.texts:
    raise WriteError("DXF drawing is empty — add at least one layer with entities or one text annotation")
```

Update `tests/conftest.py` with `--update-goldens` flag:

```python
def pytest_addoption(parser):
    parser.addoption("--update-goldens", action="store_true")
```

In `test_dxf_golden.py` use the flag:

```python
def test_golden_byte_match(tmp_path, request):
    d = _smoke_drawing()
    out = tmp_path / "smoke.dxf"; d.write(out)
    golden = Path("tests/write/goldens/smoke.dxf")
    if request.config.getoption("--update-goldens"):
        golden.write_bytes(out.read_bytes())
    assert out.read_bytes() == golden.read_bytes()
```

Generate the initial golden by running with the flag, then commit the byte-exact file.

- [ ] **Step 4: Run** → both tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/cad/write/dxf/sections.py tests/conftest.py tests/write/test_dxf_writeerror.py tests/write/test_dxf_golden.py tests/write/goldens/smoke.dxf
git commit -m "feat(write/dxf): empty-drawing WriteError and byte-golden smoke test"
```

---

## Phase H — STL writer (5 tasks)

### Task 43: stl_writer_binary

**Files:**
- Create: `src/cad/write/stl/__init__.py`, `src/cad/write/stl/binary.py`, `tests/write/test_stl_binary.py`

**Assumption refs:** `A3`

- [ ] **Step 1: Failing test**

```python
# tests/write/test_stl_binary.py
import struct
from cad import StlMesh, prism

def test_binary_prism_size_and_layout(tmp_path):
    m = StlMesh().add(prism((0, 0, 0), (2, 2, 1)))
    out = tmp_path / "prism.stl"
    m.write(out)
    data = out.read_bytes()
    assert len(data) == 84 + 12 * 50, f"expected 684 bytes, got {len(data)}"
    header = data[:80]
    (count,) = struct.unpack("<I", data[80:84])
    assert count == 12
    # parse each triangle: 12 floats LE + 2-byte attribute
    for i in range(12):
        off = 84 + i * 50
        nx, ny, nz, ax, ay, az, bx, by, bz, cx, cy, cz = struct.unpack("<12f", data[off:off+48])
        attr = struct.unpack("<H", data[off+48:off+50])[0]
        assert attr == 0
        nlen = (nx*nx + ny*ny + nz*nz) ** 0.5
        assert abs(nlen - 1.0) < 1e-5, f"triangle {i} normal not unit-length: {nlen}"
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

`src/cad/write/stl/binary.py`:

```python
from __future__ import annotations
import struct
from pathlib import Path
from cad.geom.tessellate import (
    Triangle3, extrusion_to_triangles, revolution_to_triangles,
)
from cad.geom.shapes3d import Sphere, Prism, Extrusion, Revolution
from cad.geom.vec import Vec3
from cad.errors import WriteError


def _normal(t: Triangle3) -> Vec3:
    e1 = Vec3(t.b.x - t.a.x, t.b.y - t.a.y, t.b.z - t.a.z)
    e2 = Vec3(t.c.x - t.a.x, t.c.y - t.a.y, t.c.z - t.a.z)
    n = e1.cross(e2)
    L = n.length()
    if L == 0.0:
        raise WriteError(f"degenerate triangle: {t}")
    return Vec3(n.x / L, n.y / L, n.z / L)


def _solid_to_triangles(solid, tolerance: float) -> list[Triangle3]:
    if isinstance(solid, Prism):
        return _prism_to_triangles(solid)
    if isinstance(solid, Sphere):
        return _sphere_to_triangles(solid, tolerance)
    if isinstance(solid, Extrusion):
        return extrusion_to_triangles(solid, tolerance=tolerance)
    if isinstance(solid, Revolution):
        return revolution_to_triangles(solid, tolerance=tolerance)
    raise WriteError(f"unsupported solid type: {type(solid).__name__}")


def _prism_to_triangles(p: Prism) -> list[Triangle3]:
    o = p.origin
    s = p.size
    v = [
        Vec3(o.x,         o.y,         o.z),
        Vec3(o.x + s.x,   o.y,         o.z),
        Vec3(o.x + s.x,   o.y + s.y,   o.z),
        Vec3(o.x,         o.y + s.y,   o.z),
        Vec3(o.x,         o.y,         o.z + s.z),
        Vec3(o.x + s.x,   o.y,         o.z + s.z),
        Vec3(o.x + s.x,   o.y + s.y,   o.z + s.z),
        Vec3(o.x,         o.y + s.y,   o.z + s.z),
    ]
    # 6 faces × 2 triangles = 12; deterministic diagonal
    F = [
        (0,2,1),(0,3,2),  # bottom (-z)
        (4,5,6),(4,6,7),  # top (+z)
        (0,1,5),(0,5,4),  # front (-y)
        (2,3,7),(2,7,6),  # back (+y)
        (1,2,6),(1,6,5),  # right (+x)
        (0,4,7),(0,7,3),  # left (-x)
    ]
    return [Triangle3(v[a], v[b], v[c]) for (a, b, c) in F]


def _sphere_to_triangles(sph: Sphere, tolerance: float) -> list[Triangle3]:
    # icosphere subdivision sized to chord-tolerance
    import math
    n_lat = max(8, math.ceil(math.pi * sph.radius / tolerance))
    n_lon = n_lat * 2
    pts = []
    for i in range(n_lat + 1):
        phi = math.pi * i / n_lat
        for j in range(n_lon):
            theta = 2 * math.pi * j / n_lon
            pts.append(Vec3(
                sph.centre.x + sph.radius * math.sin(phi) * math.cos(theta),
                sph.centre.y + sph.radius * math.sin(phi) * math.sin(theta),
                sph.centre.z + sph.radius * math.cos(phi),
            ))
    out: list[Triangle3] = []
    for i in range(n_lat):
        for j in range(n_lon):
            a = pts[i * n_lon + j]
            b = pts[i * n_lon + (j + 1) % n_lon]
            c = pts[(i + 1) * n_lon + (j + 1) % n_lon]
            d = pts[(i + 1) * n_lon + j]
            out.append(Triangle3(a, b, c))
            out.append(Triangle3(a, c, d))
    return out


def write_binary(mesh, path) -> None:
    triangles: list[Triangle3] = []
    for s in mesh.solids:
        triangles.extend(_solid_to_triangles(s, mesh.tolerance))
    if not triangles:
        raise WriteError("STL mesh contains no triangles")
    with Path(path).open("wb") as f:
        f.write(b"\x00" * 80)
        f.write(struct.pack("<I", len(triangles)))
        for t in triangles:
            n = _normal(t)
            f.write(struct.pack("<12fH",
                n.x, n.y, n.z,
                t.a.x, t.a.y, t.a.z,
                t.b.x, t.b.y, t.b.z,
                t.c.x, t.c.y, t.c.z,
                0,
            ))
```

- [ ] **Step 4: Run** → 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/write/stl/__init__.py src/cad/write/stl/binary.py tests/write/test_stl_binary.py
git commit -m "feat(write/stl): emit binary STL with unit-norm facet normals"
```

---

### Task 44: stl_writer_ascii

**Files:**
- Create: `src/cad/write/stl/ascii.py`, `tests/write/test_stl_ascii.py`

- [ ] **Step 1: Failing test**

```python
# tests/write/test_stl_ascii.py
from cad import StlMesh, prism

def test_ascii_prism(tmp_path):
    m = StlMesh().add(prism((0, 0, 0), (2, 2, 1)))
    out = tmp_path / "prism.stla"
    m.write(out, ascii=True)
    text = out.read_text()
    assert text.startswith("solid")
    assert text.rstrip().endswith("endsolid pyseas-cad")
    assert text.count("facet normal") == 12
    assert text.count("endloop") == 12
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

`src/cad/write/stl/ascii.py`:

```python
from __future__ import annotations
from pathlib import Path
from cad.write.stl.binary import _solid_to_triangles, _normal
from cad.errors import WriteError


def write_ascii(mesh, path) -> None:
    tris = []
    for s in mesh.solids:
        tris.extend(_solid_to_triangles(s, mesh.tolerance))
    if not tris:
        raise WriteError("STL mesh contains no triangles")
    lines = ["solid pyseas-cad"]
    for t in tris:
        n = _normal(t)
        lines.append(f"  facet normal {n.x:.8g} {n.y:.8g} {n.z:.8g}")
        lines.append("    outer loop")
        for v in (t.a, t.b, t.c):
            lines.append(f"      vertex {v.x:.8g} {v.y:.8g} {v.z:.8g}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append("endsolid pyseas-cad")
    Path(path).write_text("\n".join(lines) + "\n")
```

- [ ] **Step 4: Run** → 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/write/stl/ascii.py tests/write/test_stl_ascii.py
git commit -m "feat(write/stl): emit ASCII STL with token format compliance"
```

---

### Task 45: stl_writer_dispatcher

**Files:**
- Create: `tests/write/test_stl_dispatcher.py`

- [ ] **Step 1: Failing test**

```python
# tests/write/test_stl_dispatcher.py
import math
import struct
from cad import StlMesh, circle, sphere

def test_extrusion_dispatches_to_tessellator(tmp_path):
    e = circle((0, 0), 1.0).extrude(axis="+z", distance=1.0)
    m = StlMesh(tolerance=1e-2).add(e)
    out = tmp_path / "cyl.stl"; m.write(out)
    data = out.read_bytes()
    (count,) = struct.unpack("<I", data[80:84])
    assert count >= 100  # cylinder side wall triangles + caps

def test_sphere_dispatches_to_tessellator(tmp_path):
    s = sphere((0, 0, 0), 1.0)
    m = StlMesh(tolerance=1e-2).add(s)
    out = tmp_path / "ball.stl"; m.write(out)
    data = out.read_bytes()
    (count,) = struct.unpack("<I", data[80:84])
    assert count >= 200
```

- [ ] **Step 2: Run** → already passes if Tasks 27/28/43 land. If failing, debug dispatch in `_solid_to_triangles`.

- [ ] **Step 3: Implementation**

(Dispatcher already lives in `binary.py` from Task 43. This task verifies it integrates with Extrusion / Sphere; if extending, add the missing branch.)

- [ ] **Step 4: Run** → 2 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/write/test_stl_dispatcher.py
git commit -m "test(write/stl): integration coverage for solid → triangle dispatch"
```

---

### Task 46: stl_writer_writeerror

**Files:**
- Modify: `src/cad/write/stl/binary.py`
- Create: `tests/write/test_stl_writeerror.py`

- [ ] **Step 1: Failing test**

```python
# tests/write/test_stl_writeerror.py
import pytest
from cad import StlMesh, polyline
from cad.errors import WriteError

def test_self_intersecting_profile_surfaces_writeerror(tmp_path):
    # bow-tie polygon — earcut rejects or returns garbage; we validate before passing.
    bowtie = polyline([(0, 0), (1, 1), (1, 0), (0, 1)], closed=True)
    e = bowtie.extrude(axis="+z", distance=0.1)
    m = StlMesh().add(e)
    with pytest.raises(WriteError) as ei:
        m.write(tmp_path / "x.stl")
    msg = str(ei.value)
    # should surface the offending polyline first 3 vertices
    assert "(0" in msg and "(1" in msg
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

In `extrusion_to_triangles` (or a new pre-flight check), detect self-intersection by verifying that earcut's output triangle area sum matches the analytic polygon area within 1 %. If mismatch, raise a `WriteError` that includes the first 3 outer-loop vertices.

```python
# in tessellate.py polygon_to_triangles, before returning:
expected_area = _signed_area(outer_pts) - sum(_signed_area(_flatten_segment(h, tolerance)) for h in inner_loops)
got_area = sum(_tri_area(t) for t in triangles)
if abs(got_area - abs(expected_area)) / max(abs(expected_area), 1e-9) > 0.01:
    raise WriteError(
        f"profile is self-intersecting or earcut rejected it; first 3 vertices: "
        f"{outer_pts[:3]}"
    )
```

- [ ] **Step 4: Run** → 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/cad/geom/tessellate.py tests/write/test_stl_writeerror.py
git commit -m "feat(write/stl): WriteError on self-intersecting profile with first-3-vertices in message"
```

---

### Task 47: stl_writer_invariants

**Files:**
- Create: `tests/write/test_stl_invariants.py`

- [ ] **Step 1: Failing test**

```python
# tests/write/test_stl_invariants.py
import struct
from cad import StlMesh, prism

def test_prism_2x2x1_is_684_bytes(tmp_path):
    out = tmp_path / "prism.stl"
    StlMesh().add(prism((0, 0, 0), (2, 2, 1))).write(out)
    assert len(out.read_bytes()) == 684

def test_prism_2x2x1_has_12_triangles_with_unit_normals(tmp_path):
    out = tmp_path / "prism.stl"
    StlMesh().add(prism((0, 0, 0), (2, 2, 1))).write(out)
    data = out.read_bytes()
    (count,) = struct.unpack("<I", data[80:84])
    assert count == 12
    for i in range(count):
        off = 84 + i * 50
        nx, ny, nz = struct.unpack("<3f", data[off:off+12])
        nlen = (nx*nx + ny*ny + nz*nz) ** 0.5
        assert abs(nlen - 1.0) < 1e-5

def test_ascii_token_compliance(tmp_path):
    out = tmp_path / "prism.stla"
    StlMesh().add(prism((0, 0, 0), (2, 2, 1))).write(out, ascii=True)
    text = out.read_text()
    assert "solid" in text
    assert "endsolid" in text
    assert text.count("facet normal") == 12
```

- [ ] **Step 2: Run** → already passes if Tasks 43/44 land. If failing, debug.

- [ ] **Step 3: Implementation**

(No new code if Task 43+44 are correct. Treat this as the spec-acceptance pin for the writer.)

- [ ] **Step 4: Run** → 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/write/test_stl_invariants.py
git commit -m "test(write/stl): pin spec-acceptance invariants (684 bytes, 12 tris, unit normals)"
```

---

## Phase I — Convention enforcement + Example (2 tasks)

### Task 48: stdlib_only_check

**Files:**
- Create: `tests/conventions/__init__.py`, `tests/conventions/test_stdlib_only.py`

- [ ] **Step 1: Failing test**

```python
# tests/conventions/test_stdlib_only.py
import ast
import sys
from pathlib import Path

STDLIB = set(sys.stdlib_module_names)
SRC = Path(__file__).parent.parent.parent / "src" / "cad"


def test_no_external_imports_outside_vendor():
    bad: list[tuple[str, str]] = []
    for py in SRC.rglob("*.py"):
        if "_vendor" in py.parts:
            continue
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = (node.module or "").split(".")[0]
            elif isinstance(node, ast.Import):
                mod = node.names[0].name.split(".")[0]
            else:
                continue
            if mod in {"cad", ""}:
                continue
            if mod not in STDLIB:
                bad.append((str(py.relative_to(SRC)), mod))
    assert not bad, f"external imports outside _vendor: {bad}"
```

- [ ] **Step 2: Run**

`pytest tests/conventions/test_stdlib_only.py -q` → expected to PASS at this stage if the codebase is clean. If it fails, the failing module name + path is the bug to fix.

- [ ] **Step 3: Implementation**

If the test passes immediately, the convention is already upheld. If not, fix the offending import (likely a stray dev-deps leak).

- [ ] **Step 4: Run** → 1 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/conventions/__init__.py tests/conventions/test_stdlib_only.py
git commit -m "test(conventions): pin stdlib-only runtime invariant"
```

---

### Task 49: example_plate_with_hole

**Files:**
- Create: `examples/plate_with_hole.py`, `tests/examples/__init__.py`, `tests/examples/test_plate_with_hole.py`

**Assumption refs:** `A4`

- [ ] **Step 1: Failing test**

```python
# tests/examples/test_plate_with_hole.py
import struct
import subprocess
import sys
from pathlib import Path
import ezdxf

EXAMPLE = Path(__file__).parent.parent.parent / "examples" / "plate_with_hole.py"

def test_example_runs_and_produces_both_files(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    res = subprocess.run([sys.executable, str(EXAMPLE), "--out", str(out)], capture_output=True)
    assert res.returncode == 0, res.stderr.decode()
    dxf = out / "plate.dxf"
    stl = out / "plate.stl"
    assert dxf.exists() and stl.exists()
    # DXF: ezdxf opens, contains an LWPOLYLINE/LINE outline + a CIRCLE
    doc = ezdxf.readfile(str(dxf))
    msp = doc.modelspace()
    assert len(list(msp.query("CIRCLE"))) >= 1
    assert len(list(msp.query("LWPOLYLINE LINE"))) >= 1
    # STL parses
    data = stl.read_bytes()
    (count,) = struct.unpack("<I", data[80:84])
    assert count > 0

def test_example_uses_lowercase_factories_only():
    text = EXAMPLE.read_text()
    forbidden = ["Polyline(", "Circle(", "Vec2(", "Vec3(", "Rectangle(", "Sphere(", "Prism("]
    for token in forbidden:
        assert token not in text, f"example must use lowercase factories, found {token!r}"
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implementation**

`examples/plate_with_hole.py`:

```python
"""Plate-with-hole end-to-end example.

Runs as: python examples/plate_with_hole.py --out <dir>

Produces <dir>/plate.dxf (2D) and <dir>/plate.stl (3D), both built from one
geom source.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from cad import DxfDrawing, StlMesh, circle, rectangle


def build():
    plate_outline = rectangle((0.0, 0.0), (0.30, 0.30))
    pin_hole = circle((0.15, 0.15), 0.025)
    plate_2d = plate_outline.with_hole(pin_hole)
    plate_3d = plate_2d.extrude(axis="+z", distance=0.04)
    return plate_outline, pin_hole, plate_2d, plate_3d


def draw_dxf(out: Path) -> None:
    plate_outline, pin_hole, _, _ = build()
    d = DxfDrawing()
    d.layer("PLATE", color=7).add(plate_outline)
    d.layer("HOLES", color=1).add(pin_hole)
    d.write(out)


def model_stl(out: Path) -> None:
    *_, plate_3d = build()
    StlMesh(tolerance=1e-4).add(plate_3d).write(out)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    draw_dxf(args.out / "plate.dxf")
    model_stl(args.out / "plate.stl")
    print(f"wrote {args.out / 'plate.dxf'} and {args.out / 'plate.stl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run** → 2 passed.

- [ ] **Step 5: Smoke-load STL in slicer (manual A4 check)**

If a slicer is available, load `tmp/plate.stl` and confirm the plate sits on the bed without manual rotation. If unavailable or behaviour mismatches, log a `Known Limitations` entry on the spec at Task 50.

- [ ] **Step 6: Commit**

```bash
git add examples/plate_with_hole.py tests/examples/__init__.py tests/examples/test_plate_with_hole.py
git commit -m "feat(examples): plate-with-hole end-to-end DXF + STL"
```

---

## Phase J — Final acceptance + merge-and-cleanup (1 task)

### Task 50 (final): merge-and-cleanup

**Files:**
- Modify: `.warden/specs/2026-05-08-pyseas-cad-stage-1-design.md` (fill `Known Limitations` and `Post-Implementation Review` blocks)

**Invoke skill:** `verification-before-completion` before starting.

- [ ] **Step 1: Re-read the spec's Acceptance Criteria block**

Open `.warden/specs/2026-05-08-pyseas-cad-stage-1-design.md`. Hold §"Acceptance Criteria" in context.

- [ ] **Step 2: Run every acceptance item, fresh, in one batch**

For each item under §Acceptance Criteria, run the command, capture the output, mark ✅ pass / ⚠ known-limit / ❌ fail. Use this checklist verbatim (one bullet per spec line):

```bash
# Package shape
python -c "import cad; from cad import line, arc, circle, sphere, prism, DxfDrawing, StlMesh"
python -c "from cad.errors import CadError, SceneError, WriteError"
python -c "from cad.geom.base import Shape2D, Shape3D"
test -f src/cad/_vendor/earcut.py
test -f NOTICE && grep -q "earcut" NOTICE

# Runtime dependency promise
python -c "import importlib.metadata as m; assert (m.distribution('pyseas-cad').requires or []) == []"

# Geom layer correctness
pytest tests/geom -q --no-header --tb=line  # ≥ 30 passing
python -c "from cad import polyline; polyline([])" 2>&1 | grep ValueError
python -c "from cad import polyline; polyline([(0,0)], closed=True)" 2>&1 | grep ValueError
python -c "from cad import circle; circle((0,0), -1.0)" 2>&1 | grep ValueError
# (continue down the list)

# Tessellation correctness
pytest tests/geom/test_polygon_to_triangles.py tests/geom/test_extrusion_to_triangles.py tests/geom/test_revolution_to_triangles.py -q

# Scene layer
pytest tests/scene -q

# Writers
pytest tests/write -q

# Error model
pytest tests/errors -q

# Examples
pytest tests/examples -q

# Quality gates
pytest -q
pyright --strict src/cad
ruff check src/cad tests
pytest tests/conventions/test_stdlib_only.py -q
```

- [ ] **Step 3: Resolve every ❌ fail**

For each failing item, choose one path:
1. **Fix it** — implement the missing piece, re-run, mark ✅.
2. **Log it** — after **2-3 different approaches** (per `verification-before-completion`), write a `Known Limitations` entry: root cause, what was tried, why each failed, decision. Then mark ⚠.

Never leave ❌ items.

- [ ] **Step 4: Fill the Post-Implementation Review block in the spec**

Three subsections in `.warden/specs/2026-05-08-pyseas-cad-stage-1-design.md`:
- **Acceptance results** — paste verification output for each item.
- **Scope drift** — list every change beyond spec. For each: justify or revert.
- **Refactor proposals** — list noticed-but-not-executed improvements with trigger conditions.

- [ ] **Step 5: Surface limitations to user**

If `Known Limitations` is non-empty, summarise to the user: which acceptance items did not pass, what blocks them, suggested next step.

- [ ] **Step 6: Promote durable artifacts to wiki/**

If `.warden/research/` or `.warden/lessons/` exist (e.g., the earcut vendor research from Task 24), invoke `wiki-writer` to promote the durable note. If neither directory exists, this step is a no-op.

- [ ] **Step 7: Commit spec review**

```bash
git add .warden/specs/2026-05-08-pyseas-cad-stage-1-design.md
git commit -m "docs(spec): post-implementation review for Stage 1"
```

- [ ] **Step 8: Merge stage-1 into main**

From the worktree:

```bash
git push --set-upstream origin stage-1 2>/dev/null || true   # only if a remote exists
```

From the main repo (parent dir):

```bash
cd /home/eastill/projects/pyseas-cad
git checkout main
git merge --ff-only stage-1
```

If the merge is not fast-forward, abort and investigate — the bootstrap commits on main (`9298c57`, `075b18f`, `b40b637`) should be ancestors of `stage-1`.

- [ ] **Step 9: Worktree + branch cleanup**

```bash
cd /home/eastill/projects/pyseas-cad
git worktree remove .worktrees/stage-1
git branch -d stage-1
```

- [ ] **Step 10: Final orphan check**

```bash
warden audit  # if installed
ls .worktrees/  # should be empty or absent
git status     # clean
```

If `warden` is not on PATH, skip the audit but verify manually that `.worktrees/` is empty and `git status` reports a clean tree.

- [ ] **Step 11: Delete the plan file**

Per the `writing-plans` lifecycle (status `done` → delete completed plan files):

```bash
rm .warden/plans/2026-05-08-pyseas-cad-stage-1.md .warden/plans/2026-05-08-pyseas-cad-stage-1.yaml
git add -A && git commit -m "chore(plan): remove completed Stage 1 plan; spec carries the contract"
```

Only after these steps complete may the executing agent claim Stage 1 done.
