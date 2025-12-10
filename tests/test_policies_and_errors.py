from typing import Optional, Union

import pytest

from dependo import (
    DIException,
    MissingTypeAnnotationException,
    ServiceCollection,
    ServiceNotRegisteredException,
    ServiceProvider,
    ServiceScope,
)


class IFoo: ...


class Foo(IFoo):
    def __init__(self):
        pass


def test_skip_if_not_registered_allows_framework_args_to_pass_through():
    p = ServiceProvider(ServiceCollection().add_singleton(IFoo, Foo), skip_if_not_registered=True)

    @p.injector()
    def handler(user_id: int, foo: IFoo):
        return (user_id, foo)

    uid, foo = handler(123)
    assert uid == 123 and isinstance(foo, IFoo)


def test_missing_registration_raises_when_policy_false():
    p = ServiceProvider(ServiceCollection().add_singleton(IFoo, Foo), skip_if_not_registered=False)

    class NotRegistered:
        def __init__(self):
            pass

    @p.injector()
    def bad(x: NotRegistered): ...

    with pytest.raises(ServiceNotRegisteredException):
        bad()


def test_missing_annotation_policy_raises_in_signature_injection():
    p = ServiceProvider(ServiceCollection(), skip_if_no_annotation=False)

    def f(x):
        return x

    with pytest.raises(MissingTypeAnnotationException):
        p._inject_into_signature(f, (), {}, set(), None)


def test_service_scope_injection_required_or_skipped():
    p1 = ServiceProvider(ServiceCollection(), skip_if_not_registered=False)

    def needs_scope(scope: ServiceScope):
        return scope

    with pytest.raises(DIException):
        p1._inject_into_signature(needs_scope, (), {}, set(), scope=None)

    p2 = ServiceProvider(ServiceCollection(), skip_if_not_registered=True)

    def maybe_scope(scope: Optional[ServiceScope] = None):
        return scope

    kwargs = {}
    p2._inject_into_signature(maybe_scope, (), kwargs, set(), scope=None)
    assert "scope" not in kwargs


def test_union_selection_prefers_registered_candidate():
    class A:
        def __init__(self):
            pass

    class B:
        def __init__(self):
            pass

    class Consumer:
        def __init__(self, dep: Union[A, B]):
            self.dep = dep

    sc = ServiceCollection().add_singleton(A).add_transient(Consumer)
    p = ServiceProvider(sc)

    c = p.get_service(Consumer)
    assert isinstance(c.dep, A)


def test_function_factory_implementation_dependency_injection():
    sc = ServiceCollection().add_singleton(IFoo, lambda: Foo())

    def build_consumer(foo: IFoo):
        return {"foo": foo}

    sc.add_transient(dict, build_consumer)
    p = ServiceProvider(sc)
    result = p.get_service(dict)
    assert isinstance(result["foo"], IFoo)


def test_freeze_prevents_further_registration_after_provider_creation():
    sc = ServiceCollection().add_singleton(IFoo, Foo)
    _ = ServiceProvider(sc)  # freezes
    with pytest.raises(Exception):
        sc.add_singleton(IFoo, Foo)
