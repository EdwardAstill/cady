# cady

Small CAD package for building format-blind geometry, emitting DXF R2018,
binary/ASCII STL, or AP214 STEP, and extracting elementary surface data from
STEP files.

cady has the staged v1 feature set:

- immutable 2D and 3D geometry values,
- DXF writer for `LINE`, `LWPOLYLINE`, `CIRCLE`, `ARC`, `MTEXT`,
- limited ASCII DXF reader for basic 2D geometry and faceted 3D meshes,
- production DXF helpers for `HATCH`, `BLOCK`, `INSERT`, and built-in
  linetypes,
- native editable DXF dimensions and hatch holes/islands,
- binary and ASCII STL writer,
- AP214 STEP writer for `Prism` and supported `Extrusion` solids,
- STEP reader helpers for elementary surfaces and simple extruded-member
  reconstruction,
- model layer for named drawings, parts, assemblies, and metadata,
- end-to-end plate examples for DXF and STEP.

## Quickstart

```python
from cady import Model, circle, rectangle

profile = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))

model = Model("plate")
model.drawing("front").layer("PLATE", color=7).add(profile)
model.drawing("front").add_text("PLATE", at=(0.02, 0.02), height=0.03, layer="TEXT")
model.part("plate").add(profile.extrude("+z", 0.04))

model.write_dxf("plate.dxf")
model.write_stl("plate.stl")
```

Run the model-first example:

```bash
PYTHONPATH=src python examples/scripts/model_plate.py
```

This writes:

- `examples/gallery/model_plate.dxf`
- `examples/gallery/model_plate.stl`

Run the production DXF example:

```bash
PYTHONPATH=src python examples/scripts/production_dxf.py
```

This writes `examples/gallery/production_plate.dxf` with hatching, hatch holes,
centerlines, dimensions, a reusable block, and two inserts. Pass `--out <dir>`
to any example script to write somewhere else.

Run the STEP example:

```bash
PYTHONPATH=src python examples/scripts/production_step.py
```

This writes `examples/gallery/production_plate.step` — a two-part model (plate
and pin stud) as a viewer-loadable AP214 STEP file.

## How It Works

cady has a small native geometry model. You create cady objects such as
`Line`, `Circle`, `Rectangle`, `Polyline`, `Prism`, and `Extrusion`, attach
them to a `Model`, then writers serialize that model directly to CAD file
formats. There is no hidden OpenCASCADE-style kernel or intermediate generic
CAD object graph.

The model layer separates 2D drawings from 3D parts:

- drawings contain 2D shapes, text, hatch, blocks, inserts, and dimensions,
- parts contain 3D solids,
- assemblies group named parts.

Export is direct: DXF walks drawing entities, STL tessellates 3D solids into
triangles, and STEP emits supported B-rep solids from cady-native shapes.

STEP import is analysis-only. `cady.files.step.read_faces` parses STEP into
lightweight `StepFace` records for elementary surfaces, and
`cady.files.step.read_members` can infer simple extruded structural members
from those faces. It does not rebuild arbitrary STEP assemblies into editable
cady `Model`, `Part`, or solid objects.

The source split is:

- `cady.domain`: native cady objects: vectors, 2D shapes, 3D shapes,
  drawing objects, meshes, models, parts, and assemblies,
- `cady.build`: factory and builder functions for constructing domain objects,
- `cady.ops`: geometry algorithms such as profile helpers, transforms,
  tessellation, and triangulation,
- `cady.files`: DXF, STL, and STEP file reading/writing modules.

The old `geom`, `model`, `scene`, `write`, `read`, `exporters`, and
`importers` source packages have been removed; import from the split above or
from the top-level `cady` API.

## Semantic vs Numeric Geometry

cady keeps CAD authoring objects semantic. Shapes such as `Circle`,
`Rectangle`, `Spline`, `Extrusion`, `Part`, and `Model` preserve design intent,
holes, layers, metadata, and file-format meaning. Use them when you are
building or editing geometry, writing DXF/STL/STEP files, or keeping a model
readable.

The planned numeric layer sits beside those objects for evaluated geometry:
NumPy-backed polylines, polygons, splines, meshes, and transforms. Domain
objects convert explicitly at calculation boundaries:

```python
from cady import rectangle

profile = rectangle((0, 0), (1.0, 0.6))
array_profile = profile.to_array(tolerance=1e-3)
```

For 3D work, `Shape3D.to_array(...)`, `Part.to_array(...)`, and
`Model.to_array(...)` return `ArrayMesh3` values or lists of meshes:

```python
from cady import circle, rectangle

plate = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))
mesh = plate.extrude("+z", 0.04).to_array(tolerance=1e-3)
```

Splines remain analytic in the numeric layer as `ArrayBezierSpline2` control
points. They are only discretised when you call an explicit sampling,
tessellation, export, or visualisation function.

Detailed references:

- [Domain objects](docs/objects/domain-objects.md)
- [Numeric objects](docs/objects/numeric-objects.md)

## Layer Boundaries

The target dependency direction is:

```text
domain object.to_array(...) -> ops primitive function -> numeric result
visualisation -> domain/numeric
```

`cady.domain` owns semantic objects and should stay import-light. Domain
`to_array(...)` methods unpack object properties such as centres, radii,
control points, axes, distances, and tolerances, then call `cady.ops` with
primitive values.

`cady.ops` owns object-agnostic algorithms. Ops functions accept NumPy arrays,
array-like lists/tuples, and scalars; they may use NumPy internally, but they
do not import or inspect domain objects.

```python
# ops-level call shape
points = sample_circle_points((0.5, 0.3), radius=0.12, tolerance=1e-3)

# domain-level adaptation
polyline = circle((0.5, 0.3), 0.12).to_array(tolerance=1e-3)
```

`cady.numeric` owns validated arrays and matrix transforms. For bulk mesh
work, use row-vector arrays and `Transform3`:

```python
from cady.numeric import Transform3

rotated = mesh.transformed(
    Transform3.rotation((0, 0, 0), (0, 0, 1), 1.5707963267948966)
)
```

More detail:

- [Array operations](docs/operations/array-ops.md)
- [Tessellation](docs/operations/tessellation.md)

## Plotting And Visualisation

Static plotting lives in the optional `cady.plotting` package. Interactive
viewing lives in `cady.visualisation`. Both depend on the semantic and numeric
layers, while core cady imports do not require viewer libraries.

Install `cady[plotting]` for Matplotlib plots and `cady[visualisation]` for
the interactive VisPy viewer.

2D plotting returns the Matplotlib figure/axis so callers can customise or
save output:

```python
from cady import circle, rectangle
from cady.plotting import plot_shape2d

profile = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))
fig, ax = plot_shape2d(profile, tolerance=1e-3, save_path="plate-profile.png")
```

3D viewing accepts semantic solids, models, or numeric meshes:

```python
from cady import circle, rectangle
from cady.visualisation import view_shape3d

profile = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))
view_shape3d(profile.extrude("+z", 0.04), tolerance=1e-3, backend="matplotlib")
```

The example command is:

```bash
PYTHONPATH=src python examples/scripts/visualise_plate.py --out /tmp/cady-visualisation
```

See [visualisation docs](docs/visualisation.md) for backend and saving
behaviour.

## Current API

Geometry factories:

```python
from cady import arc, circle, line, polyline, prism, rectangle, sphere, spline
```

2D shapes:

- `Line`
- `Arc`
- `Circle`
- `Rectangle`
- `Polyline`
- `Spline`
- `Path`

3D shapes:

- `Sphere`
- `Prism`
- `Extrusion`
- `Revolution`

Scenes and writers:

```python
from cady import Assembly, Drawing2D, DxfDrawing, Model, Part, StlMesh
```

Use `Model` as the preferred organizing layer for named drawings and parts.
Use `DxfDrawing` and `StlMesh` directly for low-level or single-format output.

File API:

```python
from cady.files import dxf, step

drawing = dxf.read_drawing("profile.dxf")
mesh = dxf.read_mesh("faceted-part.dxf")
import_result = dxf.read_3d("mixed-3d.dxf")
faces = step.read_faces("frame.step")
members = step.read_members("frame.step")
```

`dxf.read_drawing` imports supported ASCII DXF `ENTITIES` into a `DxfDrawing`.
The initial reader covers `LINE`, `LWPOLYLINE`, `CIRCLE`, `ARC`, `TEXT`, and
`MTEXT`, preserving layer names and cady-supported layer colors/linetypes.
Unsupported 2D drawing entities such as hatches, blocks, inserts, and
dimensions are skipped.

`dxf.read_mesh` imports supported faceted 3D ASCII DXF entities into a
`FacetedMesh`. It currently supports `3DFACE` triangles/quads and polyface
`POLYLINE`/`VERTEX` meshes. `dxf.read_3d` returns meshes, 3D wire polylines,
and skipped-entity records for inspection. ACIS-backed entities such as
`3DSOLID`, `BODY`, `REGION`, and `SURFACE` are reported as skipped; cady does
not parse their embedded solid-kernel data.

`step.read_faces` resolves elementary `PLANE`, `CYLINDRICAL_SURFACE`, and
`CONICAL_SURFACE` faces from AP203/AP214-style STEP files. It is intended for
simple extrusion analysis, not full CAD-kernel import.

Production DXF features:

```python
from cady import Model, circle, line, rectangle

outline = rectangle((0, 0), (1.0, 0.6))
hole = circle((0.5, 0.3), 0.12)
profile = outline.with_hole(hole)

model = Model("production_plate")
front = model.drawing("front")
front.layer("PLATE").add(outline).add(hole)
front.layer("SECTION").hatch(profile, pattern="ANSI31", scale=0.025)
front.layer("CENTER", linetype="CENTER").add(line((0.5, 0.05), (0.5, 0.55)))
front.block("PIN_MARK").layer("SYMBOL").add(circle((0, 0), 0.025))
front.insert("PIN_MARK", at=(0.5, 0.3), layer="SYMBOL")
front.linear_dimension((0, 0), (1.0, 0), offset=-0.08)
front.diameter_dimension((0.5, 0.3), 0.12)
model.write_dxf("production_plate.dxf")
```

Dimensions are emitted as native DXF `DIMENSION` entities with compact anonymous
dimension blocks, so CAD viewers can treat them as dimension objects instead of
plain lines and text.

## Model API

Use one source model to export DXF, STL, and STEP:

```python
from cady import Model, circle, rectangle

plate = rectangle((0, 0), (1.0, 0.6)).with_hole(circle((0.5, 0.3), 0.12))

model = Model("padeye_plate")
model.drawing("front").layer("PLATE").add(plate)
model.part("plate").add(plate.extrude("+z", 0.04))

model.write_dxf("padeye_plate.dxf")
model.write_stl("padeye_plate.stl")
model.write_step("padeye_plate.step")
```

`write_dxf`, `write_stl`, and `write_step` are all implemented as object-level
convenience methods. The same file operations are also available through
`cady.files.dxf`, `cady.files.stl`, and `cady.files.step`. STEP export currently
supports `Prism` and `Extrusion` solids. `Revolution` and `Sphere` are not
supported by STEP export yet.

## Roadmap

Current sequence:

1. Stage 1: geometry, DXF basics, STL — implemented
2. Stage 2: `cady.domain` layer — implemented
3. Stage 3: production DXF: HATCH, BLOCK, INSERT, linetypes — implemented
4. Stage 4: dimensions and drawing helpers — implemented
5. Stage 4.6: DXF writer hardening — implemented
6. Stage 5: STEP MVP — implemented
7. Stage 6: v1 product hardening — implemented

## Viewer Support

| Format | Tested tool | Notes |
|--------|-------------|-------|
| DXF R2018 | `ezdxf` (CI) | Zero audit errors on production example. Compatible with FreeCAD, LibreCAD, and any AC1032-capable viewer. |
| STL binary | Any mesh viewer | FreeCAD, Blender, MeshLab, browser-based viewers. |
| STEP AP214 | FreeCAD (manual) | File loads as a multi-body solid. `Prism` and supported `Extrusion` solids are exported. |

## Development

Create a dev environment:

```bash
python -m venv .venv
.venv/bin/pip install -e . -r requirements-dev.txt
```

Run gates:

```bash
.venv/bin/pytest -q
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
```

cady uses `steputils` at runtime for STEP parsing. Dev tools live in
`requirements-dev.txt`.

## Boundaries

- DXF/STL/STEP writers should stay small and dependency-light.
- cady parses limited 2D and faceted 3D ASCII DXF subsets, not arbitrary DXF
  drawings or ACIS-backed DXF solids. It does not parse STL. STEP read support
  is limited to elementary surfaces and structural-member extraction helpers.
- cady is domain-blind. It does not contain `Padeye`, `Shackle`, or other
  lifting-gear objects.
- Domain recipes belong in pyseas-yard or examples.
