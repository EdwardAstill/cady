"""Longitudinal hull polylines with a keel, returned as two Wireframe3 objects.

The hull is parametrised with a cubic entry/run and parallel middle body.
Section shapes are power-curve U-sections.  Waterlines and buttocks are
sampled from the surface.

Usage:
    from linesplan_with_keel import build_linespan
    hull, keel = build_linespan()
    hull.view()
    keel.view()
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

KEEL_DEPTH = -DRAFT  # keel sits at the bottom
KEEL_THICKNESS = 0.2  # flat-bar keel half-width

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
    """Depth for section parameter t ∈ [0,1]; t=0 → keel, t=1 → waterline."""
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


def _build_centreplane_keel() -> Polyline3:
    """Centreline keel polyline at the bottom of the hull."""
    return Polyline3([(float(xi), 0.0, KEEL_DEPTH) for xi in _x])


def _build_keel_port() -> Polyline3:
    """Port edge of the flat-bar keel."""
    return Polyline3([(float(xi), KEEL_THICKNESS, KEEL_DEPTH) for xi in _x])


# ── Public API ──────────────────────────────────────────────────────


def build_linespan() -> tuple[Wireframe3, Wireframe3]:
    """Build longitudinal hull polylines with a keel.

    Returns
    -------
    hull : Wireframe3
        Waterlines, buttocks, and deck edge (sheer line).
    keel : Wireframe3
        Flat-bar keel at the bottom: centreline and port-side polylines.
    """
    hull_polylines: list[Polyline3] = []

    for z in WATERLINE_DEPTHS:
        wl = _build_waterline(z)
        if wl is not None:
            hull_polylines.append(wl)

    for y in BUTTOCK_OFFSETS:
        bk = _build_buttock(y)
        if bk is not None:
            hull_polylines.append(bk)

    hull_polylines.append(_build_deck_edge())

    keel_polylines = [_build_centreplane_keel(), _build_keel_port()]

    hull = Wireframe3.from_polylines(hull_polylines)
    keel = Wireframe3.from_polylines(keel_polylines)
    return hull, keel


# ── CLI ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    hull, keel = build_linespan()
    print(f"hull: {len(hull.vertices)} vertices, {len(hull.edges)} edges")
    print(f"keel: {len(keel.vertices)} vertices, {len(keel.edges)} edges")
    hull.view(title="Linesplan 3 — Hull Polylines")
    keel.view(title="Linesplan 3 — Keel")
