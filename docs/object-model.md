# Object model

cady's authoring objects are immutable values. Methods that change placement,
topology, or feature history return new objects. Numeric arrays and triangle
meshes are explicit conversion boundaries, and sampling or meshing APIs take a
keyword-only `tolerance`.

## Choosing the main value

Use the value that owns the behavior you need:

| Value | Role |
|---|---|
| Geometry values | Curves, regions, surfaces, meshes, wireframes, and point clouds. |
| `Body3` | One generated solid and its feature history. |
| `Drawing2` | A layered 2D drafting document. |
| `Part` | One named item made from one or more independent bodies. |
| `Assembly` | Positioned parts and nested assemblies. |
| `Scene` | Camera, lighting, style, pose, and viewing state. |
| `Document` | An optional registry tying related drawings, products, and scenes together. |

There is no required top-level model object. File writers and viewers accept
the relevant direct object.

## Coordinates

`Point2` and `Point3` are public immutable position values. `Vector2` and
`Vector3` are public immutable direction and displacement values. Geometry
constructors accept coordinate sequences and normalize semantic fields to the
appropriate point or vector type:

```python
from cady import Line3, Point3, Vector3

start = Point3(1.0, 2.0, 3.0)
offset = Vector3(0.0, 0.0, 2.0)
end = start + offset
line = Line3(start, end)
```

Point subtraction produces a vector, while adding or subtracting a vector from
a point produces a point. Tuple-style coordinate inputs remain convenient at
construction boundaries.

## 2D geometry

Curves include `Line2`, `Arc2`, `Spline2`, `Polyline2`, `Circle2`, and
`Ellipse2`. They expose geometry queries such as `bounds()`, `boundary`,
`points()`, and `length`. Lines and closed conics convert directly with
`to_array(tolerance=...)`; arcs and splines first use
`discretize(tolerance=...)` to produce a polyline.

`Polyline2` can be open or closed. Only closed `Polyline2` values can produce a
`Mesh2` with `to_mesh(tolerance=...)`.

`Region2` is a filled planar area with one closed outer loop and optional closed
holes. It stays semantic until `loops(tolerance=...)` or `to_array(tolerance=...)`
samples the boundary curves.

```python
from cady import Circle2, Polyline2, Region2

outline = Polyline2(
    ((0.0, 0.0), (1.0, 0.0), (1.0, 0.6), (0.0, 0.6)),
    closed=True,
)
mesh = outline.to_mesh(tolerance=1e-3)

plate = Region2.rectangle(1.0, 0.6)
hole = Circle2((0.5, 0.3), 0.12)
region = Region2(plate.outer, holes=(hole,))
loops = region.loops(tolerance=1e-3)
```

## 3D geometry

`Plane3` is the placement frame for planar work. It stores an origin, an
orthonormal x-axis, and a normal; `y_axis` is derived to keep the frame
right-handed. `Surface2` and `Surface3` are parametric surfaces, and `Region3`
places a 2D parameter region on a `Surface3`.

```python
from cady import Plane3, Region2, Region3, Surface3

plane = Plane3.from_normal(
    origin=(0.0, 0.0, 5.0),
    normal=(0.0, 0.0, 1.0),
)
point = plane.point(0.5, 0.3)

surface = Surface3.plane(plane=plane)
patch = Region3.from_region(Region2.rectangle(1.0, 0.6), surface=surface)
mesh = patch.to_mesh(tolerance=1e-3)
```

3D curves include `Line3`, `Arc3`, `Spline3`, and `Polyline3`. `Polyline3` can
store straight vertices or curve objects implementing the `Curve3` protocol.
Closed `Polyline3` values are meshable only when their sampled loop is planar
within the supplied tolerance.

## Meshes, Wireframes, And Points

`Mesh2` and `Mesh3` are indexed triangle meshes. They store `vertices`, `faces`,
and optional display `edges`. `triangles` expands face indices into point
triples, and `boundary_loops` derives open boundaries from face topology.

`Wireframe3` is edge-only 3D topology. It stores connected lines, can split
crossing edges, prune dangling branches, triangulate closed loops, and convert
to `Mesh3` with `to_mesh(tolerance=...)`.

`PointCloud2` and `PointCloud3` are unconnected point collections. They are not
curves, wireframes, or meshes until another operation explicitly constructs that
topology.

`Transform2` and `Transform3` live in `cady.operations`. They are immutable,
chainable transforms for translation, rotation, scaling, mirroring, composition,
and array conversion. Geometry types that support placement expose methods such
as `transformed(...)` or accept a transform-like pose at a product or scene
boundary.

## Bodies And Products

`Body3` is the immutable history of one generated solid followed by ordered
modifiers. Meshable generators currently include region extrusion and primitive
bodies such as boxes, cylinders, and spheres. A second independent generator
does not belong in the same `Body3`; use `Part.with_bodies(...)` to compose
independent solids. Recorded features without evaluators raise explicitly when
mesh conversion reaches them.

```python
from cady import Body3, Part, Region2

profile = Region2.rectangle(1.0, 0.6)
body = Body3.from_region(profile).extrude(0.04)
mesh = body.to_mesh(tolerance=1e-3)

box_body = Body3.box(width=1.0, depth=0.6, height=0.04)
cylinder_body = Body3.cylinder(radius=0.5, height=2.0)
part = Part("two solids").with_bodies(box_body, cylinder_body)
```

`Part` groups one or more independent bodies into a named manufacturable item;
`Assembly` places parts or subassemblies, and `Document` optionally registers
those objects. File writers and view preparation convert at the edge of the
system.

The main product methods follow the immutable pattern:

- `Part.with_body(...)` and `Part.with_bodies(...)` add independent solids.
- `Part.with_material(...)` and `Part.with_metadata(...)` add descriptive data.
- `Assembly.add_part(...)` and `Assembly.add_assembly(...)` add positioned
  instances.
- `Assembly.flatten()` resolves the hierarchy into placed parts.
- `Part.to_mesh(...)` and `Assembly.to_mesh(...)` convert at a chosen tolerance.

## Drawings

`Drawing2` owns layers, drawing entities, blocks, dimension styles, headers, and
metadata. `add_layer(...)`, `add(...)`, `add_entity(...)`, `add_block(...)`, and
`add_dimension(...)` return updated drawings. `bounds()` measures the document,
while `to_arrays(tolerance=...)` performs numeric conversion.

```python
from cady import Drawing2, Line2, Text2

drawing = (
    Drawing2("profile")
    .add_layer("OUTLINE")
    .add(Line2((0.0, 0.0), (1.0, 0.0)), layer="OUTLINE")
    .add_entity(Text2("PROFILE", at=(0.0, 0.1), height=0.05))
)
```

## Scenes

`Scene` stores semantic targets rather than sampled arrays. `add(...)` attaches
a target with optional pose and style, `with_overlay(...)` adds view aids, and
`view(tolerance=...)` opens the optional viewer. For backend-independent use,
`cady.view.prepare_scene(...)` converts the scene to `RenderScene` data.

Supported curves are sampled during preparation, not when added. Meshable
targets are meshed at the same boundary, so changing the tolerance does not
change the source scene.

## Documents

`Document` is useful when related drawings, parts, assemblies, and scenes need
one named registry. Use `add_drawing(...)`, `add_part(...)`,
`add_assembly(...)`, and `add_scene(...)` to build it. `get(kind, name)` and
`names(kind)` provide lookup without changing the stored values.
