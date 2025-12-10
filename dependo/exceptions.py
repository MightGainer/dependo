class DIException(Exception):
    """Base class for all dependency-injection-related exceptions."""

    pass


class ServiceNotRegisteredException(DIException):
    """Raised when an attempt is made to resolve an unregistered service."""

    def __init__(self, service_type: type):
        super().__init__(f"Service '{service_type.__name__}' is not registered.")


class FrozenCollectionException(DIException):
    """Raised when attempting to modify a frozen ServiceCollection."""

    def __init__(self):
        super().__init__("Cannot modify a frozen service collection.")


class InvalidLifetimeException(DIException):
    """Raised when an invalid lifetime value is used in registration."""

    def __init__(self, lifetime: str):
        super().__init__(f"Invalid lifetime '{lifetime}'.")


class MissingTypeAnnotationException(DIException):
    """Raised when a required constructor/function argument is missing a type hint."""

    def __init__(self, param_name: str, target: object):
        name = getattr(target, "__name__", str(target))
        super().__init__(f"Missing type annotation for parameter '{param_name}' in {name}().")


class CircularDependencyException(DIException):
    """Raised when a circular dependency chain is detected."""

    def __init__(self, chain: str):
        super().__init__(f"Circular dependency detected: {chain}")
