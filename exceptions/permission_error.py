class PermissionError(Exception):
    """Raised when an authenticated user lacks ownership of a resource — maps to HTTP 403."""
    pass
