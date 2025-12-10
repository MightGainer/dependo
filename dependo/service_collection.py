import types
from inspect import _empty, isclass, signature
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from .exceptions import (
    CircularDependencyException,
    FrozenCollectionException,
    InvalidLifetimeException,
)
from .lifetime import Lifetime
from .service_descriptor import ServiceDescriptor


class ServiceCollection:
    """
    Central registry of all services available to a `ServiceProvider`.

    This class allows you to **register dependencies** with different lifetimes
    before creating a `ServiceProvider`.

    Services can be added as:
        - Singletons (same instance across application lifetime)
        - Scoped (per `ServiceScope`)
        - Transient (new per resolution)

    Once the `ServiceProvider` is created, the collection becomes frozen and cannot
    be modified to preserve consistency between scopes.

    Example
    -------
    ```python
    services = ServiceCollection()
    services.add_singleton(IDatabase, Database)
    services.add_scoped(IRepository, Repository)
    provider = ServiceProvider(services)
    ```
    """

    def __init__(self) -> None:
        """Initialize an empty, modifiable service registry."""
        self._services: Dict[Tuple[Type, Optional[str]], List[ServiceDescriptor]] = {}
        self._frozen = False

    # ======================================================
    # Core add() method (internal utility)
    # ======================================================

    def _add(
        self,
        service_type: Type,
        implementation: Any,
        lifetime: str,
        name: str | None = None,
    ) -> None:
        """
        Internal helper registering a service descriptor.

        Parameters
        ----------
        service_type : Type
            The abstract/interface type being registered.
        implementation : Any
            The class or factory to be instantiated.
        lifetime : str
            One of the lifetimes from `Lifetime` enum (`singleton`, `scoped`, `transient`).
        name : str | None, optional
            Optional registration name (for named resolution).

        Raises
        ------
        FrozenCollectionException
            If the collection has been frozen.
        InvalidLifetimeException
            If a provided lifetime string is invalid.
        """
        if self._frozen:
            raise FrozenCollectionException()
        if lifetime not in (
            Lifetime.SINGLETON.value,
            Lifetime.SCOPED.value,
            Lifetime.TRANSIENT.value,
        ):
            raise InvalidLifetimeException(lifetime)

        key = (service_type, name)
        desc = ServiceDescriptor(implementation or service_type, lifetime)
        self._services.setdefault(key, []).append(desc)

    # ======================================================
    # Public API: registration methods
    # ======================================================

    def add_singleton(self, service_type: Type, implementation: Any = None, name: str | None = None):
        """
        Register a service with **singleton lifetime**.

        Parameters
        ----------
        service_type : Type
            The interface or abstract type.
        implementation : Any, optional
            The concrete implementation or instance factory.
            Defaults to the service type itself.
        name : str | None, optional
            Optional name for differentiated registration.
        """
        self._add(service_type, implementation or service_type, Lifetime.SINGLETON.value, name)
        return self

    def add_scoped(self, service_type: Type, implementation: Any = None, name: str | None = None):
        """
        Register a service with **scoped lifetime**.

        A new instance will be created per `ServiceScope` and cached until
        the scope is disposed.
        """
        self._add(service_type, implementation or service_type, Lifetime.SCOPED.value, name)
        return self

    def add_transient(self, service_type: Type, implementation: Any = None, name: str | None = None):
        """
        Register a service with **transient lifetime**.

        A new instance will be created for every resolution.
        """
        self._add(service_type, implementation or service_type, Lifetime.TRANSIENT.value, name)
        return self

    def add_singleton_instance(self, service_type: Type, instance: Any, name: str | None = None):
        """
        Register an already-created singleton instance.

        The instance itself will be reused permanently (no factory invocation).
        """
        self._add(service_type, instance, Lifetime.SINGLETON.value, name)
        return self

    # ======================================================
    # Freezing and dependency validation
    # ======================================================

    def freeze(self) -> None:
        """
        Freeze the collection to prevent further modifications.

        This is automatically called when a `ServiceProvider` is created.
        Also triggers a lightweight cycle detection to alert developers early.
        """
        self._frozen = True
        self._check_direct_cycles()

    def _check_direct_cycles(self) -> None:
        """
        Perform a lightweight **direct circular dependency check** at registration time.

        Detects simple two-class cycles such as:
            A → B and B → A

        Note: Deep or indirect cycles are detected dynamically at runtime.
        """
        deps: Dict[Type, list[Type]] = {}

        # Build a shallow dependency graph for all classes
        for (stype, _), lst in self._services.items():
            for desc in lst:
                impl = desc.implementation
                if isclass(impl):
                    target = getattr(impl, "__init__", None)
                    if target is None:
                        continue

                    # Safely compute signature and type hints
                    try:
                        sig = signature(target)
                    except Exception:
                        # If we cannot inspect it, skip (no annotations we can use)
                        continue

                    # Try to get type hints; fall back to raw __annotations__; else empty
                    try:
                        globalns = getattr(target, "__globals__", getattr(impl, "__dict__", {}))
                        hints = get_type_hints(target, globalns=globalns)
                    except Exception:
                        hints = getattr(target, "__annotations__", {}) or {}

                    for name, param in sig.parameters.items():
                        if name == "self":
                            continue
                        ann = hints.get(name, param.annotation)
                        if ann is _empty:
                            continue

                        # Handle Optional/Union annotations
                        origin = get_origin(ann)
                        if origin in (Union, types.UnionType):
                            args = [a for a in get_args(ann) if a is not type(None)]

                            # Prefer the first registered type that exists in the collection
                            chosen = None
                            for cand in args:
                                if (cand, None) in self._services and self._services[(cand, None)]:
                                    chosen = cand
                                    break
                            if chosen is None and args:
                                chosen = args[0]  # fallback to first non-None
                            if chosen is not None:
                                ann = chosen

                        deps.setdefault(stype, []).append(ann)

        # Check mutual dependencies A <-> B
        for a, lst2 in deps.items():
            for b in lst2:
                if b in deps and a in deps.get(b, []):
                    raise CircularDependencyException(f"{a.__name__} <-> {b.__name__}")

    # ======================================================
    # Accessor
    # ======================================================

    @property
    def services(self) -> Dict[Tuple[Type, str | None], List[ServiceDescriptor]]:
        """
        Return the internal dictionary of service registrations.

        Returns
        -------
        Dict[Tuple[Type, str | None], List[ServiceDescriptor]]
            Mapping between (type, name) pair and registered descriptors.
        """
        return self._services
