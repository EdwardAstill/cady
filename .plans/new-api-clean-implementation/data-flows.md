# Data Flows

## 2D Authoring To DXF

```text
Profile2D / Curve2D
  -> Drawing2D.add(..., layer=...)
  -> DrawingEntity
  -> files.dxf.render(drawing, tolerance=...)
  -> DXF sections/tables/entities
  -> .dxf text file
```

Rules:

- Curves that DXF supports natively should be emitted as native entities:
  `Line2D` -> `LINE`, `Circle2D` -> `CIRCLE`, `Arc2D` -> `ARC`.
- Profiles and unsupported curves may be flattened to `LWPOLYLINE` at the DXF
  writer boundary using the explicit `tolerance`.
- Hatches consume `Profile2D` or closed curves and emit DXF `HATCH`.
- Dimensions and blocks remain drawing-level entities, not geometry-level
  curves.

## DXF To Drawing2D

```text
.dxf text
  -> files.dxf.parser.pairs/sections/entity_chunks
  -> files.dxf.reader
  -> Drawing2D(layers, entities, text, metadata)
```

Rules:

- Layer table records create `Layer` values.
- Unsupported 2D entities are skipped with a report in `DxfImportResult` when
  using `dxf.read`; `read_drawing` may ignore unsupported non-fatal entities
  but must raise `ReadError` for malformed input.
- Imported 2D polylines stay as drawing curves. They are not automatically
  promoted to profiles in the first implementation.

## DXF To Mesh3D

```text
.dxf text
  -> files.dxf.parser
  -> 3DFACE / polyface POLYLINE extraction
  -> Mesh3D
```

Rules:

- `3DFACE` triangles and quads become triangle faces.
- Polyface records become triangle faces.
- Multiple supported meshes can be returned in `DxfImportResult.meshes`.
- `dxf.read_mesh(path)` returns `Mesh3D.merged(result.meshes)`.
- 3D wires are returned separately as `Polyline3D`.
- ACIS-backed `3DSOLID`, `BODY`, `REGION`, and `SURFACE` are reported as
  skipped. Do not fake them as bodies.

## Profile To Body To Mesh

```text
Profile2D
  -> Body3D(features=(ExtrudeFeature(...),))
  -> ops/evaluate3d
  -> triangle primitives
  -> Mesh3D
```

Rules:

- Domain `Body3D` stores feature intent.
- Evaluation code converts features to primitive numeric data.
- Mesh output is explicit through `to_mesh(tolerance=...)`.
- `Mesh3D` is evaluated data and can be exported/viewed, but does not replace
  `Body3D` during authoring.

## Part And Assembly To Mesh

```text
Part.bodies
  -> body.to_mesh(tolerance=...)
  -> Mesh3D.merged(...)

Assembly.instances
  -> recursive flatten
  -> placed part meshes
  -> Mesh3D.merged(...)
```

Rules:

- A part with multiple bodies merges those body meshes for STL/viewing.
- Assembly instance poses are applied to the target part/assembly result.
- Repeated parts share the same semantic object but produce distinct placed
  mesh geometry.
- Assembly flattening detects cycles before recursion.

## Scene To Visualisation

```text
Scene
  -> visible SceneObject targets
  -> target evaluation:
       Drawing2D -> 2D arrays
       Body3D/Part/Assembly -> Mesh3D
       Mesh3D -> Mesh3D
  -> backend adapter
  -> matplotlib/vispy/pyvista output
```

Rules:

- Scene pose/display overrides are applied after target placement.
- Camera and lights are passed to backend adapters as value objects.
- Backends may ignore unsupported lights/camera properties initially, but must
  not require those objects to import backend packages.

## Document To Export

```text
Document
  -> choose content by format
  -> drawing/mesh/step writer
```

Rules:

- `Document` is a registry, not a mandatory root.
- DXF export from `Document` should require exactly one drawing unless the API
  accepts an explicit drawing name.
- STL export merges all meshable body/part/assembly contents.
- STEP export emits supported body/part/assembly contents and skips/raises for
  unsupported bodies according to a documented policy.
