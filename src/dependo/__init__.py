from .decorators import inject, scoped_inject, scopeless_inject
from .exceptions import *
from .lifetime import Lifetime
from .service_collection import ServiceCollection
from .service_descriptor import ServiceDescriptor
from .service_provider import ServiceProvider
from .service_scope import ServiceScope

__all__ = [
    # Core
    "ServiceProvider",
    "ServiceScope",
    "ServiceCollection",
    "ServiceDescriptor",
    "Lifetime",
    # Exceptions
    "DIException",
    "ServiceNotRegisteredException",
    "FrozenCollectionException",
    "InvalidLifetimeException",
    "MissingTypeAnnotationException",
    "CircularDependencyException",
    # Decorators
    "inject",
    "scoped_inject",
    "scopeless_inject",
]


"""
Notes and guidance

Prefer ServiceProvider.injector() (scoped per call) for decorating handlers/functions. This ensures scoped services work by default and avoids surprising “raise or skip” behavior.
Avoid class decorators. When you truly need to construct an injected class, use class_factory with an Injectable mixin pattern:
class Injectable:
@classmethod
def create(cls: type[T], /, *args, **kwargs) -> T:
from app.infrastructure.di.di_container import container
factory = container.service_provider.class_factory(cls, use_scope=True)
return factory(*args, **kwargs)

For framework adapters (FastAPI/aiogram), set skip_if_not_registered=True on the ServiceProvider so unknown params are left for the framework to supply.
Named registrations are for explicit resolution only: provider.get_service(T, name). Implicit injection ignores names.
Multiple registrations: last wins by convention.

"""
