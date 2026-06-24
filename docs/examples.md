# Examples

Examples live in `examples/scripts`. Generated outputs live in
`examples/gallery`.

Run examples from the repository root:

```bash
PYTHONPATH=src .venv/bin/python examples/scripts/plate_with_hole.py
PYTHONPATH=src .venv/bin/python examples/scripts/model_plate.py
PYTHONPATH=src .venv/bin/python examples/scripts/production_dxf.py
PYTHONPATH=src .venv/bin/python examples/scripts/production_step.py
```

Most scripts accept `--out <dir>`.

## Scripts

| Script | Shows |
|---|---|
| `example_geometry.py` | Shared plate/profile/part/scene builders used by the examples. |
| `plate_with_hole.py` | Direct `Drawing2D` and `Part` export to DXF/STL. |
| `model_plate.py` | Optional `Document` registry around a drawing and part. |
| `production_dxf.py` | A denser drawing using layers and additional 2D entities. |
| `production_step.py` | Assembly export through the STEP facade. |
| `visualise_plate.py` | Scene summary plus DXF/STL outputs for the plate. |
| `visualise_3d.py` | Interactive VisPy scene viewing for generated 3D objects. |
| `visualise_linesplan_9m.py` | Reading 3D DXF wires directly, then as an origin-centred `Mesh3D` scene. |

## Example shape

The shared plate example builds the same concepts used by the docs:

```python
outline = profile_rectangle(1.0, 0.6)
hole = circle2d((0.5, 0.3), 0.12)
profile = Profile2D(outline.outer, holes=(hole,))

drawing = Drawing2D("front").add(profile.outer, layer="PLATE").add(hole, layer="PLATE")
part = Part("plate").with_body(Body3D.from_profile(profile).extrude(0.04))
document = Document("model_plate").add_drawing(drawing, name="front").add_part(part)
```

Keep new examples focused on one workflow and add tests when an example becomes
part of the supported behavior surface.
