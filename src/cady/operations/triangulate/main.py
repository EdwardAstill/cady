# pyright: reportMissingParameterType=false, reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false
# pyright: reportUnknownVariableType=false
"""Public 2D triangulation dispatch."""

from cady.operations.triangulate import ear_delaunay_refinement, pizza_web

SUPPORTED_CONSTRAINTS = {
    "ear_delaunay_refinement": ear_delaunay_refinement.SUPPORTED_CONSTRAINTS,
    "pizza_web": pizza_web.SUPPORTED_CONSTRAINTS,
}


def triangulate(nodes, edges, *, algorithm="ear_delaunay_refinement", **constraints):
    """Triangulate closed 2D edge loops and return nodes, edges, and faces."""
    if algorithm not in SUPPORTED_CONSTRAINTS:
        raise ValueError(f"unsupported triangulation algorithm {algorithm!r}")
    unsupported = sorted(
        name for name in constraints if name not in SUPPORTED_CONSTRAINTS[algorithm]
    )
    if unsupported:
        names = ", ".join(unsupported)
        raise ValueError(
            f"{algorithm!r} does not support triangulation constraint(s): {names}"
        )
    if algorithm == "pizza_web":
        return pizza_web.pizza_web_triangulate(nodes, edges, **constraints)
    return ear_delaunay_refinement.ear_delaunay_refinement_triangulate(
        nodes,
        edges,
        **constraints,
    )
