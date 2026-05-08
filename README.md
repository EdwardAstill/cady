# pyseas-cad

Small, pure-stdlib, write-only CAD package for building format-blind geometry
and emitting DXF R2018 or STL.

pyseas-cad is currently at **Stage 1**:

- immutable 2D and 3D geometry values,
- DXF writer for `LINE`, `LWPOLYLINE`, `CIRCLE`, `ARC`, `MTEXT`,
- binary and ASCII STL writer,
- end-to-end plate-with-hole example.

STEP support is planned, but not implemented by the package yet.

## Quickstart

```python
from cad import DxfDrawing, StlMesh, circle, rectangle

profile = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))
solid = profile.extrude("+z", 0.04)

drawing = DxfDrawing()
drawing.layer("PLATE", color=7).add(profile)
drawing.add_text("PLATE", at=(0.02, 0.02), height=0.03, layer="TEXT")
drawing.write("plate.dxf")

StlMesh(tolerance=1e-3).add(solid).write("plate.stl")
```

Run the included example:

```bash
python examples/plate_with_hole.py --out /tmp/pyseas-cad-demo
```

This writes:

- `/tmp/pyseas-cad-demo/plate.dxf`
- `/tmp/pyseas-cad-demo/plate.stl`

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
from cad import DxfDrawing, StlMesh
```

Use `DxfDrawing` for 2D shapes and annotations. Use `StlMesh` for 3D shapes.

## Target v1 API

The roadmap moves toward a model-first API where one source model can export
DXF, STL, and STEP:

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

`Model` and STEP export are not implemented yet. They are the planned Stage 2
and Stage 5 work.

## Roadmap

The controlling roadmap is:

```text
.warden/specs/2026-05-08-pyseas-cad-v1-roadmap.md
```

Current sequence:

1. Stage 1: geometry, DXF basics, STL — implemented
2. Stage 2: `cad.model` layer — next
3. Stage 3: production DXF: HATCH, BLOCK, INSERT, linetypes
4. Stage 4: dimensions and drawing helpers
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
