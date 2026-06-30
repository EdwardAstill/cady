# View Render Architecture Plan

## Objective

Make the Cady view stack professional, clear, and maintainable without turning
it into a large rendering framework.

The target is a small layered design:

```text
Geometry / Body / Mesh
  -> Part
  -> PartInstance / Assembly
  -> SceneObject
  -> Scene
  -> RenderScene
  -> VispyCanvas
```

Each layer should own one kind of meaning. Geometry owns shape. Product objects
own product identity and placement. Scene objects own view wrapping and display
style. Render scene objects own backend-independent render data. The canvas owns
the live backend window.

## Scope

This plan covers the `cady.view` product-to-view boundary:

- scene model naming and responsibilities
- render preparation naming
- VisPy canvas extraction and naming
- overlay model cleanup
- docs and tests that describe the flow

This plan does not cover:

- changing geometry semantics
- collapsing `Part` and `PartInstance`
- making a public canvas API
- adding a 2D interactive scene system
- changing file export behavior

## Target Responsibilities

| Layer | Responsibility |
|---|---|
| Geometry / Body / Mesh | Shape only. No view, product, camera, or placement meaning. |
| `Part` | Reusable product definition: name, bodies, material, metadata. |
| `PartInstance` | One placement of a part inside an assembly. |
| `Assembly` | Product structure made from part and assembly instances. |
| `SceneObject` | View wrapper around a target, optional view pose, display style, metadata. |
| `Scene` | View description: objects, camera, lights, overlays, units, metadata. |
| `RenderScene` | Backend-independent render payload: arrays, camera, lights, overlays. |
| `DrawBatch` | GPU draw-call payloads for faces, edges, points, and lines. |
| `VispyCanvas` | Backend-specific runtime object: window, shaders, GPU state, interaction. |

## Design Decisions

### Keep `Part` and `PartInstance` separate

`Part` is the reusable product definition. `PartInstance` is one placement of
that product inside an assembly. Merging them would make repeated parts awkward
and would mix product definition with product placement.

Users should usually create instances indirectly:

```python
assembly = Assembly("frame").add(part, name="left_plate", pose=(0.0, 0.0, 0.0))
```

Manual construction of `PartInstance` can remain available, but it should not be
the main path in examples.

### Keep `SceneObject` separate from `PartInstance`

`PartInstance` is product placement. `SceneObject` is view wrapping. They both
can carry a pose-like value, but the meaning is different:

- assembly pose means "where this part is in the product"
- scene pose means "where this target is placed for this view"

This lets the same product be shown in different scenes without rewriting the
product structure.

### Rename `PreparedScene` to `RenderScene`

The render-prepared value is not another authoring scene. It is the
backend-independent render description produced from a `Scene`. The clearer name
is `RenderScene`.

The implementation should make `RenderScene` the public preparation type in
`cady.view`. Remove the old public `PreparedScene` export as part of the rename,
unless downstream compatibility becomes an explicit requirement before
implementation starts.

### Keep canvas internal for now

The live canvas is a real object, but it should not become public yet. A public
canvas API would imply commitments around screenshots, embedding, camera
updates, close behavior, and event lifetimes.

For now, keep the API:

```python
scene.view(...)
view_scene(scene, ...)
```

Internally, the flow should be:

```text
Scene.view()
  -> view_scene(scene)
  -> prepare_scene(scene)
  -> _make_vispy_canvas(render_scene)
  -> app.run()
```

### Make overlays explicit scene values

`ScaleBarOverlay` already fits this model. Local axes should also become an
overlay model value rather than an always-on special case hidden inside the
canvas.

Target overlay values:

```python
Scene(overlays=(ScaleBarOverlay(), LocalAxesOverlay()))
```

The renderer may still decide that a specific overlay only works for specific
camera modes, but the scene should own the requested overlay list.

### Preserve lazy viewer imports

No PyQt, VisPy, or OpenGL modules should import at `cady`, `cady.view`, or model
module import time. VisPy imports belong inside functions that open or prepare
the backend-specific canvas.

## Target Module Layout

```text
src/cady/view/
  scene.py
  camera.py
  light.py
  style.py
  overlay.py
  render_scene.py
  draw_batches.py
  interaction.py
  overlay_renderers.py
  vispy_canvas.py
  vispy_viewer.py
  open_view.py
```

`vispy_viewer.py` should be the public lazy entry-point module. `vispy_canvas.py`
should hold the internal backend-specific canvas class/factory.

## Done Criteria

- `RenderScene` is the name used by code, tests, and notes.
- No current source references to `PreparedScene` remain unless a deliberate
  compatibility alias is added and documented.
- `vispy_viewer.py` no longer contains a large nested canvas implementation.
- A backend-specific internal `VispyCanvas` object owns the live VisPy runtime.
- `ScaleBarOverlay` and local axes are explicit overlay model values.
- The public flow remains simple: `Scene.view(...)` and `view_scene(scene, ...)`.
- Import-boundary tests still prove that VisPy is lazy.
- `viewing.md` explains the final architecture accurately.
