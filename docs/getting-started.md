# Getting Started

## Install

```bash
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pip install --group dev -e .
```

Optional extras are declared in `pyproject.toml`:

```bash
.venv/bin/pip install -e '.[plotting]'
.venv/bin/pip install -e '.[visualisation]'
.venv/bin/pip install -e '.[all]'
```

Run examples from the repository root with `PYTHONPATH=src`.

## First drawing and part

```python
from cady import Body3D, Drawing2D, Part, Profile2D, circle2d, profile_rectangle
from cady.files import dxf, stl

outline = profile_rectangle(1.0, 0.6)
hole = circle2d((0.5, 0.3), 0.12)
profile = Profile2D(outline.outer, holes=(hole,))

drawing = (
    Drawing2D("front")
    .add_layer("PLATE", color=7)
    .add(profile.outer, layer="PLATE")
    .add(hole, layer="PLATE")
    .add_text("PLATE", at=(0.02, 0.02), height=0.03, layer="PLATE")
)

part = Part("plate").with_body(Body3D.from_profile(profile).extrude(0.04))

dxf.write(drawing, "plate.dxf", tolerance=1e-3)
stl.write(part, "plate.stl", tolerance=1e-3)
```

This keeps the drawing and part separate. The drawing contains 2D CAD entities;
the part contains meshable 3D bodies.

## Grouping with a document

`Document` is an optional registry for named project contents:

```python
from cady import Document

document = (
    Document("plate_job", units="m")
    .add_drawing(drawing, name="front")
    .add_part(part, name="plate")
)

drawing = document.get("drawing", "front")
part = document.get("part", "plate")
```

Use direct objects when that is simpler. File writers do not require a document.

## Reading files

```python
from cady.files import dxf, step

drawing = dxf.read_drawing("profile.dxf")
mesh = dxf.read_mesh("faceted-part.dxf")
result = dxf.read("mixed.dxf")

faces = step.read_faces("member.step")
members = step.read_members("member.step")
```

DXF read support is limited to basic 2D entities, `3DFACE` meshes, and 3D
polyline wires. STEP read support is for elementary surface/member analysis,
not arbitrary editable CAD reconstruction.

## Numeric conversion

Authoring objects remain semantic until you request evaluated geometry:

```python
profile_array = profile.to_array(tolerance=1e-3)
mesh = part.to_mesh(tolerance=1e-3)
```

Smaller tolerances create denser sampled curves and meshes.

## Run examples

```bash
PYTHONPATH=src .venv/bin/python examples/scripts/plate_with_hole.py
PYTHONPATH=src .venv/bin/python examples/scripts/model_plate.py
PYTHONPATH=src .venv/bin/python examples/scripts/production_dxf.py
PYTHONPATH=src .venv/bin/python examples/scripts/production_step.py
```

Most scripts write to `examples/gallery` and accept `--out <dir>`.
