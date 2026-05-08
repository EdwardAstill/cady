class CadError(Exception):
    """Base class for pyseas-cad scene and writer failures."""


class SceneError(CadError):
    """Raised when a shape is added to an incompatible scene."""


class WriteError(CadError):
    """Raised when CAD serialisation cannot complete."""
