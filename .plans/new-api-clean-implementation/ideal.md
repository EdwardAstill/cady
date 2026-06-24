# Ideal New API Architecture

## Purpose

Replace the current public object model with a clean API where geometry,
drawings, product structure, viewing, and evaluated mesh data are separate
concepts. Do not preserve legacy names or compatibility shims.

## Inputs

- Author-created 2D geometry: curves, closed curves, profiles, and drawings.
- Author-created 3D geometry: faces, bodies, parts, and assemblies.
- Imported DXF files.
- Optional document-level metadata such as units, title, author, and named
  object registries.
- Optional viewing state: camera, lights, visibility, section/exploded/display
  overrides.

## Outputs

- `Drawing2D` objects from 2D DXF content.
- `Mesh3D` objects from DXF content where mesh-like geometry is present.
- STL from `Mesh3D`, `Body3D`, `Part`, or `Assembly`.
- STEP from supported `Body3D`, `Part`, or flattened `Assembly` geometry.
- DXF from `Drawing2D`.
- Viewable scenes from `Drawing2D`, `Body3D`, `Part`, `Assembly`, or `Mesh3D`.

## Invariants

- Domain objects are immutable frozen dataclasses.
- Geometry authoring objects remain semantic until an explicit evaluation
  boundary.
- Every tessellation/export/evaluation path accepts `tolerance` explicitly.
- Domain and view value objects stay import-light: no matplotlib, pyvista, or
  other backend imports at module scope.
- `cady.numeric` must not import `cady.domain`.
- Geometry operations accept numeric primitives/arrays, not domain objects.
- File readers/writers and visualisation adapters depend inward on domain and
  numeric objects; domain objects do not depend on file formats or backends.
- No backwards compatibility layer is required for the old `Model`, `Shape2D`,
  `Shape3D`, `Prism`, `Sphere`, `Extrusion`, or `DxfDrawing` API if a cleaner
  replacement exists.

## Core Concepts

### 2D Geometry

`Curve2D` is open geometry: `Line2D`, `Arc2D`, `Spline2D`, `Polyline2D`.

`ClosedCurve2D` is boundary geometry: `Circle2D`, `Ellipse2D`,
`ClosedPolyline2D`.

`Profile2D` is a filled region:

```text
Profile2D
  outer -> ClosedCurve2D
  holes -> tuple[ClosedCurve2D, ...]
```

Profiles are the source for fills, hatches, extrusions, and placed faces.
Convenience shapes such as rectangles are factories, not core shape classes.

### Drawings

`Drawing2D` is a first-class document object for 2D CAD sheets and DXF output.
It is not just a list of curves and it does not require a `Document`.

```text
Drawing2D
  name
  units
  layers -> tuple[Layer, ...]
  entities -> tuple[DrawingEntity, ...]
  blocks -> tuple[BlockDefinition, ...]
  dim_styles -> tuple[DimStyle, ...]
  metadata
```

Drawing entities wrap geometry with drafting metadata:

```text
DrawingEntity
  geometry -> Curve2D | ClosedCurve2D | Profile2D
  layer -> str
  style/display attributes

Text2D, Hatch2D, Insert2D, Dimension2D
```

DXF import rules:

- purely 2D drafting entities become `Drawing2D`;
- mesh/polyface/3D face content may become `Mesh3D`;
- future work may promote recognised 2D profiles into `Profile2D` and recognised
  3D DXF content into `Body3D` or `Assembly`, but this is not required first.

### 3D Geometry

`Frame3D` places local 2D coordinates into 3D space.

`Face3D` is a `Profile2D` placed in a `Frame3D`.

`Body3D` is editable solid geometry. It owns feature history and evaluates to a
boundary representation or mesh when needed.

```text
Body3D
  name
  features -> tuple[Feature, ...]
  metadata
```

Supported first-pass features:

- `ExtrudeFeature(profile, frame, distance)`;
- `RevolveFeature(profile_or_face, axis, angle)`;
- primitive feature factories for box/cylinder/cone/sphere where feasible;
- booleans can be planned but may be deferred if the backend is not ready.

### Product Structure

`Part` is one manufacturable item.

```text
Part
  name
  bodies -> tuple[Body3D, ...]
  material
  display_style
  metadata
```

Multiple bodies are allowed in a part when they represent one item. Separate
items belong in an assembly.

`Assembly` is a tree of placed `Part` and `Assembly` instances.

```text
Assembly
  name
  instances -> tuple[PartInstance | AssemblyInstance, ...]
  metadata

PartInstance
  name
  part -> Part
  pose -> Pose3D
  metadata

AssemblyInstance
  name
  assembly -> Assembly
  pose -> Pose3D
  metadata
```

Assemblies do not merge geometry. Boolean operations create a new `Body3D`.

### Viewing

`Scene` is view/presentation state. It never owns the authoritative CAD model.

```text
Scene
  name
  objects -> tuple[SceneObject, ...]
  cameras -> tuple[Camera, ...]
  active_camera -> str | None
  lights -> tuple[Light, ...]
  display defaults
  metadata

SceneObject
  name
  target -> Drawing2D | Body3D | Part | Assembly | Mesh3D
  pose -> Pose3D
  visible -> bool
  display_style -> DisplayStyle | None
```

`Camera` and `Light` live in `cady.view` as backend-independent frozen value
objects. Visualisation adapters translate them into matplotlib/pyvista state.

### Document

`Document` is optional project-level organisation:

```text
Document
  name
  units
  drawings -> tuple[Drawing2D, ...]
  parts -> tuple[Part, ...]
  assemblies -> tuple[Assembly, ...]
  scenes -> tuple[Scene, ...]
  metadata
```

Users should not need `Document` to create, export, import, or view a single
drawing, body, part, assembly, mesh, or scene.

## Module Boundaries

```text
cady.geometry2d    2D curves, profiles, drawing geometry values
cady.geometry3d    frames, faces, bodies, shells, features, meshes
cady.drawing       Drawing2D, layers, blocks, hatches, dimensions
cady.product       Part, Assembly, instances, materials
cady.view          Scene, SceneObject, Camera, Light, DisplayStyle
cady.document      optional Document registry
cady.numeric       arrays, transforms, validation, evaluated geometry
cady.ops           numeric algorithms and evaluation helpers
cady.files         dxf/stl/step readers and writers
cady.visualisation optional backend adapters
```

Dependency direction:

```text
geometry2d, geometry3d, drawing, product, view, document
  -> numeric only at explicit evaluation boundaries
ops -> numeric
files -> domain/view/numeric/ops
visualisation -> domain/view/numeric/ops
```

## Error Strategy

- `CadError`: base package error.
- `GeometryError`: invalid curve/profile/body construction.
- `DrawingError`: invalid layers, blocks, dimensions, or drawing composition.
- `ProductError`: invalid part/assembly structure or cycles.
- `ViewError`: invalid camera, light, scene object, or active camera reference.
- `ReadError`: file import failures.
- `WriteError`: file export failures.

## First Implementation Scope

- Clean public API and file structure.
- Direct authoring of curves, profiles, drawings, bodies, parts, assemblies,
  scenes, cameras, and lights.
- DXF read to `Drawing2D` for 2D content.
- DXF read to `Mesh3D` for mesh-like content.
- DXF write from `Drawing2D`.
- STL write from `Mesh3D`, `Body3D`, `Part`, and flattened `Assembly`.
- STEP write from supported bodies/parts and flattened assemblies where current
  STEP support allows.
- Optional visualisation consumes `Scene` plus direct objects by wrapping direct
  objects in a default scene.
