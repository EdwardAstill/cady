# Raw Source Notes: Linesplan Wireframe Meshing

**Date retrieved:** 2026-06-25

## VTK Ruled Surface Filter

URL: https://vtk.org/doc/nightly/html/classvtkRuledSurfaceFilter.html

The VTK documentation describes `vtkRuledSurfaceFilter` as a surface generator
from a set of lines. The important constraint is that the input lines are
assumed to be parallel in the loose sense of not intersecting and staying close.
It creates strips by connecting each pair of adjacent lines. VTK also notes that
input points can be used directly or polylines can be resampled.

Implication for cady: this matches the current loft-like station connection
better than a full linesplan network. It is not sufficient for a DXF containing
crossing buttocks and waterlines that should constrain the surface.

## Gordon Surface / Curve-Network Interpolation

URL: https://analysissitus.org/refdoc/classtigl_1_1_c_tigl_interpolate_curve_network.html

Analysis Situs documents TiGL's curve-network interpolation as a Gordon surface
method. The described pipeline computes profile/guide intersections, sorts
profiles and guides, reparametrizes them for compatibility, then computes the
Gordon surface.

URL: https://dlr-sc.github.io/tigl/pages/features.html

TiGL's feature documentation says curve-network interpolation based on Gordon
surfaces is the backbone of its surface modeling, including aircraft wings and
fuselages. This is useful evidence because those models are also profile/guide
curve surface problems rather than arbitrary point clouds.

URL: https://www.caeses.com/blog/2019/gordon-surface-for-curve-networks/

CAESES presents Gordon surfaces as a curve-network surface patch technique.
Its practical requirements are ordered U/V curves and curve intersections at
crossing locations. It also calls out parameterization as important for good
results.

URL: https://docs.bentley.com/LiveContent/web/Promis.e%20Help-v9/en/ConstructSurfaceByNetwork.html

Bentley's "Surface by Network of Curves" documentation describes a B-spline
surface constructed from a Gordon surface and states that elements in one
direction must intersect elements in the other direction.

## occ_gordon

URL: https://github.com/rainman110/occ_gordon

`occ_gordon` is a lightweight C++/Python library implementing Gordon
surface interpolation with B-spline surfaces inside OpenCASCADE. Its README
describes curve networks as interconnected curves that form a surface skeleton,
and lists curve-network reparametrization and Python bindings.

Implication for cady: this is the closest available reference backend for the
desired algorithm, but it depends on OpenCASCADE/pythonocc and is too heavy for
cady's current core runtime constraints. It is a candidate optional backend or
validation oracle, not an unapproved default runtime dependency.

## geomdl / NURBS-Python

URL: https://nurbs-python.readthedocs.io/en/5.x/module_fitting.html
URL: https://pypi.org/project/geomdl/

`geomdl` provides B-spline/NURBS curve and surface interpolation and
approximation from data grids. Its surface fitting API expects points in a
rectangular U/V grid. PyPI lists it as pure Python, MIT licensed, and requiring
Python 3.10 or newer.

Implication for cady: useful for fitting/evaluating B-spline surfaces once a
compatible grid has been built, but it does not by itself solve curve-network
classification, intersection, sorting, or Gordon reparametrization.

## Gmsh Surface Filling / Transfinite Surfaces

URL: https://gmsh.info/doc/texinfo/

Gmsh supports transfinite surfaces and surface filling from curve loops. Its
documentation limits built-in `addSurfaceFilling` to one loop of three or four
curves, while OpenCASCADE-kernel surface filling creates a B-spline surface
matching bounding curves and optional points.

Implication for cady: useful for filling already-decomposed patches, but it is
not a direct solution for an entire linesplan network with many intersecting
sections, buttocks, and waterlines.

## OpenCASCADE Interpolation / Approximation

URL: https://dev.opencascade.org/doc/overview/html/occt_user_guides__modeling_data.html
URL: https://dev.opencascade.org/doc/refman/html/class_geom_fill.html

OpenCASCADE documents interpolation and approximation utilities for B-spline
curves and surfaces, and `GeomFill::Surface` builds a ruled surface between two
curves. These are strong CAD primitives but do not constitute a full
curve-network meshing pipeline by themselves.

## Surface Reconstruction From Non-Parallel Curve Networks

URL: https://profiles.wustl.edu/en/publications/surface-reconstruction-from-non-parallel-curve-networks/
DOI: https://doi.org/10.1111/j.1467-8659.2008.01112.x

The Washington University publication page summarizes Liu, Bajaj, Deasy, Low,
and Ju's 2008 method for surfaces from cross-section curve networks on
arbitrarily oriented planes. The abstract claims the algorithm handles arbitrary
shape/topology and interpolates each cross-section curve network.

Implication for cady: academically relevant for arbitrary curve networks, but it
targets closed surface networks from cross-sections and does not appear to have
a small maintained Python implementation. It is not the first implementation
target for this repo.

## Ship Hull / Linesplan Context

URL: https://www.mdpi.com/2077-1312/11/9/1816
URL: https://www.cs.engr.uky.edu/~cheng/PUBL/CAD-D-05-155.pdf
URL: https://www.sarc.nl/images/publications/ihcs1997.pdf

Ship-hull literature consistently frames hull reconstruction as B-spline/NURBS
curve and surface modeling from stations and related hull lines. The relevant
theme is fair surface reconstruction constrained by traditional linesplan
curves, not point-cloud meshing.

