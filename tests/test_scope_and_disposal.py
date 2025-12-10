import pytest

from dependo import ServiceCollection, ServiceNotRegisteredException, ServiceProvider


def test_scope_get_service_policy_when_missing():
    p1 = ServiceProvider(ServiceCollection(), skip_if_not_registered=True)
    with p1.create_scope() as scope:
        assert scope.get_service(int) is None

    p2 = ServiceProvider(ServiceCollection(), skip_if_not_registered=False)
    with p2.create_scope() as scope:
        with pytest.raises(ServiceNotRegisteredException):
            scope.get_service(int)


def test_provider_dispose_calls_close_and___exit__():
    called = {"close": 0, "exit": 0}

    class WithClose:
        def __init__(self):
            pass

        def close(self):
            called["close"] += 1

    class WithExit:
        def __init__(self):
            pass

        def __exit__(self, exc_type, exc, tb):
            called["exit"] += 1

    sc = ServiceCollection().add_singleton(WithClose).add_singleton(WithExit)
    p = ServiceProvider(sc)
    _ = p.get_service(WithClose)
    _ = p.get_service(WithExit)
    p.dispose()
    assert called["close"] == 1
    assert called["exit"] == 1


def test_scope_dispose_calls_close_and_dispose():
    called = {"close": 0, "dispose": 0}

    class WithClose:
        def __init__(self):
            pass

        def close(self):
            called["close"] += 1

    class WithDispose:
        def __init__(self):
            pass

        def dispose(self):
            called["dispose"] += 1

    sc = ServiceCollection().add_scoped(WithClose).add_scoped(WithDispose)
    p = ServiceProvider(sc)
    with p.create_scope() as scope:
        scope.get_service(WithClose)
        scope.get_service(WithDispose)
    assert called == {"close": 1, "dispose": 1}
