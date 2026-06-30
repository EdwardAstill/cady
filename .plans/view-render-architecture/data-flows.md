# Data Flows

## Direct View Flow

```text
Geometry / Body / Mesh / Wireframe / PointCloud
  -> Scene.add(...)
  -> SceneObject
  -> Scene
  -> prepare_scene(scene, tolerance=...)
  -> RenderScene
  -> build_canvas_geometry(render_scene, gloo)
  -> CanvasGeometry
  -> VispyCanvas
  -> OpenGL draw calls
```

Use this flow for quick inspection and simple examples.

## Product View Flow

```text
Geometry / Body / Mesh
  -> Part
  -> Assembly.add(part, pose=...)
  -> PartInstance
  -> Assembly
  -> Scene.add(assembly)
  -> SceneObject
  -> prepare_scene(scene, tolerance=...)
  -> RenderScene
  -> VispyCanvas
```

`PartInstance` placement is resolved when an assembly is flattened or meshed.
`SceneObject` placement remains a view-layer placement around the target.

## Scene View Flow

```text
scene.view(...)
  -> cady.view.view_scene(scene, ...)
  -> prepare_scene(scene, tolerance=...)
  -> _make_vispy_canvas(render_scene, title=...)
  -> app.run()
```

`Scene.view(...)` should stay a convenience wrapper. It should not import VisPy
until the viewer function is actually requested.

## Render Preparation Flow

```text
SceneObject.target
  -> point cloud path, or
  -> polyline path, or
  -> meshable path
  -> SceneMesh / SceneLine
```

Render preparation resolves:

- style visibility
- target conversion
- object pose transform
- mesh faces and edges
- point rendering mode
- line indices
- camera value
- scene light values
- overlay values

Render preparation does not create GPU buffers or open windows.

## Draw Batch Flow

```text
RenderScene.meshes / RenderScene.lines
  -> face batches
  -> edge batches
  -> point batches
  -> scene bounds
```

Draw batches are backend-facing draw-call payloads. A single mesh can create
more than one draw batch, for example shaded faces plus edge outlines.

## Overlay Flow

```text
Scene.overlays
  -> RenderScene.overlays
  -> overlay renderer factory
  -> screen-space drawing during canvas draw event
```

Overlays are not model geometry. They describe information drawn over the
viewer, such as a scale bar or local axes.

## Lazy Import Flow

```text
import cady
import cady.view
```

These imports must not import VisPy, PyQt, or OpenGL.

```text
scene.view(...)
view_scene(scene, ...)
```

Only these viewer paths should require VisPy.
