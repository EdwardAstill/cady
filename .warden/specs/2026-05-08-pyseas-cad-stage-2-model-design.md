# pyseas-cad Stage 2 - Model Layer

**Status:** approved planning contract.
**Date:** 2026-05-08.
**Author:** Edward Astill, with Codex as planning partner.
**Scope:** Stage 2 of pyseas-cad. Add a domain-blind model layer that lets one
caller-owned model organize named drawings, parts, assemblies, and metadata,
then export DXF and STL through the Stage 1 writers.

---

## 1. Goal

Stage 2 introduces `cad.model` and the preferred v1 API:

```python
from cad import Model, circle, rectangle

plate = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))

model = Model("padeye_plate", created_at="2026-05-08T00:00:00Z")
model.drawing("front").layer("PLATE").add(plate)
model.part("plate").add(plate.extrude("+z", 0.04))

model.write_dxf("padeye_plate.dxf")
model.write_stl("padeye_plate.stl")
```

`Model.write_step(...)` is reserved in this stage and raises a clear
`NotImplementedError` that names Stage 5.

## 2. Constraints

pyseas-cad remains a small pure-stdlib runtime package. Existing Stage 1
geometry, `DxfDrawing`, and `StlMesh` APIs continue to work. The model layer is
an organizer and export facade; it does not replace immutable geometry values or
teach the core about pyseas-yard objects such as padeyes, shackles, welds, or
bolts.

The model layer must keep direct writer details out of caller code without
forking writer behavior. DXF still flows through `DxfDrawing`; STL still flows
through `StlMesh`.

## 3. Alternatives Considered

| Criterion | Thin facade over scenes | New shared document writer | Writer-specific only |
|---|---|---|---|
| Complexity | Low | Medium-high | Low now, high later |
| Preserves Stage 1 APIs | Yes | Risky | Yes |
| Future STEP metadata | Good | Good | Poor |
| DXF/STL behavior drift risk | Low | Medium | None |
| Implementation effort | Small | Larger refactor | No Stage 2 value |

Decision: implement a thin model facade. It gives v1 a coherent public API and
part/drawing metadata while preserving the Stage 1 scene writers.

## 4. Public API Contract

### 4.1 Exports

`cad.__init__` exports:

- `Model`
- `Drawing2D`
- `ModelLayer`
- `Part`
- `Assembly`
- `ModelMetadata`

`cad.model` exports the same names.

### 4.2 Model

```python
Model(
    name: str,
    *,
    units: str = "m",
    author: str | None = None,
    source: str | None = None,
    created_at: datetime | str | None = None,
)
```

Rules:

- `name` must be non-empty.
- `units` defaults to `"m"` and must stay `"m"` in Stage 2.
- `created_at=None` uses current UTC time.
- `created_at` accepts a timezone-aware `datetime` or an ISO-8601 string.
- A trailing `"Z"` string is accepted and normalized to UTC.
- Naive datetimes are rejected with `ValueError`.

Methods:

```python
model.drawing(name: str) -> Drawing2D
model.part(name: str) -> Part
model.assembly(name: str) -> Assembly
model.write_dxf(path: str | Path) -> Model
model.write_stl(path: str | Path, *, ascii: bool = False, tolerance: float = 1e-3) -> Model
model.write_step(path: str | Path) -> NoReturn
model.to_dict() -> dict[str, object]
```

Repeated `drawing`, `part`, and `assembly` calls return the existing object for
that name.

`write_dxf` emits all drawing entities into one DXF file. Stage 2 does not add
layout/sheet separation; drawing names are organization metadata for callers and
future stages.

`write_stl` emits all model parts into one STL mesh. Part names are metadata for
future STEP and debug output; STL itself remains a triangle soup.

### 4.3 Drawing2D and ModelLayer

`Drawing2D` owns one internal `DxfDrawing`.

```python
drawing.layer(name: str, color: int = 7) -> ModelLayer
drawing.add_text(text: str, at: tuple[float, float] | Vec2, height: float, layer: str = "0") -> Drawing2D
drawing.to_dxf_drawing() -> DxfDrawing
```

`ModelLayer.add(shape: Shape2D) -> ModelLayer` delegates to the underlying Stage
1 `Layer.add` and keeps the same runtime `SceneError` behavior for wrong
dimensionality.

### 4.4 Part

```python
part.add(*solids: Shape3D) -> Part
part.to_stl_mesh(*, tolerance: float = 1e-3) -> StlMesh
```

`Part.add` accepts only `Shape3D` values and raises `SceneError` when bypassing
the type checker with a 2D shape.

### 4.5 Assembly

`Assembly` is a lightweight named grouping of model parts for future STEP work.

```python
assembly.add(*parts: Part | str) -> Assembly
```

Stage 2 exporters do not interpret assemblies. `to_dict` includes assembly names
and referenced part names.

### 4.6 Debug Representation

`Model.to_dict()` returns a JSON-compatible dict with:

- model name,
- metadata,
- drawing names and per-layer entity counts,
- part names and solid counts,
- assembly names and referenced part names.

It is a debug/test representation only, not a supported interchange format.

## 5. Test Strategy

Working means a caller can build one model, add 2D and 3D geometry to named
containers, export DXF/STL through the model facade, and keep all Stage 1 direct
scene APIs working.

| Behavior | Risk | Layer | Tool | Assertion |
|---|---|---|---|---|
| Model metadata validation | Medium | Unit | pytest | rejects empty name, unsupported units, naive datetime |
| Drawing facade delegates to DXF | High | Integration | pytest + ezdxf | model DXF opens and has expected entities |
| Part facade delegates to STL | High | Integration | pytest + struct | model STL has expected triangle count bytes |
| Direct Stage 1 APIs remain | High | Regression | pytest existing suites | existing tests still pass |
| Wrong dimensionality rejected | Medium | Unit | pytest | SceneError from model facade |
| Public exports available | Medium | Unit + pyright | pytest, pyright | `from cad import Model` works and strict source passes |
| STEP reserved behavior | Low | Unit | pytest | NotImplementedError message names Stage 5 |
| Docs and examples match API | Medium | Smoke | pytest examples | model-first example writes files |

## 6. Acceptance Criteria

- `from cad import Model` works.
- `Model(...).drawing(...).layer(...).add(shape2d).write_dxf(path)` emits a DXF
  accepted by `ezdxf.readfile(path)` with no audit errors.
- `Model(...).part(...).add(shape3d).write_stl(path)` emits the same binary STL
  triangle count as the equivalent `StlMesh` path for a prism.
- Existing `DxfDrawing` and `StlMesh` tests keep passing.
- `Model.write_step(path)` raises `NotImplementedError` with "Stage 5" in the
  message.
- Runtime package metadata still has no dependencies.
- `pytest -q`, `pyright src/cad`, and `ruff check src/cad tests` pass.
- README and examples show the model-first API.
- Stage 3 DXF spec/plan stubs are created or updated from the shipped Stage 2
  API.

## 7. Non-Goals

- No STEP writer implementation.
- No HATCH, BLOCK, INSERT, linetype expansion, or dimensions.
- No sheet/layout system.
- No DXF/STL parsing.
- No domain objects.
- No runtime dependencies.

## 8. Post-Implementation Review

To be filled when Stage 2 is complete:

- Shipped API differences from this spec:
- Verification commands and results:
- Known limitations:
- Stage 3 plan updates made:
- Preference-lock decisions added:
