class CadError(Exception):
    """Base class for cady scene and writer failures."""


class SceneError(CadError):
    """Raised when a shape is added to an incompatible scene."""


class ReadError(CadError):
    """Raised when CAD input cannot be parsed into cady objects."""


class WriteError(CadError):
    """Raised when CAD serialisation cannot complete."""
