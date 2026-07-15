"""Editable solid bodies composed from inline feature records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, TypeAlias

from cady.geometry.mesh import Mesh3
from cady.geometry.plane3 import Plane3
from cady.operations.mesh.construction import extrusion_mesh
from cady.operations.mesh.primitives import (
    box_mesh,
    cylinder_mesh,
    sphere_mesh,
)
from cady.operations.transforms import Transform3
from cady.utils import finite, positive, positive_tolerance

Point3: TypeAlias = tuple[float, float, float]

if TYPE_CHECKING:
    from cady.view import Camera, DisplayStyle, Light
    from cady.view.style import RenderMode
    from cady.view.viewer import Projection

PrimitiveKind = Literal["box", "cylinder", "sphere", "cone"]
BooleanKind = Literal["union", "difference", "intersection"]


@dataclass(frozen=True, slots=True)
class RegionFeature:
    """Stored source region placed in a 3D plane."""

    region: object
    plane: Plane3

    def __post_init__(self) -> None:
        _validate_region(self.region)
        _validate_plane(self.plane)


@dataclass(frozen=True, slots=True)
class ExtrudeFeature:
    """Linear sweep of a region along its plane normal."""

    region: object
    plane: Plane3
    distance: float

    def __post_init__(self) -> None:
        _validate_region(self.region)
        _validate_plane(self.plane)
        distance = finite(self.distance, "extrude distance")
        if distance == 0.0:
            raise ValueError("extrude distance must be finite and non-zero")
        object.__setattr__(self, "distance", distance)


@dataclass(frozen=True, slots=True)
class RevolveFeature:
    """Angular sweep of a region around its local plane axis."""

    region: object
    plane: Plane3
    angle: float

    def __post_init__(self) -> None:
        _validate_region(self.region)
        _validate_plane(self.plane)
        angle = finite(self.angle, "revolve angle")
        if angle == 0.0:
            raise ValueError("revolve angle must be finite and non-zero")
        object.__setattr__(self, "angle", angle)


@dataclass(frozen=True, slots=True)
class PrimitiveFeature:
    """Named primitive solid with validated scalar parameters."""

    kind: PrimitiveKind
    parameters: Mapping[str, float]
    plane: Plane3

    def __post_init__(self) -> None:
        if self.kind not in {"box", "cylinder", "sphere", "cone"}:
            raise ValueError(f"unsupported primitive kind {self.kind!r}")
        _validate_plane(self.plane)
        parameters = {key: finite(value, key) for key, value in self.parameters.items()}
        object.__setattr__(self, "parameters", MappingProxyType(parameters))


@dataclass(frozen=True, slots=True)
class BooleanFeature:
    """Boolean operation to apply against another body-like tool."""

    kind: BooleanKind
    tool: object

    def __post_init__(self) -> None:
        if self.kind not in {"union", "difference", "intersection"}:
            raise ValueError(f"unsupported boolean kind {self.kind!r}")


@dataclass(frozen=True, slots=True)
class FilletFeature:
    """Deferred edge-rounding request recorded on a body."""

    radius: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "radius", positive(self.radius, "radius"))


@dataclass(frozen=True, slots=True)
class ChamferFeature:
    """Deferred edge-bevel request recorded on a body."""

    distance: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "distance", positive(self.distance, "distance"))


Feature: TypeAlias = (
    RegionFeature
    | ExtrudeFeature
    | RevolveFeature
    | PrimitiveFeature
    | BooleanFeature
    | FilletFeature
    | ChamferFeature
)

_FEATURE_TYPES = (
    RegionFeature,
    ExtrudeFeature,
    RevolveFeature,
    PrimitiveFeature,
    BooleanFeature,
    FilletFeature,
    ChamferFeature,
)
_GENERATOR_TYPES = (ExtrudeFeature, RevolveFeature, PrimitiveFeature)


@dataclass(frozen=True, slots=True)
class Body3:
    """Semantic 3D body defined by an ordered feature history."""

    name: str | None = None
    features: tuple[Feature, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=lambda: {})

    def __post_init__(self) -> None:
        features = tuple(self.features)
        _validate_feature_history(features)
        object.__setattr__(self, "features", features)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def from_region(
        cls,
        region: object,
        *,
        plane: Plane3 | None = None,
    ) -> Body3:
        return cls(
            features=(
                RegionFeature(region, Plane3.world_xy() if plane is None else plane),
            )
        )

    @classmethod
    def box(
        cls,
        *,
        width: float,
        depth: float,
        height: float,
        plane: Plane3 | None = None,
    ) -> Body3:
        width = positive(width, "width")
        depth = positive(depth, "depth")
        height = positive(height, "height")
        return cls(
            features=(
                PrimitiveFeature(
                    "box",
                    {"width": width, "depth": depth, "height": height},
                    Plane3.world_xy() if plane is None else plane,
                ),
            )
        )

    @classmethod
    def cylinder(
        cls,
        *,
        radius: float,
        height: float,
        plane: Plane3 | None = None,
    ) -> Body3:
        radius = positive(radius, "radius")
        height = positive(height, "height")
        return cls(
            features=(
                PrimitiveFeature(
                    "cylinder",
                    {"radius": radius, "height": height},
                    Plane3.world_xy() if plane is None else plane,
                ),
            )
        )

    @classmethod
    def sphere(
        cls,
        *,
        radius: float,
        center: Point3 = (0.0, 0.0, 0.0),
    ) -> Body3:
        radius = positive(radius, "radius")
        return cls(
            features=(
                PrimitiveFeature(
                    "sphere",
                    {"radius": radius},
                    Plane3.from_normal(center, (0.0, 0.0, 1.0)),
                ),
            )
        )

    def extrude(
        self,
        distance: float,
        *,
        region: object | None = None,
        plane: Plane3 | None = None,
    ) -> Body3:
        if region is None:
            region_feature = self._last_region_feature()
            resolved_region = region_feature.region
            resolved_plane = region_feature.plane if plane is None else plane
        else:
            resolved_region = region
            resolved_plane = Plane3.world_xy() if plane is None else plane
        features = tuple(
            feature for feature in self.features if not isinstance(feature, RegionFeature)
        )
        return replace(
            self,
            features=(*features, ExtrudeFeature(resolved_region, resolved_plane, distance)),
        )

    def with_feature(self, feature: Feature) -> Body3:
        return replace(self, features=(*self.features, feature))

    def transformed(self, transform: Transform3) -> Body3:
        return replace(
            self,
            features=tuple(_transform_feature(feature, transform) for feature in self.features),
        )

    def to_mesh(self, *, tolerance: float) -> Mesh3:
        tolerance = positive_tolerance(tolerance)
        mesh: Mesh3 | None = None
        for feature in self.features:
            generated = _feature_to_mesh(feature, tolerance=tolerance)
            if generated is not None:
                mesh = generated
        if mesh is None:
            raise ValueError("body has no meshable features")
        return mesh

    def view(
        self,
        *,
        name: str | None = None,
        title: str | None = None,
        camera: Camera | None = None,
        style: DisplayStyle | None = None,
        light: Light | None = None,
        color: tuple[float, float, float] | None = None,
        render_mode: RenderMode | None = None,
        projection: Projection = "orthographic",
        center: bool = True,
        tolerance: float = 1e-3,
    ) -> None:
        from cady.view.viewer import open_target_view

        open_target_view(
            self,
            name=name,
            title=title,
            camera=camera,
            style=style,
            light=light,
            color=color,
            render_mode=render_mode,
            projection=projection,
            center=center,
            tolerance=tolerance,
        )

    def _last_region_feature(self) -> RegionFeature:
        for feature in reversed(self.features):
            if isinstance(feature, RegionFeature):
                return feature
        raise ValueError("region is required when body has no stored region")


def _primitive_to_mesh(feature: PrimitiveFeature, *, tolerance: float) -> Mesh3:
    parameters = feature.parameters
    if feature.kind == "box":
        return box_mesh(
            feature.plane,
            width=parameters["width"],
            depth=parameters["depth"],
            height=parameters["height"],
        )
    if feature.kind == "cylinder":
        return cylinder_mesh(
            feature.plane,
            radius=parameters["radius"],
            height=parameters["height"],
            tolerance=tolerance,
        )
    if feature.kind == "sphere":
        return sphere_mesh(feature.plane, radius=parameters["radius"], tolerance=tolerance)
    raise NotImplementedError(f"{feature.kind} primitive evaluation is not implemented")


def _feature_to_mesh(feature: Feature, *, tolerance: float) -> Mesh3 | None:
    if isinstance(feature, RegionFeature):
        return None
    if isinstance(feature, PrimitiveFeature):
        return _primitive_to_mesh(feature, tolerance=tolerance)
    if isinstance(feature, ExtrudeFeature):
        return extrusion_mesh(
            feature.region,
            feature.plane,
            distance=feature.distance,
            tolerance=tolerance,
        )
    if isinstance(feature, RevolveFeature):
        raise NotImplementedError("revolve feature evaluation is not implemented")
    if isinstance(feature, BooleanFeature):
        raise NotImplementedError("boolean feature evaluation is not implemented")
    operation = "fillet" if isinstance(feature, FilletFeature) else "chamfer"
    raise NotImplementedError(f"{operation} feature evaluation is not implemented")


def _transform_feature(feature: Feature, transform: Transform3) -> Feature:
    if isinstance(
        feature,
        (RegionFeature, ExtrudeFeature, PrimitiveFeature, RevolveFeature),
    ):
        return replace(feature, plane=feature.plane.transformed(transform))
    return feature


def _validate_region(region: object) -> None:
    if not callable(getattr(region, "loops", None)) and not callable(
        getattr(region, "to_array", None)
    ):
        raise TypeError(
            "region must provide loops(tolerance=...) or to_array(tolerance=...)"
        )


def _validate_plane(plane: object) -> None:
    if not isinstance(plane, Plane3):
        raise TypeError("feature plane must be a Plane3")


def _validate_feature_history(features: tuple[Feature, ...]) -> None:
    region_seen = False
    generator_seen = False
    for feature in features:
        if type(feature) not in _FEATURE_TYPES:
            raise TypeError(f"unsupported feature {type(feature).__name__}")
        if isinstance(feature, RegionFeature):
            if region_seen:
                raise ValueError("body can contain at most one pending region feature")
            if generator_seen:
                raise ValueError("region feature must precede the solid generator")
            region_seen = True
        elif isinstance(feature, _GENERATOR_TYPES):
            if generator_seen:
                raise ValueError(
                    "body can contain only one solid generator; use "
                    "Part.with_bodies(...) for independent solids or an explicit "
                    "boolean operation"
                )
            generator_seen = True
        else:
            if not generator_seen:
                raise ValueError("body modifier requires a solid generator")
