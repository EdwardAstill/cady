# Object model

cady's authoring objects are immutable values. Methods that change placement,
topology, or feature history return new objects. Numeric arrays and triangle
meshes are explicit conversion boundaries, and sampling or meshing APIs take a
keyword-only `tolerance`.

## Coordinates

Geometry values store coordinates as plain point tuples:

```python
point2 = (1.0, 2.0)
point3 = (1.0, 2.0, 3.0)
```

There is no public `Vec2` or `Vec3` value type. Use tuples for construction and
the helpers in `cady.operations.coordinates` when operation code needs vector
arithmetic.

## 2D geometry

Curves include `Line2`, `Arc2`, `Spline2`, `Polyline2`, `Circle2`, and
`Ellipse2`. They expose cheap geometry queries such as `bounds()`, `boundary`,
and `points()`, and convert to point arrays with `to_array(tolerance=...)`.

`Polyline2` can be open or closed. Only closed `Polyline2` values can produce a
`Mesh2` with `to_mesh(tolerance=...)`.

`Region2` is a filled planar area with one closed outer loop and optional closed
holes. It stays semantic until `loops(tolerance=...)` or `to_array(tolerance=...)`
samples the boundary curves.

```python
from cady import Polyline2, Region2, circle2, region_rectangle

outline = Polyline2(
    ((0.0, 0.0), (1.0, 0.0), (1.0, 0.6), (0.0, 0.6)),
    closed=True,
)
mesh = outline.to_mesh(tolerance=1e-3)

plate = region_rectangle(1.0, 0.6)
hole = circle2((0.5, 0.3), 0.12)
region = Region2(plate.outer, holes=(hole,))
loops = region.loops(tolerance=1e-3)
```

## 3D geometry

`Plane3` is the placement frame for planar work. It stores an origin, an
orthonormal x-axis, and a normal; `y_axis` is derived to keep the frame
right-handed. `Surface2` and `Surface3` are parametric surfaces, and `Region3`
places a 2D parameter region on a `Surface3`.

```python
from cady import Plane3, Region3, Surface3, region_rectangle

plane = Plane3.from_normal(
    origin=(0.0, 0.0, 5.0),
    normal=(0.0, 0.0, 1.0),
)
point = plane.point(0.5, 0.3)

surface = Surface3.plane(plane=plane)
patch = Region3.from_region(region_rectangle(1.0, 0.6), surface=surface)
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

## Bodies And Products

`Body3` is a semantic feature-history body. Meshable paths currently include
region extrusion and primitive bodies such as boxes, cylinders, and spheres.
Unsupported features such as revolve, boolean, fillet, and chamfer can stay in
history until evaluators exist.

```python
from cady import Body3, box, cylinder, region_rectangle

profile = region_rectangle(1.0, 0.6)
body = Body3.from_region(profile).extrude(0.04)
mesh = body.to_mesh(tolerance=1e-3)

box_body = box(width=1.0, depth=0.6, height=0.04)
cylinder_body = cylinder(radius=0.5, height=2.0)
```

`Part`, `Assembly`, and `Document` group geometry without changing the geometry
boundary model. File writers and view preparation convert at the edge of the
system.
