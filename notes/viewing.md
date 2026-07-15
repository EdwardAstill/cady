# Viewing

VisPy is the rendering backend, not the CAD model. Cady keeps objects semantic
until the viewing boundary, then converts them into arrays, camera values, and
lighting values that VisPy can pass to OpenGL.

```text
Cady object -> Scene -> prepare_scene(...) -> RenderScene -> VispyCanvas
```

`RenderScene` is not another authoring scene. It is the scene after Cady has
converted semantic objects into renderable arrays, camera values, lighting
values, and overlay values.

## What VisPy Needs

VisPy needs four groups of data:

- draw-batch data: the geometry to draw
- camera/projection data: where the viewer is looking from
- lighting data: how shaded surfaces should be coloured
- overlay data: screen-space information drawn over the rendered scene

A draw batch is one GPU draw call. It is not always the same as one Cady object:
one mesh object can become a face batch for shaded triangles and an edge batch
for outlines.

### Draw Batches

For each draw batch, VisPy needs geometry arrays.

| Data | Shape | Meaning |
|---|---:|---|
| vertex array | `(N, 3)` floats | The 3D point coordinates. Each row is one point: `x, y, z`. |
| face index array | `(F, 3)` integers | Triangle connectivity. Each row gives three vertex indices from the vertex array. |
| edge index array | `(E, 2)` integers | Line connectivity. Each row gives two vertex indices from the vertex array. |
| normal array | `(N, 3)` floats | Per-vertex surface directions used for shaded lighting. |
| color array | `(N, 3)` floats | Per-vertex RGB values passed into the shader. |

Index arrays avoid repeating point coordinates. The index values always refer to
rows in the vertex array for the same object or draw batch.

### Camera And Projection

For camera/projection, the viewer passes matrices and viewport state.

| Data | Shape | Meaning |
|---|---:|---|
| model matrix | `(4, 4)` floats | Moves object/local coordinates into the viewer's current orientation. |
| view matrix | `(4, 4)` floats | Represents camera distance and pan. |
| projection matrix | `(4, 4)` floats | Converts 3D view coordinates into screen clip space. |
| viewport size | `(width, height)` integers | The canvas pixel size, used for aspect ratio and resize handling. |
| near/far clip planes | scalars | Depth limits used when building the projection matrix. |

Cady stores camera intent as a `Camera`: `position`, `target`, `up`,
`projection`, field of view or orthographic scale, and near/far clipping planes.
The VisPy viewer turns that into the `u_model`, `u_view`, and `u_projection`
shader uniforms.

### Lighting

For lighting, the shader needs light values.

| Data | Shape | Meaning |
|---|---:|---|
| light direction | `(3,)` floats | Direction used to calculate diffuse shading from surface normals. |
| ambient light | `(3,)` floats | Base RGB light applied even when a face points away from the light. |
| diffuse light | `(3,)` floats | RGB light strength applied based on the face normal direction. |
| lighting flag | scalar | Enables shaded lighting for faces and disables it for flat lines/edges. |

Lighting uses the normal array. A face pointing toward the light is brighter; a
face pointing away keeps mostly the ambient light. Edges, polylines, and points
are drawn flat, so they do not need meaningful normals.

### Shader Inputs

VisPy's `gloo.Program` pairs the arrays with shader inputs.

| Shader input | Kind | Meaning |
|---|---|---|
| `a_position` | attribute | Per-vertex position from the vertex array. |
| `a_normal` | attribute | Per-vertex normal used by shaded faces. |
| `a_color` | attribute | Per-vertex RGB colour. |
| `u_model` | uniform | Current model/orientation matrix. |
| `u_view` | uniform | Current view/camera matrix. |
| `u_projection` | uniform | Current projection matrix. |
| `u_light_direction` | uniform | Directional light vector. |
| `u_ambient_light` | uniform | Ambient RGB light. |
| `u_diffuse_light` | uniform | Diffuse RGB light. |

Attributes change per vertex. Uniforms are shared across one draw call.

## Examples

### 2D Square In 3D Coordinates

VisPy can draw 2D data, but Cady's viewer represents even this square as 3D
points with `z = 0`.

```text
vertices = [
  (0, 0, 0),
  (1, 0, 0),
  (1, 1, 0),
  (0, 1, 0),
]

faces = [
  (0, 1, 2),
  (0, 2, 3),
]

edges = [
  (0, 1),
  (1, 2),
  (2, 3),
  (3, 0),
]
```

The face rows say: draw triangle `0-1-2`, then triangle `0-2-3`. The edge rows
say: draw four line segments around the boundary.

### 3D Cube

A cube has eight corner vertices. Its six square sides are usually sent to the
GPU as twelve triangles.

```text
vertices = [
  (0, 0, 0),  # 0
  (1, 0, 0),  # 1
  (1, 1, 0),  # 2
  (0, 1, 0),  # 3
  (0, 0, 1),  # 4
  (1, 0, 1),  # 5
  (1, 1, 1),  # 6
  (0, 1, 1),  # 7
]

faces = [
  (0, 1, 2), (0, 2, 3),  # bottom
  (4, 6, 5), (4, 7, 6),  # top
  (0, 4, 5), (0, 5, 1),  # front
  (1, 5, 6), (1, 6, 2),  # right
  (2, 6, 7), (2, 7, 3),  # back
  (3, 7, 4), (3, 4, 0),  # left
]

edges = [
  (0, 1), (1, 2), (2, 3), (3, 0),
  (4, 5), (5, 6), (6, 7), (7, 4),
  (0, 4), (1, 5), (2, 6), (3, 7),
]
```

The cube can be drawn as shaded faces, wireframe edges, or both. In shaded mode,
Cady also builds normals so the shader can light each face.

## Cady View API

The public API is deliberately higher-level than VisPy. Users create scenes from
Cady objects; the view layer handles conversion to render buffers.

```python
from cady import Camera, DirectionalLight, DisplayStyle, Scene, box
from cady.view import view_scene

part = box(1.0, 1.0, 1.0)
scene = (
    Scene(
        "box",
        camera=Camera.orthographic(
            position=(2.0, -2.0, 1.5),
            target=(0.0, 0.0, 0.0),
            scale=2.0,
        ),
        lights=(DirectionalLight(direction=(-1.0, -1.0, -2.0), intensity=1.4),),
    )
    .add(part, style=DisplayStyle(color=(0.62, 0.68, 0.72)))
)

view_scene(scene, tolerance=1e-3)
```

The same scene can also open itself:

```python
scene.view(tolerance=1e-3, title="Box")
```

`Scene.view(...)` is only a convenience entry point. It lazy-loads the public
`view_scene(...)` helper, which prepares the scene and creates the VisPy canvas.

A `Scene` is complete as soon as it is created. It always contains:

- `objects`: targets plus optional name, pose, style, and metadata
- `camera`: the active `Camera` object
- `lights`: `AmbientLight`, `DirectionalLight`, or `PointLight` values
- `overlays`: screen-space scene annotations such as `ScaleBarOverlay`
- `units` and metadata

The user can omit `camera` and `lights` when constructing a scene, but the
defaults are still real objects stored directly on the `Scene` value. Default
scenes do not include overlays; scale bars and local axes are opt-in.

```python
scene = Scene("box")

scene.camera  # default Camera
scene.lights  # default light tuple
scene.overlays  # empty by default
```

The target passed to `Scene.add(...)` can be a mesh, a meshable CAD value, a
part, an assembly, a document with meshable contents, a wireframe, a polyline,
or a point cloud.

The product-to-view flow is a tree, not a single mandatory chain. A scene can
wrap a raw geometry value, a part, or a full assembly.

```text
Geometry / Body / Mesh
├─ can be viewed directly
│  └─ SceneObject
│     └─ Scene
│        └─ RenderScene
│           └─ VisPy draw batches
└─ can define a product part
   └─ Part
      ├─ can be viewed directly
      │  └─ SceneObject
      │     └─ Scene
      │        └─ RenderScene
      │           └─ VisPy draw batches
      └─ can be placed in an assembly
         └─ PartInstance
            └─ Assembly
               └─ SceneObject
                  └─ Scene
                     └─ RenderScene
                        └─ VisPy draw batches
```

`Part` is the reusable product definition: name, bodies, material, and metadata.
`PartInstance` is one placement of a part inside an assembly. `SceneObject` is
the viewer wrapper: target, optional view pose, display style, and metadata.

Overlays are separate from scene objects. They describe information drawn over
the viewer rather than geometry placed in the model. `ScaleBarOverlay` draws a
screen-space scale bar for orthographic cameras. `LocalAxesOverlay` draws the
local X/Y/Z axes marker.

```python
from cady import LocalAxesOverlay, ScaleBarOverlay

scene = Scene(
    "box",
    overlays=(
        ScaleBarOverlay(min_pixels=40.0, max_pixels=120.0),
        LocalAxesOverlay(),
    ),
).add(part)

scene_without_overlays = Scene("plain", overlays=()).add(part)
```

## Backend Flow

The viewer backend keeps the conversion steps separate:

```text
Scene
  -> prepare_scene(...)
  -> RenderScene
  -> vispy.draw_batches.build_canvas_geometry(...)
  -> vispy.canvas._make_vispy_canvas(...)
```

`Scene` is the public model. It stores semantic targets, a camera, lights,
overlays, units, and metadata. It should not know about VisPy, GPU buffers, or
OpenGL state.

`RenderScene` is the backend-independent render description. It contains
`SceneMesh` and `SceneLine` payloads, the active `Camera`, lighting values, and
overlay values. This is the main boundary where meshable Cady objects become
arrays.

This layer is useful because it keeps two responsibilities apart:

- `Scene` answers: what does the user want to view?
- `RenderScene` answers: what arrays and render settings does the backend need?

`scene.py` owns both the public `Scene` model and the backend-independent
`RenderScene` preparation boundary. It does not import VisPy, GPU buffers, or
OpenGL state.

`viewer.py` is the public viewer entry point. It keeps helpers such as
`view_scene(...)`, `view_lines(...)`, and the quick `open_target_view(...)`
path used by target `.view(...)` methods.

`view/vispy/` contains the VisPy backend internals:

- `canvas.py` is the lazy VisPy runtime boundary. It imports VisPy only when a
  viewer is actually opened, creates the canvas and shader programs, routes
  mouse/key events, asks `interaction.py` for matrices, asks `overlays.py` to
  update/draw overlays, and draws the prepared batches.
- `draw_batches.py` turns prepared mesh and line payloads into GPU draw
  batches. It owns the split into face batches, edge batches, and point batches.
  Shaded meshes use only explicit display edges; wireframe meshes can derive
  their raw triangle edges.
- `mesh_buffers.py` owns the flat shaded face buffers.
- `interaction.py` owns camera interaction state for orbit, pan, zoom, keyboard
  view changes, camera orientation, model/view matrices, orthographic scale, and
  projection clip planes.
- `overlays.py` owns screen-space overlay drawing for `ScaleBarOverlay` and
  `LocalAxesOverlay`.

The public flow remains:

```text
target -> Scene.add(...) -> prepare_scene(..., tolerance=...) -> view_scene(...)
```

`viewer.open_target_view(...)` is the quick-view path used by target `.view(...)`
helpers. It checks bounds or meshes the target, optionally recentres it, fits an
orthographic camera by default, chooses a shaded or wireframe style, builds a
one-object `Scene`, then calls the lazy public viewer helper.

The public `cady.view` package re-exports model values and `prepare_scene`
directly, but loads viewer-opening helpers through `__getattr__`. Keep new
viewer entry points behind that lazy boundary unless they are pure data/model
helpers.

Useful tests:

- `tests/view/test_scene.py` covers immutable scene values.
- `tests/view/test_camera.py` and `tests/view/test_lights.py` cover view-state
  validation.
- `tests/view/test_object_view_methods.py` covers object `.view(...)` helpers.
- `tests/view/test_vispy_viewer.py` covers viewer preparation and lazy imports.
