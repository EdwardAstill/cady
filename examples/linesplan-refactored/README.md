# Linesplan Refactored Example

1. Read The Linesplan DXF

1.1 Start from `examples/inputs/linesplan_9m.dxf`.

1.2 Read the DXF curves as the source linesplan geometry.

1.3 Keep the curves classified as station sections. These are the hull
cross-sections used by the rest of the process.

1.4 Store these station sections as 3D station polylines.

2. Clean The Station Polylines

2.1 Convert each station polyline into an ordered list of 3D points.

2.2 Snap points with a very small `y` value onto the centreline by setting
`y = 0`.

2.3 Remove repeated neighbouring points so each station is a clean path.

2.4 Ignore very short station fragments that are too small to contribute to the
hull shape.

3. Join Station Fragments

3.1 Compare each station fragment with the remaining station fragments.

3.2 If two fragment endpoints are close enough, join them into one longer
station polyline.

3.3 If a fragment endpoint lands near the middle of another fragment, insert
that endpoint into the other fragment and join them there.

3.4 If two fragments describe the same points, keep only one copy.

3.5 Store the joined station polylines ordered along the boat by their `x`
position.

4. Orient Each Station

4.1 Find the highest point on the station where `y` is positive.

4.2 Discard any points after that highest positive-`y` point. This keeps the
part of the station used for this hull surface.

4.3 Orient the station so its start point is at the larger `z` value.

4.4 Store these oriented station polylines as the prepared station set.

5. Find The Keel Shape Change

5.1 Look along each prepared station for the strongest upper discontinuity in
the keel-region shape.

5.2 If no discontinuity is found, keep the whole station in the main upper hull
group.

5.3 If a discontinuity is found, split the station at that point.

5.4 Store the first part as a yellow top polyline.

5.5 Store the second part as a red top polyline.

5.6 Store the prepared station end points as green points. These are used later
when deciding which patch edges must meet the centreline.

6. Create Nodes On Each Station Group

6.1 For each station group, choose a shared number of nodes from the typical
station length in that group.

6.2 Walk along each station and place nodes at even intervals.

6.3 Force every node on the same station to share the station's median `x`
position. This keeps each station row planar in the length direction.

6.4 Store these node rows for the yellow top group and the red top group.

7. Create Open Mesh Patches

7.1 Turn each group of node rows into an open mesh patch.

7.2 Connect neighbouring nodes along each station row.

7.3 Connect matching nodes between neighbouring station rows.

7.4 Store the yellow patch and red patch as the positive-`y` half of the hull.

8. Store The Boundary Nodes Needed Later

8.1 Store the first node from every yellow patch row as a yellow boundary node.

8.2 Compare the end of each source polyline with the green points from step 5.6.

8.3 When a polyline end matches a green point, store the last node from that row
as a green boundary node.

8.4 Keep the row number with each boundary node so neighbouring boundary nodes
can be grouped together later.

9. Complete The Half Hull To The Centreline

9.1 Sort yellow and green boundary nodes by their row number.

9.2 Group neighbouring boundary nodes into continuous chains.

9.3 For each chain, create a centreline strip by pairing each boundary node with
the same point projected to `y = 0`.

9.4 Add these centreline strips to the positive-`y` half hull.

10. Mirror The Half Hull

10.1 Mirror the positive-`y` half hull across the centreline plane.

10.2 Store the mirrored patches as the negative-`y` half of the hull.

10.3 Combine the original half patches and mirrored half patches as the full set
of open hull patches.

11. Cap The Keel Ends

11.1 Take the node rows from the red top patch.

11.2 Keep the first and last red rows along the boat.

11.3 For each kept row, pair it with its mirrored row.

11.4 Store those paired rows as keel end cap faces.

12. Build The Final Hull Mesh

12.1 Combine the open hull patches and keel end caps into one mesh.

12.2 Merge points that represent the same position so the mesh shares vertices
where patches meet.

12.3 Close any remaining open boundaries.

12.4 Store the result as the closed hull mesh.

12.5 If closing fails, keep the combined open mesh so the hull shape can still
be inspected.

13. Clean The Mesh Faces

13.1 Compare neighbouring faces in the final hull mesh.

13.2 When connected faces sit on the same plane, combine them into one larger
face.

13.3 Keep any face group that cannot be represented as one simple face in its
existing form.

13.4 Split every face that is not already triangular into triangular faces.

13.5 Derive an automatic triangulation guide from each merged face shape.
Detailed refinement is used for simple quads, while larger boundary loops get a
bounded interior seed so the cleanup does not create excessive mesh density.

13.6 Require every non-degenerate output triangle to have a minimum angle of at
least 20 degrees.

13.7 Store the result as the cleaned triangular hull mesh only if that quality
requirement is satisfied.

13.8 Decimate the cleaned mesh directly in `main.py` with a target of 11,000
faces only after the clean step succeeds.

13.9 If the clean step fails, show the merged coplanar mesh and report the
minimum-angle failure instead of displaying bad cleaned triangles.

14. Check The Result

14.1 With the default DXF, the process currently reports:

```text
polyline groups: yellow=65, red=4
mesh patches: 4
combined mesh: 8886 vertices, 8742 faces
closed mesh: 8886 vertices, 17766 faces
merged coplanar mesh: 8886 vertices, 9360 faces
cleaned mesh: failed - triangulation produced a triangle angle 4.79804 below min_angle_degrees 20
```

14.2 These numbers are a quick check that the same station groups, patch count,
final hull mesh, merged coplanar mesh, and strict triangle quality failure are
still being produced.
