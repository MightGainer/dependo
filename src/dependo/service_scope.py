from typing import Any, Dict, Optional, Tuple, Type

from .exceptions import ServiceNotRegisteredException
from .service_descriptor import ServiceDescriptor


class ServiceScope:
    """
    Provides a **scoped lifetime context** for resolving dependencies that are
    registered as *scoped* in a `ServiceProvider`.

    When created (via `provider.create_scope()`), the scope acts as an isolated
    cache for services with `Lifetime.SCOPED`. Once disposed, all cached
    instances are released and optionally closed.

    Typical usage:
    ---------------
    ```python
    provider = ServiceProvider(collection)
    with provider.create_scope() as scope:
        svc = scope.get_service(MyScopedService)
    ```

    The scope supports both synchronous and asynchronous context management.
    """

    def __init__(self, provider: "ServiceProvider") -> None:  # type: ignore
        """
        Initialize a new service resolution scope for the specified provider.

        Parameters
        ----------
        provider : ServiceProvider
            The parent provider used to resolve dependencies within this scope.
        """
        self._provider = provider
        self._scoped_cache: Dict[Tuple[ServiceDescriptor, Optional[str]], Any] = {}

    # ======================================================
    # Public service resolution
    # ======================================================

    def get_service(self, service_type: Type, name: str | None = None) -> Any:
        """
        Resolve a service instance within this scope.

        - If a corresponding singleton or scoped registration exists, it is
          reused or created as needed.
        - If no registration exists and the provider’s policy
          `skip_if_not_registered` is `True`, returns `None`.
        - Otherwise, raises `ServiceNotRegisteredException`.

        Parameters
        ----------
        service_type : Type
            The abstract/interface type to resolve.
        name : str | None, optional
            The named registration to resolve (optional).

        Returns
        -------
        Any
            The resolved service instance or `None` if skipped.
        """
        instances = self._provider._resolve_all(service_type, name, scope=self)
        if not instances:
            if self._provider.skip_if_not_registered:
                return None
            else:
                raise ServiceNotRegisteredException(service_type)
        return instances[-1]

    # ======================================================
    # Context manager support (sync + async)
    # ======================================================

    def __enter__(self):
        """
        Enter the synchronous context manager, returning itself.

        Returns
        -------
        ServiceScope
            The scope instance itself.
        """
        return self

    def __exit__(self, exc_type, exc, tb):
        """
        Exit the synchronous context manager and dispose of scoped instances.

        Ensures cleanup by calling `dispose()` even if exceptions occurred.
        """
        self.dispose()

    async def __aenter__(self):
        """
        Enter an asynchronous context (`async with`) returning self.

        Returns
        -------
        ServiceScope
            The scope instance itself.
        """
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """
        Exit the asynchronous context manager and dispose of scoped instances.
        """
        self.dispose()

    # ======================================================
    # Disposal / cleanup
    # ======================================================

    def dispose(self) -> None:
        """
        Dispose all services cached in this scope.

        Each cached instance is checked for the following methods:
        `close()`, `dispose()`, and `__exit__`. If found, these methods are
        called in a best-effort manner (exceptions are suppressed).
        """
        for inst in list(self._scoped_cache.values()):
            for method in ("close", "dispose", "__exit__"):
                fn = getattr(inst, method, None)
                if callable(fn):
                    try:
                        fn()
                    except Exception:
                        pass
        self._scoped_cache.clear()
