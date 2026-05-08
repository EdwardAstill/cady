# pyseas-cad

Small, pure-stdlib, write-only CAD package for building format-blind geometry
and emitting DXF R2018 or STL.

```python
from cad import DxfDrawing, StlMesh, rectangle

plate = rectangle((0, 0), (1, 0.5))
DxfDrawing().layer("PLATE").add(plate).write("plate.dxf")
StlMesh().add(plate.extrude("+z", 0.01)).write("plate.stl")
```

Stage 1 supports lines, arcs, circles, rectangles, polylines, splines, paths,
spheres, prisms, extrusions, revolutions, DXF LINE/LWPOLYLINE/CIRCLE/ARC/MTEXT,
and binary/ASCII STL output.

