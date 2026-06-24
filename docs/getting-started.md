# Getting Started

## Overview

cady builds small CAD models in Python and writes them to DXF, STL, or STEP.
The normal flow is: create semantic shapes, attach them to a `Model`, then
export the model.

## Details

## Install

```bash
python -m venv .venv
.venv/bin/pip install -e . -r requirements-dev.txt
```

Optional extras:

```bash
.venv/bin/pip install -e '.[plotting]'
.venv/bin/pip install -e '.[visualisation]'
```

## First Model

```python
from cady import Model, circle, rectangle

profile = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))

model = Model("plate")
model.drawing("front").layer("PLATE").add(profile)
model.part("plate").add(profile.extrude("+z", 0.04))

model.write_dxf("plate.dxf")
model.write_stl("plate.stl")
model.write_step("plate.step")
```

The profile remains a rectangle with a circular hole until export,
visualisation, or `to_array(...)` needs evaluated geometry.

## Run Examples

```bash
PYTHONPATH=src python examples/scripts/model_plate.py
PYTHONPATH=src python examples/scripts/production_dxf.py
PYTHONPATH=src python examples/scripts/production_step.py
```

Most scripts write to `examples/gallery` and accept `--out <dir>`.

## Export And Read

Use `write_dxf(...)` for 2D drawings, `write_stl(...)` for triangle meshes,
and `write_step(...)` for supported AP214 solids.

Read support is intentionally limited:

```python
from cady.files import dxf, step

drawing = dxf.read_drawing("profile.dxf")
mesh = dxf.read_mesh("faceted-part.dxf")
faces = step.read_faces("frame.step")
members = step.read_members("frame.step")
```

## Array Conversion

Stay semantic while authoring. Convert only when numeric work needs it:

```python
profile_array = profile.to_array(tolerance=1e-3)
mesh = profile.extrude("+z", 0.04).to_array(tolerance=1e-3)
```

Smaller tolerances create denser sampled curves and meshes.

