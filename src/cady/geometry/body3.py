"""Editable solid bodies composed from inline feature records."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, Protocol, TypeAlias, cast

from cady.geometry.mesh import Mesh3
from cady.geometry.plane3 import Plane3
from cady.operations.meshes import (
    box_mesh,
    cylinder_mesh,
    extrusion_mesh,
    sphere_mesh,
)
from cady.operations.transforms import Transform3
from cady.utils import finite, positive

Point3: TypeAlias = tuple[float, float, float]

if TYPE_CHECKING:
    from cady.view import Camera, DisplayStyle, Light
    from cady.view.open_view import Projection
    from cady.view.style import RenderMode

PrimitiveKind = Literal["box", "cylinder", "sphere", "cone"]
BooleanKind = Literal["union", "difference", "intersection"]


class Feature(Protocol):
    """Marker protocol for body construction records."""

    pass


@dataclass(frozen=True, slots=True)
class RegionFeature:
    """Stored source region placed in a 3D plane."""

    region: object
    plane: Plane3


@dataclass(frozen=True, slots=True)
class ExtrudeFeature:
    """Linear sweep of a region along its plane normal."""

    region: object
    plane: Plane3
    distance: float

    def __post_init__(self) -> None:
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


MeshEvaluator: TypeAlias = Callable[[Feature, float], Mesh3 | None]
TransformEvaluator: TypeAlias = Callable[[Feature, Transform3], Feature]


@dataclass(frozen=True, slots=True)
class Body3:
    """Semantic 3D body defined by an ordered feature history."""

    name: str | None = None
    features: tuple[Feature, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=lambda: {})

    def __post_init__(self) -> None:
        object.__setattr__(self, "features", tuple(self.features))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def from_region(
        cls,
        region: object,
        *,
        plane: Plane3 | None = None,
    ) -> Body3:
        return cls(features=(RegionFeature(region, plane or Plane3.world_xy()),))

    @classmethod
    def box(
        cls,
        *,
        width: float,
        depth: float,
        height: float,
        plane: Plane3 | None = None,
    ) -> Body3:
        return cls(
            features=(
                PrimitiveFeature(
                    "box",
                    {"width": width, "depth": depth, "height": height},
                    plane or Plane3.world_xy(),
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
        return cls(
            features=(
                PrimitiveFeature(
                    "cylinder",
                    {"radius": radius, "height": height},
                    plane or Plane3.world_xy(),
                ),
            )
        )

    @classmethod
    def sphere(
        cls,
        *,
        radius: float,
        centre: Point3 = (0.0, 0.0, 0.0),
    ) -> Body3:
        return cls(
            features=(
                PrimitiveFeature(
                    "sphere",
                    {"radius": radius},
                    Plane3.from_normal(centre, (0.0, 0.0, 1.0)),
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
            resolved_plane = plane or region_feature.plane
        else:
            resolved_region = region
            resolved_plane = plane or Plane3.world_xy()
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
        meshes: list[Mesh3] = []
        for feature in self.features:
            mesh = _feature_to_mesh(feature, tolerance=tolerance)
            if mesh is not None:
                meshes.append(mesh)
        if not meshes:
            raise ValueError("body has no meshable features")
        return Mesh3.merged(meshes)

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
        from cady.view.open_view import open_target_view

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


def _region_feature_to_mesh(_feature: Feature, _tolerance: float) -> Mesh3 | None:
    return None


def _extrude_feature_to_mesh(feature: Feature, tolerance: float) -> Mesh3:
    extrude = cast(ExtrudeFeature, feature)
    return extrusion_mesh(
        extrude.region,
        extrude.plane,
        distance=extrude.distance,
        tolerance=tolerance,
    )


def _revolve_feature_to_mesh(_feature: Feature, _tolerance: float) -> Mesh3:
    raise NotImplementedError("revolve feature evaluation is not implemented")


def _boolean_feature_to_mesh(_feature: Feature, _tolerance: float) -> Mesh3:
    raise NotImplementedError("boolean feature evaluation is not implemented")


def _edge_finish_feature_to_mesh(_feature: Feature, _tolerance: float) -> Mesh3:
    raise NotImplementedError("fillet and chamfer feature evaluation is not implemented")


def _feature_to_mesh(feature: Feature, *, tolerance: float) -> Mesh3 | None:
    evaluator = _FEATURE_MESH_EVALUATORS.get(type(feature))
    if evaluator is None:
        raise TypeError(f"unsupported feature {type(feature).__name__}")
    return evaluator(feature, tolerance)


def _transform_feature_plane(feature: Feature, transform: Transform3) -> Feature:
    plane_feature = cast(
        RegionFeature | ExtrudeFeature | PrimitiveFeature | RevolveFeature,
        feature,
    )
    return replace(plane_feature, plane=plane_feature.plane.transformed(transform))


def _transform_feature(feature: Feature, transform: Transform3) -> Feature:
    transformer = _FEATURE_TRANSFORMERS.get(type(feature))
    if transformer is None:
        return feature
    return transformer(feature, transform)


_FEATURE_MESH_EVALUATORS: Mapping[type[object], MeshEvaluator] = MappingProxyType(
    {
        RegionFeature: _region_feature_to_mesh,
        PrimitiveFeature: lambda feature, tolerance: _primitive_to_mesh(
            cast(PrimitiveFeature, feature),
            tolerance=tolerance,
        ),
        ExtrudeFeature: _extrude_feature_to_mesh,
        RevolveFeature: _revolve_feature_to_mesh,
        BooleanFeature: _boolean_feature_to_mesh,
        FilletFeature: _edge_finish_feature_to_mesh,
        ChamferFeature: _edge_finish_feature_to_mesh,
    }
)


_FEATURE_TRANSFORMERS: Mapping[type[object], TransformEvaluator] = MappingProxyType(
    {
        RegionFeature: _transform_feature_plane,
        ExtrudeFeature: _transform_feature_plane,
        PrimitiveFeature: _transform_feature_plane,
        RevolveFeature: _transform_feature_plane,
    }
)
