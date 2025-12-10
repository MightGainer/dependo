from dependo import Injectable, ServiceCollection, ServiceProvider, inject


class IMessageService:
    def send(self, text: str): ...


class HelloMessageService(IMessageService):
    def __init__(self):
        self.sent = []

    def send(self, text: str):
        self.sent.append(text)


def test_injectable_mixin_create():
    class EmailService(Injectable):
        def __init__(self, msg: IMessageService):
            self.msg = msg

    services = ServiceCollection().add_singleton(IMessageService, HelloMessageService)
    provider = ServiceProvider(services)
    email = EmailService.create(provider)
    email.msg.send("Hello world!")
    assert provider.get_service(IMessageService).sent == ["Hello world!"]


def test_class_factory_with_property_injection_and_scopeless():
    class A:
        def __init__(self):
            self.ok = True

    class B:
        def __init__(self, a: A):
            self.a = a

        @inject()
        def a_prop(self) -> A: ...  # type: ignore

    services = ServiceCollection().add_singleton(A).add_transient(B)
    p = ServiceProvider(services)

    # Using class_factory with scope
    factory = p.class_factory(B, use_scope=True)
    b1 = factory()
    assert b1.a.ok is True
    # property injected by _inject_properties during instantiate
    assert b1.a_prop.ok is True

    # Without scope (still works for non-scoped services)
    factory2 = p.class_factory(B, use_scope=False)
    b2 = factory2()
    assert b2.a.ok is True
