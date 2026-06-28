"""Source 3D arcs, polylines, and wireframes for the testing examples.

Change the three source arcs here when experimenting with the strip-mesh
example. ``testing5-strip-mesh.py`` imports these rows directly.
"""

from __future__ import annotations

from math import cos, pi, sqrt

from cady import Polyline3, Wireframe3, arc3

RADIUS = 5.0
SAMPLES = 33
DIAGONAL_SCALE = 1.0 / sqrt(2.0)
ARC_SAMPLE_TOLERANCE = 1.01 * RADIUS * (1.0 - cos(pi / (2.0 * (SAMPLES - 1))))

STATION_ARC = arc3(
    (0.0, 0.0, 0.0),
    RADIUS,
    -pi / 2.0,
    pi / 2.0,
    x_axis=(1.0, 0.0, 0.0),
    y_axis=(0.0, 1.0, 0.0),
)
DIAGONAL_ARC = arc3(
    (0.0, 0.0, 0.0),
    RADIUS,
    -pi / 2.0,
    pi / 2.0,
    x_axis=(DIAGONAL_SCALE, 0.0, -DIAGONAL_SCALE),
    y_axis=(0.0, 1.0, 0.0),
)
BUTTOCK_ARC = arc3(
    (0.0, 0.0, 0.0),
    RADIUS,
    -pi / 2.0,
    pi / 2.0,
    x_axis=(0.0, 0.0, -1.0),
    y_axis=(0.0, 1.0, 0.0),
)

STATION_POLYLINE = Polyline3((STATION_ARC,))
DIAGONAL_POLYLINE = Polyline3((DIAGONAL_ARC,))
BUTTOCK_POLYLINE = Polyline3((BUTTOCK_ARC,))

SOURCE_LINESPLAN = (
    STATION_POLYLINE,
    DIAGONAL_POLYLINE,
    BUTTOCK_POLYLINE,
)

STATION_DISCRETISED_POLYLINE = STATION_POLYLINE.discretise(
    tolerance=ARC_SAMPLE_TOLERANCE,
)
DIAGONAL_DISCRETISED_POLYLINE = DIAGONAL_POLYLINE.discretise(
    tolerance=ARC_SAMPLE_TOLERANCE,
)
BUTTOCK_DISCRETISED_POLYLINE = BUTTOCK_POLYLINE.discretise(
    tolerance=ARC_SAMPLE_TOLERANCE,
)

LINESPLAN = (
    STATION_DISCRETISED_POLYLINE,
    DIAGONAL_DISCRETISED_POLYLINE,
    BUTTOCK_DISCRETISED_POLYLINE,
)

STATION_WIREFRAME = Wireframe3.from_polylines((STATION_DISCRETISED_POLYLINE,))
DIAGONAL_WIREFRAME = Wireframe3.from_polylines((DIAGONAL_DISCRETISED_POLYLINE,))
BUTTOCK_WIREFRAME = Wireframe3.from_polylines((BUTTOCK_DISCRETISED_POLYLINE,))

WIREFRAME_OBJECTS = (
    STATION_WIREFRAME,
    DIAGONAL_WIREFRAME,
    BUTTOCK_WIREFRAME,
)
