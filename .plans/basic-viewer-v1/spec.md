# Basic viewer v1

## Goal

Make the native viewer a reliable, quiet CAD preview: shaded geometry on a
neutral background with orbit, pan, and zoom camera control. Keep lighting to
one ambient term plus one directional term, with no shadows or material effects.

## Scope

- Preserve the public `Scene`, `Camera`, light, overlay, and `DisplayStyle` APIs.
- Remove default scale-bar/local-axis clutter; overlays remain opt-in.
- Do not generate tessellation edges over shaded meshes. Explicit display edges
  remain visible, and wireframe mode still derives triangle edges when needed.
- Use restrained default ambient/directional values and a neutral canvas.
- Make the interaction orbit around the declared camera target instead of
  silently replacing it with the geometry bounds center.
- Fix the missing-cap regression exposed by the plate-with-hole viewer case.

## Non-goals

- Shadows, specular highlights, multiple rendered directional lights, point-light
  evaluation, materials, picking, editing, or a toolbar.
- Replacing Vispy or the current lazy viewer import boundary.
- Removing existing public scene/light/overlay values.

## Acceptance criteria

- A region extrusion with a hole produces top and bottom cap triangles.
- A shaded mesh without explicit display edges produces no edge overlay batch.
- Wireframe mode remains visible by deriving triangle edges.
- A default `Scene` has no overlays and uses restrained simple lights.
- The viewer canvas uses a neutral non-white background.
- Orbit/pan/zoom remain available, and the camera target is the orbit center.
- Viewer, geometry, convention, type, lint, and render-smoke checks pass.

## Risks

- Removing generated shaded edges changes the default appearance deliberately;
  callers can use wireframe mode or explicit mesh display edges.
- Changing default overlays is a visual default change, not an API removal.
- The hole-cap repair must preserve boundary coordinates so extruded side walls
  meet the caps.

