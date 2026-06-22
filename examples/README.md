# Examples

`scripts/` contains runnable example programs.

`gallery/` contains generated DXF and STL products from those scripts. The
production DXF gallery file demonstrates hatch holes/islands and native editable
dimensions.

Examples use object-level write methods such as `model.write_dxf(...)`. The
public format facade is available as `cady.files` when code needs named read
targets such as `step.read_faces(...)` or explicit file modules.

Run all gallery examples from the repository root:

```bash
PYTHONPATH=src python examples/scripts/plate_with_hole.py
PYTHONPATH=src python examples/scripts/model_plate.py
PYTHONPATH=src python examples/scripts/production_dxf.py
PYTHONPATH=src python examples/scripts/production_step.py
```

Each script accepts `--out <dir>` when you want to write products somewhere
other than `examples/gallery`.

Run the visualisation example after installing the optional plotting backend:

```bash
PYTHONPATH=src python examples/scripts/visualise_plate.py --out /tmp/cady-visualisation
```

It writes a 2D profile plot and a static 3D preview image when
`cady.visualisation`, `cady.numeric`, and the selected backend are available.
