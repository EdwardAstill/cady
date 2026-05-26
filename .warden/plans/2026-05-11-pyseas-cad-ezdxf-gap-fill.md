# cady ezdxf Gap-Fill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the four feature gaps that prevent `cady` from being a drop-in replacement for `ezdxf` in `pyseas-yard/src/yard/draw/`.

**Architecture:** Each gap is a self-contained addition to the existing DXF scene/writer layers — entities defined in `cady/scene/dxf.py`, emitted by `cady/write/dxf/*`, exposed through fluent methods on `DxfDrawing`. No changes to the existing public API; everything is additive.

**Tech Stack:** Pure-stdlib Python, dataclasses, pytest, pyright strict.

---

## Audit — what `pyseas-yard/src/yard/draw/` actually uses from ezdxf

| ezdxf API | cady status | Gap task |
|---|---|---|
| `msp.add_line` | ✅ | — |
| `msp.add_circle` | ✅ | — |
| `msp.add_arc` | ✅ | — |
| `msp.add_lwpolyline` | ✅ | — |
| `msp.add_text` | ✅ | — |
| `msp.add_linear_dim` | ✅ | — |
| `msp.add_radius_dim` | ✅ | — |
| `msp.add_diameter_dim` | ✅ | — |
| `msp.add_angular_dim_3p` | ❌ | **Task 1** |
| `doc.dimstyles.add(...).dxf.dim{txt,asz,dec,exe,exo,gap}` | ⚠ built-in only | **Task 2** |
| `doc.header["$INSUNITS"] = n` | ⚠ no header API | **Task 3** |
| `ezdxf.bbox.extents(msp)` | ⚠ private `_bounds` | **Task 4** |
| `doc.layers.add` | ✅ | — |
| `doc.saveas` | ✅ | — |

Hatches and blocks are already covered (`HatchEntity`, `BlockDefinition`, `insert()`); `yard/draw/` does not currently use them, so they're not on the critical path.

---

## File Map

| File | Action |
|---|---|
| `src/cady/scene/dxf.py` | Modify — add `AngularDimensionEntity`, `DimStyle` dataclass, `header` field on `DxfDrawing`, `angular_dimension()` and `dimstyle()` methods, public `bounds` property |
| `src/cady/write/dxf/dimensions.py` | Modify — emit angular dimension block + DIMENSION entity |
| `src/cady/write/dxf/tables.py` | Modify — `dimstyle_table()` reads custom DimStyle settings, supports named non-Standard dimstyles |
| `src/cady/write/dxf/document.py` | Modify — write user-supplied header vars; make `_bounds` public |
| `src/cady/write/dxf/blocks.py` | Modify — include angular dim block names in `dimension_block_names()` |
| `src/cady/__init__.py` | Modify — export `DimStyle`, `AngularDimensionEntity` |
| `tests/scene/test_dxf_angular_dim.py` | Create — unit tests for angular dimension scene API |
| `tests/write/test_dxf_angular_dim.py` | Create — emitter tests for angular dim DXF output |
| `tests/scene/test_dxf_dimstyle.py` | Create — unit tests for custom DimStyle |
| `tests/write/test_dxf_dimstyle.py` | Create — emitter tests for DIMSTYLE table content |
| `tests/scene/test_dxf_header.py` | Create — unit tests for header metadata |
| `tests/write/test_dxf_header.py` | Create — emitter tests for HEADER section content |
| `tests/scene/test_dxf_bounds.py` | Create — unit tests for the public bounds property |

---

### Task 1: Angular dimension (3-point)

**Files:**
- Create: `tests/scene/test_dxf_angular_dim.py`
- Create: `tests/write/test_dxf_angular_dim.py`
- Modify: `src/cady/scene/dxf.py`
- Modify: `src/cady/write/dxf/dimensions.py`
- Modify: `src/cady/write/dxf/blocks.py`

- [ ] **Step 1: Write failing scene test**

Create `tests/scene/test_dxf_angular_dim.py`:

```python
"""Scene-layer tests for angular dimension entities."""

import math

import pytest

from cady import DxfDrawing
from cady.scene.dxf import AngularDimensionEntity


def test_angular_dimension_records_three_points_and_radius() -> None:
    drawing = DxfDrawing()
    drawing.layer("DIMS", color=2)
    drawing.angular_dimension(
        center=(0.0, 0.0),
        p1=(1.0, 0.0),
        p2=(0.0, 1.0),
        distance=0.5,
        layer="DIMS",
    )
    assert len(drawing.dimensions) == 1
    dim = drawing.dimensions[0]
    assert isinstance(dim, AngularDimensionEntity)
    assert dim.center == (0.0, 0.0)
    assert dim.p1 == (1.0, 0.0)
    assert dim.p2 == (0.0, 1.0)
    assert dim.distance == pytest.approx(0.5)
    assert dim.layer == "DIMS"
    assert dim.measurement_text == "90"


def test_angular_dimension_measurement_uses_degrees() -> None:
    drawing = DxfDrawing()
    drawing.layer("DIMS")
    drawing.angular_dimension(
        center=(0.0, 0.0),
        p1=(1.0, 0.0),
        p2=(math.cos(math.radians(30.0)), math.sin(math.radians(30.0))),
        distance=0.5,
        layer="DIMS",
    )
    assert drawing.dimensions[0].measurement_text == "30"


def test_angular_dimension_rejects_unknown_layer() -> None:
    drawing = DxfDrawing()
    with pytest.raises(ValueError, match="layer 'DIMS' not registered"):
        drawing.angular_dimension(
            center=(0.0, 0.0),
            p1=(1.0, 0.0),
            p2=(0.0, 1.0),
            distance=0.5,
            layer="DIMS",
        )
```

- [ ] **Step 2: Run failing test**

```bash
uv run pytest tests/scene/test_dxf_angular_dim.py -x
```
Expected: FAIL — `AngularDimensionEntity` and `angular_dimension` don't exist.

- [ ] **Step 3: Add AngularDimensionEntity dataclass and method**

In `src/cady/scene/dxf.py`, after the existing `DimensionEntity` class, add:

```python
@dataclass(frozen=True, slots=True)
class AngularDimensionEntity:
    """3-point angular dimension (vertex + two ray endpoints)."""

    center: Vec2
    p1: Vec2
    p2: Vec2
    distance: float
    layer: str
    dimstyle: str = "PYSEAS"
    measurement_text: str = ""

    def __post_init__(self) -> None:
        if self.distance <= 0:
            raise ValueError("AngularDimensionEntity: distance must be positive")
        if self.measurement_text == "":
            import math

            v1 = (self.p1[0] - self.center[0], self.p1[1] - self.center[1])
            v2 = (self.p2[0] - self.center[0], self.p2[1] - self.center[1])
            mag1 = math.hypot(*v1)
            mag2 = math.hypot(*v2)
            if mag1 == 0 or mag2 == 0:
                raise ValueError("AngularDimensionEntity: rays must be non-degenerate")
            cos_a = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (mag1 * mag2)))
            angle_deg = math.degrees(math.acos(cos_a))
            object.__setattr__(
                self,
                "measurement_text",
                _format_measurement(angle_deg),
            )
```

Then add an `angular_dimension` method on `DxfDrawing`, alongside the existing `linear_dimension` / `radius_dimension` methods:

```python
    def angular_dimension(
        self,
        center: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
        distance: float,
        *,
        layer: str,
        dimstyle: str = "PYSEAS",
    ) -> DxfDrawing:
        self._require_layer(layer)
        self._dimensions.append(
            AngularDimensionEntity(
                center=center,
                p1=p1,
                p2=p2,
                distance=distance,
                layer=layer,
                dimstyle=dimstyle,
            )
        )
        return self
```

Update the `dimensions` property's return type union to include `AngularDimensionEntity`.

- [ ] **Step 4: Run scene test to verify pass**

```bash
uv run pytest tests/scene/test_dxf_angular_dim.py -x
```
Expected: PASS

- [ ] **Step 5: Write failing emitter test**

Create `tests/write/test_dxf_angular_dim.py`:

```python
"""Emitter tests for angular dimensions."""

from cady import DxfDrawing
from cady.write.dxf.sections import render_dxf


def test_angular_dimension_emits_dimension_entity() -> None:
    drawing = DxfDrawing()
    drawing.layer("DIMS")
    drawing.angular_dimension(
        center=(0.0, 0.0),
        p1=(1.0, 0.0),
        p2=(0.0, 1.0),
        distance=0.5,
        layer="DIMS",
    )
    out = render_dxf(drawing)
    assert "DIMENSION" in out
    # Angular dim subclass marker
    assert "AcDb3PointAngularDimension" in out
    # Dimension type group code 70 = 5 (3-point angular)
    assert "\n 70\n5\n" in out


def test_angular_dimension_block_definition_present() -> None:
    drawing = DxfDrawing()
    drawing.layer("DIMS")
    drawing.angular_dimension(
        center=(0.0, 0.0),
        p1=(1.0, 0.0),
        p2=(0.0, 1.0),
        distance=0.5,
        layer="DIMS",
    )
    out = render_dxf(drawing)
    # One DIMENSION entity should produce one *D# block
    assert out.count("BLOCK\n  2\n*D") == 1
```

- [ ] **Step 6: Run emitter test to verify it fails**

```bash
uv run pytest tests/write/test_dxf_angular_dim.py -x
```
Expected: FAIL — emitter doesn't know about angular dims yet.

- [ ] **Step 7: Implement angular dim emitter**

In `src/cady/write/dxf/dimensions.py`, add handling for `AngularDimensionEntity`. The DIMENSION entity has:
- group 100: `AcDbDimension`
- group 100: `AcDb3PointAngularDimension`
- group 70: 5 (3-point angular dimension type)
- group 10: center (the vertex)
- group 13: p1 (first ray endpoint)
- group 14: p2 (second ray endpoint)
- group 15: center repeated (definition point on first extension line per spec; ezdxf uses the vertex)
- group 16: arc-pass-through point at `distance` along the angle bisector

Compute the bisector point:

```python
def _angular_dim_arc_point(dim: AngularDimensionEntity) -> tuple[float, float]:
    import math

    v1 = (dim.p1[0] - dim.center[0], dim.p1[1] - dim.center[1])
    v2 = (dim.p2[0] - dim.center[0], dim.p2[1] - dim.center[1])
    mag1 = math.hypot(*v1)
    mag2 = math.hypot(*v2)
    nx = v1[0] / mag1 + v2[0] / mag2
    ny = v1[1] / mag1 + v2[1] / mag2
    bm = math.hypot(nx, ny)
    if bm == 0:
        # collinear rays — fall back to perpendicular of v1
        return (dim.center[0] - v1[1] / mag1 * dim.distance,
                dim.center[1] + v1[0] / mag1 * dim.distance)
    return (dim.center[0] + nx / bm * dim.distance,
            dim.center[1] + ny / bm * dim.distance)
```

Add an `angular_dimension_entity(dim, block_name)` function alongside the existing per-type emitters that emits the DIMENSION pairs and follow the same block-definition pattern as the other dim types.

Update the dispatcher in this file to route `AngularDimensionEntity` to the new emitter.

- [ ] **Step 8: Wire the block name list**

In `src/cady/write/dxf/blocks.py`, ensure `dimension_block_names(drawing)` iterates over `AngularDimensionEntity` instances too.

- [ ] **Step 9: Run all tests**

```bash
uv run pytest tests/write/test_dxf_angular_dim.py tests/scene/test_dxf_angular_dim.py -x
```
Expected: PASS

- [ ] **Step 10: Run full suite to verify no regression**

```bash
uv run pytest
```
Expected: all tests pass.

- [ ] **Step 11: Commit**

```bash
git add src/cady/scene/dxf.py src/cady/write/dxf/dimensions.py src/cady/write/dxf/blocks.py tests/scene/test_dxf_angular_dim.py tests/write/test_dxf_angular_dim.py
git commit -m "feat(dxf): add 3-point angular dimension"
```

---

### Task 2: Custom DIMSTYLE configuration

**Files:**
- Create: `tests/scene/test_dxf_dimstyle.py`
- Create: `tests/write/test_dxf_dimstyle.py`
- Modify: `src/cady/scene/dxf.py`
- Modify: `src/cady/write/dxf/tables.py`
- Modify: `src/cady/__init__.py`

- [ ] **Step 1: Write failing scene test**

Create `tests/scene/test_dxf_dimstyle.py`:

```python
"""Scene-layer tests for custom DIMSTYLE configuration."""

import pytest

from cady import DimStyle, DxfDrawing


def test_dimstyle_defaults_match_existing_builtin() -> None:
    style = DimStyle(name="PYSEAS")
    assert style.text_height == 0.18
    assert style.arrow_size == 0.18
    assert style.decimal_places == 4


def test_dimstyle_can_override_parameters() -> None:
    style = DimStyle(
        name="DETAIL",
        text_height=2.5,
        arrow_size=2.5,
        decimal_places=1,
        extension_offset=1.0,
        extension_extend=1.0,
        text_gap=1.0,
    )
    assert style.text_height == 2.5
    assert style.decimal_places == 1
    assert style.extension_extend == 1.0


def test_drawing_register_dimstyle_makes_it_available() -> None:
    drawing = DxfDrawing()
    drawing.dimstyle(DimStyle(name="DETAIL", text_height=3.0))
    drawing.layer("DIMS")
    drawing.linear_dimension(
        p1=(0.0, 0.0),
        p2=(1.0, 0.0),
        offset=0.5,
        layer="DIMS",
        dimstyle="DETAIL",
    )
    assert drawing.dimensions[0].dimstyle == "DETAIL"


def test_drawing_rejects_dimension_for_unknown_dimstyle() -> None:
    drawing = DxfDrawing()
    drawing.layer("DIMS")
    with pytest.raises(ValueError, match="dimstyle 'DETAIL' not registered"):
        drawing.linear_dimension(
            p1=(0.0, 0.0),
            p2=(1.0, 0.0),
            offset=0.5,
            layer="DIMS",
            dimstyle="DETAIL",
        )
```

- [ ] **Step 2: Run failing test**

```bash
uv run pytest tests/scene/test_dxf_dimstyle.py -x
```
Expected: FAIL — `DimStyle` not defined, `dimstyle()` method missing, layer-style validation missing.

- [ ] **Step 3: Add DimStyle and dimstyle registration**

In `src/cady/scene/dxf.py`:

```python
@dataclass(frozen=True, slots=True)
class DimStyle:
    """User-configurable dimension style parameters."""

    name: str
    text_height: float = 0.18  # DXF dimtxt
    arrow_size: float = 0.18   # dimasz
    decimal_places: int = 4    # dimdec
    extension_offset: float = 0.0625  # dimexo
    extension_extend: float = 0.18    # dimexe
    text_gap: float = 0.09     # dimgap

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("DimStyle: name must be non-empty")
        if self.decimal_places < 0:
            raise ValueError("DimStyle: decimal_places must be non-negative")
```

In `DxfDrawing.__init__`, seed `self._dimstyles: dict[str, DimStyle] = {"PYSEAS": DimStyle(name="PYSEAS")}`.

Add the registration method:

```python
    def dimstyle(self, style: DimStyle) -> DxfDrawing:
        self._dimstyles[style.name] = style
        return self

    @property
    def dimstyles(self) -> tuple[DimStyle, ...]:
        return tuple(self._dimstyles.values())

    def _require_dimstyle(self, name: str) -> None:
        if name not in self._dimstyles:
            raise ValueError(f"dimstyle {name!r} not registered")
```

In each `linear_dimension` / `radius_dimension` / `diameter_dimension` / `angular_dimension` / `aligned_dimension` method, call `self._require_dimstyle(dimstyle)` before appending the entity.

- [ ] **Step 4: Export DimStyle**

In `src/cady/__init__.py`, add `DimStyle` to imports from `cady.scene` and to `__all__`.

In `src/cady/scene/__init__.py`, add `DimStyle` to the re-exports from `cady.scene.dxf`.

- [ ] **Step 5: Run scene test**

```bash
uv run pytest tests/scene/test_dxf_dimstyle.py -x
```
Expected: PASS

- [ ] **Step 6: Write failing emitter test**

Create `tests/write/test_dxf_dimstyle.py`:

```python
"""Emitter tests for DIMSTYLE table generation."""

from cady import DimStyle, DxfDrawing
from cady.write.dxf.sections import render_dxf


def test_dimstyle_table_includes_user_dimstyle() -> None:
    drawing = DxfDrawing()
    drawing.dimstyle(DimStyle(name="DETAIL", text_height=3.0, arrow_size=2.0))
    drawing.layer("DIMS")
    drawing.linear_dimension(
        p1=(0.0, 0.0),
        p2=(1.0, 0.0),
        offset=0.5,
        layer="DIMS",
        dimstyle="DETAIL",
    )
    out = render_dxf(drawing)
    # The dimstyle name must appear as a record
    assert "  2\nDETAIL\n" in out


def test_dimstyle_table_writes_text_height_group_140() -> None:
    drawing = DxfDrawing()
    drawing.dimstyle(DimStyle(name="DETAIL", text_height=3.0))
    drawing.layer("DIMS")
    drawing.linear_dimension(
        p1=(0.0, 0.0),
        p2=(1.0, 0.0),
        offset=0.5,
        layer="DIMS",
        dimstyle="DETAIL",
    )
    out = render_dxf(drawing)
    # Group 140 = DIMTXT (text height)
    assert "\n140\n3.0\n" in out


def test_dimstyle_table_omits_user_styles_when_no_dimensions_use_them() -> None:
    drawing = DxfDrawing()
    drawing.dimstyle(DimStyle(name="UNUSED"))
    out = render_dxf(drawing)
    assert "UNUSED" not in out
```

- [ ] **Step 7: Run emitter test**

```bash
uv run pytest tests/write/test_dxf_dimstyle.py -x
```
Expected: FAIL — emitter still writes only the hard-coded `Standard` row.

- [ ] **Step 8: Update tables emitter**

In `src/cady/write/dxf/tables.py`, change `dimstyle_table` to accept the drawing's registered dimstyles and a set of dimstyle names actually referenced by dimensions in the drawing. Emit one DIMSTYLE record per referenced style, mapping fields:

| DimStyle field | DXF group code |
|---|---|
| `name` | 2 |
| `text_height` | 140 (DIMTXT) |
| `arrow_size` | 41 (DIMASZ) |
| `decimal_places` | 271 (DIMDEC) — short, group code 70 family |
| `extension_offset` | 42 (DIMEXO) |
| `extension_extend` | 44 (DIMEXE) |
| `text_gap` | 147 (DIMGAP) |

Keep the existing `Standard` record so unrelated DXF readers don't choke.

Update the call site (likely in `src/cady/write/dxf/document.py` or `sections.py`) to pass the drawing's dimstyles list and the set of names referenced by `drawing.dimensions`.

- [ ] **Step 9: Run emitter test**

```bash
uv run pytest tests/write/test_dxf_dimstyle.py -x
```
Expected: PASS

- [ ] **Step 10: Run full suite**

```bash
uv run pytest
```
Expected: all tests pass.

- [ ] **Step 11: Commit**

```bash
git add src/cady/scene/dxf.py src/cady/scene/__init__.py src/cady/__init__.py src/cady/write/dxf/tables.py src/cady/write/dxf/document.py tests/scene/test_dxf_dimstyle.py tests/write/test_dxf_dimstyle.py
git commit -m "feat(dxf): support user-configurable DIMSTYLE"
```

---

### Task 3: HEADER metadata (`$INSUNITS` and friends)

**Files:**
- Create: `tests/scene/test_dxf_header.py`
- Create: `tests/write/test_dxf_header.py`
- Modify: `src/cady/scene/dxf.py`
- Modify: `src/cady/write/dxf/document.py`

- [ ] **Step 1: Write failing scene test**

Create `tests/scene/test_dxf_header.py`:

```python
"""Tests for DXF HEADER variables."""

import pytest

from cady import DxfDrawing


def test_header_starts_empty() -> None:
    drawing = DxfDrawing()
    assert drawing.header == {}


def test_set_insunits_records_int() -> None:
    drawing = DxfDrawing()
    drawing.set_header("$INSUNITS", 4)  # 4 = millimetres
    assert drawing.header["$INSUNITS"] == 4


def test_set_header_rejects_unknown_variable() -> None:
    drawing = DxfDrawing()
    with pytest.raises(ValueError, match=r"unknown HEADER variable"):
        drawing.set_header("$NOPE", 1)


def test_set_header_returns_self_for_chaining() -> None:
    drawing = DxfDrawing()
    result = drawing.set_header("$INSUNITS", 4)
    assert result is drawing
```

- [ ] **Step 2: Run failing test**

```bash
uv run pytest tests/scene/test_dxf_header.py -x
```
Expected: FAIL — no `header` or `set_header`.

- [ ] **Step 3: Add header API**

In `src/cady/scene/dxf.py`:

```python
# Group code per header variable. Extend this map as variables are added.
_HEADER_VARS: dict[str, int] = {
    "$INSUNITS": 70,
    "$MEASUREMENT": 70,
    "$LUNITS": 70,
    "$AUNITS": 70,
}
```

In `DxfDrawing.__init__`, initialise `self._header: dict[str, int | float | str] = {}`. Add:

```python
    @property
    def header(self) -> dict[str, int | float | str]:
        return dict(self._header)

    def set_header(self, name: str, value: int | float | str) -> DxfDrawing:
        if name not in _HEADER_VARS:
            raise ValueError(f"unknown HEADER variable {name!r}")
        self._header[name] = value
        return self
```

- [ ] **Step 4: Run scene test**

```bash
uv run pytest tests/scene/test_dxf_header.py -x
```
Expected: PASS

- [ ] **Step 5: Write failing emitter test**

Create `tests/write/test_dxf_header.py`:

```python
"""Emitter tests for HEADER section."""

from cady import DxfDrawing
from cady.write.dxf.sections import render_dxf


def test_header_section_includes_insunits_when_set() -> None:
    drawing = DxfDrawing()
    drawing.set_header("$INSUNITS", 4)
    out = render_dxf(drawing)
    assert "$INSUNITS" in out
    # Group code 70 (int16) for INSUNITS, value 4
    assert "$INSUNITS\n 70\n4\n" in out


def test_header_section_omits_unset_variables() -> None:
    drawing = DxfDrawing()
    out = render_dxf(drawing)
    assert "$INSUNITS" not in out
```

- [ ] **Step 6: Run emitter test**

```bash
uv run pytest tests/write/test_dxf_header.py -x
```
Expected: FAIL — `_header` in `document.py` doesn't read drawing.header.

- [ ] **Step 7: Update header emitter**

In `src/cady/write/dxf/document.py`, find `_header(bounds)` and extend it to accept the drawing (or its `_header` dict) and append a pair per user-set variable using the group code from `_HEADER_VARS`. Existing bound-derived $EXTMIN/$EXTMAX pairs stay unchanged.

- [ ] **Step 8: Run emitter test**

```bash
uv run pytest tests/write/test_dxf_header.py -x
```
Expected: PASS

- [ ] **Step 9: Run full suite**

```bash
uv run pytest
```
Expected: all tests pass.

- [ ] **Step 10: Commit**

```bash
git add src/cady/scene/dxf.py src/cady/write/dxf/document.py tests/scene/test_dxf_header.py tests/write/test_dxf_header.py
git commit -m "feat(dxf): allow setting HEADER variables (\$INSUNITS et al)"
```

---

### Task 4: Public bounding-box property

**Files:**
- Create: `tests/scene/test_dxf_bounds.py`
- Modify: `src/cady/scene/dxf.py`
- Modify: `src/cady/write/dxf/document.py`

- [ ] **Step 1: Write failing test**

Create `tests/scene/test_dxf_bounds.py`:

```python
"""Public bounds property on DxfDrawing."""

import pytest

from cady import DxfDrawing
from cady.geom import circle, line


def test_bounds_for_empty_drawing_is_zero_zero() -> None:
    drawing = DxfDrawing()
    lo, hi = drawing.bounds
    assert lo == (0.0, 0.0)
    assert hi == (0.0, 0.0)


def test_bounds_covers_lines_and_circles() -> None:
    drawing = DxfDrawing()
    drawing.layer("GEOM")
    drawing.layer("GEOM").add(line((0.0, 0.0), (10.0, 5.0)))
    drawing.layer("GEOM").add(circle((3.0, -2.0), 1.5))
    lo, hi = drawing.bounds
    assert lo == pytest.approx((0.0, -3.5))
    assert hi == pytest.approx((10.0, 5.0))
```

- [ ] **Step 2: Run failing test**

```bash
uv run pytest tests/scene/test_dxf_bounds.py -x
```
Expected: FAIL — `bounds` not a public property.

- [ ] **Step 3: Promote `_bounds` to a public `bounds` property**

In `src/cady/write/dxf/document.py`, rename `_bounds(drawing)` to a module-level public function `bounds(drawing)` (keep `_bounds` as a thin alias to avoid touching the writer call sites in this task).

In `src/cady/scene/dxf.py`, on `DxfDrawing`:

```python
    @property
    def bounds(self) -> tuple[Vec2, Vec2]:
        from cady.write.dxf.document import bounds as _compute_bounds

        return _compute_bounds(self)
```

- [ ] **Step 4: Run test**

```bash
uv run pytest tests/scene/test_dxf_bounds.py -x
```
Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
uv run pytest
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/cady/scene/dxf.py src/cady/write/dxf/document.py tests/scene/test_dxf_bounds.py
git commit -m "feat(dxf): expose drawing.bounds as a public property"
```

---

### Task 5: Gates and integration check

**Files:** none new — verification only.

- [ ] **Step 1: Run the full test suite**

```bash
uv run pytest
```
Expected: all tests pass, zero regressions in pre-existing files.

- [ ] **Step 2: Run pyright in strict mode**

```bash
uv run pyright
```
Expected: 0 errors.

- [ ] **Step 3: Sanity-check end-to-end with an angular dim + custom dimstyle + INSUNITS**

```bash
uv run python - <<'PY'
from cady import DxfDrawing, DimStyle

drawing = DxfDrawing()
drawing.set_header("$INSUNITS", 4)
drawing.dimstyle(DimStyle(name="DETAIL", text_height=2.5, arrow_size=2.0, decimal_places=1))
drawing.layer("OUTLINE", color=7)
drawing.layer("DIMS", color=2)

from cady.geom import line
drawing.layer("OUTLINE").add(line((0.0, 0.0), (10.0, 0.0)))
drawing.layer("OUTLINE").add(line((0.0, 0.0), (0.0, 10.0)))

drawing.angular_dimension(
    center=(0.0, 0.0), p1=(10.0, 0.0), p2=(0.0, 10.0),
    distance=5.0, layer="DIMS", dimstyle="DETAIL",
)
drawing.write("/tmp/cady-ezdxf-gap.dxf")
print("bounds:", drawing.bounds)
print("dimstyles:", [s.name for s in drawing.dimstyles])
print("header:", drawing.header)
PY
```

Expected: writes a valid DXF, prints `bounds: ((0.0, 0.0), (10.0, 10.0))` (or close), lists both `PYSEAS` and `DETAIL`, prints `{'$INSUNITS': 4}`.

- [ ] **Step 4: Final commit**

```bash
git commit --allow-empty -m "chore(dxf): ezdxf gap-fill complete (angular dim, dimstyle, header, bounds)"
```

---

## Acceptance Commands

```bash
uv run pytest
uv run pyright
uv run python -c "from cady import DxfDrawing, DimStyle; print('ok')"
```

## Notes for Implementer

- **DXF group codes:** group 140 = DIMTXT (text height as double), group 41 = DIMASZ (arrow size as double), group 147 = DIMGAP, group 271 = DIMDEC (short int). Reference: `cady/notes/step-format-cheatsheet.md` style reference exists for STEP; if there is no equivalent DXF cheatsheet, the AutoCAD DXF Reference (publicly available PDF) is authoritative.
- **3-point angular DIMENSION:** AutoLISP/ezdxf uses `AcDb3PointAngularDimension` subclass marker and dimtype 5 (group 70). Definition points are: 10 (vertex), 13 (ray 1 end), 14 (ray 2 end), 15 (repeat of vertex or arc-pass-through depending on dialect), 16 (arc-pass-through point on the bisector at the dimension radius). Verify against `ezdxf`'s output if a reference is needed: `ezdxf` lives in `~/.cache/uv/...` or can be inspected with `uv pip install ezdxf` in a scratch venv.
- **Layer/dimstyle validation:** mirror the existing `_require_layer` pattern when adding `_require_dimstyle`. Apply it to all existing dimension methods so the policy is uniform.
- **Backward compatibility:** the built-in `PYSEAS` dimstyle must remain the default when a dimension is added without specifying a dimstyle. Existing tests already assume this.
- **No new third-party deps.** Everything is stdlib + dataclasses.

## Migration follow-up (not in this plan)

Once these four tasks land, `pyseas-yard/src/yard/draw/_ezdxf.py` can be re-implemented on top of `cady`. That migration is intentionally **not** part of this plan — it lives in pyseas-yard and is its own discrete piece of work after cady's gaps are closed.
