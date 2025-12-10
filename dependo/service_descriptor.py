from typing import Any


class ServiceDescriptor:
    """
    Represents a single service registration (type + lifetime + implementation).

    This is created internally during `ServiceCollection.add_*()` calls.
    """

    def __init__(self, implementation: Any, lifetime: str) -> None:
        """
        Construct a new ServiceDescriptor.

        Parameters
        ----------
        implementation : Any
            The implementing class, callable, or prebuilt instance.
        lifetime : str
            The lifetime type (singleton, scoped, transient).
        """
        self.implementation = implementation
        self.lifetime = lifetime

    def __repr__(self) -> str:
        """Human-readable representation for debugging."""
        return f"ServiceDescriptor({self.implementation!r}, lifetime={self.lifetime})"
