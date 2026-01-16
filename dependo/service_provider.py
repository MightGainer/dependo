from __future__ import annotations

import inspect
import threading
import types
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from inspect import _empty
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from .service_descriptor import ServiceDescriptor

try:
    # Python 3.11+
    from typing import ParamSpec, Protocol, overload
except ImportError:
    from typing_extensions import ParamSpec, Protocol, overload  # type: ignore

from .exceptions import (
    CircularDependencyException,
    DIException,
    MissingTypeAnnotationException,
    ServiceNotRegisteredException,
)
from .lifetime import Lifetime
from .service_collection import ServiceCollection
from .service_scope import ServiceScope

# ==========================================================
# Internal iterative dependency resolution structures
# ==========================================================


class _ResolutionState(Enum):
    """Represents the state of a dependency resolution task."""

    PENDING = "pending"
    RESOLVING = "resolving"
    RESOLVED = "resolved"


@dataclass
class _ResolutionTask:
    """
    Represents a single dependency resolution job used in the iterative resolver.

    Parameters
    ----------
    service_type : type
        The abstract type being requested.
    implementation : Any
        The implementation or factory used to instantiate the service.
    lifetime : str
        The lifetime type ('singleton', 'scoped', 'transient').
    resolved_dependencies : dict[str, Any]
        Already resolved dependencies required by this implementation.
    state : _ResolutionState
        Current task status (pending, resolving, or resolved).
    result : Any | None
        The resolved instance returned after instantiation.
    """

    service_type: Type
    implementation: Any
    lifetime: str
    resolved_dependencies: dict[str, Any]
    state: _ResolutionState = _ResolutionState.PENDING
    result: Any | None = None


T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")


class _CallableInjector(Protocol):
    """Protocol definition for callable injection."""

    @overload
    def __call__(self, __func: Callable[P, R]) -> Callable[P, R]: ...
    @overload
    def __call__(self, __func: Callable[..., Any]) -> Callable[..., Any]: ...


# ==========================================================
# Service Provider (core DI container)
# ==========================================================


class ServiceProvider:
    """
    Core dependency injection container responsible for service resolution, lifetime handling,
    and dependency injection for functions and classes.

    Parameters
    ----------
    collection : ServiceCollection
        The service registrations to initialize from.
    skip_if_default : bool, optional
        Skip injecting parameters with a default value (default: True).
    skip_if_not_registered : bool, optional
        Skip unknown dependencies instead of raising errors (useful for frameworks such as FastAPI).
    skip_if_no_annotation : bool, optional
        Skip parameters lacking type hints instead of raising (default: True).

    Notes
    -----
    - Singletons are cached globally within the provider.
    - Scoped services are cached per `ServiceScope` instance.
    """

    def __init__(
        self,
        collection: ServiceCollection,
        *,
        skip_if_default: bool = True,
        skip_if_not_registered: bool = True,
        skip_if_no_annotation: bool = True,
    ):
        self._collection = collection
        self._collection.freeze()  # Prevent modifications after initialization
        self._services = collection.services

        self._singletons: Dict[Tuple[Any, Optional[str]], Any] = {}
        self._singleton_lock = threading.Lock()

        # Injection policy configuration
        self.skip_if_default = skip_if_default
        self.skip_if_not_registered = skip_if_not_registered
        self.skip_if_no_annotation = skip_if_no_annotation

    # ======================================================
    # Public service resolution
    # ======================================================

    def get_service(self, service_type: Type, name: str | None = None) -> Any:
        """
        Retrieve a single instance of a registered service.

        Raises
        ------
        ServiceNotRegisteredException
            If the service type is not registered.

        Returns
        -------
        Any
            The resolved instance.
        """
        instances = self._resolve_all(service_type, name=name, scope=None)
        if not instances:
            raise ServiceNotRegisteredException(service_type)
        return instances[-1]
    
    def try_get_service(self, service_type: Type, name: str | None = None) -> Any | None:
        """
        Retrieve a single instance of a registered service or None if the service type is not registered.

        Returns
        -------
        Any
            The resolved instance or None if the service type is not registered.
        """
        instances = self._resolve_all(service_type, name=name, scope=None)
        if not instances:
            return None

        return instances[-1]

    def get_services(self, service_type: Type, name: str | None = None) -> List[Any]:
        """Return all registered implementations for a given type."""
        return self._resolve_all(service_type, name, scope=None)

    def create_scope(self) -> ServiceScope:
        """Create and return a new scope for resolving scoped services."""
        return ServiceScope(self)

    # ======================================================
    # Injection decorators
    # ======================================================

    def injector(self) -> _CallableInjector:
        """
        Callable decorator that automatically injects missing parameters using a new scope per call.

        Notes
        -----
        - Creates a new scope for each invocation.
        - Injects missing dependencies using registered types.
        - Recommended default decorator for DI-enabled callables.

        Raises
        ------
        TypeError
            If applied to a class instead of a callable.
        """

        def decorator(func: Callable[..., Any]):
            if inspect.isclass(func):
                raise TypeError(
                    "injector() can only decorate callables. " "For class injection, use class_factory(cls, use_scope=True)."
                )
            return self._inject_function(func, use_scope=True)

        return decorator

    def scopeless_injector(self) -> _CallableInjector:
        """
        Callable decorator that injects dependencies without creating a scope.

        Warning
        -------
        This method should be avoided unless necessary. Scoped services will not work.
        """

        def decorator(func: Callable[..., Any]):
            if inspect.isclass(func):
                raise TypeError(
                    "scopeless_injector() can only decorate functions. " "Use ServiceProvider.class_factory(...) for classes."
                )
            return self._inject_function(func, use_scope=False)

        return decorator

    def class_factory(self, cls: Type[T], *, use_scope: bool = True) -> Callable[..., T]:
        """
        Return a factory function for constructing classes with injected constructor dependencies.

        Automatically:
        - Injects missing constructor arguments.
        - Assigns `_provider` to the created instance.
        - Performs property injection.

        Parameters
        ----------
        cls : Type[T]
            The class to be created.
        use_scope : bool, optional
            Whether to use a new scope per creation (default: True).

        Returns
        -------
        Callable[..., T]
            Factory function returning fully injected class instances.
        """
        original_init = cls.__init__

        def factory(*args: Any, **kwargs: Any) -> T:
            if use_scope:
                with self.create_scope() as scope:
                    self._inject_into_signature(original_init, args, kwargs, skip_params={"self"}, scope=scope)
                    instance = cls(*args, **kwargs)
                    setattr(instance, "_provider", self)
                    self._inject_properties(instance, scope=scope)
                    return instance
            else:
                self._inject_into_signature(original_init, args, kwargs, skip_params={"self"}, scope=None)
                instance = cls(*args, **kwargs)
                setattr(instance, "_provider", self)
                self._inject_properties(instance, scope=None)
                return instance

        return factory

    # ======================================================
    # Internal: wrapping functions/coroutines for DI
    # ======================================================

    def _inject_function(self, func: Callable[P, R], use_scope: bool = False) -> Callable[P, R]:
        """
        Wrap a callable or coroutine for automatic dependency injection.

        Parameters
        ----------
        func : Callable[P, R]
            The callable to decorate.
        use_scope : bool
            Whether to create a new scope per invocation.

        Returns
        -------
        Callable[P, R]
            Wrapper that performs DI resolution before call.
        """
        sig = inspect.signature(func)
        skip_params = set()
        params = list(sig.parameters.values())
        if params and params[0].name in ("self", "cls"):
            skip_params.add(params[0].name)

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                if use_scope:
                    async with self.create_scope() as scope:
                        self._inject_into_signature(func, args, kwargs, skip_params=skip_params, scope=scope)
                        return await func(*args, **kwargs)
                else:
                    self._inject_into_signature(func, args, kwargs, skip_params=skip_params, scope=None)
                    return await func(*args, **kwargs)

            return wrapper  # type: ignore
        else:

            @wraps(func)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                if use_scope:
                    with self.create_scope() as scope:
                        self._inject_into_signature(func, args, kwargs, skip_params=skip_params, scope=scope)
                        return func(*args, **kwargs)
                else:
                    self._inject_into_signature(func, args, kwargs, skip_params=skip_params, scope=None)
                    return func(*args, **kwargs)

            return wrapper  # type: ignore

    # ======================================================
    # Core service resolution logic
    # ======================================================

    def _resolve_all(self, service_type: Type, name: str | None, scope: Optional[ServiceScope]) -> List[Any]:
        """Resolve all implementations for the given service type (optionally filtered by `name`)."""
        key = (service_type, name)
        descriptors = self._services.get(key, [])
        results: List[Any] = []
        for desc in descriptors:
            results.append(self._resolve_descriptor_iterative(desc, service_type, name, scope))
        return results

    def _resolve_descriptor_iterative(
        self, descriptor: ServiceDescriptor, root_type: Type, name: str | None, scope: Optional[ServiceScope]
    ) -> Any:
        """Resolve a service descriptor iteratively, respecting its lifetime."""
        impl = descriptor.implementation
        lifetime = descriptor.lifetime
        cache_key = (descriptor, name)

        if lifetime == Lifetime.SINGLETON.value:
            with self._singleton_lock:
                if cache_key in self._singletons:
                    return self._singletons[cache_key]
                instance = self._resolve_iteratively(root_type, impl, lifetime, scope)
                self._singletons[cache_key] = instance
                return instance

        elif lifetime == Lifetime.SCOPED.value:
            if scope is None:
                raise DIException(f"Cannot resolve scoped service '{root_type.__name__}' outside of a scope.")
            if cache_key in scope._scoped_cache:
                return scope._scoped_cache[cache_key]
            instance = self._resolve_iteratively(root_type, impl, lifetime, scope)
            scope._scoped_cache[cache_key] = instance
            return instance

        else:
            return self._resolve_iteratively(root_type, impl, lifetime, scope)

    def _resolve_iteratively(self, service_type: Type, implementation: Any, lifetime: str, scope: Optional[ServiceScope]) -> Any:
        """
        Iteratively resolve dependencies without recursion (prevents call stack overflow).

        Raises
        ------
        CircularDependencyException
            If circular references are detected between registered types.
        """
        root_task = _ResolutionTask(service_type, implementation, lifetime, resolved_dependencies={})
        task_stack = [root_task]
        resolved_cache: dict[Type, Any] = {}
        resolution_path: list[Type] = []

        while task_stack:
            task = task_stack[-1]

            # Handle resolved items
            if task.state == _ResolutionState.RESOLVED:
                task_stack.pop()
                resolved_cache[task.service_type] = task.result
                if task.service_type in resolution_path:
                    resolution_path.remove(task.service_type)
                continue

            if task.state == _ResolutionState.PENDING:
                # Circular detection
                if task.service_type in resolution_path:
                    chain = " -> ".join([c.__name__ for c in [*resolution_path, task.service_type]])
                    raise CircularDependencyException(chain)
                resolution_path.append(task.service_type)
                task.state = _ResolutionState.RESOLVING

                deps = self._get_dependencies(task.implementation)
                all_ready = True

                for pname, dep_type in deps.items():
                    # Handle special cases explicitly
                    if dep_type is ServiceProvider:
                        task.resolved_dependencies[pname] = self
                        continue
                    if dep_type is ServiceScope:
                        if scope is None:
                            raise DIException(f"Cannot inject ServiceScope outside of scope for {task.service_type.__name__}")
                        task.resolved_dependencies[pname] = scope
                        continue

                    selected_dep_base, is_optional = self._select_union_or_optional(dep_type)

                    if selected_dep_base in resolved_cache:
                        task.resolved_dependencies[pname] = resolved_cache[selected_dep_base]
                        continue

                    desc_list = self._services.get((selected_dep_base, None))
                    if not desc_list:
                        if is_optional:
                            task.resolved_dependencies[pname] = None
                            continue
                        raise ServiceNotRegisteredException(selected_dep_base)

                    dep_desc = desc_list[-1]
                    all_ready = False
                    task_stack.append(_ResolutionTask(selected_dep_base, dep_desc.implementation, dep_desc.lifetime, {}))

                if all_ready:
                    task.result = self._instantiate(task, scope)
                    task.state = _ResolutionState.RESOLVED
                continue

            if task.state == _ResolutionState.RESOLVING:
                deps = self._get_dependencies(task.implementation)
                for pname, dep_type in deps.items():
                    if pname not in task.resolved_dependencies:
                        selected_dep_base, _ = self._select_union_or_optional(dep_type)
                        if selected_dep_base in resolved_cache:
                            task.resolved_dependencies[pname] = resolved_cache[selected_dep_base]
                task.result = self._instantiate(task, scope)
                task.state = _ResolutionState.RESOLVED

        return root_task.result

    # ======================================================
    # Dependency Analysis & Instantiation
    # ======================================================

    def _get_dependencies(self, implementation: Any) -> dict[str, Type]:
        deps: dict[str, Type] = {}
        target = None
        if inspect.isclass(implementation):
            target = getattr(implementation, "__init__", None)
        elif isinstance(implementation, types.FunctionType):
            target = implementation
        elif isinstance(implementation, types.MethodType):
            target = implementation.__func__

        if target is None:
            return deps

        # If the target is a built-in wrapper (no __globals__/__annotations__), skip
        try:
            sig = inspect.signature(target)
        except Exception:
            return deps

        # get_type_hints may fail for builtins; fall back to __annotations__ or {}.
        try:
            hints = get_type_hints(target, globalns=getattr(target, "__globals__", getattr(implementation, "__dict__", {})))
        except Exception:
            hints = getattr(target, "__annotations__", {}) or {}

        for pname, param in sig.parameters.items():
            if pname == "self":
                continue
            if param.default != inspect.Parameter.empty and self.skip_if_default:
                continue
            ann = hints.get(pname, param.annotation)
            if ann is _empty:
                continue
            deps[pname] = ann
        return deps

    def _instantiate(self, task: _ResolutionTask, scope: Optional[ServiceScope]) -> Any:
        """Instantiate a dependency instance from the given task and resolved kwargs."""
        impl = task.implementation
        kwargs = task.resolved_dependencies

        if not callable(impl):
            return impl
        if inspect.isclass(impl):
            instance = impl(**kwargs)
            setattr(instance, "_provider", self)
            self._inject_properties(instance, scope)
            return instance
        if isinstance(impl, (types.FunctionType, types.MethodType)):
            return impl(**kwargs)
        return impl

    # ======================================================
    # Helpers and property-level DI
    # ======================================================

    def _select_union_or_optional(self, tp: Any) -> tuple[Type, bool]:
        """Select a concrete type from Union/Optional annotations."""
        origin = get_origin(tp)
        if origin in (Union, types.UnionType):
            args = list(get_args(tp))
            is_optional = type(None) in args
            candidate_types = [a for a in args if a is not type(None)]
            for cand in candidate_types:
                if (cand, None) in self._services and self._services[(cand, None)]:
                    return cand, is_optional
            if candidate_types:
                return candidate_types[0], is_optional
            return type(None), True
        return tp, False

    def _safe_get(self, dep_type: Type, scope: Optional[ServiceScope]) -> Any:
        """Safely retrieve special-case dependencies (ServiceProvider, ServiceScope)."""
        if dep_type is ServiceProvider:
            return self
        if dep_type is ServiceScope:
            if scope is None:
                raise DIException("Cannot inject ServiceScope outside of scope.")
            return scope
        return self.get_service(dep_type)

    def _inject_properties(self, instance: Any, scope: Optional[ServiceScope]) -> None:
        """Perform property-level injection on specially decorated `@inject` properties."""
        cls_dict = vars(instance.__class__)
        for name, prop in cls_dict.items():
            if prop is None or not isinstance(prop, property) or not getattr(prop.fget, "__di_inject__", False):
                continue
            hints = get_type_hints(prop.fget, globalns=prop.fget.__globals__)
            dep_type = hints.get("return")
            if dep_type is None or dep_type is _empty:
                if self.skip_if_no_annotation:
                    continue
                raise MissingTypeAnnotationException("return", prop.fget)
            selected_dep_base, is_opt = self._select_union_or_optional(dep_type)
            try:
                dep = self._safe_get(selected_dep_base, scope)
            except ServiceNotRegisteredException:
                if is_opt:
                    dep = None
                else:
                    raise
            setattr(instance, f"_{name}", dep)

    def dispose(self) -> None:
        """Clean up all cached singleton instances and call their `dispose()` or `close()` methods."""
        for inst in list(self._singletons.values()):
            for m in ("close", "dispose", "__exit__"):
                fn = getattr(inst, m, None)
                if callable(fn):
                    try:
                        if m == "__exit__":
                            fn(None, None, None)
                        else:
                            fn()
                    except Exception:
                        pass
        self._singletons.clear()

    # ======================================================
    # Parameter-level injection into signatures
    # ======================================================

    def _inject_into_signature(
        self,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        skip_params: Set[str] | None = None,
        scope: Optional[ServiceScope] = None,
    ) -> None:
        """
        Inject missing callable parameters according to provider policies.

        Notes
        -----
        - Respects skip_if_default, skip_if_not_registered, skip_if_no_annotation.
        - Handles Optional and Union[T1, T2].
        - Does not use named registrations implicitly.
        """
        skip_params = skip_params or set()
        sig = inspect.signature(func)
        hints = get_type_hints(func, globalns=func.__globals__)

        bound = sig.bind_partial(*args, **kwargs)
        provided = set(bound.arguments.keys()) - skip_params

        for name, param in sig.parameters.items():
            if name in skip_params or name in provided:
                continue

            ann = hints.get(name, param.annotation)
            if ann is _empty:
                if self.skip_if_no_annotation:
                    continue
                raise MissingTypeAnnotationException(name, func)

            has_default = param.default != inspect.Parameter.empty
            if has_default and self.skip_if_default:
                continue

            selected_dep_base, is_opt = self._select_union_or_optional(ann)

            if selected_dep_base is ServiceProvider:
                kwargs[name] = self
                continue
            if selected_dep_base is ServiceScope:
                if scope is None:
                    if self.skip_if_not_registered or is_opt or has_default:
                        continue
                    raise DIException("Cannot inject ServiceScope outside of scope.")
                kwargs[name] = scope
                continue

            desc_list = self._services.get((selected_dep_base, None))
            if not desc_list:
                if self.skip_if_not_registered:
                    if has_default:
                        kwargs[name] = param.default
                    elif is_opt:
                        kwargs[name] = None
                    continue
                if is_opt:
                    kwargs[name] = None
                    continue
                raise ServiceNotRegisteredException(selected_dep_base)

            dep_desc = desc_list[-1]  # last registration wins
            value = self._resolve_descriptor_iterative(dep_desc, selected_dep_base, None, scope)
            kwargs[name] = value
