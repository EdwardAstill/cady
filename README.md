# cady

cady is a small native CAD geometry package for building 2D drawings, meshable
3D parts, assemblies, and view scenes in Python. It writes DXF, STL, and STEP
files without requiring a large CAD kernel at runtime.

Start with [docs/index.md](docs/index.md) for the full documentation.

## What cady provides

- immutable 2D geometry values such as `Line2`, `Circle2`, open or closed
  `Polyline2`, `Spline2`, `Ellipse2`, `Region2`, and `Mesh2`;
- meshable 3D geometry through `Body3`, `Region3`, `Surface3`, `Plane3`,
  `Mesh3`, and closed 3D polylines;
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

Build a plate region, put the 2D curves into a drawing, extrude the region
into a part, and write DXF/STL files:

```python
from cady import Body3, Circle2, Drawing2, Line2, Part, Region2, Text2
from cady.files import dxf, stl

outline = Region2.rectangle(1.0, 0.6)
hole = Circle2((0.5, 0.3), 0.12)
region = Region2(outline.outer, holes=(hole,))

drawing = (
    Drawing2("front")
    .add_layer("PLATE", color=7)
    .add_layer("CENTER", color=3, linetype="CENTER")
    .add(region.outer, layer="PLATE")
    .add(hole, layer="PLATE")
    .add(Line2((0.5, 0.05), (0.5, 0.55)), layer="CENTER")
    .add_entity(Text2("PLATE", at=(0.02, 0.02), height=0.03, layer="PLATE"))
)

body = Body3.from_region(region).extrude(0.04)
part = Part("plate").with_body(body)

dxf.write(drawing, "plate.dxf", tolerance=1e-3)
stl.write(part, "plate.stl", tolerance=1e-3)
```

All core objects are immutable. Methods such as `.add(...)`, `.with_body(...)`,
and `.with_metadata(...)` return new values rather than mutating the original.

## Direct objects first

cady does not require a top-level model object. Use the object that matches the
work:

- use `Drawing2` for 2D drafting and DXF output;
- use `Body3` for editable meshable geometry;
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
  `Drawing2`; region-like objects are sampled to closed polylines when no
  direct DXF entity exists.
- DXF reads basic 2D drawing entities, `3DFACE` triangles/quads, and 3D
  polyline wires. ACIS-backed solids are reported as skipped records.
- STL writes binary or ASCII triangle meshes from `Mesh3`, `Body3`, `Part`,
  `Assembly`, or meshable `Document` contents.
- STEP write currently emits mesh vertices and triangular face loops from
  meshable targets. STEP read remains analysis-oriented and extracts elementary
  faces and simple extruded members.

## Examples

```bash
PYTHONPATH=src .venv/bin/python examples/scripts/plate_with_hole.py
PYTHONPATH=src .venv/bin/python examples/scripts/model_plate.py
PYTHONPATH=src .venv/bin/python examples/scripts/production_dxf.py
PYTHONPATH=src .venv/bin/python examples/scripts/production_step.py
PYTHONPATH=src .venv/bin/python examples/scripts/visualise_3.py --shape all
```

File-producing scripts write to `examples/files/created` by default and accept
`--out <dir>`.

## Package layout

```text
cady.geometry     2D/3D curves, regions, surfaces, meshes, and bodies
cady.operations   NumPy-backed transforms, meshing, and topology algorithms
cady.measurement  object-level distance and intersection queries
cady.drawing      drawing documents, layers, entities, and dimensions
cady.product      parts, assemblies, materials, and flattening
cady.view         scenes, cameras, styles, and optional viewer helpers
cady.vessels      vessel-specific workflows such as linesplan meshing
cady.files        DXF, STL, and STEP facades
cady.document     optional top-level registry
cady.errors       shared exception hierarchy
```

The legacy `Model`, `Shape2`, `Shape3`, `Rectangle`, `Prism`, `Extrusion`,
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
