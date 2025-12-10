from dependo import ServiceCollection, ServiceProvider


class IStorage:
    def save(self, data: str): ...


class FileStorage(IStorage):
    def __init__(self):
        self.saved = []

    def save(self, data: str):
        self.saved.append(("file", data))


class S3Storage(IStorage):
    def __init__(self):
        self.saved = []

    def save(self, data: str):
        self.saved.append(("s3", data))


def test_named_registrations_explicit_resolution():
    services = ServiceCollection().add_singleton(IStorage, FileStorage, name="file").add_singleton(IStorage, S3Storage, name="s3")
    provider = ServiceProvider(services)

    file_storage = provider.get_service(IStorage, name="file")
    s3_storage = provider.get_service(IStorage, name="s3")

    file_storage.save("local.txt")
    s3_storage.save("remote.txt")

    assert file_storage.saved == [("file", "local.txt")]
    assert s3_storage.saved == [("s3", "remote.txt")]


def test_implicit_injection_ignores_names_last_win_rule_for_unnamed():
    class Impl1(IStorage):
        def __init__(self):
            pass

        def save(self, data: str):
            pass

    class Impl2(IStorage):
        def __init__(self):
            pass

        def save(self, data: str):
            pass

    sc = ServiceCollection().add_transient(IStorage, Impl1).add_transient(IStorage, Impl2)
    p = ServiceProvider(sc)
    resolved = p.get_service(IStorage)
    assert isinstance(resolved, Impl2)

    all_impls = p.get_services(IStorage)
    assert len(all_impls) == 2 and isinstance(all_impls[0], Impl1) and isinstance(all_impls[1], Impl2)
