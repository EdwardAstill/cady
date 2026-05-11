# Examples

`scripts/` contains runnable example programs.

`gallery/` contains generated DXF and STL products from those scripts. The
production DXF gallery file demonstrates hatch holes/islands and self-rendered
dimensions.

Run all gallery examples from the repository root:

```bash
PYTHONPATH=src python examples/scripts/plate_with_hole.py
PYTHONPATH=src python examples/scripts/model_plate.py
PYTHONPATH=src python examples/scripts/production_dxf.py
```

Each script accepts `--out <dir>` when you want to write products somewhere
other than `examples/gallery`.
