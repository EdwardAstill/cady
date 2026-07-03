"""Longitudinal polylines for a ship hull, bundled as a Wireframe3.

The hull is parametrised with a cubic entry/run and parallel middle body.
Section shapes are power-curve U-sections.  Waterlines and buttocks are
sampled from the surface and collected into a single Wireframe3.

Usage:
    from wireframe import build_linespan
    linespan = build_linespan()
    linespan.view()
"""

from __future__ import annotations

import numpy as np

from cady import Polyline3, Wireframe3

# ── Hardcoded hull parameters ───────────────────────────────────────
LENGTH = 100.0  # length between perpendiculars
BEAM = 20.0  # moulded breadth
DRAFT = 10.0  # draft at midship
SECTION_EXPONENT = 2.5  # section shape: >2 = U-shaped
N_STATIONS = 101  # discretisation along the hull

ENTRY_FRAC = 0.15  # fraction of length for fore entry
RUN_FRAC = 0.15  # fraction of length for aft run

WATERLINE_DEPTHS = (-9.0, -7.0, -5.0, -3.0, -1.0)
BUTTOCK_OFFSETS = (1.5, 3.0, 4.5, 6.0, 7.5, 9.0)

# ── Hull surface helpers ────────────────────────────────────────────

_x = np.linspace(0.0, LENGTH, N_STATIONS)


def _beam(xi: float) -> float:
    """Half-breadth at the waterline for a given longitudinal position."""
    if ENTRY_FRAC * LENGTH <= xi <= (1.0 - RUN_FRAC) * LENGTH:
        return BEAM / 2.0
    if xi < ENTRY_FRAC * LENGTH:
        t = xi / (ENTRY_FRAC * LENGTH)
        return (BEAM / 2.0) * t * t * (3.0 - 2.0 * t)
    t = (xi - (1.0 - RUN_FRAC) * LENGTH) / (RUN_FRAC * LENGTH)
    return (BEAM / 2.0) * (1.0 - t * t * (3.0 - 2.0 * t))


def _section_half_breadth(xi: float, t: float) -> float:
    """Half-breadth at station xi, section parameter t ∈ [0,1]."""
    return _beam(xi) * (t**SECTION_EXPONENT)


def _section_depth(t: float) -> float:
    """Depth for section parameter t ∈ [0,1]; t=0→keel, t=1→waterline."""
    return DRAFT * (t - 1.0)


# ── Polyline builders ───────────────────────────────────────────────


def _build_waterline(depth_z: float) -> Polyline3 | None:
    """Sample the waterline at constant depth z."""
    t = depth_z / DRAFT + 1.0
    if not (0.0 <= t <= 1.0):
        return None
    pts: list[tuple[float, float, float]] = []
    for xi in _x:
        y = _section_half_breadth(xi, t)
        if y > 0.0:
            pts.append((float(xi), y, float(depth_z)))
    return Polyline3(pts) if len(pts) >= 2 else None


def _build_buttock(offset_y: float) -> Polyline3 | None:
    """Sample a buttock at constant half-breadth y."""
    pts: list[tuple[float, float, float]] = []
    for xi in _x:
        b = _beam(xi)
        if b < offset_y:
            continue
        t = (offset_y / b) ** (1.0 / SECTION_EXPONENT)
        z = _section_depth(t)
        pts.append((float(xi), float(offset_y), float(z)))
    return Polyline3(pts) if len(pts) >= 2 else None


def _build_deck_edge() -> Polyline3:
    """Longitudinal polyline tracing the deck edge (sheer)."""
    return Polyline3([(float(xi), _beam(xi), 0.0) for xi in _x])


def _build_keel() -> Polyline3:
    """Longitudinal polyline tracing the keel on the centreplane."""
    return Polyline3([(float(xi), 0.0, -DRAFT) for xi in _x])


# ── Public API ──────────────────────────────────────────────────────


def build_linespan() -> Wireframe3:
    """Build and return a Wireframe3 of longitudinal hull polylines.

    Includes waterlines at five depths, buttocks at six half-breadth
    offsets, the deck edge (sheer line), and the keel line.
    """
    polylines: list[Polyline3] = []

    for z in WATERLINE_DEPTHS:
        wl = _build_waterline(z)
        if wl is not None:
            polylines.append(wl)

    for y in BUTTOCK_OFFSETS:
        bk = _build_buttock(y)
        if bk is not None:
            polylines.append(bk)

    polylines.append(_build_deck_edge())
    polylines.append(_build_keel())

    return Wireframe3.from_polylines(polylines)


# ── CLI ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ls = build_linespan()
    print(f"linespan: {len(ls.vertices)} vertices, {len(ls.edges)} edges")
    ls.view(title="Linesplan 3 — Longitudinal Polylines")
