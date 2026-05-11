# Stage 5 STEP MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write a pure-stdlib AP214 STEP exporter that converts `Part` objects containing `Prism` solids into valid, viewer-loadable STEP files via `Model.write_step(path)`.

**Architecture:** Add `cad.write.step` alongside DXF/STL writers. An `IdAllocator` handles sequential STEP entity numbering. `brep.py` converts a `Prism` into a six-face `MANIFOLD_SOLID_BREP`. `document.py` assembles the AP214 file frame (header, application context, units, product structure). `Model.write_step` iterates parts, emits one product per part. Unsupported solids (`Sphere`, `Extrusion`, `Revolution`) raise `WriteError` listing the unsupported type.

**Tech Stack:** Python 3.11+, pure stdlib, pytest, pyright strict, ruff. No new runtime dependencies.

**Schema:** AP214 (`AUTOMOTIVE_DESIGN`), meters, MANIFOLD_SOLID_BREP with planar ADVANCED_FACEs. Verification: structural text assertions (no external STEP validator available on this host).

---

## File Map

| Path | Action | Responsibility |
|---|---|---|
| `src/cad/write/step/__init__.py` | Create | Package marker |
| `src/cad/write/step/ids.py` | Create | Sequential entity ID allocator |
| `src/cad/write/step/brep.py` | Create | `Prism` → 6-face `MANIFOLD_SOLID_BREP` entities |
| `src/cad/write/step/document.py` | Create | Assemble full AP214 STEP text from parts list |
| `src/cad/model/core.py` | Modify | Replace `write_step` stub with real implementation |
| `tests/model/test_model_step.py` | Modify | Replace stub test; add model-level STEP tests |
| `tests/write/test_step.py` | Create | Unit tests for IdAllocator, brep, and document |

---

## Topology Reference (do not alter)

Box vertices for `Prism(origin, size)` where `x0,y0,z0 = origin` and `x1,y1,z1 = x0+|dx|, y0+|dy|, z0+|dz|` (always use `min/max` to normalise):

```
v0=(x0,y0,z0)  v1=(x1,y0,z0)  v2=(x1,y1,z0)  v3=(x0,y1,z0)  # bottom ring
v4=(x0,y0,z1)  v5=(x1,y0,z1)  v6=(x1,y1,z1)  v7=(x0,y1,z1)  # top ring
```

12 directed edge curves (index, vi→vj, direction-unit-vector):
```
e0 (0→1, +X)   e1 (1→2, +Y)   e2 (2→3, −X)   e3 (3→0, −Y)   # bottom ring
e4 (4→5, +X)   e5 (5→6, +Y)   e6 (6→7, −X)   e7 (7→4, −Y)   # top ring
e8 (0→4, +Z)   e9 (1→5, +Z)   e10(2→6, +Z)   e11(3→7, +Z)   # verticals
```

6 faces (vertex loop CCW from outside, outward normal, reference direction for PLANE):
```
F0 bottom  v0→v3→v2→v1   normal=(0,0,−1)  ref=(1,0,0)   origin=v0
F1 top     v4→v5→v6→v7   normal=(0,0,+1)  ref=(1,0,0)   origin=v4
F2 front   v0→v1→v5→v4   normal=(0,−1,0)  ref=(1,0,0)   origin=v0
F3 back    v3→v7→v6→v2   normal=(0,+1,0)  ref=(−1,0,0)  origin=v3
F4 right   v1→v2→v6→v5   normal=(+1,0,0)  ref=(0,1,0)   origin=v1
F5 left    v0→v4→v7→v3   normal=(−1,0,0)  ref=(0,1,0)   origin=v0
```

Oriented-edge truth table (edge index, face, sense):

| edge | in faces (.T.) | in faces (.F.) |
|------|---------------|----------------|
| e0   | F2            | F0             |
| e1   | F4            | F0             |
| e2   | F3            | F0             |
| e3   | F5            | F0             |
| e4   | F1            | F2             |
| e5   | F1            | F4             |
| e6   | F1            | F3             |
| e7   | F1            | F5             |
| e8   | F5            | F2             |
| e9   | F2            | F4             |
| e10  | F4            | F3             |
| e11  | F3            | F5             |

---

## Task 1 — Package skeleton + failing tests

**Files:**
- Create: `src/cad/write/step/__init__.py`
- Create: `tests/write/test_step.py`

- [ ] **Step 1.1: Create empty package**

```python
# src/cad/write/step/__init__.py
```
(empty file — just a package marker)

- [ ] **Step 1.2: Write failing tests**

Create `tests/write/test_step.py`:

```python
from __future__ import annotations

from cad import Model, WriteError, prism
from cad.write.step.ids import IdAllocator
from cad.write.step.document import render_step


def test_id_allocator_returns_sequential_ids() -> None:
    ids = IdAllocator()
    assert ids.add("FOO('bar')") == 1
    assert ids.add("BAZ()") == 2


def test_id_allocator_renders_data_section() -> None:
    ids = IdAllocator()
    ids.add("FOO('x')")
    ids.add("BAR(#1)")
    assert ids.render_data() == "#1=FOO('x');\n#2=BAR(#1);"


def test_render_step_contains_iso_header() -> None:
    parts = [Model("m").part("plate")]
    parts[0].add(prism((0, 0, 0), (1, 0.5, 0.01)))
    text = render_step(parts, "plate")
    assert text.startswith("ISO-10303-21;")
    assert text.strip().endswith("END-ISO-10303-21;")
    assert "FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));" in text


def test_render_step_contains_manifold_solid_brep_for_prism() -> None:
    from cad.model.core import Part
    part = Part("box")
    part.add(prism((0, 0, 0), (1, 1, 1)))
    text = render_step([part], "box_model")
    assert "MANIFOLD_SOLID_BREP" in text
    assert "CLOSED_SHELL" in text
    assert text.count("ADVANCED_FACE") == 6
    assert text.count("EDGE_CURVE") == 12


def test_render_step_rejects_sphere_solid() -> None:
    from cad import sphere
    from cad.model.core import Part
    part = Part("bad")
    part.add(sphere((0, 0, 0), 1.0))
    try:
        render_step([part], "bad")
        assert False, "expected WriteError"
    except WriteError:
        pass


def test_model_write_step_produces_file(tmp_path) -> None:
    model = Model("demo")
    model.part("plate").add(prism((0, 0, 0), (1, 0.5, 0.01)))
    model.write_step(tmp_path / "demo.step")
    text = (tmp_path / "demo.step").read_text(encoding="ascii")
    assert "MANIFOLD_SOLID_BREP" in text
```

- [ ] **Step 1.3: Run — verify all fail (ImportError / NotImplementedError)**

```bash
.venv/bin/pytest tests/write/test_step.py -q
```

Expected: collection errors or 6 failures. No passes yet.

- [ ] **Step 1.4: Commit skeleton**

```bash
git add src/cad/write/step/__init__.py tests/write/test_step.py
git commit -m "test(step): add failing tests for Stage 5 STEP writer"
```

---

## Task 2 — IdAllocator

**Files:**
- Create: `src/cad/write/step/ids.py`

- [ ] **Step 2.1: Implement**

```python
# src/cad/write/step/ids.py
from __future__ import annotations


class IdAllocator:
    """Sequential entity ID counter and registry for a STEP DATA section."""

    def __init__(self) -> None:
        self._n = 0
        self._lines: list[str] = []

    def add(self, definition: str) -> int:
        self._n += 1
        self._lines.append(f"#{self._n}={definition};")
        return self._n

    def render_data(self) -> str:
        return "\n".join(self._lines)
```

- [ ] **Step 2.2: Run targeted tests**

```bash
.venv/bin/pytest tests/write/test_step.py -q -k "id_allocator"
```

Expected: 2 passed.

- [ ] **Step 2.3: Commit**

```bash
git add src/cad/write/step/ids.py
git commit -m "feat(step): add IdAllocator for sequential entity numbering"
```

---

## Task 3 — Box BRep generator

**Files:**
- Create: `src/cad/write/step/brep.py`

This file converts a `Prism(origin, size)` into all STEP entities required for a `MANIFOLD_SOLID_BREP`. It uses the topology defined in the Topology Reference above.

- [ ] **Step 3.1: Implement**

```python
# src/cad/write/step/brep.py
from __future__ import annotations

from cad.geom.shapes3d import Prism
from cad.write.step.ids import IdAllocator


def _f(v: float) -> str:
    """Compact STEP float: no trailing zeros, preserves full precision."""
    formatted = f"{v:.10G}"
    return formatted


def _cp(ids: IdAllocator, x: float, y: float, z: float) -> int:
    return ids.add(f"CARTESIAN_POINT('',({_f(x)},{_f(y)},{_f(z)}))")


def _dir(ids: IdAllocator, x: float, y: float, z: float) -> int:
    return ids.add(f"DIRECTION('',({_f(x)},{_f(y)},{_f(z)}))")


def _vp(ids: IdAllocator, cp_id: int) -> int:
    return ids.add(f"VERTEX_POINT('',#{cp_id})")


def _line(ids: IdAllocator, cp_id: int, dir_id: int) -> int:
    vec_id = ids.add(f"VECTOR('',#{dir_id},1.0)")
    return ids.add(f"LINE('',#{cp_id},#{vec_id})")


def _ec(ids: IdAllocator, vp_s: int, vp_e: int, line_id: int) -> int:
    return ids.add(f"EDGE_CURVE('',#{vp_s},#{vp_e},#{line_id},.T.)")


def _oe(ids: IdAllocator, ec_id: int, forward: bool) -> int:
    sense = ".T." if forward else ".F."
    return ids.add(f"ORIENTED_EDGE('',*,*,#{ec_id},{sense})")


def _el(ids: IdAllocator, oe_ids: list[int]) -> int:
    refs = ",".join(f"#{i}" for i in oe_ids)
    return ids.add(f"EDGE_LOOP('',({refs}))")


def _fob(ids: IdAllocator, el_id: int) -> int:
    return ids.add(f"FACE_OUTER_BOUND('',#{el_id},.T.)")


def _plane(
    ids: IdAllocator,
    origin: tuple[float, float, float],
    normal: tuple[float, float, float],
    ref: tuple[float, float, float],
) -> int:
    cp_id = _cp(ids, *origin)
    n_id = _dir(ids, *normal)
    r_id = _dir(ids, *ref)
    a2p_id = ids.add(f"AXIS2_PLACEMENT_3D('',#{cp_id},#{n_id},#{r_id})")
    return ids.add(f"PLANE('',#{a2p_id})")


def _af(ids: IdAllocator, fob_id: int, plane_id: int) -> int:
    return ids.add(f"ADVANCED_FACE('',(#{fob_id}),#{plane_id},.T.)")


def prism_brep(ids: IdAllocator, solid: Prism) -> int:
    """Emit all entities for a box MANIFOLD_SOLID_BREP; return its entity ID."""
    # Normalise bounds so size components are always positive.
    ox, oy, oz = solid.origin.x, solid.origin.y, solid.origin.z
    sx, sy, sz = solid.size.x, solid.size.y, solid.size.z
    x0, x1 = (ox, ox + sx) if sx > 0 else (ox + sx, ox)
    y0, y1 = (oy, oy + sy) if sy > 0 else (oy + sy, oy)
    z0, z1 = (oz, oz + sz) if sz > 0 else (oz + sz, oz)

    # 8 vertex positions (bottom ring first, then top ring)
    coords: list[tuple[float, float, float]] = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),  # v0-v3
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),  # v4-v7
    ]
    cp_ids = [_cp(ids, *c) for c in coords]
    vp_ids = [_vp(ids, c) for c in cp_ids]

    # 12 edge curves: (vi, vj, direction-unit-vector)
    edge_defs: list[tuple[int, int, tuple[float, float, float]]] = [
        (0, 1, (1, 0, 0)), (1, 2, (0, 1, 0)), (2, 3, (-1, 0, 0)), (3, 0, (0, -1, 0)),
        (4, 5, (1, 0, 0)), (5, 6, (0, 1, 0)), (6, 7, (-1, 0, 0)), (7, 4, (0, -1, 0)),
        (0, 4, (0, 0, 1)), (1, 5, (0, 0, 1)), (2, 6, (0, 0, 1)),  (3, 7, (0, 0, 1)),
    ]
    ec_ids: list[int] = []
    for vi, vj, dxyz in edge_defs:
        line_id = _line(ids, cp_ids[vi], _dir(ids, *dxyz))
        ec_ids.append(_ec(ids, vp_ids[vi], vp_ids[vj], line_id))

    # Edge lookup: (vi, vj) → (edge_index, forward)
    edge_lu: dict[tuple[int, int], tuple[int, bool]] = {}
    for idx, (vi, vj, _) in enumerate(edge_defs):
        edge_lu[(vi, vj)] = (idx, True)
        edge_lu[(vj, vi)] = (idx, False)

    # 6 face definitions: (vertex_loop, outward_normal, ref_dir, origin_vertex_idx)
    face_defs: list[tuple[
        list[int],
        tuple[float, float, float],
        tuple[float, float, float],
        int,
    ]] = [
        ([0, 3, 2, 1], (0,  0, -1), ( 1, 0, 0), 0),  # bottom
        ([4, 5, 6, 7], (0,  0,  1), ( 1, 0, 0), 4),  # top
        ([0, 1, 5, 4], (0, -1,  0), ( 1, 0, 0), 0),  # front
        ([3, 7, 6, 2], (0,  1,  0), (-1, 0, 0), 3),  # back
        ([1, 2, 6, 5], (1,  0,  0), ( 0, 1, 0), 1),  # right
        ([0, 4, 7, 3], (-1, 0,  0), ( 0, 1, 0), 0),  # left
    ]

    af_ids: list[int] = []
    for vloop, normal, ref, ov in face_defs:
        n = len(vloop)
        oe_ids = [
            _oe(ids, ec_ids[edge_lu[(vloop[k], vloop[(k + 1) % n])][0]],
                edge_lu[(vloop[k], vloop[(k + 1) % n])][1])
            for k in range(n)
        ]
        el_id = _el(ids, oe_ids)
        fob_id = _fob(ids, el_id)
        plane_id = _plane(ids, coords[ov], normal, ref)
        af_ids.append(_af(ids, fob_id, plane_id))

    shell_refs = ",".join(f"#{i}" for i in af_ids)
    cs_id = ids.add(f"CLOSED_SHELL('',({shell_refs}))")
    return ids.add(f"MANIFOLD_SOLID_BREP('',#{cs_id})")
```

- [ ] **Step 3.2: Run targeted tests**

```bash
.venv/bin/pytest tests/write/test_step.py -q -k "manifold or advanced_face or edge_curve"
```

Expected: those tests still fail (no `render_step` or `document.py` yet) but with ImportError — not AttributeError. The brep code itself has no reachable test yet.

- [ ] **Step 3.3: Commit**

```bash
git add src/cad/write/step/brep.py
git commit -m "feat(step): implement Prism to MANIFOLD_SOLID_BREP BRep generator"
```

---

## Task 4 — STEP document renderer

**Files:**
- Create: `src/cad/write/step/document.py`

This function assembles the full AP214 STEP text for a list of `Part` objects. Each Part becomes one PRODUCT in the file. Only `Prism` solids are supported; any other `Shape3D` raises `WriteError`.

- [ ] **Step 4.1: Implement**

```python
# src/cad/write/step/document.py
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from cad.errors import WriteError
from cad.geom.shapes3d import Prism
from cad.geom.base import Shape3D
from cad.write.step.brep import prism_brep
from cad.write.step.ids import IdAllocator

if TYPE_CHECKING:
    from cad.model.core import Part


_HEADER_TMPL = """\
ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('PySeas CAD'),'2;1');
FILE_NAME('{name}','{ts}',(''),(''),'','PySeas CAD','');
FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));
ENDSEC;
DATA;
"""

_FOOTER = "ENDSEC;\nEND-ISO-10303-21;\n"


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")


def render_step(parts: list[Part], model_name: str, *, timestamp: str | None = None) -> str:
    """Render an AP214 STEP file for the given parts.

    Each Part must contain only Prism solids. Any other Shape3D raises WriteError.
    Parts with no solids are skipped silently.
    Raises WriteError if no part has any supported solids.
    """
    ts = timestamp or _now_iso()
    ids = IdAllocator()

    # ── Shared application context ─────────────────────────────────────────
    app_ctx = ids.add(
        "APPLICATION_CONTEXT"
        "('core data for automotive mechanical design processes')"
    )
    ids.add(
        f"APPLICATION_PROTOCOL_DEFINITION"
        f"('international standard','automotive_design',2000,#{app_ctx})"
    )
    prod_ctx = ids.add(f"PRODUCT_CONTEXT('',#{app_ctx},'mechanical')")

    # ── Units (metres, radians, steradians) ────────────────────────────────
    len_unit = ids.add("(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT($,.METRE.))")
    angle_unit = ids.add("(NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.))")
    solid_angle_unit = ids.add("(NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT())")
    uncertainty = ids.add(
        f"UNCERTAINTY_MEASURE_WITH_UNIT"
        f"(LENGTH_MEASURE(1.E-6),#{len_unit},'distance accuracy value','')"
    )
    geom_ctx = ids.add(
        f"(GEOMETRIC_REPRESENTATION_CONTEXT(3)"
        f" GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{uncertainty}))"
        f" GLOBAL_UNIT_ASSIGNED_CONTEXT((#{len_unit},#{angle_unit},#{solid_angle_unit}))"
        f" REPRESENTATION_CONTEXT('',''))"
    )

    any_solid = False

    for part in parts:
        if not part.solids:
            continue

        solid_ids: list[int] = []
        for solid in part.solids:
            if isinstance(solid, Prism):
                solid_ids.append(prism_brep(ids, solid))
            else:
                raise WriteError(
                    f"STEP export does not support {type(solid).__name__}; "
                    f"only Prism is supported in Stage 5"
                )

        if not solid_ids:
            continue

        any_solid = True

        # ── Product / part structure ───────────────────────────────────────
        product = ids.add(
            f"PRODUCT('{part.name}','{part.name}','',(#{prod_ctx}))"
        )
        prod_form = ids.add(f"PRODUCT_DEFINITION_FORMATION('','',#{product})")
        pdc = ids.add(
            f"PRODUCT_DEFINITION_CONTEXT('part definition',#{app_ctx},'design')"
        )
        prod_def = ids.add(f"PRODUCT_DEFINITION('','',#{prod_form},#{pdc})")
        pds = ids.add(f"PRODUCT_DEFINITION_SHAPE('','',#{prod_def})")

        # ── Part placement (identity) ──────────────────────────────────────
        cp0 = ids.add("CARTESIAN_POINT('',(0.,0.,0.))")
        dz = ids.add("DIRECTION('',(0.,0.,1.))")
        dx = ids.add("DIRECTION('',(1.,0.,0.))")
        placement = ids.add(f"AXIS2_PLACEMENT_3D('',#{cp0},#{dz},#{dx})")

        # ── Shape representations ──────────────────────────────────────────
        solid_refs = ",".join(f"#{i}" for i in solid_ids)
        brep_rep = ids.add(
            f"ADVANCED_BREP_SHAPE_REPRESENTATION"
            f"('',(#{placement},{solid_refs}),#{geom_ctx})"
        )
        ids.add(f"SHAPE_DEFINITION_REPRESENTATION(#{pds},#{brep_rep})")

    if not any_solid:
        raise WriteError("no supported solids in any part; cannot write STEP file")

    header = _HEADER_TMPL.format(name=model_name, ts=ts)
    return header + ids.render_data() + "\n" + _FOOTER
```

- [ ] **Step 4.2: Run all STEP tests**

```bash
.venv/bin/pytest tests/write/test_step.py -q
```

Expected: 6 passed (all tests except the model-level `test_model_write_step_produces_file` which still hits `NotImplementedError`).

- [ ] **Step 4.3: Commit**

```bash
git add src/cad/write/step/document.py
git commit -m "feat(step): implement AP214 STEP document renderer for Prism solids"
```

---

## Task 5 — Wire Model.write_step; update existing tests

**Files:**
- Modify: `src/cad/model/core.py` (lines 332–334 — the `write_step` stub)
- Modify: `tests/model/test_model_step.py`

- [ ] **Step 5.1: Update `Model.write_step`**

In `src/cad/model/core.py`, replace:

```python
    def write_step(self, path: str | Path) -> NoReturn:
        raise NotImplementedError("STEP export is reserved for Stage 5")
```

with:

```python
    def write_step(self, path: str | Path) -> Model:
        from cad.write.step.document import render_step
        text = render_step(list(self._parts.values()), self.name)
        Path(path).write_text(text, encoding="ascii")
        return self
```

Also remove the `NoReturn` import if it is no longer used elsewhere. Check the imports at the top of `core.py` and remove `NoReturn` from the `from typing import NoReturn, cast` line if `NoReturn` is only used by `write_step`.

- [ ] **Step 5.2: Replace `tests/model/test_model_step.py`**

```python
from __future__ import annotations

import pytest

from cad import Model, WriteError, prism, sphere


def test_write_step_prism_creates_file(tmp_path) -> None:
    model = Model("demo")
    model.part("plate").add(prism((0, 0, 0), (1, 0.5, 0.01)))
    result = model.write_step(tmp_path / "demo.step")
    assert result is model
    text = (tmp_path / "demo.step").read_text(encoding="ascii")
    assert "MANIFOLD_SOLID_BREP" in text
    assert "CLOSED_SHELL" in text


def test_write_step_multiple_prisms_in_one_part(tmp_path) -> None:
    model = Model("demo")
    part = model.part("body")
    part.add(prism((0, 0, 0), (1, 1, 1)))
    part.add(prism((2, 0, 0), (0.5, 0.5, 0.5)))
    model.write_step(tmp_path / "multi.step")
    text = (tmp_path / "multi.step").read_text(encoding="ascii")
    assert text.count("MANIFOLD_SOLID_BREP") == 2
    assert text.count("CLOSED_SHELL") == 2


def test_write_step_multiple_parts(tmp_path) -> None:
    model = Model("demo")
    model.part("plate").add(prism((0, 0, 0), (1, 0.5, 0.01)))
    model.part("pin").add(prism((0.1, 0.1, 0.01), (0.05, 0.05, 0.1)))
    model.write_step(tmp_path / "assembly.step")
    text = (tmp_path / "assembly.step").read_text(encoding="ascii")
    assert text.count("PRODUCT(") == 2
    assert text.count("MANIFOLD_SOLID_BREP") == 2


def test_write_step_rejects_sphere(tmp_path) -> None:
    model = Model("demo")
    model.part("ball").add(sphere((0, 0, 0), 1.0))
    with pytest.raises(WriteError, match="Sphere"):
        model.write_step(tmp_path / "ball.step")


def test_write_step_empty_model_raises(tmp_path) -> None:
    model = Model("demo")
    with pytest.raises(WriteError, match="no supported solids"):
        model.write_step(tmp_path / "empty.step")


def test_write_step_negative_size_prism(tmp_path) -> None:
    model = Model("demo")
    # Prism size components can be negative; writer must normalise bounds
    model.part("plate").add(prism((1, 1, 1), (-1, -0.5, -0.01)))
    model.write_step(tmp_path / "neg.step")
    text = (tmp_path / "neg.step").read_text(encoding="ascii")
    assert "MANIFOLD_SOLID_BREP" in text


def test_write_step_file_has_ap214_schema(tmp_path) -> None:
    model = Model("demo")
    model.part("box").add(prism((0, 0, 0), (1, 1, 1)))
    model.write_step(tmp_path / "box.step")
    text = (tmp_path / "box.step").read_text(encoding="ascii")
    assert "FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));" in text
    assert "SI_UNIT($,.METRE.)" in text
```

- [ ] **Step 5.3: Run model STEP tests**

```bash
.venv/bin/pytest tests/model/test_model_step.py -v
```

Expected: 7 passed.

- [ ] **Step 5.4: Run full test suite to check for regressions**

```bash
.venv/bin/pytest -q
```

Expected: all previously passing tests still pass, plus the new ones.

- [ ] **Step 5.5: Commit**

```bash
git add src/cad/model/core.py tests/model/test_model_step.py
git commit -m "feat(step): wire Model.write_step through AP214 renderer"
```

---

## Task 6 — Pyright + ruff gates

**Files:** (no source changes — just gate verification)

- [ ] **Step 6.1: Run pyright**

```bash
.venv/bin/pyright src/cad
```

Expected: 0 errors, 0 warnings.

If pyright complains about `NoReturn` vs `Model` return type mismatch in `write_step`, confirm the import removal in Task 5.1 was applied.

- [ ] **Step 6.2: Run ruff**

```bash
.venv/bin/ruff check src/cad tests examples/scripts
```

Expected: no issues.

Fix any complaints before continuing.

- [ ] **Step 6.3: Commit any lint fixes**

Only if changes were made:

```bash
git add -p
git commit -m "fix(step): resolve pyright/ruff issues in STEP writer"
```

---

## Task 7 — Stdlib-only convention check + plan update

**Files:**
- Modify: `.warden/plans/2026-05-11-pyseas-cad-stage-5-step-v1.md` (status)

- [ ] **Step 7.1: Verify no runtime dependencies added**

```bash
.venv/bin/python -c "
import importlib.metadata as m
reqs = m.distribution('pyseas-cad').requires or []
print('deps:', reqs)
assert reqs == [], 'unexpected runtime dependency'
"
```

Expected: `deps: []`

- [ ] **Step 7.2: Run full gate suite one final time**

```bash
.venv/bin/pytest -q && \
.venv/bin/pyright src/cad && \
.venv/bin/ruff check src/cad tests examples/scripts
```

Expected: all pass.

- [ ] **Step 7.3: Update plan status**

In `.warden/plans/2026-05-11-pyseas-cad-stage-5-step-v1.md`, change:

```
**Status:** complete
```

to:

```
**Status:** complete
```

- [ ] **Step 7.4: Final commit**

```bash
git add .warden/plans/2026-05-11-pyseas-cad-stage-5-step-v1.md
git commit -m "docs: mark Stage 5 STEP plan complete"
```

---

## Acceptance Criteria

| Check | Command |
|---|---|
| All tests pass | `.venv/bin/pytest -q` |
| Pyright clean | `.venv/bin/pyright src/cad` |
| Ruff clean | `.venv/bin/ruff check src/cad tests examples/scripts` |
| No runtime deps | `python -c "import importlib.metadata as m; assert (m.distribution('pyseas-cad').requires or []) == []"` |
| Prism writes valid STEP | `test_write_step_prism_creates_file` passes |

## Non-Goals (Stage 5)

- STEP parser / round-trip
- `Extrusion`, `Revolution`, `Sphere` solid support
- Assembly structure (`NEXT_ASSEMBLY_USAGE_OCCURRENCE`)
- GD&T / tolerances
- External STEP validator (no tool available on this host)
- Gallery STEP file (deferred to Stage 6 polish)
