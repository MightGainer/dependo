from dependo import ServiceCollection, ServiceProvider


class IFoo: ...


class Foo(IFoo):
    def __init__(self):
        pass


class Bar:
    def __init__(self, foo: IFoo):
        self.foo = foo


class Counter:
    count = 0

    def __init__(self):
        Counter.count += 1


def test_singleton_scoped_transient_behaviors():
    sc = ServiceCollection().add_singleton(IFoo, Foo).add_scoped(Bar).add_transient(Counter)
    p = ServiceProvider(sc)

    a = p.get_service(IFoo)
    b = p.get_service(IFoo)
    assert a is b

    with p.create_scope() as s1:
        b1 = s1.get_service(Bar)
        b2 = s1.get_service(Bar)
        assert b1 is b2
    with p.create_scope() as s2:
        b3 = s2.get_service(Bar)
        assert b3 is not b1

    c1 = p.get_service(Counter)
    c2 = p.get_service(Counter)
    assert c1 is not c2
    assert Counter.count >= 2


def test_add_singleton_instance_is_used():
    class Some:
        def __init__(self):
            pass

    obj = Some()
    sc = ServiceCollection().add_singleton_instance(Some, obj)
    p = ServiceProvider(sc)
    assert p.get_service(Some) is obj
