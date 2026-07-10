# File Formats

cady exposes small file facades under `cady.files`. The writers accept direct
objects instead of requiring a top-level model.

```python
from cady.files import dxf, step, stl
```

## DXF

Write a `Drawing2`:

```python
dxf.write(drawing, "front.dxf", tolerance=1e-3)
text = dxf.render(drawing, tolerance=1e-3)
```

Current DXF output emits:

- `LINE` from `Line2`;
- `LWPOLYLINE` from open and closed `Polyline2`;
- `CIRCLE` from `Circle2`;
- `ARC` from `Arc2`;
- `TEXT` from `Text2`;
- layer table records for drawing layers;
- sampled closed polylines for other region-like objects that expose
  `to_array(tolerance=...)`.

The drawing object can model hatches, blocks, inserts, and dimensions, but the
current DXF writer does not emit those entities yet.

Read support:

```python
drawing = dxf.read_drawing("profile.dxf")
mesh = dxf.read_mesh("faceted-part.dxf")
result = dxf.read("mixed.dxf")
```

`dxf.read(...)` returns a `DxfImportResult` with:

- `drawing` for supported 2D entities;
- `meshes` for `3DFACE` triangle/quad entities;
- `wires` for 3D `POLYLINE` vertex sequences;
- `skipped` records for unsupported entities such as ACIS-backed solids.

Implementation notes: [DXF format cheatsheet](dxf-format-cheatsheet.md).

## STL

Write binary or ASCII STL from any meshable target:

```python
stl.write(part, "plate.stl", tolerance=1e-3)
stl.write(assembly, "assembly-ascii.stl", ascii=True, tolerance=1e-3)
```

Supported targets include `Mesh3`, `Body3`, `Part`, `Assembly`, and
`Document` values containing meshable parts or assemblies.

STL has no curves, layers, units, materials, or product structure. cady writes
triangles only.

## STEP

Write STEP from meshable targets:

```python
step.write(part, "plate.step", tolerance=1e-3)
text = step.render(assembly, tolerance=1e-3)
```

The current writer emits an ISO-10303-21 file with Cartesian points and
`POLY_LOOP` records for triangular mesh faces. It is useful as a simple mesh
exchange path, not a full AP214/AP242 B-rep solid exporter.

Read support is analysis-oriented:

```python
faces = step.read_faces("member.step")
members = step.read_members("member.step")
```

`read_faces(...)` parses elementary surface data. `read_members(...)` attempts
to infer simple extruded members from parsed faces. cady does not rebuild
arbitrary STEP assemblies into editable `Body3`, `Part`, or `Assembly` values.

Implementation notes: [STEP format cheatsheet](step-format-cheatsheet.md).

## Choosing a format

- DXF: 2D drawing entities and basic 2D import.
- STL: triangle meshes for mesh tools, printing, and simple viewers.
- STEP: currently mesh-flavored exchange plus elementary surface/member
  analysis.
