# Examples

`scripts/` contains runnable example programs. `gallery/` contains generated
DXF, STL, and STEP artifacts.

Examples use the current value API directly:

- `Drawing2D` for 2D drawings;
- `Body3D`, `Part`, and `Assembly` for meshable geometry;
- `Document` for optional named grouping;
- `Scene`, `Camera`, `Light`, and `DisplayStyle` for view descriptions;
- `cady.files.dxf`, `cady.files.stl`, and `cady.files.step` for file I/O.

Run gallery examples from the repository root:

```bash
PYTHONPATH=src .venv/bin/python examples/scripts/plate_with_hole.py
PYTHONPATH=src .venv/bin/python examples/scripts/model_plate.py
PYTHONPATH=src .venv/bin/python examples/scripts/production_dxf.py
PYTHONPATH=src .venv/bin/python examples/scripts/production_step.py
```

Each script accepts `--out <dir>` when you want products somewhere other than
`examples/gallery`.

View-related examples:

```bash
PYTHONPATH=src .venv/bin/python examples/scripts/visualise_plate.py --out /tmp/cady-visualisation
PYTHONPATH=src .venv/bin/python examples/scripts/visualise_3d.py --shape plate
PYTHONPATH=src .venv/bin/python examples/scripts/visualise_linesplan_9m.py
```

The linesplan example first opens the imported DXF wires directly, then opens a
second scene built from `Mesh3D.from_dxf(...)`. Both scenes are shifted so their
bounding-box centre sits at the world origin before fitting the profile camera.
