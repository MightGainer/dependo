import asyncio

import pytest

from dependo import CircularDependencyException, ServiceCollection, ServiceProvider


# Interfaces and services with explicit __init__
class IMessageService:
    def send(self, text: str): ...


class ConsoleMessageService(IMessageService):
    def __init__(self):
        self.sent = []

    def send(self, text: str):
        self.sent.append(text)


def test_quick_start_like_example():
    services = ServiceCollection().add_singleton(IMessageService, ConsoleMessageService)
    provider = ServiceProvider(services)

    @provider.injector()
    def handler(msg: IMessageService):
        msg.send("Hello from Dependo!")

    handler()
    msg = provider.get_service(IMessageService)
    assert msg.sent == ["Hello from Dependo!"]


def test_inject_service_provider_into_consumer():
    # Must be registered to resolve
    class UsesSP:
        def __init__(self, sp: ServiceProvider):
            self.sp = sp

    services = ServiceCollection().add_transient(UsesSP)
    provider = ServiceProvider(services)
    inst = provider.get_service(UsesSP)
    assert isinstance(inst.sp, ServiceProvider)
    assert inst.sp is provider


def test_direct_and_runtime_cycles():
    # Avoid local string forward refs. Patch annotations after class defs.
    class A:
        def __init__(self, b): ...
    class B:
        def __init__(self, a): ...

    # Inject annotations to simulate A->B and B->A
    A.__init__.__annotations__ = {"b": B}
    B.__init__.__annotations__ = {"a": A}

    # direct detection during freeze
    sc1 = ServiceCollection().add_transient(A).add_transient(B)
    with pytest.raises(CircularDependencyException):
        sc1.freeze()

    # deep/runtime detection as well (if freeze is no-op)
    sc2 = ServiceCollection().add_transient(A).add_transient(B)

    with pytest.raises(CircularDependencyException):
        p = ServiceProvider(sc2)


def test_async_injection_from_readme():
    class JobRunner:
        def __init__(self):
            self.ran = False

        async def run(self):
            self.ran = True

    services = ServiceCollection().add_scoped(JobRunner)
    provider = ServiceProvider(services)

    @provider.injector()
    async def handler(job: JobRunner):
        await job.run()
        return job

    job = asyncio.run(handler())
    assert job.ran is True
