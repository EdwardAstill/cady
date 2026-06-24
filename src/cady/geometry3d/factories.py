from __future__ import annotations

from cady.geometry3d.body import Body3D
from cady.geometry3d.frame import Frame3D, Point3Like


def box(
    width: float,
    depth: float,
    height: float,
    *,
    frame: Frame3D | None = None,
) -> Body3D:
    return Body3D.box(width=width, depth=depth, height=height, frame=frame)


def cylinder(
    radius: float,
    height: float,
    *,
    frame: Frame3D | None = None,
) -> Body3D:
    return Body3D.cylinder(radius=radius, height=height, frame=frame)


def sphere(
    radius: float,
    *,
    centre: Point3Like = (0.0, 0.0, 0.0),
) -> Body3D:
    return Body3D.sphere(radius=radius, centre=centre)
