# cady

cady is a small native CAD geometry package for building 2D drawings, meshable
3D parts, assemblies, and view scenes in Python. It writes DXF, STL, and STEP
files without requiring a large CAD kernel at runtime.

Start with [docs/index.md](docs/index.md) for the full documentation.

## What cady provides

- immutable 2D geometry values such as `Line2D`, `Circle2D`, `Polyline2D`,
  `ClosedPolyline2D`, `Spline2D`, `Ellipse2D`, and `Profile2D`;
- meshable 3D geometry through `Body3D`, `Face3D`, `Frame3D`, and `Mesh3D`;
- product structure with `Part`, `Assembly`, placed part instances, materials,
  and metadata;
- 2D drafting documents with layers, text, hatches, blocks, inserts, and
  dimensions;
- backend-independent view descriptions with scenes, cameras, lights, and
  display styles;
- file facades for DXF drawing I/O, STL mesh output, STEP mesh output, and STEP
  surface/member analysis.

cady keeps authoring geometry semantic until an explicit numeric boundary:

```text
geometry value -> to_array(...) or to_mesh(...) -> numeric arrays or file output
```

Every conversion that samples curves or meshes takes an explicit `tolerance`
keyword.

## Install

```bash
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/pip install -e '.[all]'  # optional plotting/viewer extras
```

For local development:

```bash
.venv/bin/pip install --group dev -e .
```

Run scripts from the repository root with `PYTHONPATH=src`.

## Quickstart

Build a plate profile, put the 2D curves into a drawing, extrude the profile
into a part, and write DXF/STL files:

```python
from cady import Body3D, Drawing2D, Part, Profile2D, circle2d, line2d, profile_rectangle
from cady.files import dxf, stl

outline = profile_rectangle(1.0, 0.6)
hole = circle2d((0.5, 0.3), 0.12)
profile = Profile2D(outline.outer, holes=(hole,))

drawing = (
    Drawing2D("front")
    .add_layer("PLATE", color=7)
    .add_layer("CENTER", color=3, linetype="CENTER")
    .add(profile.outer, layer="PLATE")
    .add(hole, layer="PLATE")
    .add(line2d((0.5, 0.05), (0.5, 0.55)), layer="CENTER")
    .add_text("PLATE", at=(0.02, 0.02), height=0.03, layer="PLATE")
)

body = Body3D.from_profile(profile).extrude(0.04)
part = Part("plate").with_body(body)

dxf.write(drawing, "plate.dxf", tolerance=1e-3)
stl.write(part, "plate.stl", tolerance=1e-3)
```

All core objects are immutable. Methods such as `.add(...)`, `.with_body(...)`,
and `.with_metadata(...)` return new values rather than mutating the original.

## Direct objects first

cady does not require a top-level model object. Use the object that matches the
work:

- use `Drawing2D` for 2D drafting and DXF output;
- use `Body3D` for editable meshable geometry;
- use `Part` for one named manufacturable item;
- use `Assembly` for placed parts or subassemblies;
- use `Scene` for cameras, lights, display styles, and viewer state;
- use `Document` only when you want one registry of named drawings, parts,
  assemblies, and scenes.

Example document:

```python
from cady import Document

document = (
    Document("plate_job", units="m")
    .add_drawing(drawing, name="front")
    .add_part(part, name="plate")
    .with_metadata(author="cady")
)
```

File writers also accept suitable direct objects, so a document is optional.

## File I/O

```python
from cady.files import dxf, step, stl

dxf.write(drawing, "front.dxf", tolerance=1e-3)
imported_drawing = dxf.read_drawing("front.dxf")

stl.write(part, "plate.stl", tolerance=1e-3)
stl.write(part, "plate-ascii.stl", ascii=True, tolerance=1e-3)

step.write(part, "plate.step", tolerance=1e-3)
faces = step.read_faces("member.step")
members = step.read_members("member.step")
```

Current file support is deliberately small:

- DXF writes `LINE`, `LWPOLYLINE`, `CIRCLE`, `ARC`, and `TEXT` entities from a
  `Drawing2D`; profile-like objects are sampled to closed polylines when no
  direct DXF entity exists.
- DXF reads basic 2D drawing entities, `3DFACE` triangles/quads, and 3D
  polyline wires. ACIS-backed solids are reported as skipped records.
- STL writes binary or ASCII triangle meshes from `Mesh3D`, `Body3D`, `Part`,
  `Assembly`, `ArrayMesh3`, or meshable `Document` contents.
- STEP write currently emits mesh vertices and triangular face loops from
  meshable targets. STEP read remains analysis-oriented and extracts elementary
  faces and simple extruded members.

## Examples

```bash
PYTHONPATH=src .venv/bin/python examples/scripts/plate_with_hole.py
PYTHONPATH=src .venv/bin/python examples/scripts/model_plate.py
PYTHONPATH=src .venv/bin/python examples/scripts/production_dxf.py
PYTHONPATH=src .venv/bin/python examples/scripts/production_step.py
PYTHONPATH=src .venv/bin/python examples/scripts/visualise_3d.py --shape all
```

Most scripts write to `examples/gallery` and accept `--out <dir>`.

## Package layout

```text
cady.geometry2d   2D curves, closed curves, profiles, and factories
cady.geometry3d   bodies, faces, frames, meshes, features, and primitives
cady.drawing      drawing documents, layers, text, hatches, blocks, dimensions
cady.product      parts, assemblies, materials, and assembly flattening
cady.view         backend-independent scenes, cameras, lights, display styles
cady.document     optional top-level registry
cady.numeric      NumPy-backed evaluated arrays and transforms
cady.ops          object-agnostic geometry algorithms
cady.files        DXF, STL, and STEP facades
cady.visualisation optional scene adapter helpers
cady.errors       shared exception hierarchy
```

The legacy `Model`, `Shape2D`, `Shape3D`, `Rectangle`, `Prism`, `Extrusion`,
`DxfDrawing`, `StlMesh`, `cady.domain`, `cady.build`, `cady.plotting`, and
`write_model(...)` APIs have been removed from this branch.

## Development gates

```bash
.venv/bin/pytest -q
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
```

The convention tests enforce import boundaries and the runtime dependency
allowlist.
