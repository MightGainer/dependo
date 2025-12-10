from dataclasses import dataclass, field

from dependo import ServiceCollection, ServiceProvider, inject


class Config:
    def __init__(self):
        self.env = "production"


class Logger:
    def __init__(self):
        self.logs = []

    def log(self, text: str):
        self.logs.append(text)


@dataclass
class Worker:
    config: Config
    logger: Logger

    def run(self):
        self.logger.log(f"Running worker in {self.config.env} mode")


def test_dataclass_simple_injection():
    sp = ServiceProvider(ServiceCollection().add_singleton(Config).add_singleton(Logger).add_transient(Worker))
    w = sp.get_service(Worker)
    w.run()
    assert w.logger.logs == ["Running worker in production mode"]


@dataclass
class Repo:
    db: "DB"
    table: str = field(default="users")

    def count(self):
        return f"{self.table}:{self.db.name}"


class DB:
    def __init__(self):
        self.name = "main"


def test_dataclass_with_defaults_and_literal_fields():
    sp = ServiceProvider(ServiceCollection().add_singleton(DB).add_transient(Repo))
    r = sp.get_service(Repo)
    assert r.count() == "users:main"


class Mailer:
    def __init__(self):
        self.sent = []

    def send(self, to: str, text: str):
        self.sent.append((to, text))


@dataclass
class Notification:
    mailer: Mailer
    message: str

    def send(self, user: str):
        self.mailer.send(user, self.message)


@dataclass
class NotificationService:
    mailer: Mailer

    def create_welcome(self) -> Notification:
        return Notification(self.mailer, "Welcome!")


def test_nested_injection_with_dataclass_from_readme():
    sp = ServiceProvider(ServiceCollection().add_singleton(Mailer).add_transient(Notification).add_scoped(NotificationService))

    @sp.injector()
    def send_welcome(notification_service: NotificationService):
        notif = notification_service.create_welcome()
        notif.send("user@example.com")
        return notification_service.mailer

    mailer = send_welcome()
    assert mailer.sent == [("user@example.com", "Welcome!")]


@dataclass
class AppStatus:
    app_name: str
    _provider: ServiceProvider

    @inject()
    def logger(self) -> Logger: ...  # type: ignore

    @inject()
    def config(self) -> Config: ...  # type: ignore

    def report(self):
        self.logger.log(f"{self.app_name} v{self.config.env} is running")


def test_dataclass_with_property_injection():
    sp = ServiceProvider(ServiceCollection().add_singleton(Logger).add_singleton(Config))
    status = AppStatus("DependoApp", sp)
    status.report()
    assert status.logger.logs == ["DependoApp vproduction is running"]
