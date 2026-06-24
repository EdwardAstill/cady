# Examples

## Overview

Examples live in `examples/scripts` and generated outputs live in
`examples/gallery`.

## Details

## Scripts

| Script | Shows |
|---|---|
| `plate_with_hole.py` | Minimal profile and extrusion. |
| `model_plate.py` | Model-first DXF/STL export. |
| `production_dxf.py` | Hatches, dimensions, blocks, inserts, and linetypes. |
| `production_step.py` | AP214 STEP export. |
| `visualise_plate.py` | Static plot/viewer output. |
| `visualise_3d.py` | 3D visualisation. |
| `visualise_linesplan_9m.py` | Visualising an input drawing. |

Run from the repository root:

```bash
PYTHONPATH=src python examples/scripts/model_plate.py
PYTHONPATH=src python examples/scripts/production_dxf.py
PYTHONPATH=src python examples/scripts/production_step.py
```

Most scripts accept `--out <dir>`.

## Adding Examples

Prefer model-first examples:

```python
model = Model("example")
model.drawing("front").layer("PART").add(profile)
model.part("part").add(profile.extrude("+z", 0.04))
```

Add a test under `tests/examples` when an example is part of the supported
workflow.

