class ServiceError(RuntimeError):
    """Base service-layer error."""


class PlayerReadServiceError(ServiceError):
    """Read use-case error."""


class PlayerRefreshServiceError(ServiceError):
    """Refresh use-case error."""
