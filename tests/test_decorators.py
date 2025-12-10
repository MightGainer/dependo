import asyncio

import pytest

from dependo import (
    DIException,
    ServiceCollection,
    ServiceProvider,
    inject,
    scoped_inject,
    scopeless_inject,
)


class IFoo: ...


class Foo(IFoo):
    def __init__(self):
        pass


def test_inject_property_basic_and_cache():
    sc = ServiceCollection().add_singleton(IFoo, Foo)
    p = ServiceProvider(sc)

    class C:
        def __init__(self):
            self._provider = p  # provider discoverable

        @inject()
        def foo(self) -> IFoo: ...  # type: ignore

    c = C()
    f1 = c.foo
    f2 = c.foo
    assert isinstance(f1, IFoo)
    assert f1 is f2  # cached in _foo


def test_inject_property_missing_provider_raises():
    class C:
        @inject()
        def foo(self) -> IFoo: ...  # type: ignore

    with pytest.raises(DIException):
        _ = C().foo


def test_inject_property_optional_unregistered_is_none():
    from typing import Optional

    p = ServiceProvider(ServiceCollection())  # IFoo not registered

    class C:
        def __init__(self):
            self._provider = p

        @inject()
        def maybe(self) -> Optional[IFoo]: ...

    c = C()
    assert c.maybe is None


def test_scoped_and_scopeless_inject_function_decorators_and_type_errors():
    p = ServiceProvider(ServiceCollection().add_singleton(IFoo, Foo))

    @scoped_inject(p)
    def f(foo: IFoo):
        return foo

    assert isinstance(f(), IFoo)

    @scopeless_inject(p)
    def g(foo: IFoo):
        return foo

    assert isinstance(g(), IFoo)

    with pytest.raises(TypeError):

        class K:
            pass

        scoped_inject(p)(K)
    with pytest.raises(TypeError):

        class L:
            pass

        scopeless_inject(p)(L)


def test_injector_and_scoped_inject_for_async_functions():
    p = ServiceProvider(ServiceCollection().add_singleton(IFoo, Foo))

    @p.injector()
    async def h(foo: IFoo):
        return foo

    async def run():
        x = await h()
        return x

    res = asyncio.run(run())
    assert isinstance(res, IFoo)
