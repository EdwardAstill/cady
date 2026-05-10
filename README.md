# pyseas-cad

Small, pure-stdlib, write-only CAD package for building format-blind geometry
and emitting DXF R2018 or STL.

pyseas-cad is currently at **Stage 3**:

- immutable 2D and 3D geometry values,
- DXF writer for `LINE`, `LWPOLYLINE`, `CIRCLE`, `ARC`, `MTEXT`,
- production DXF helpers for `HATCH`, `BLOCK`, `INSERT`, and built-in
  linetypes,
- binary and ASCII STL writer,
- model layer for named drawings, parts, assemblies, and metadata,
- end-to-end plate-with-hole example.

STEP support is planned, but not implemented by the package yet.

## Quickstart

```python
from cad import Model, circle, rectangle

profile = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))

model = Model("plate")
model.drawing("front").layer("PLATE", color=7).add(profile)
model.drawing("front").add_text("PLATE", at=(0.02, 0.02), height=0.03, layer="TEXT")
model.part("plate").add(profile.extrude("+z", 0.04))

model.write_dxf("plate.dxf")
model.write_stl("plate.stl")
```

Run the model-first example:

```bash
python examples/model_plate.py --out /tmp/pyseas-cad-demo
```

This writes:

- `/tmp/pyseas-cad-demo/model_plate.dxf`
- `/tmp/pyseas-cad-demo/model_plate.stl`

Run the production DXF example:

```bash
python examples/production_dxf.py --out /tmp/pyseas-cad-production
```

This writes `/tmp/pyseas-cad-production/production_plate.dxf` with hatching,
centerlines, a reusable block, and two inserts.

## Current API

Geometry factories:

```python
from cad import arc, circle, line, polyline, prism, rectangle, sphere, spline
```

2D shapes:

- `Line`
- `Arc`
- `Circle`
- `Rectangle`
- `Polyline`
- `Spline`
- `Path`

3D shapes:

- `Sphere`
- `Prism`
- `Extrusion`
- `Revolution`

Scenes and writers:

```python
from cad import Assembly, Drawing2D, DxfDrawing, Model, Part, StlMesh
```

Use `Model` as the preferred organizing layer for named drawings and parts.
Use `DxfDrawing` and `StlMesh` directly for low-level or single-format output.

Production DXF features:

```python
from cad import Model, circle, line, rectangle

outline = rectangle((0, 0), (1.0, 0.6))

model = Model("production_plate")
front = model.drawing("front")
front.layer("PLATE").add(outline)
front.layer("SECTION").hatch(outline, pattern="ANSI31", scale=0.025)
front.layer("CENTER", linetype="CENTER").add(line((0.5, 0.05), (0.5, 0.55)))
front.block("PIN_MARK").layer("SYMBOL").add(circle((0, 0), 0.025))
front.insert("PIN_MARK", at=(0.5, 0.3), layer="SYMBOL")
model.write_dxf("production_plate.dxf")
```

## Target v1 API

The roadmap moves toward one source model exporting DXF, STL, and STEP:

```python
from cad import Model, circle, rectangle

plate = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))

model = Model("padeye_plate")
model.drawing("front").layer("PLATE").add(plate)
model.part("plate").add(plate.extrude("+z", 0.04))

model.write_dxf("padeye_plate.dxf")
model.write_stl("padeye_plate.stl")
model.write_step("padeye_plate.step")
```

`Model.write_dxf` and `Model.write_stl` are implemented. `Model.write_step`
is reserved and raises `NotImplementedError` until Stage 5.

## Roadmap

The controlling roadmap is:

```text
.warden/specs/2026-05-08-pyseas-cad-v1-roadmap.md
```

Current sequence:

1. Stage 1: geometry, DXF basics, STL — implemented
2. Stage 2: `cad.model` layer — implemented
3. Stage 3: production DXF: HATCH, BLOCK, INSERT, linetypes — implemented
4. Stage 4: dimensions and drawing helpers — next
5. Stage 5: STEP MVP and v1 hardening

## Development

Create a dev environment:

```bash
python -m venv .venv
.venv/bin/pip install -e . -r requirements-dev.txt
```

Run gates:

```bash
.venv/bin/pytest -q
.venv/bin/pyright src/cad
.venv/bin/ruff check src/cad tests
.venv/bin/python -c "import importlib.metadata as m; assert (m.distribution('pyseas-cad').requires or []) == []"
```

Runtime package metadata must have no dependencies. Dev tools live in
`requirements-dev.txt`.

## Boundaries

- Runtime code stays pure stdlib.
- pyseas-cad is write-only. It does not parse DXF, STL, or STEP.
- pyseas-cad is domain-blind. It does not contain `Padeye`, `Shackle`, or other
  lifting-gear objects.
- Domain recipes belong in pyseas-yard or examples.
