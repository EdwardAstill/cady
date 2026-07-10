# Examples

`scripts/` contains runnable examples, grouped further where useful.
`files/` contains inputs and `files/created/` is the default output directory.

Examples use the current value API directly:

- `Drawing2` for 2D drawings;
- `Body3`, `Part`, and `Assembly` for meshable geometry;
- `Document` for optional named grouping;
- `Scene`, `Camera`, `Light`, and `DisplayStyle` for view descriptions;
- `cady.files.dxf`, `cady.files.stl`, and `cady.files.step` for file I/O.

Run file-producing examples from the repository root:

```bash
PYTHONPATH=src .venv/bin/python examples/scripts/plate_with_hole.py
PYTHONPATH=src .venv/bin/python examples/scripts/model_plate.py
PYTHONPATH=src .venv/bin/python examples/scripts/production_dxf.py
PYTHONPATH=src .venv/bin/python examples/scripts/production_step.py
```

Each script accepts `--out <dir>` when you want products somewhere other than
`examples/files/created`.

View-related examples:

```bash
PYTHONPATH=src .venv/bin/python examples/scripts/visualise_plate.py --out /tmp/cady-visualisation
PYTHONPATH=src .venv/bin/python examples/scripts/visualise_3.py --shape plate
PYTHONPATH=src .venv/bin/python examples/scripts/meshes/pointcloud2mesh.py --no-view
PYTHONPATH=src .venv/bin/python examples/scripts/meshes/mesh_decimate.py --case surface --no-view
```
