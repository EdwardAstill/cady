# Object Examples

This folder is a small library of ready-made semantic Cady objects. Each module
contains named values and a `main()` summary that can be run from the repository
root:

```bash
PYTHONPATH=src .venv/bin/python examples/objects/meshes.py
PYTHONPATH=src .venv/bin/python examples/objects/polylines.py
PYTHONPATH=src .venv/bin/python examples/objects/pointclouds.py
PYTHONPATH=src .venv/bin/python examples/objects/wireframes.py
```

The modules keep objects in Cady's authoring types (`Mesh3`, `Polyline2`,
`Polyline3`, `PointCloud2`, `PointCloud3`, and `Wireframe3`) so they can be
imported into scripts, scenes, file exports, or tests without generated assets.
