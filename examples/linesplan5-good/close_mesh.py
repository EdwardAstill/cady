from loft_polylines2 import  MIRRORED_STATION_POLYLINES, loft_polylines2, STATION_POLYLINES





half_unclosed_mesh = loft_polylines2(STATION_POLYLINES)


# close mesh

# add on front and back faces
front_polyline = MIRRORED_STATION_POLYLINES[0]
back_polyline = MIRRORED_STATION_POLYLINES[-1]

# use the closed planar cap thing i have for meshes not this from curves thing
front_mesh = Mesh3.from_curves([front_polyline])
back_mesh = Mesh3.from_curves([back_polyline])



#find remaining open edges of half_unclosed_mesh and fill them in with a mesh cap
