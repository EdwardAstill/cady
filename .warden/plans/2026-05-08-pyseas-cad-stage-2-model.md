# pyseas-cad Stage 2 Model Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task when tasks are independent. For same-session manual execution, follow this plan directly. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the `cad.model` layer so one domain-blind model can organize drawings, parts, assemblies, metadata, and export DXF/STL through existing Stage 1 writers.

**Architecture:** Implement a thin facade over `DxfDrawing` and `StlMesh`; do not rewrite DXF/STL writers. `Model` owns named `Drawing2D`, `Part`, and `Assembly` objects plus metadata. Exports aggregate model containers into Stage 1 scenes, preserving direct `DxfDrawing` and `StlMesh` APIs.

**Tech Stack:** Python 3.11+, stdlib runtime, pytest, pyright strict via `pyproject.toml`, ruff, ezdxf for DXF verification.

**Recommended Skills:** test-driven-development, python, writing, reviewer, verification-before-completion, git

**Recommended MCPs:** none

**Status:** approved
**Refinement passes:** 1 (structured validation clean: YAML sidecar validates, worktree precondition satisfied, no placeholder markers found)

## Bootstrap Context

This plan was created in `.worktrees/stage-2-model/` on branch `stage-2-model`.
The controlling design is `.warden/specs/2026-05-08-pyseas-cad-stage-2-model-design.md`.

## Assumptions

- `A1` — Stage 2 model layer should be a facade over existing `DxfDrawing` and `StlMesh`, not a writer refactor.
  Type: architectural
  Source: v1 roadmap Stage 2 and Stage 2 design spec §3
  Check: implementation keeps `src/cad/write/**` behavior unchanged except imports if needed.
  If false: stop and redesign Stage 2 around a shared writer contract before implementation.
  Owner: Task 3 and Task 5.

- `A2` — Runtime remains pure stdlib.
  Type: policy
  Source: README boundaries and v1 roadmap product principles
  Check: `python -c "import importlib.metadata as m; assert (m.distribution('pyseas-cad').requires or []) == []"`
  If false: remove dependency or record explicit architecture decision before continuing.
  Owner: Task 10.

- `A3` — Existing direct Stage 1 APIs remain supported.
  Type: compatibility
  Source: v1 roadmap Stage 2 acceptance
  Check: `pytest tests/scene tests/write tests/examples -q` passes after model implementation.
  If false: adjust model facade to delegate without breaking scene APIs.
  Owner: Task 10.

- `A4` — `Model.write_dxf` may flatten all named drawings into one modelspace DXF in Stage 2.
  Type: design
  Source: Stage 2 design spec §4.2
  Check: DXF smoke test asserts entities from two named drawings appear in one readable DXF.
  If false: add a sheet/layout design before implementing multi-drawing export.
  Owner: Task 4.

- `A5` — `Assembly` is metadata-only in Stage 2.
  Type: design
  Source: Stage 2 design spec §4.5
  Check: tests assert `Assembly.to_dict` references part names, while STL/DXF exporters ignore assemblies.
  If false: defer assemblies from Stage 2 or write a separate assembly export design.
  Owner: Task 6.

---

## File Structure

```
src/cad/
├── __init__.py                  # add model-layer public re-exports
└── model/
    ├── __init__.py              # re-export model public types
    └── core.py                  # Model, Drawing2D, ModelLayer, Part, Assembly, ModelMetadata

tests/
├── examples/
│   └── test_model_plate.py      # model-first example smoke
└── model/
    ├── __init__.py
    ├── test_model_core.py       # metadata, named containers, exports
    ├── test_model_dxf.py        # DXF facade and ezdxf smoke
    ├── test_model_stl.py        # STL facade and binary invariants
    └── test_model_step.py       # reserved STEP behavior

examples/
└── model_plate.py               # model-first DXF/STL example

.warden/
├── specs/2026-05-08-pyseas-cad-stage-2-model-design.md
├── specs/2026-05-08-pyseas-cad-stage-3-dxf-production-design.md
└── plans/2026-05-08-pyseas-cad-stage-3-dxf-production.md
```

## Phase A - Model Core

### Task 1: model package scaffold and metadata

**Files:**
- Create: `src/cad/model/__init__.py`
- Create: `src/cad/model/core.py`
- Create: `tests/model/__init__.py`
- Create: `tests/model/test_model_core.py`
- Modify: `src/cad/__init__.py`

**Ownership:**
- In scope: model package exports, `ModelMetadata`, `Model` constructor, named container placeholders.
- Out of scope: DXF/STL export behavior, example docs.

**Assumption refs:** `A2`

**Invoke skill:** `@test-driven-development` and `@python` before starting this task.

- [ ] **Step 1: Write the failing tests**

Add tests covering public import, metadata validation, stable timestamp parsing, and named container identity:

```python
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cad import Assembly, Drawing2D, Model, ModelMetadata, Part


def test_model_imports_from_top_level() -> None:
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    assert model.name == "demo"
    assert isinstance(model.metadata, ModelMetadata)


def test_model_rejects_invalid_metadata() -> None:
    with pytest.raises(ValueError, match="model name"):
        Model("")
    with pytest.raises(ValueError, match="units"):
        Model("demo", units="mm")
    with pytest.raises(ValueError, match="timezone"):
        Model("demo", created_at=datetime(2026, 5, 8))


def test_model_normalizes_created_at() -> None:
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    assert model.metadata.created_at == datetime(2026, 5, 8, tzinfo=UTC)


def test_named_containers_are_reused() -> None:
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    assert isinstance(model.drawing("front"), Drawing2D)
    assert model.drawing("front") is model.drawing("front")
    assert isinstance(model.part("plate"), Part)
    assert model.part("plate") is model.part("plate")
    assert isinstance(model.assembly("assy"), Assembly)
    assert model.assembly("assy") is model.assembly("assy")
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/model/test_model_core.py -q`
Expected: FAIL with missing `cad.Model` / `cad.model`.

- [ ] **Step 3: Implement minimal model core**

Create frozen/slots where practical for metadata and normal dataclasses for mutable containers. Implement:

```python
@dataclass(frozen=True, slots=True)
class ModelMetadata:
    units: str = "m"
    author: str | None = None
    source: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
```

Implement `_parse_created_at`, `Model.__init__`, `drawing`, `part`, and `assembly`.
Use placeholder container classes with `name` and `_model` fields.

- [ ] **Step 4: Export public names**

Update `src/cad/model/__init__.py` and top-level `src/cad/__init__.py` with:

- `Model`
- `Drawing2D`
- `ModelLayer`
- `Part`
- `Assembly`
- `ModelMetadata`

- [ ] **Step 5: Verify**

Run: `pytest tests/model/test_model_core.py -q`
Expected: PASS.

Run: `pyright src/cad`
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add src/cad/__init__.py src/cad/model tests/model
git commit -m "feat(model): add model core metadata"
```

### Task 2: debug representation

**Files:**
- Modify: `src/cad/model/core.py`
- Modify: `tests/model/test_model_core.py`

**Ownership:**
- In scope: JSON-compatible `Model.to_dict` for names/counts/metadata.
- Out of scope: serializing full geometry.

**Assumption refs:** `A5`

**Invoke skill:** `@test-driven-development` and `@python` before starting this task.

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_model_to_dict_is_debug_shape_only() -> None:
    model = Model(
        "demo",
        author="Edward",
        source="unit-test",
        created_at="2026-05-08T00:00:00Z",
    )
    model.drawing("front")
    model.part("plate")
    model.assembly("assy").add("plate")

    data = model.to_dict()

    assert data["name"] == "demo"
    assert data["metadata"] == {
        "units": "m",
        "author": "Edward",
        "source": "unit-test",
        "created_at": "2026-05-08T00:00:00+00:00",
    }
    assert data["drawings"] == [{"name": "front", "layers": []}]
    assert data["parts"] == [{"name": "plate", "solids": 0}]
    assert data["assemblies"] == [{"name": "assy", "parts": ["plate"]}]
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/model/test_model_core.py::test_model_to_dict_is_debug_shape_only -q`
Expected: FAIL with missing `to_dict` / `Assembly.add`.

- [ ] **Step 3: Implement**

Add `Assembly.add(*parts: Part | str) -> Assembly` and `to_dict` methods for `Model`,
`Drawing2D`, `Part`, and `Assembly`. Keep values JSON-compatible.

- [ ] **Step 4: Verify**

Run: `pytest tests/model/test_model_core.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cad/model/core.py tests/model/test_model_core.py
git commit -m "feat(model): add debug representation"
```

## Phase B - DXF Facade

### Task 3: drawing facade and layer delegation

**Files:**
- Modify: `src/cad/model/core.py`
- Create: `tests/model/test_model_dxf.py`

**Ownership:**
- In scope: `Drawing2D.layer`, `ModelLayer.add`, `Drawing2D.add_text`, `Drawing2D.to_dxf_drawing`.
- Out of scope: `Model.write_dxf`.

**Assumption refs:** `A1`, `A3`

**Invoke skill:** `@test-driven-development` and `@python` before starting this task.

- [ ] **Step 1: Write failing tests**

```python
from __future__ import annotations

import pytest

from cad import Model, SceneError, circle, rectangle, sphere
from cad.scene import DxfDrawing


def test_drawing_layer_delegates_to_dxf_drawing() -> None:
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")
    layer = drawing.layer("PLATE", color=7).add(rectangle((0, 0), (1, 1)))
    assert layer is drawing.layer("PLATE")

    dxf = drawing.to_dxf_drawing()
    assert isinstance(dxf, DxfDrawing)
    assert "PLATE" in dxf.layers
    assert len(dxf.layers["PLATE"].entities) == 1


def test_drawing_text_delegates_to_dxf_drawing() -> None:
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")
    assert drawing.add_text("PLATE", at=(0, 0), height=0.1, layer="TEXT") is drawing
    assert drawing.to_dxf_drawing().texts[0].text == "PLATE"


def test_drawing_rejects_3d_shapes() -> None:
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")
    with pytest.raises(SceneError):
        drawing.layer("BAD").add(sphere((0, 0, 0), 1))  # type: ignore[arg-type]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/model/test_model_dxf.py -q`
Expected: FAIL with missing methods.

- [ ] **Step 3: Implement**

Make `Drawing2D` hold a private `DxfDrawing`. `ModelLayer` wraps a Stage 1
`Layer` and delegates `add`. Return stable `ModelLayer` wrappers by layer name.

- [ ] **Step 4: Verify**

Run: `pytest tests/model/test_model_dxf.py -q`
Expected: PASS.

Run: `pytest tests/scene tests/write -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cad/model/core.py tests/model/test_model_dxf.py
git commit -m "feat(model): add drawing facade"
```

### Task 4: model DXF export

**Files:**
- Modify: `src/cad/model/core.py`
- Modify: `tests/model/test_model_dxf.py`

**Ownership:**
- In scope: `Model.write_dxf`, multi-drawing flattening into one DXF modelspace.
- Out of scope: HATCH/BLOCK/INSERT/DIMENSION.

**Assumption refs:** `A1`, `A3`, `A4`

**Invoke skill:** `@test-driven-development` and `@python` before starting this task.

- [ ] **Step 1: Write failing tests**

Append:

```python
def test_model_write_dxf_round_trips(tmp_path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "model.dxf"

    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    model.drawing("front").layer("PLATE").add(rectangle((0, 0), (1, 1)))
    model.drawing("holes").layer("HOLES", color=1).add(circle((0.5, 0.5), 0.2))
    assert model.write_dxf(path) is model

    doc = ezdxf.readfile(path)
    audit = doc.audit()
    assert not audit.errors
    counts: dict[str, int] = {}
    for entity in doc.modelspace():
        counts[entity.dxftype()] = counts.get(entity.dxftype(), 0) + 1
    assert counts["LWPOLYLINE"] == 1
    assert counts["CIRCLE"] == 1


def test_model_write_dxf_matches_direct_scene_for_single_drawing(tmp_path) -> None:
    direct_path = tmp_path / "direct.dxf"
    model_path = tmp_path / "model.dxf"

    direct = DxfDrawing()
    direct.layer("PLATE").add(rectangle((0, 0), (1, 1)))
    direct.write(direct_path)

    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    model.drawing("front").layer("PLATE").add(rectangle((0, 0), (1, 1)))
    model.write_dxf(model_path)

    assert model_path.read_text(encoding="ascii") == direct_path.read_text(encoding="ascii")
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/model/test_model_dxf.py -q`
Expected: FAIL with missing `write_dxf`.

- [ ] **Step 3: Implement**

Implement `Model.write_dxf(path)` by creating an aggregate `DxfDrawing`, copying
layers/entities/texts from each `Drawing2D` in insertion order, then calling
`DxfDrawing.write(path)`. Preserve layer colors from first creation.

- [ ] **Step 4: Verify**

Run: `pytest tests/model/test_model_dxf.py -q`
Expected: PASS.

Run: `pytest tests/write/test_dxf.py tests/scene/test_scene.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cad/model/core.py tests/model/test_model_dxf.py
git commit -m "feat(model): add dxf export facade"
```

## Phase C - STL Facade

### Task 5: part facade and STL export

**Files:**
- Modify: `src/cad/model/core.py`
- Create: `tests/model/test_model_stl.py`

**Ownership:**
- In scope: `Part.add`, `Part.to_stl_mesh`, `Model.write_stl`.
- Out of scope: new tessellation behavior.

**Assumption refs:** `A1`, `A3`

**Invoke skill:** `@test-driven-development` and `@python` before starting this task.

- [ ] **Step 1: Write failing tests**

```python
from __future__ import annotations

import struct

import pytest

from cad import Model, SceneError, circle, prism, rectangle
from cad.scene import StlMesh


def test_part_add_delegates_to_stl_mesh() -> None:
    part = Model("demo", created_at="2026-05-08T00:00:00Z").part("box")
    assert part.add(prism((0, 0, 0), (1, 1, 1))) is part
    mesh = part.to_stl_mesh(tolerance=1e-3)
    assert isinstance(mesh, StlMesh)
    assert len(mesh.triangles) == 12


def test_part_rejects_2d_shapes() -> None:
    part = Model("demo", created_at="2026-05-08T00:00:00Z").part("bad")
    with pytest.raises(SceneError):
        part.add(circle((0, 0), 1))  # type: ignore[arg-type]


def test_model_write_stl_combines_parts(tmp_path) -> None:
    path = tmp_path / "model.stl"
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    model.part("box").add(prism((0, 0, 0), (1, 1, 1)))
    model.part("plate").add(rectangle((0, 0), (1, 1)).extrude("+z", 0.1))

    assert model.write_stl(path, tolerance=1e-3) is model

    data = path.read_bytes()
    assert struct.unpack("<I", data[80:84])[0] > 12
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/model/test_model_stl.py -q`
Expected: FAIL with missing methods.

- [ ] **Step 3: Implement**

Store solids on `Part`. Implement `Part.to_stl_mesh` and `Model.write_stl` by
adding all solids from all parts to one `StlMesh(tolerance=tolerance)`.
Forward `ascii` to `StlMesh.write`.

- [ ] **Step 4: Verify**

Run: `pytest tests/model/test_model_stl.py -q`
Expected: PASS.

Run: `pytest tests/write/test_stl.py tests/scene/test_scene.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cad/model/core.py tests/model/test_model_stl.py
git commit -m "feat(model): add stl export facade"
```

### Task 6: assembly metadata behavior

**Files:**
- Modify: `src/cad/model/core.py`
- Modify: `tests/model/test_model_core.py`

**Ownership:**
- In scope: `Assembly.add` validation and `to_dict` part references.
- Out of scope: assembly-aware STL/DXF export.

**Assumption refs:** `A5`

**Invoke skill:** `@test-driven-development` and `@python` before starting this task.

- [ ] **Step 1: Write failing tests**

Append:

```python
def test_assembly_accepts_parts_and_part_names() -> None:
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    plate = model.part("plate")
    assy = model.assembly("assy")

    assert assy.add(plate, "future_part") is assy
    assert model.to_dict()["assemblies"] == [
        {"name": "assy", "parts": ["plate", "future_part"]}
    ]


def test_assembly_rejects_empty_part_reference() -> None:
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    with pytest.raises(ValueError, match="part reference"):
        model.assembly("assy").add("")
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/model/test_model_core.py -q`
Expected: FAIL until assembly validation is complete.

- [ ] **Step 3: Implement**

Normalize `Part` objects to their names. Reject empty string references. Preserve
insertion order and allow repeated references only if there is a reason; default
to de-duplicating exact names.

- [ ] **Step 4: Verify**

Run: `pytest tests/model/test_model_core.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cad/model/core.py tests/model/test_model_core.py
git commit -m "feat(model): add assembly metadata"
```

## Phase D - Reserved STEP and Examples

### Task 7: reserved STEP behavior

**Files:**
- Modify: `src/cad/model/core.py`
- Create: `tests/model/test_model_step.py`

**Ownership:**
- In scope: explicit Stage 5 placeholder.
- Out of scope: any STEP file generation.

**Invoke skill:** `@test-driven-development` and `@python` before starting this task.

- [ ] **Step 1: Write failing test**

```python
from __future__ import annotations

import pytest

from cad import Model


def test_write_step_is_reserved_for_stage_5(tmp_path) -> None:
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    with pytest.raises(NotImplementedError, match="Stage 5"):
        model.write_step(tmp_path / "demo.step")
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/model/test_model_step.py -q`
Expected: FAIL with missing `write_step`.

- [ ] **Step 3: Implement**

Add `Model.write_step(self, path: str | Path) -> NoReturn` raising:

```python
raise NotImplementedError("STEP export is reserved for Stage 5")
```

- [ ] **Step 4: Verify**

Run: `pytest tests/model/test_model_step.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cad/model/core.py tests/model/test_model_step.py
git commit -m "feat(model): reserve step export"
```

### Task 8: model-first example

**Files:**
- Create: `examples/model_plate.py`
- Create: `tests/examples/test_model_plate.py`
- Modify: `README.md`

**Ownership:**
- In scope: runnable example and README quickstart update.
- Out of scope: replacing Stage 1 example.

**Assumption refs:** `A3`

**Invoke skill:** `@test-driven-development`, `@python`, and `@writing` before starting this task.

- [ ] **Step 1: Write failing example test**

```python
from __future__ import annotations

import subprocess
import sys


def test_model_plate_example(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, "examples/model_plate.py", "--out", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""
    assert (tmp_path / "model_plate.dxf").stat().st_size > 0
    assert (tmp_path / "model_plate.stl").stat().st_size > 0
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/examples/test_model_plate.py -q`
Expected: FAIL because example does not exist.

- [ ] **Step 3: Add example**

Create `examples/model_plate.py` using:

```python
from cad import Model, circle, rectangle
```

Build one profile, add it to `model.drawing("front")`, add extruded solid to
`model.part("plate")`, then write `model_plate.dxf` and `model_plate.stl`.

- [ ] **Step 4: Update README**

Make the README quickstart use `Model` as the preferred API. Keep direct
`DxfDrawing` and `StlMesh` documented as supported lower-level APIs. Update
"Current API" to include `Model`, `Drawing2D`, `Part`, and `Assembly`.

- [ ] **Step 5: Verify**

Run: `pytest tests/examples/test_model_plate.py tests/examples/test_plate_with_hole.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add README.md examples/model_plate.py tests/examples/test_model_plate.py
git commit -m "docs: add model-first example"
```

## Phase E - Stage Closeout

### Task 9: downstream roadmap artifacts

**Files:**
- Modify: `.warden/specs/2026-05-08-pyseas-cad-stage-2-model-design.md`
- Create: `.warden/specs/2026-05-08-pyseas-cad-stage-3-dxf-production-design.md`
- Create: `.warden/plans/2026-05-08-pyseas-cad-stage-3-dxf-production.md`
- Modify: `.warden/preference-lock.json`
- Modify: `.warden/plans/2026-05-08-pyseas-cad-v1-stage-plans.md` if shipped API differs from current plan.

**Ownership:**
- In scope: stage-end docs and preference decisions.
- Out of scope: implementing Stage 3.

**Assumption refs:** `A1`, `A4`, `A5`

**Invoke skill:** `@writing` before starting this task.

- [ ] **Step 1: Update Stage 2 post-implementation review**

Fill these fields in the Stage 2 spec:

- shipped API differences,
- verification commands/results,
- known limitations,
- Stage 3 plan updates,
- preference-lock decisions.

- [ ] **Step 2: Add preference-lock decisions**

Record at least:

- `model-layer`: thin facade over Stage 1 scenes.
- `model-dxf-export`: flatten named drawings into one modelspace DXF in Stage 2.
- `model-stl-export`: aggregate all parts into one STL mesh.
- `assembly-stage-2`: metadata-only grouping; exporters ignore assemblies.
- `step-placeholder`: `Model.write_step` reserved until Stage 5.

- [ ] **Step 3: Create Stage 3 spec stub**

Create `.warden/specs/2026-05-08-pyseas-cad-stage-3-dxf-production-design.md`
with status `draft`, carrying Stage 3 scope from the roadmap and referencing the
actual Stage 2 model API.

- [ ] **Step 4: Create Stage 3 plan stub**

Create `.warden/plans/2026-05-08-pyseas-cad-stage-3-dxf-production.md` with
status `draft`, high-level TDD task headings for HATCH, BLOCK, INSERT, linetypes,
model-first examples, and ezdxf audit tests. Do not mark it approved until Stage
2 review is complete.

- [ ] **Step 5: Verify docs mention no stale Stage 2 marker as current work**

Run: `rg "Stage 2|Model" README.md .warden/specs .warden/plans`
Expected: README names Stage 2 as implemented/current API after implementation;
Stage 3 artifacts name production DXF as next.

- [ ] **Step 6: Commit**

```bash
git add .warden README.md
git commit -m "docs: close stage 2 planning artifacts"
```

### Task 10: full verification and final review

**Files:**
- No planned source edits unless verification finds defects.

**Ownership:**
- In scope: full test/type/lint gates and final code review.
- Out of scope: new feature work.

**Assumption refs:** `A2`, `A3`

**Invoke skill:** `@verification-before-completion`, then `@reviewer`, then `@git`.

- [ ] **Step 1: Run focused model tests**

Run: `pytest tests/model tests/examples -q`
Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 3: Run type check**

Run: `pyright src/cad`
Expected: 0 errors.

- [ ] **Step 4: Run lint**

Run: `ruff check src/cad tests`
Expected: 0 violations.

- [ ] **Step 5: Verify runtime dependencies**

Run:

```bash
python -c "import importlib.metadata as m; assert (m.distribution('pyseas-cad').requires or []) == []"
```

Expected: exits 0.

- [ ] **Step 6: Review diff**

Run: `git diff --stat main...HEAD && git diff main...HEAD`
Expected: changes are scoped to model layer, tests, examples, README, and Warden artifacts.

- [ ] **Step 7: Commit fixes if any**

If review finds defects, fix them with focused commits and repeat Steps 1-6.

- [ ] **Step 8: Final stage commit marker if needed**

If Task 9 did not already commit closeout docs after verification results were
known, commit the final spec/review updates:

```bash
git add .warden README.md
git commit -m "docs: record stage 2 verification"
```

## Final Acceptance

Run all commands from Task 10 successfully. Then Stage 2 can be merged to `main`
with a fast-forward merge from the root repo:

```bash
git switch main
git merge --ff-only stage-2-model
git branch -d stage-2-model
git worktree remove .worktrees/stage-2-model
```
