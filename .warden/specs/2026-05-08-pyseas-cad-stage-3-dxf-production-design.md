# cady Stage 3 - Production DXF

**Status:** approved planning contract.
**Date:** 2026-05-11.
**Purpose:** Add production-oriented DXF features to the Stage 2 model-first API:
HATCH, BLOCK, INSERT, and linetypes.

---

## 1. Goal

Stage 3 makes 2D output useful for pyseas-yard-style fabrication and review
drawings without starting the dimension engine.

Target user flow:

```python
from cady import Model, circle, line, rectangle

outline = rectangle((0, 0), (1.0, 0.6))
hole = circle((0.5, 0.3), 0.12)

model = Model("production_plate")
front = model.drawing("front")
front.layer("PLATE", color=7).add(outline).add(hole)
front.layer("SECTION", color=8).hatch(outline, pattern="ANSI31", scale=0.025)
front.layer("CENTER", color=3, linetype="CENTER").add(line((0.5, 0.05), (0.5, 0.55)))

symbol = front.block("PIN_MARK", base=(0, 0))
symbol.layer("SYMBOL", color=2).add(circle((0, 0), 0.025))
front.insert("PIN_MARK", at=(0.5, 0.3), layer="SYMBOL")

model.write_dxf("production_plate.dxf")
```

## 2. Constraints

Runtime remains pure stdlib. Stage 1 direct APIs and Stage 2 `Model` APIs remain
supported. DXF output stays R2018 (`AC1032`) and write-only. Geometry stays
format-blind; hatch, block, insert, and linetype data live in `cady.scene.dxf`
and model facade wrappers, not in `cady.geom`.

Stage 3 is not a full drafting system. Dimensions move to Stage 4. Sheet/title
block layout remains outside core.

## 3. Alternatives Considered

| Criterion | Layer-level hatch/block facade | Drawing-level only | Raw writer-only API |
|---|---|---|---|
| User ergonomics | Best: matches existing `layer(...).add(...)` | Acceptable but more verbose | Poor |
| Preserves existing API | Yes | Yes | Yes |
| Model-first fit | Strong | Medium | Weak |
| Implementation effort | Medium | Low | Low |
| Stage 4 extensibility | Good | Good | Poor |

Decision: add low-level state to `DxfDrawing`, expose hatch through `Layer` and
`ModelLayer`, and expose block/insert at drawing level. This keeps layer-owned
visual styling natural while keeping block definitions and insert references in
the drawing namespace where DXF expects them.

## 4. Public API Contract

### 4.1 Linetypes

`Layer` keeps its existing `linetype` field. `DxfDrawing.layer` and
`Drawing2D.layer` gain an optional keyword:

```python
layer(name: str, color: int = 7, linetype: str = "CONTINUOUS")
```

Rules:

- Existing positional calls continue to work.
- Re-requesting an existing layer returns it and does not mutate color or
  linetype.
- Supported built-in linetypes: `CONTINUOUS`, `HIDDEN`, `CENTER`.
- Any other linetype raises `SceneError` until custom pattern registration is
  separately designed.

The DXF writer emits an `LTYPE` table containing `CONTINUOUS` plus every
non-continuous linetype used by a layer.

### 4.2 HATCH

Layer-level API:

```python
Layer.hatch(
    boundary: Shape2D,
    *,
    pattern: str = "ANSI31",
    angle: float = 45.0,
    scale: float = 1.0,
) -> Layer
```

Model facade:

```python
ModelLayer.hatch(...) -> ModelLayer
```

Rules:

- `boundary` must be closed.
- `pattern` supports `ANSI31` only in Stage 3.
- `scale` must be positive.
- Hatches are stored separately from layer shape entities so tests can count
  ordinary shapes and hatches independently.
- DXF HATCH boundary supports closed polylines/rectangles and closed shapes that
  can be flattened to a closed polyline. Holes in hatches are not required in
  Stage 3; hole hatching can be expressed by hatching only the desired outline.

### 4.3 BLOCK and INSERT

Drawing-level API:

```python
DxfDrawing.block(name: str, base: Vec2 | tuple[float, float] = (0, 0)) -> BlockDefinition
DxfDrawing.insert(
    name: str,
    at: Vec2 | tuple[float, float],
    *,
    layer: str = "0",
    scale: float = 1.0,
    rotation: float = 0.0,
) -> DxfDrawing
```

Model facade:

```python
Drawing2D.block(...) -> BlockDefinition
Drawing2D.insert(...) -> Drawing2D
```

Rules:

- Block names must be non-empty and unique in one drawing.
- A block definition has layers and text support similar to `DxfDrawing`, but no
  nested block definitions in Stage 3.
- `insert` requires a previously defined block name.
- `scale` must be positive.
- `rotation` is degrees, matching DXF group code semantics.
- Insert layer controls the `INSERT` entity layer. Definition entity layers are
  preserved inside the block definition.
- `Model.write_dxf` merges block definitions from named drawings. Duplicate
  block names across drawings raise `SceneError`.

### 4.4 Writer Layout

Keep public imports stable:

```python
from cady.write.dxf.sections import render_dxf, write_dxf
```

Internal writer modules:

- `entities.py`: LINE/LWPOLYLINE/CIRCLE/ARC/MTEXT/INSERT dispatch.
- `hatch.py`: HATCH boundary conversion and entity emission.
- `blocks.py`: BLOCK/ENDBLK section body emission.
- `tables.py`: LAYER and LTYPE table bodies.
- `document.py`: section ordering and top-level DXF rendering.

## 5. Test Strategy

Working means a caller can create a model-first drawing with normal geometry,
text, ANSI31 hatch, a reusable block inserted twice, and a hidden/center
linetype layer, then write a DXF that `ezdxf` opens and audits without errors.

| Behavior | Risk | Layer | Tool | Assertion |
|---|---|---|---|---|
| Linetype table | Medium | Writer | pytest + text checks + ezdxf | LTYPE table includes CENTER/HIDDEN when used |
| Hatch validation | Medium | Scene | pytest | rejects open boundary, bad pattern, non-positive scale |
| Hatch writer | High | Writer | pytest + ezdxf | modelspace contains HATCH and audit has no errors |
| Block validation | Medium | Scene | pytest | rejects duplicate/empty block names and unknown inserts |
| Block/insert writer | High | Writer | pytest + ezdxf | BLOCKS contains definition, ENTITIES contains INSERTs |
| Model merge | High | Integration | pytest | hatches, linetypes, blocks, inserts survive `Model.write_dxf` |
| Existing behavior | High | Regression | pytest existing tests | Stage 1/2 tests pass unchanged |
| Docs/example | Medium | Smoke | pytest subprocess | production example writes DXF with new entity types |

## 6. Acceptance Criteria

- Existing `DxfDrawing.layer("NAME", color)` and `Model.drawing(...).layer(...)`
  calls remain valid.
- A drawing using `linetype="CENTER"` emits a valid `LTYPE` table and opens in
  `ezdxf`.
- `Layer.hatch(rectangle(...), pattern="ANSI31")` emits a valid HATCH entity.
- A block definition can be inserted twice and appears as one `BLOCK` plus two
  `INSERT` entities in a readable DXF.
- `Model.write_dxf` preserves hatches, block definitions, inserts, and
  linetypes from `Drawing2D`.
- `pytest tests/write -q -k dxf`, `pytest tests/model tests/examples -q`,
  `pytest -q`, `pyright src/cady`, and `ruff check src/cady tests` pass.
- README includes one production-style DXF example.
- Stage 4 dimensions spec and plan drafts are created or updated.

## 7. Non-Goals

- No DIMENSION entities.
- No custom linetype pattern registration beyond built-in `HIDDEN` and `CENTER`.
- No nested block definitions.
- No hatch holes or associative hatch metadata.
- No DXF parser.
- No domain-specific symbols in core.

## 8. Post-Implementation Review

Filled 2026-05-11.

- Shipped API differences from this spec: none material. The shipped API uses
  layer-level `hatch`, drawing-level `block`/`insert`, and built-in `CENTER` /
  `HIDDEN` linetypes as specified.
- Verification commands and results:
  - Focused Stage 3 entity tests passed during implementation:
    `tests/write/test_dxf_linetypes.py`, `tests/write/test_dxf_hatch.py`,
    `tests/write/test_dxf_blocks.py`, and
    `tests/model/test_model_dxf_production.py`.
  - `.venv/bin/ruff check src/cady tests` -> pass.
  - `.venv/bin/pyright src/cady` -> 0 errors, 0 warnings.
  - `.venv/bin/pytest -q` -> 88 passed, 28 dependency warnings.
  - `.venv/bin/python -c "import importlib.metadata as m; assert (m.distribution('cady').requires or []) == []"` -> pass.
- Known limitations:
  - HATCH supports ANSI31 with one closed flattened boundary.
  - Custom linetype registration is not implemented.
  - Nested block definitions and block attributes are not implemented.
  - Dimensions remain Stage 4.
- Stage 4 plan updates made:
  - Created `.warden/specs/2026-05-08-cady-stage-4-dimensions-design.md`.
  - Created `.warden/plans/2026-05-08-cady-stage-4-dimensions.md`.
- Preference-lock decisions added:
  - `dxf-linetypes-stage-3`
  - `dxf-hatch-api`
  - `dxf-block-api`
  - `dxf-insert-api`
  - `model-dxf-production-export`
