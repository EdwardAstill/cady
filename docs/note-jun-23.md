# Note Jun 23

This note records the 3D viewer issue investigated on June 23, 2026: circular
holes in extruded plates showed jagged rims, apparent gaps on the top face,
and see-through side walls. The symptoms appeared in the VisPy viewer, but the
main fault was in tessellation rather than only in rendering.

## Symptoms

The user-visible symptoms were:

- edges appeared on flat or almost-flat surfaces where no feature edge should
  be shown;
- some real orientation-change edges were missing;
- circular extrusions showed many vertical side-facet lines;
- a plate with a circular hole showed a gap along the top surface near the
  hole;
- the hole wall looked jagged and partly see-through.

The computational geometry names for these problems are:

- **non-conforming triangulation**: adjacent surfaces are triangulated with
  different vertex sets, so their boundaries do not actually match;
- **mesh cracks**: visible or topological openings caused by unmatched
  boundary edges;
- **T-junctions**: one triangle edge terminates against the middle of another
  edge rather than sharing the same endpoint;
- **non-watertight mesh** or **open-boundary mesh**: at least one mesh edge is
  owned by only one triangle instead of exactly two triangles;
- **inconsistent face winding**: triangle vertex order is wrong for some
  faces, causing normals to point the wrong way;
- **inverted normals**: the visible lighting/inside-out appearance caused by
  wrong winding;
- **faceted tessellation**: a curved surface is approximated by flat segments,
  which is expected, but should not create false feature edges when treated as
  a smooth patch;
- **depth fighting** or **overlay leakage**: line overlays compete with filled
  faces at nearly the same depth.

## Root Cause

The plate-with-hole case exposed a real geometry fault. `polygon_to_triangles`
used a square grid/raster fill for profiles with holes. That produced cap
triangles whose vertices came from the grid, not from the exact hole boundary.

The extrusion side wall, however, was built from the sampled circular hole
loop. This meant the cap and the cylindrical wall were separate surfaces that
only visually touched. Their edges did not share the same vertex coordinates,
so the mesh was not watertight.

That explains the top gap and see-through behaviour: the viewer was drawing an
open mesh with mismatched boundaries. Tuning VisPy edge display could hide some
lines, but it could not make the mesh topologically correct.

There was also a winding issue for inner loops. Outer boundary side walls and
hole side walls need opposite orientation. A hole wall should face into the
void, not outward like an outer perimeter wall.

## Rendering Lessons

The viewer still needed rendering fixes, but those were secondary:

- orientation edges should be boundaries between smooth face patches, not every
  triangle edge;
- smooth curved tessellation should hide internal side facets while preserving
  real sharp creases;
- face normals should be smoothed within smooth patches and split at hard
  creases;
- line overlays should be drawn after filled faces with depth testing and
  polygon offset, following the same general pattern used in VisPy's outlined
  mesh examples.

This fixed the edge display model, but the plate artefact only disappeared
properly once the tessellation produced a valid mesh.

## Fix

The fix replaced the holed-profile grid fill with boundary-conforming
triangulation:

1. Flatten the outer loop and each hole loop with the requested tolerance.
2. Preserve the exact sampled boundary vertices.
3. Bridge each hole into the outer polygon without crossing existing
   boundaries.
4. Ear-clip the resulting simple polygon.
5. Build extrusion side walls from the same boundary loops.
6. Reverse the side-wall winding for inner loops so hole-wall normals point
   into the void.

After this, cap triangles and side-wall triangles share the same boundary
edges. A watertight extrusion should have every topological edge owned by
exactly two triangles.

## Regression Coverage

The regression tests added or tightened were:

- a profile with a circular hole uses the exact hole boundary edges in the cap
  triangulation;
- an extrusion with a hole is watertight;
- circular extrusion side facets are hidden as smooth tessellation, while the
  top and bottom rims remain visible;
- plate-with-hole visualisation edges now assert the expected real perimeter
  and hole-rim edges rather than allowing raster-grid artefacts;
- smooth normals are shared across smooth joins and split at hard creases.

The full gates passed after the fix:

```bash
.venv/bin/pytest -q
.venv/bin/pyright src/cady
.venv/bin/ruff check src/cady tests
git diff --check
```

At the time of the note, the test result was:

```text
256 passed, 13 skipped
```

## Practical Takeaway

When a 3D preview shows gaps, see-through surfaces, or jagged holes, do not
start by assuming the renderer is wrong. First check mesh topology:

- do adjacent surfaces share the same boundary vertices?
- does every closed-solid edge have exactly two owning triangles?
- are outer loops and hole loops wound in opposite directions where needed?
- are normals consistent with the intended inside/outside of the solid?

Only after those checks pass should viewer edge classification, smoothing,
depth testing, and polygon offset be tuned.
