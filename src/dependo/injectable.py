from typing import Any, Type, TypeVar

from .service_provider import ServiceProvider

T = TypeVar("T", bound="Injectable")


class Injectable:
    """
    Base mixin for DI-aware classes, providing a `.create()` helper method.

    Typical usage:
    ---------------
    ```python
    class Foo(Injectable):
        def __init__(self, bar: IBar):
            self.bar = bar

    foo = Foo.create(provider)
    ```

    This class pattern improves ergonomics when working with frameworks
    that need to create injected instances without decorators or factories.
    """

    @classmethod
    def create(cls: Type[T], provider: ServiceProvider, /, *args: Any, **kwargs: Any) -> T:
        """
        Create an instance of this class using the supplied `ServiceProvider`.

        Parameters
        ----------
        provider : ServiceProvider
            The DI provider responsible for injecting constructor parameters.

        Returns
        -------
        T
            A fully constructed and injected instance of this class.
        """
        return provider.class_factory(cls, *args, **kwargs)()
