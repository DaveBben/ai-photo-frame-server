"""Custom exceptions for local_shazam."""


class LocalShazamError(Exception):
    """Base exception for local_shazam errors."""


class ConfigurationError(LocalShazamError):
    """Raised when configuration is invalid."""


class ServiceError(LocalShazamError):
    """Raised when an external service call fails."""
