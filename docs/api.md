# Main objects and methods

The top-level `cady` package exports the values used for ordinary authoring.
Algorithmic helpers and file formats stay in focused subpackages such as
`cady.operations`, `cady.measurement`, and `cady.files`.

Most cady objects are immutable. A method named `add(...)`, `with_...(...)`, or
`transformed(...)` returns a new value. Methods that sample a curve or create a
mesh take an explicit keyword-only `tolerance`.

## Choosing an object

| Need | Main object |
|---|---|
| A position or displacement | `Point2`, `Point3`, `Vector2`, `Vector3` |
| A line, arc, spline, or path | `Line2`, `Line3`, `Arc2`, `Arc3`, `Spline2`, `Spline3`, `Polyline2`, `Polyline3` |
| A filled planar profile | `Region2` |
| A plane or parametric surface in 3D | `Plane3`, `Surface3`, `Region3` |
| Triangle or edge topology | `Mesh2`, `Mesh3`, `Wireframe3` |
| Unconnected samples | `PointCloud2`, `PointCloud3` |
| One generated solid | `Body3` |
| A 2D drafting document | `Drawing2` |
| A named item made from bodies | `Part` |
| Positioned parts and subassemblies | `Assembly` |
| Viewer state | `Scene` |
| A registry of related artefacts | `Document` |

## Coordinates and curves

`Point2` and `Point3` represent positions. `Vector2` and `Vector3` represent
directions or displacements. Points support affine arithmetic with vectors;
vectors provide `length`, `normalized()`, `dot(...)`, scaling, and vector
arithmetic. `Vector3` also provides `cross(...)`.

Geometry constructors accept coordinate sequences as well as point values:

```python
from cady import Line3, Point3, Vector3

start = Point3(1.0, 2.0, 3.0)
end = start + Vector3(0.0, 0.0, 2.0)
line = Line3(start, end)
```

The curve classes share a small vocabulary:

| Objects | Important methods and properties |
|---|---|
| `Line2`, `Line3` | `bounds()`, `points()`, `length`, `to_array(tolerance=...)` |
| `Arc2`, `Arc3` | `bounds()`, `points()`, `length`, `reverse()`, `discretize(tolerance=...)` |
| `Spline2`, `Spline3` | `bounds()`, `points()`, `length`, `discretize(tolerance=...)` |
| `Polyline2`, `Polyline3` | `from_curves(...)`, `bounds()`, `points()`, `length`, `reverse()`, `discretize(...)`, `to_array(...)` |
| `Circle2`, `Ellipse2` | `bounds()`, `points()`, `length`, `to_array(tolerance=...)` |

`Polyline2` and `Polyline3` may be open or closed. A closed polyline can use
`to_mesh(tolerance=...)` when it defines a valid planar boundary.

## Regions, planes, and surfaces

`Region2` represents a filled outer loop with optional holes. Use
`Region2.rectangle(...)` or `Region2.circle(...)` for common profiles,
`loops(tolerance=...)` to sample every boundary, and
`to_array(tolerance=...)` to sample the outer boundary.

`Plane3` is a local 3D frame. Its main constructors are `world_xy()`,
`from_normal(...)`, and `fit(...)`. Use `point(u, v)` and `coordinates(point)`
to move between local and world coordinates, `project(...)` for projection,
and `transformed(...)` to place a plane with a `Transform3`.

`Surface2` and `Surface3` describe parametric surfaces. Their `plane(...)` and
`parametric(...)` constructors create surfaces, while `point(u, v)` evaluates
them. `Surface3.normal(u, v)` evaluates a surface normal. `Region3` places a 2D
region on a surface and converts it with `to_mesh(tolerance=...)`.

## Meshes, wireframes, and point clouds

| Object | Purpose | Important methods and properties |
|---|---|---|
| `Mesh2`, `Mesh3` | Indexed triangle topology | `merged(...)`, `bounds()`, `triangles`, `area`, `boundary_loops`, `to_array(...)`, `transformed(...)` |
| `Mesh3` | 3D mesh analysis and editing | `volume`, `closed`, `triangulate(...)`, `decimate(...)`, `remesh(...)`, `to_wireframe()`, `view(...)` |
| `Wireframe3` | Indexed edges without faces | `from_polylines(...)`, `from_edges(...)`, `bounds()`, `to_mesh(...)`, `transformed(...)`, `view(...)` |
| `PointCloud2`, `PointCloud3` | Unconnected point samples | `bounds()`, `points()`, `to_array(...)`, `transformed(...)`, `mirror(...)` |

## Bodies and products

`Body3` describes one generated solid. Create a primitive with `box(...)`,
`cylinder(...)`, or `sphere(...)`, or create an extrusion with
`from_region(...).extrude(...)`. Use `transformed(...)` for placement,
`to_mesh(tolerance=...)` for conversion, and `view(...)` for the optional
interactive viewer.

```python
from cady import Body3, Part, Region2

profile = Region2.rectangle(1.0, 0.6)
plate = Body3.from_region(profile).extrude(0.04)
pin = Body3.cylinder(radius=0.05, height=0.12)
part = Part("plate and pin").with_bodies(plate, pin)
```

A `Body3` has one solid generator. Use `Part.with_bodies(...)` for independent
solids rather than placing multiple generators in one body.

`Part` is a named manufacturable item. Its main methods are `with_body(...)`,
`with_bodies(...)`, `with_material(...)`, `with_metadata(...)`,
`to_mesh(tolerance=...)`, and `view(...)`.

`Assembly` contains positioned part or assembly instances. Use
`add_part(...)`, `add_assembly(...)`, and `with_metadata(...)` to build it;
`flatten()` resolves the hierarchy and `to_mesh(tolerance=...)` converts the
placed result.

## Drawings

`Drawing2` is a named 2D drafting document containing layers and entities.

| Method | Purpose |
|---|---|
| `add_layer(...)` | Add or reuse a layer definition. |
| `add(geometry, layer=...)` | Wrap geometry as a drawing entity. |
| `add_entity(...)` | Add text, hatches, inserts, dimensions, or an existing entity. |
| `add_block(...)`, `insert(...)` | Define and place reusable blocks. |
| `with_dim_style(...)`, `add_dimension(...)` | Configure and add dimensions. |
| `with_header(...)`, `with_metadata(...)` | Return a drawing with updated descriptive data. |
| `bounds()` | Return bounds covering the drawing entities. |
| `to_arrays(tolerance=...)` | Convert supported drawing geometry at an explicit boundary. |

## Scenes and viewing

`Scene` stores targets together with a camera, lights, display styles, poses,
and overlays. `add(...)`, `add_object(...)`, `with_overlay(...)`, and
`with_metadata(...)` return updated scenes. `Scene.view(...)` opens the optional
viewer.

`prepare_scene(...)` is the backend-independent conversion boundary:

```python
from cady import Circle2, Scene
from cady.view import prepare_scene

circle = Circle2((0.0, 0.0), 1.0)
scene = Scene("profile").add(circle, name="outline")
render_scene = prepare_scene(scene, tolerance=1e-3)
```

Scenes keep their targets semantic. Preparation samples supported curves,
lifts 2D curves onto `z = 0`, applies object poses, and converts meshable
targets into render data. `Camera.look_at(...)`, `perspective(...)`, and
`orthographic(...)` create camera values; `DisplayStyle` controls color,
visibility, and render mode.

## Documents

`Document` is optional. It is an immutable registry for named drawings, parts,
assemblies, and scenes. Use `add_drawing(...)`, `add_part(...)`,
`add_assembly(...)`, or `add_scene(...)`, then retrieve entries with
`get(kind, name)` or list them with `names(kind)`.

## Operations, measurements, and files

`cady.operations` exposes `Transform2`, `Transform3`, triangulation, and focused
mesh helpers. Transforms are chainable values with methods such as
`translate(...)`, `rotate(...)`, `scale(...)`, `mirror(...)`, `compose(...)`,
`inverse()`, and `apply_points(...)`.

`cady.measurement.distance(...)` and `intersection(...)` perform object-level
geometric queries.

File facades live under `cady.files`:

| Facade | Main entry points |
|---|---|
| `dxf` | `read(...)`, `read_drawing(...)`, `read_mesh(...)`, `read_curves(...)`, `read_wireframe(...)`, `write(...)` |
| `stl` | `write(...)` for meshable 3D targets |
| `step` | `write(...)`, `read_mesh(...)`, `read_faces(...)`, `read_members(...)` |

Writers that sample or mesh data accept `tolerance=...`; pass it explicitly so
the conversion quality is visible at the file boundary.

## Errors

`CadError` is the shared error base. Public specialisations include
`GeometryError`, `DrawingError`, `ProductError`, `ViewError`, `ReadError`, and
`WriteError`.
