# Algorithm Selection

**Lane:** 1 / curve-network surfacing for linesplans
**Date:** 2026-06-25
**Confidence:** high for architecture, medium for exact implementation backend

## Answer

Use a curve-network surfacing pipeline, with Gordon surface interpolation as the
target algorithm family. Do not use `dxf.read_mesh` as a format-level shortcut,
and do not treat a linesplan as only a list of parallel section curves.

## Evidence

### The local DXF is a curve network, not just a station loft

- Local inventory of `examples/inputs/linesplan_9m.dxf`: 68 `SECTIONS`, 19
  `BUTTOCKS`, 9 `WATERLINES`, 4 `Knuckle`, 5 layer `0` polylines, plus 15
  `LINE` entities.
- The current hidden mesh conversion selected only 65 section-like curves and
  appended the original 9,610 DXF edges as display-only mesh edges. That is why
  visible wireframe lines exist where no mesh faces exist.
- Confidence: high. This came from local DXF parsing and mesh topology counts.

### Ruled/loft surfaces are only a fallback

- VTK's `vtkRuledSurfaceFilter` expects lines that do not intersect and remain
  close; it creates strips between adjacent generating lines
  ([raw/algorithm-sources.md#vtk-ruled-surface-filter]).
- This is suitable for an explicit "loft ordered section curves" operation, but
  it does not use crossing buttocks/waterlines as constraints.
- Confidence: high. VTK's official docs define the assumptions directly.

### Gordon / curve-network interpolation matches the problem best

- TiGL/Analysis Situs documents Gordon curve-network interpolation as:
  compute intersections, sort profiles/guides, reparametrize for compatibility,
  then compute the Gordon surface
  ([raw/algorithm-sources.md#gordon-surface--curve-network-interpolation]).
- CAESES and Bentley describe the same practical requirements: ordered U/V
  curves with intersections at crossing locations
  ([raw/algorithm-sources.md#gordon-surface--curve-network-interpolation]).
- TiGL uses Gordon surfaces as a core surface modeling method for profile/guide
  curve aircraft geometry, which is structurally similar to hull sections and
  guide curves.
- Confidence: high. Multiple CAD-oriented sources agree on the algorithm family
  and the prerequisites.

### Libraries can help, but should not be added to core without approval

- `occ_gordon` is a close reference implementation and supports Python, but it
  depends on OpenCASCADE/pythonocc
  ([raw/algorithm-sources.md#occ_gordon]).
- `geomdl` is pure Python and supports B-spline/NURBS fitting, but its surface
  fitting API assumes a rectangular U/V point grid and does not classify or
  reparametrize a curve network
  ([raw/algorithm-sources.md#geomdl--nurbs-python]).
- Gmsh and OpenCASCADE have useful primitives for patch filling/ruled surfaces,
  but are not direct full-network solutions
  ([raw/algorithm-sources.md#gmsh-surface-filling--transfinite-surfaces],
  [raw/algorithm-sources.md#opencascade-interpolation--approximation]).
- Confidence: medium. The fit is clear, but exact dependency choice needs a
  prototype and approval because cady currently has strict runtime dependency
  limits.

### Point-cloud reconstruction is the wrong primary path

- Point-cloud/NURBS reconstruction literature is useful when the input is dense
  scanned points. The cady input is named curve data with semantic layers.
- Poisson, ball-pivoting, generic RBF, and unordered point-cloud B-spline
  fitting would not guarantee that waterlines, buttocks, knuckles, and sections
  remain visible constraints of the generated mesh.
- Confidence: medium. This is an inference from algorithm inputs/outputs rather
  than a single source disqualifying every point-cloud method.

## Recommendation

Build a dedicated linesplan curve-network mesher:

1. DXF parsing produces only `Wireframe3D` plus source metadata such as layer.
2. A classifier turns the wireframe into a `LinesplanCurveNetwork` with profiles
   and guide curves.
3. A curve-network surfacing stage snaps/intersects the curves, creates a
   compatible U/V parameter grid, and evaluates a Gordon-style surface.
4. Mesh extraction samples the surface along both profile and guide isolines so
   the mesh topology contains the curves that constrained the surface.
5. Source wireframes are rendered as a separate overlay, never copied into
   `Mesh3D.edges`.

## Gaps

- The existing DXF reader may not preserve layer metadata on the merged
  `Wireframe3D`; the plan should add a structured import result for source
  curves rather than relying on merged edges alone.
- Exact intersection tolerances and station/guide classification rules need
  tests against `linesplan_9m.dxf`.
- Whether to use `occ_gordon` as an optional backend or implement a sampled
  Gordon-style mesher in NumPy needs a small spike before committing to a new
  dependency.

