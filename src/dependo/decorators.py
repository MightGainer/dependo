from __future__ import annotations

import inspect
from typing import Optional, get_type_hints

from .exceptions import (
    DIException,
    MissingTypeAnnotationException,
    ServiceNotRegisteredException,
)
from .service_provider import ServiceProvider


def inject(provider: Optional[ServiceProvider] = None):
    """
    Property decorator that enables **lazy property injection** through a `ServiceProvider`.

    This decorator is used to mark properties whose values should be
    automatically resolved from a dependency injection container.

    Example
    -------
    ```python
    class MyComponent:
        @inject()
        def db(self) -> IDatabase:
            ...
    ```

    The first time `obj.db` is accessed:
    - The provider is located (explicitly or implicitly via `_provider` on instance).
    - The dependency type (`IDatabase`) is resolved from the provider.
    - The result is cached as a private attribute (`_db`).

    Parameters
    ----------
    provider : ServiceProvider, optional
        Explicit `ServiceProvider` instance to use for resolution.
        If omitted, the system will search for an attribute of type
        `ServiceProvider` on the instance (`_provider`, `provider`, `service_provider`).

    Raises
    ------
    DIException
        If no provider instance is available.
    MissingTypeAnnotationException
        If the property’s return type is not properly annotated.
    ServiceNotRegisteredException
        If the resolved dependency is not registered and is not optional.
    """

    def decorator(fn):
        attr_name = f"_{fn.__name__}"

        def _find_provider_on_instance(self) -> Optional[ServiceProvider]:
            """Try locating a provider from known attributes or instance dict."""
            for candidate in ("_provider", "provider", "service_provider"):
                if hasattr(self, candidate):
                    try:
                        val = getattr(self, candidate)
                    except Exception:
                        val = None
                    if isinstance(val, ServiceProvider):
                        return val
            try:
                for val in vars(self).values():
                    if isinstance(val, ServiceProvider):
                        return val
            except Exception:
                pass
            return None

        def wrapper(self):
            # Return cached value if already injected (by _inject_properties)
            if hasattr(self, attr_name):
                return getattr(self, attr_name)

            prov = provider if provider is not None else _find_provider_on_instance(self)
            if prov is None:
                raise DIException(
                    "No ServiceProvider available for property injection. "
                    "Pass a provider explicitly to @inject() or attach one to the instance."
                )

            # Resolve the dependency type (property return annotation)
            hints = get_type_hints(fn, globalns=fn.__globals__)
            dep_type = hints.get("return")
            if not dep_type or dep_type is inspect._empty:
                if getattr(prov, "skip_if_no_annotation", True):
                    return None  # do not cache, might be resolved later
                else:
                    raise MissingTypeAnnotationException("return", fn)
            else:
                selected_dep_base, is_opt = prov._select_union_or_optional(dep_type)
                try:
                    value = prov.get_service(selected_dep_base)
                except ServiceNotRegisteredException:
                    if is_opt:
                        value = None
                    else:
                        raise

            setattr(self, attr_name, value)
            return value

        prop = property(wrapper)
        prop.fget.__di_inject__ = True  # mark as DI-aware property
        return prop

    return decorator


def scoped_inject(provider: ServiceProvider):
    """
    Function decorator applying **scoped injection** per call (fast alias for `provider.injector()`).

    Example
    -------
    ```python
    @scoped_inject(provider)
    def handler(repo: IUserRepository):
        repo.do_something()
    ```

    Parameters
    ----------
    provider : ServiceProvider
        The provider whose scope policy is applied.

    Raises
    ------
    TypeError
        If applied to a class instead of a function.
    """

    def decorator(func):
        if inspect.isclass(func):
            raise TypeError(
                "scoped_inject decorates functions only. "
                "Use ServiceProvider.class_factory(cls, use_scope=True) for class construction."
            )
        return provider.injector()(func)

    return decorator


def scopeless_inject(provider: ServiceProvider):
    """
    Function decorator for callables that require DI without creating a new scope.

    This mirrors `ServiceProvider.scopeless_injector()` and should be used only
    for advanced or performance-critical scenarios, as scoped services will not
    be available.

    Raises
    ------
    TypeError
        If applied to a class instead of a callable.
    """

    def decorator(func):
        if inspect.isclass(func):
            raise TypeError(
                "scopeless_inject decorates functions only. "
                "Use ServiceProvider.class_factory(cls, use_scope=True) for class construction."
            )
        return provider.scopeless_injector()(func)

    return decorator
