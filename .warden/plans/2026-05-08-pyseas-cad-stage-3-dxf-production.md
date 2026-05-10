# pyseas-cad Stage 3 Production DXF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task when tasks are independent. For same-session manual execution, follow this plan directly. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add production DXF support for linetypes, ANSI31 hatches, block definitions, and inserts through the model-first API.

**Architecture:** Extend `cad.scene.dxf` with explicit scene state for linetypes, hatches, blocks, and inserts. Keep `cad.write.dxf.sections.render_dxf` as the stable public writer wrapper while adding focused writer modules for HATCH, BLOCKS, INSERT, and LTYPE output. Expose model-first methods by delegating `Drawing2D` and `ModelLayer` to the underlying `DxfDrawing` scene.

**Tech Stack:** Python 3.11+, pure-stdlib runtime, pytest, pyright strict via `pyproject.toml`, ruff, ezdxf for DXF verification.

**Recommended Skills:** test-driven-development, python, writing, reviewer, verification-before-completion, git

**Recommended MCPs:** none

**Status:** approved
**Refinement passes:** 1 (structured validation clean: worktree precondition satisfied, no unresolved markers found, YAML sidecar validates)

## Bootstrap Context

This plan was created in `.worktrees/stage-3-dxf-plan/` on branch
`stage-3-dxf-plan`.

Controlling design:
`.warden/specs/2026-05-08-pyseas-cad-stage-3-dxf-production-design.md`.

## Assumptions

- `A1` — Runtime remains pure stdlib.
  Type: policy
  Source: README boundaries and roadmap product principles
  Check: `.venv/bin/python -c "import importlib.metadata as m; assert (m.distribution('pyseas-cad').requires or []) == []"`
  If false: remove runtime dependency or record explicit architecture decision before continuing.
  Owner: Task 10.

- `A2` — DXF output continues to target R2018 (`AC1032`) and metres (`$INSUNITS=6`).
  Type: architectural
  Source: preference lock `dxf-version` and `units`
  Check: golden or text tests assert `AC1032` and `$INSUNITS`.
  If false: revise roadmap and compatibility notes before implementation.
  Owner: Task 10.

- `A3` — `ezdxf` can audit the Stage 3 HATCH/BLOCK/INSERT subset.
  Type: external
  Source: existing DXF test strategy
  Check: `ezdxf.readfile(path).audit()` has no errors on smoke files.
  If false: capture the failing entity subset in Known Limitations and narrow acceptance.
  Owner: Tasks 4 and 7.

- `A4` — Built-in `CENTER` and `HIDDEN` linetypes are enough for Stage 3.
  Type: design
  Source: Stage 3 design spec §4.1
  Check: README production example uses only built-in linetypes.
  If false: design custom linetype registration before implementation.
  Owner: Task 2.

- `A5` — Block definitions are drawing-local and `Model.write_dxf` rejects duplicate block names across drawings.
  Type: design
  Source: Stage 3 design spec §4.3
  Check: model integration tests cover duplicate block-name rejection.
  If false: add model-wide block namespace design before implementation.
  Owner: Tasks 6 and 8.

---

## File Structure

```
src/cad/
├── model/core.py                    # Drawing2D/ModelLayer delegates for hatches, blocks, inserts, linetypes
├── scene/dxf.py                     # Layer, DxfDrawing, HatchEntity, BlockDefinition, InsertEntity
└── write/dxf/
    ├── blocks.py                    # BLOCK/ENDBLK and INSERT emission helpers
    ├── document.py                  # section ordering, counts, bounds, aggregate render
    ├── entities.py                  # existing entities plus INSERT dispatch if kept there
    ├── hatch.py                     # ANSI31 HATCH emission
    ├── tables.py                    # LAYER + LTYPE table bodies
    └── sections.py                  # stable render_dxf/write_dxf wrapper

tests/
├── examples/test_production_dxf.py
├── model/test_model_dxf_production.py
└── write/
    ├── test_dxf_blocks.py
    ├── test_dxf_hatch.py
    └── test_dxf_linetypes.py

examples/
└── production_dxf.py
```

## Phase A - Linetypes

### Task 1: scene linetype API

**Files:**
- Modify: `src/cad/scene/dxf.py`
- Modify: `src/cad/model/core.py`
- Create: `tests/write/test_dxf_linetypes.py`
- Modify: `tests/scene/test_scene.py`
- Modify: `tests/model/test_model_dxf.py`

**Ownership:**
- In scope: `Layer.linetype`, `DxfDrawing.layer(..., linetype=...)`, `Drawing2D.layer(..., linetype=...)`, validation for built-in linetypes.
- Out of scope: LTYPE table serialization.

**Assumption refs:** `A4`

**Invoke skill:** `@test-driven-development`, then `@python`.

- [ ] **Step 1: Write failing scene/model tests**

Add tests:

```python
from __future__ import annotations

import pytest

from cad import DxfDrawing, Model, SceneError


def test_dxf_layer_accepts_builtin_linetype() -> None:
    layer = DxfDrawing().layer("CENTERLINES", color=3, linetype="CENTER")
    assert layer.linetype == "CENTER"


def test_dxf_layer_rejects_unknown_linetype() -> None:
    with pytest.raises(SceneError, match="linetype"):
        DxfDrawing().layer("X", linetype="DASHDOT")


def test_model_layer_accepts_builtin_linetype() -> None:
    layer = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front").layer(
        "HIDDEN", color=8, linetype="HIDDEN"
    )
    assert layer.name == "HIDDEN"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/write/test_dxf_linetypes.py tests/model/test_model_dxf.py -q`
Expected: FAIL because `DxfDrawing.layer` and `Drawing2D.layer` do not accept `linetype`.

- [ ] **Step 3: Implement scene/model API**

Add a local constant in `src/cad/scene/dxf.py`:

```python
SUPPORTED_LINETYPES = {"CONTINUOUS", "HIDDEN", "CENTER"}
```

Update `DxfDrawing.layer` and `Drawing2D.layer` signatures to accept
`linetype: str = "CONTINUOUS"`, normalize to uppercase, and raise `SceneError`
when unsupported. Preserve old calls by keeping `color` second.

- [ ] **Step 4: Verify**

Run: `.venv/bin/pytest tests/write/test_dxf_linetypes.py tests/scene/test_scene.py tests/model/test_model_dxf.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cad/scene/dxf.py src/cad/model/core.py tests/write/test_dxf_linetypes.py tests/scene/test_scene.py tests/model/test_model_dxf.py
git commit -m "feat(dxf): add built-in linetype layer API"
```

### Task 2: LTYPE table writer

**Files:**
- Modify: `src/cad/write/dxf/tables.py`
- Modify: `src/cad/write/dxf/document.py`
- Modify: `tests/write/test_dxf_linetypes.py`

**Ownership:**
- In scope: `LTYPE` table body for `CONTINUOUS`, `HIDDEN`, and `CENTER`.
- Out of scope: custom linetype registration.

**Assumption refs:** `A2`, `A4`

**Invoke skill:** `@test-driven-development`, then `@python`.

- [ ] **Step 1: Write failing writer tests**

Add tests:

```python
from cad import DxfDrawing, line
from cad.write.dxf.sections import render_dxf


def test_ltype_table_emits_used_builtin_linetype() -> None:
    drawing = DxfDrawing()
    drawing.layer("CENTERLINES", color=3, linetype="CENTER").add(line((0, 0), (1, 0)))

    text = render_dxf(drawing)

    assert "\n2\nLTYPE\n" in text
    assert "\n2\nCENTER\n" in text
    assert "\n8\nCENTERLINES\n" in text
    assert "\n6\nCENTER\n" in text


def test_linetype_round_trip_with_ezdxf(tmp_path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "linetype.dxf"
    drawing = DxfDrawing()
    drawing.layer("HIDDEN_LINES", color=8, linetype="HIDDEN").add(line((0, 0), (1, 0)))
    drawing.write(path)

    audit = ezdxf.readfile(path).audit()

    assert not audit.errors
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/write/test_dxf_linetypes.py -q`
Expected: FAIL because no `LTYPE` table is emitted.

- [ ] **Step 3: Implement LTYPE table**

Add built-in linetype records in `src/cad/write/dxf/tables.py`. Emit
`CONTINUOUS` plus non-continuous linetypes used by drawing layers before the
LAYER table inside `TABLES`.

- [ ] **Step 4: Verify**

Run: `.venv/bin/pytest tests/write/test_dxf_linetypes.py tests/write/test_dxf.py -q`
Expected: PASS. Existing golden may need an intentional update because TABLES
now contains an `LTYPE` table.

- [ ] **Step 5: Commit**

```bash
git add src/cad/write/dxf/tables.py src/cad/write/dxf/document.py tests/write/test_dxf_linetypes.py tests/write/goldens/smoke.dxf
git commit -m "feat(dxf): emit linetype table"
```

## Phase B - HATCH

### Task 3: hatch scene API

**Files:**
- Modify: `src/cad/scene/dxf.py`
- Modify: `src/cad/model/core.py`
- Create: `tests/write/test_dxf_hatch.py`
- Create: `tests/model/test_model_dxf_production.py`

**Ownership:**
- In scope: `HatchEntity`, `Layer.hatch`, `ModelLayer.hatch`, validation.
- Out of scope: DXF HATCH serialization.

**Invoke skill:** `@test-driven-development`, then `@python`.

- [ ] **Step 1: Write failing tests**

Add tests:

```python
import pytest

from cad import DxfDrawing, Model, SceneError, line, rectangle


def test_layer_hatch_records_closed_boundary() -> None:
    drawing = DxfDrawing()
    layer = drawing.layer("SECTION")
    assert layer.hatch(rectangle((0, 0), (1, 1)), pattern="ANSI31", scale=0.025) is layer
    assert drawing.hatches[0].layer == "SECTION"
    assert drawing.hatches[0].pattern == "ANSI31"


def test_layer_hatch_rejects_open_boundary() -> None:
    with pytest.raises(SceneError, match="closed"):
        DxfDrawing().layer("SECTION").hatch(line((0, 0), (1, 0)))


def test_model_layer_hatch_delegates() -> None:
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")
    drawing.layer("SECTION").hatch(rectangle((0, 0), (1, 1)))
    assert drawing.to_dxf_drawing().hatches[0].layer == "SECTION"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/write/test_dxf_hatch.py tests/model/test_model_dxf_production.py -q`
Expected: FAIL because hatch APIs are missing.

- [ ] **Step 3: Implement scene/model API**

Add `HatchEntity` dataclass to `src/cad/scene/dxf.py` with boundary, layer,
pattern, angle, and scale. Store `hatches: list[HatchEntity]` on `DxfDrawing`.
Give `Layer` a `_drawing` back-reference or a narrow hatch callback so
`Layer.hatch(...)` appends to the owning drawing.

- [ ] **Step 4: Verify**

Run: `.venv/bin/pytest tests/write/test_dxf_hatch.py tests/model/test_model_dxf_production.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cad/scene/dxf.py src/cad/model/core.py tests/write/test_dxf_hatch.py tests/model/test_model_dxf_production.py
git commit -m "feat(dxf): add hatch scene API"
```

### Task 4: HATCH writer

**Files:**
- Create: `src/cad/write/dxf/hatch.py`
- Modify: `src/cad/write/dxf/document.py`
- Modify: `src/cad/write/dxf/entities.py`
- Modify: `tests/write/test_dxf_hatch.py`
- Modify: `tests/write/goldens/smoke.dxf` if table changes affect golden output.

**Ownership:**
- In scope: ANSI31 HATCH entity emission for closed polyline-like boundaries.
- Out of scope: hatch holes, associative hatch metadata.

**Assumption refs:** `A3`

**Invoke skill:** `@test-driven-development`, then `@python`.

- [ ] **Step 1: Write failing writer tests**

Add tests:

```python
from cad import DxfDrawing, rectangle
from cad.write.dxf.sections import render_dxf


def test_hatch_entity_emits_ansi31() -> None:
    drawing = DxfDrawing()
    drawing.layer("SECTION").hatch(rectangle((0, 0), (1, 1)), pattern="ANSI31", scale=0.025)

    text = render_dxf(drawing)

    assert "\n0\nHATCH\n" in text
    assert "\n2\nANSI31\n" in text
    assert "\n8\nSECTION\n" in text


def test_hatch_round_trip_with_ezdxf(tmp_path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "hatch.dxf"
    drawing = DxfDrawing()
    drawing.layer("SECTION").hatch(rectangle((0, 0), (1, 1)), pattern="ANSI31", scale=0.025)
    drawing.write(path)

    doc = ezdxf.readfile(path)
    audit = doc.audit()
    counts: dict[str, int] = {}
    for entity in doc.modelspace():
        counts[entity.dxftype()] = counts.get(entity.dxftype(), 0) + 1

    assert not audit.errors
    assert counts["HATCH"] == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/write/test_dxf_hatch.py -q`
Expected: FAIL because hatches are not serialized.

- [ ] **Step 3: Implement HATCH writer**

Create `hatch_entity(hatch: HatchEntity) -> list[str]`. Use flattened boundary
points from rectangles, polylines, and `curves_to_polyline` fallback. Add hatches
to entity count, bounds, and ENTITIES section in `document.py`.

- [ ] **Step 4: Verify**

Run: `.venv/bin/pytest tests/write/test_dxf_hatch.py tests/write/test_dxf.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cad/write/dxf/hatch.py src/cad/write/dxf/document.py src/cad/write/dxf/entities.py tests/write/test_dxf_hatch.py tests/write/goldens/smoke.dxf
git commit -m "feat(dxf): emit ansi31 hatch"
```

## Phase C - BLOCK and INSERT

### Task 5: block and insert scene API

**Files:**
- Modify: `src/cad/scene/dxf.py`
- Modify: `src/cad/model/core.py`
- Create: `tests/write/test_dxf_blocks.py`
- Modify: `tests/model/test_model_dxf_production.py`

**Ownership:**
- In scope: `BlockDefinition`, `DxfDrawing.block`, `DxfDrawing.insert`, `Drawing2D.block`, `Drawing2D.insert`, validation.
- Out of scope: DXF BLOCKS/INSERT serialization.

**Assumption refs:** `A5`

**Invoke skill:** `@test-driven-development`, then `@python`.

- [ ] **Step 1: Write failing tests**

Add tests:

```python
import pytest

from cad import DxfDrawing, Model, SceneError, circle


def test_block_definition_records_entities() -> None:
    drawing = DxfDrawing()
    block = drawing.block("PIN_MARK", base=(0, 0))
    assert block.layer("SYMBOL").add(circle((0, 0), 0.025)) is block.layers["SYMBOL"]
    assert drawing.blocks["PIN_MARK"] is block


def test_insert_requires_existing_block() -> None:
    with pytest.raises(SceneError, match="block"):
        DxfDrawing().insert("MISSING", at=(0, 0))


def test_model_drawing_block_and_insert_delegates() -> None:
    drawing = Model("demo", created_at="2026-05-08T00:00:00Z").drawing("front")
    drawing.block("PIN_MARK").layer("SYMBOL").add(circle((0, 0), 0.025))
    assert drawing.insert("PIN_MARK", at=(1, 1), layer="SYMBOL") is drawing
    assert drawing.to_dxf_drawing().inserts[0].name == "PIN_MARK"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/write/test_dxf_blocks.py tests/model/test_model_dxf_production.py -q`
Expected: FAIL because block APIs are missing.

- [ ] **Step 3: Implement scene/model API**

Add `BlockDefinition` and `InsertEntity` dataclasses. Give `BlockDefinition`
`layer(...)` and `add_text(...)` methods matching `DxfDrawing` where needed.
Validate non-empty block names, unique names, known insert names, positive scale.

- [ ] **Step 4: Verify**

Run: `.venv/bin/pytest tests/write/test_dxf_blocks.py tests/model/test_model_dxf_production.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cad/scene/dxf.py src/cad/model/core.py tests/write/test_dxf_blocks.py tests/model/test_model_dxf_production.py
git commit -m "feat(dxf): add block and insert scene API"
```

### Task 6: BLOCKS and INSERT writer

**Files:**
- Create: `src/cad/write/dxf/blocks.py`
- Modify: `src/cad/write/dxf/document.py`
- Modify: `src/cad/write/dxf/entities.py`
- Modify: `tests/write/test_dxf_blocks.py`

**Ownership:**
- In scope: BLOCK/ENDBLK section emission and INSERT entity emission.
- Out of scope: nested blocks and attributes.

**Assumption refs:** `A3`

**Invoke skill:** `@test-driven-development`, then `@python`.

- [ ] **Step 1: Write failing writer tests**

Add tests:

```python
from cad import DxfDrawing, circle
from cad.write.dxf.sections import render_dxf


def test_block_and_insert_emit_dxf_tokens() -> None:
    drawing = DxfDrawing()
    drawing.block("PIN_MARK").layer("SYMBOL").add(circle((0, 0), 0.025))
    drawing.insert("PIN_MARK", at=(1, 1), layer="SYMBOL")
    drawing.insert("PIN_MARK", at=(2, 1), layer="SYMBOL", rotation=90)

    text = render_dxf(drawing)

    assert "\n0\nBLOCK\n" in text
    assert "\n2\nPIN_MARK\n" in text
    assert text.count("\n0\nINSERT\n") == 2
    assert "\n50\n90\n" in text


def test_block_insert_round_trip_with_ezdxf(tmp_path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "blocks.dxf"
    drawing = DxfDrawing()
    drawing.block("PIN_MARK").layer("SYMBOL").add(circle((0, 0), 0.025))
    drawing.insert("PIN_MARK", at=(1, 1), layer="SYMBOL")
    drawing.insert("PIN_MARK", at=(2, 1), layer="SYMBOL")
    drawing.write(path)

    doc = ezdxf.readfile(path)
    audit = doc.audit()

    assert not audit.errors
    assert "PIN_MARK" in doc.blocks
    assert sum(1 for entity in doc.modelspace() if entity.dxftype() == "INSERT") == 2
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/write/test_dxf_blocks.py -q`
Expected: FAIL because BLOCKS/INSERT are not serialized.

- [ ] **Step 3: Implement writer**

Create `blocks_section_body(drawing: DxfDrawing) -> list[str]` and
`insert_entity(insert: InsertEntity) -> list[str]`. Add insert entities to entity
count and bounds. Use block definition base point for BLOCK records.

- [ ] **Step 4: Verify**

Run: `.venv/bin/pytest tests/write/test_dxf_blocks.py tests/write/test_dxf.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cad/write/dxf/blocks.py src/cad/write/dxf/document.py src/cad/write/dxf/entities.py tests/write/test_dxf_blocks.py
git commit -m "feat(dxf): emit blocks and inserts"
```

## Phase D - Model Integration and Examples

### Task 7: model export aggregation for production DXF state

**Files:**
- Modify: `src/cad/model/core.py`
- Modify: `tests/model/test_model_dxf_production.py`

**Ownership:**
- In scope: `Model.write_dxf` copies hatches, blocks, inserts, and linetypes from `Drawing2D` scenes into the aggregate `DxfDrawing`.
- Out of scope: model-wide block namespace API.

**Assumption refs:** `A5`

**Invoke skill:** `@test-driven-development`, then `@python`.

- [ ] **Step 1: Write failing model integration tests**

Add tests:

```python
from cad import Model, SceneError, circle, rectangle


def test_model_write_dxf_preserves_hatch_blocks_inserts_and_linetypes(tmp_path) -> None:
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "production.dxf"
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    drawing = model.drawing("front")
    drawing.layer("PLATE").add(rectangle((0, 0), (1, 1)))
    drawing.layer("SECTION", linetype="HIDDEN").hatch(rectangle((0, 0), (1, 1)))
    drawing.block("PIN_MARK").layer("SYMBOL").add(circle((0, 0), 0.025))
    drawing.insert("PIN_MARK", at=(0.5, 0.5), layer="SYMBOL")

    model.write_dxf(path)
    doc = ezdxf.readfile(path)
    audit = doc.audit()

    assert not audit.errors
    assert "PIN_MARK" in doc.blocks
    assert sum(1 for entity in doc.modelspace() if entity.dxftype() == "HATCH") == 1
    assert sum(1 for entity in doc.modelspace() if entity.dxftype() == "INSERT") == 1


def test_model_write_dxf_rejects_duplicate_block_names_across_drawings(tmp_path) -> None:
    model = Model("demo", created_at="2026-05-08T00:00:00Z")
    model.drawing("front").block("PIN_MARK")
    model.drawing("side").block("PIN_MARK")

    with pytest.raises(SceneError, match="duplicate block"):
        model.write_dxf(tmp_path / "duplicate.dxf")
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/model/test_model_dxf_production.py -q`
Expected: FAIL because `Model.write_dxf` does not copy new scene state yet.

- [ ] **Step 3: Implement aggregation**

Update `Model.write_dxf` to copy layers with linetype, hatches, block
definitions, inserts, and text. Reject duplicate block names across named
drawings.

- [ ] **Step 4: Verify**

Run: `.venv/bin/pytest tests/model/test_model_dxf_production.py tests/model/test_model_dxf.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cad/model/core.py tests/model/test_model_dxf_production.py
git commit -m "feat(model): preserve production dxf state"
```

### Task 8: production DXF example and README

**Files:**
- Create: `examples/production_dxf.py`
- Create: `tests/examples/test_production_dxf.py`
- Modify: `README.md`

**Ownership:**
- In scope: one runnable model-first production DXF example.
- Out of scope: domain-specific padeye/shackle recipes.

**Invoke skill:** `@test-driven-development`, `@python`, then `@writing`.

- [ ] **Step 1: Write failing example test**

```python
from __future__ import annotations

import subprocess
import sys


def test_production_dxf_example(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, "examples/production_dxf.py", "--out", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout == ""
    assert (tmp_path / "production_plate.dxf").stat().st_size > 0
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv/bin/pytest tests/examples/test_production_dxf.py -q`
Expected: FAIL because example does not exist.

- [ ] **Step 3: Add example**

Create `examples/production_dxf.py` that builds a model with outline, text,
ANSI31 hatch, a CENTER or HIDDEN linetype layer, one block definition, and two
inserts. It writes `production_plate.dxf`.

- [ ] **Step 4: Update README**

Update Current API and add a short production DXF example showing hatches,
linetypes, blocks, and inserts. Keep limitations honest: dimensions remain
Stage 4, STEP remains Stage 5.

- [ ] **Step 5: Verify**

Run: `.venv/bin/pytest tests/examples/test_production_dxf.py tests/examples -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add README.md examples/production_dxf.py tests/examples/test_production_dxf.py
git commit -m "docs: add production dxf example"
```

## Phase E - Stage Closeout

### Task 9: Stage 3 documentation and downstream artifacts

**Files:**
- Modify: `.warden/specs/2026-05-08-pyseas-cad-stage-3-dxf-production-design.md`
- Modify: `.warden/preference-lock.json`
- Modify: `.warden/plans/2026-05-08-pyseas-cad-v1-stage-plans.md`
- Create: `.warden/specs/2026-05-08-pyseas-cad-stage-4-dimensions-design.md`
- Create: `.warden/plans/2026-05-08-pyseas-cad-stage-4-dimensions.md`

**Ownership:**
- In scope: closeout review and next-stage planning artifacts.
- Out of scope: implementing dimensions.

**Invoke skill:** `@writing`.

- [ ] **Step 1: Fill Stage 3 post-implementation review**

Record shipped API differences, verification results, known limitations, Stage 4
updates, and preference-lock decisions.

- [ ] **Step 2: Add preference-lock decisions**

Record:

- `dxf-linetypes-stage-3`
- `dxf-hatch-api`
- `dxf-block-api`
- `dxf-insert-api`
- `model-dxf-production-export`

- [ ] **Step 3: Create Stage 4 dimensions design draft**

Create `.warden/specs/2026-05-08-pyseas-cad-stage-4-dimensions-design.md` with
status `draft`, carrying roadmap scope and actual Stage 3 API references.

- [ ] **Step 4: Create Stage 4 dimensions plan draft**

Create `.warden/plans/2026-05-08-pyseas-cad-stage-4-dimensions.md` with status
`draft`, headings for dimension strategy, linear/aligned/radial/angular
dimensions, helper geometry, examples, and viewer smoke tests.

- [ ] **Step 5: Verify docs state Stage 4 is next**

Run: `rg "Stage 3|Stage 4|HATCH|INSERT|DIMENSION" README.md .warden/specs .warden/plans`
Expected: Stage 3 is implemented/current, Stage 4 dimensions are next.

- [ ] **Step 6: Commit**

```bash
git add .warden README.md
git commit -m "docs: close stage 3 planning artifacts"
```

### Task 10: full verification and review

**Files:**
- No planned source edits unless verification finds defects.

**Ownership:**
- In scope: final acceptance gates.
- Out of scope: new feature work.

**Assumption refs:** `A1`, `A2`, `A3`

**Invoke skill:** `@verification-before-completion`, then `@reviewer`, then `@git`.

- [ ] **Step 1: Run focused DXF tests**

Run: `.venv/bin/pytest tests/write -q -k dxf`
Expected: PASS.

- [ ] **Step 2: Run model/example tests**

Run: `.venv/bin/pytest tests/model tests/examples -q`
Expected: PASS.

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/pytest -q`
Expected: PASS.

- [ ] **Step 4: Run type check**

Run: `.venv/bin/pyright src/cad`
Expected: 0 errors.

- [ ] **Step 5: Run lint**

Run: `.venv/bin/ruff check src/cad tests`
Expected: 0 violations.

- [ ] **Step 6: Verify runtime dependencies**

Run:

```bash
.venv/bin/python -c "import importlib.metadata as m; assert (m.distribution('pyseas-cad').requires or []) == []"
```

Expected: exits 0.

- [ ] **Step 7: Review diff**

Run: `git diff --stat main...HEAD && git diff main...HEAD`
Expected: changes are scoped to Stage 3 DXF scene/writer/model/docs/tests.

- [ ] **Step 8: Commit final fixes if any**

If review finds defects, fix them with focused commits and repeat Steps 1-7.

## Final Acceptance

After Task 10 passes, merge with:

```bash
git switch main
git merge --ff-only stage-3-dxf-plan
```
