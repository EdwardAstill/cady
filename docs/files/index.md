# File Formats

## Overview

cady writes DXF R2018, binary/ASCII STL, and AP214 STEP. It reads a limited
ASCII DXF subset and elementary STEP surfaces for analysis.

## Details

## DXF

Write drawings through `Model` or the file facade:

```python
model.write_dxf("drawing.dxf")
dxf.write_model(model, "drawing.dxf", tolerance=1e-3)
```

Supported output includes lines, polylines, circles, arcs, text, layers,
hatches, blocks, inserts, linetypes, and native dimensions.

Read support covers a limited ASCII subset:

```python
drawing = dxf.read_drawing("profile.dxf")
mesh = dxf.read_mesh("faceted-part.dxf")
result = dxf.read_3d("mixed-3d.dxf")
```

`read_3d(...)` reports unsupported ACIS-backed entities such as `3DSOLID`,
`BODY`, `REGION`, and `SURFACE` as skipped records.

Implementation notes: [DXF format cheatsheet](dxf-format-cheatsheet.md).

## STL

Write STL when you need triangle mesh output:

```python
model.write_stl("part.stl")
model.write_stl("part-ascii.stl", ascii=True)
```

STL has no semantic curves, layers, units, or assemblies. cady tessellates
3D shapes, so tolerance controls curved mesh density.

## STEP

Write STEP when a CAD tool needs supported solid geometry:

```python
model.write_step("part.step")
step.write_model(model, "part.step")
```

STEP export currently supports `Prism` and supported `Extrusion` solids. It
does not export `Sphere` or `Revolution` as STEP solids yet.

Read support is analysis-only:

```python
faces = step.read_faces("frame.step")
members = step.read_members("frame.step")
```

`read_faces(...)` resolves elementary plane, cylindrical, and conical faces.
`read_members(...)` infers simple extruded structural members from those
faces. cady does not rebuild arbitrary STEP assemblies into editable models.

Implementation notes: [STEP format cheatsheet](step-format-cheatsheet.md).

## Choosing A Format

- DXF: 2D drawings with editable CAD entities.
- STL: triangle meshes for mesh tools and printing.
- STEP: supported solids for mechanical CAD tools.

