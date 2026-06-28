"""Shared exception hierarchy for cady packages."""

class CadError(Exception):
    """Base class for cady failures."""


class GeometryError(CadError):
    """Raised when geometry is invalid or cannot be evaluated."""


class DrawingError(CadError):
    """Raised when drawing composition is invalid."""


class ProductError(CadError):
    """Raised when part or assembly structure is invalid."""


class ViewError(CadError):
    """Raised when scene, camera, or light state is invalid."""


class ReadError(CadError):
    """Raised when CAD input cannot be parsed into cady objects."""


class WriteError(CadError):
    """Raised when CAD serialisation cannot complete."""
