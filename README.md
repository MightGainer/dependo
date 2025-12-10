# 🧩 Dependo — Modern Dependency Injection for Python

**Dependo** is a fast, typed, elegant dependency injection container inspired by **.NET’s DI system**, built for **Python 3.10+**.  
It supports `singleton`, `scoped`, and `transient` lifetimes — with automatic injection, async‑ready scopes, and minimal boilerplate.

---

## ✨ Features Overview

- 📦 **.NET‑style lifetimes**: Singleton / Scoped / Transient  
- 🧠 **Type‑hint‑driven** injection — no decorators required  
- 🔗 **Chainable** registration API (`.add_singleton().add_scoped()...`)  
- ⚙️ Async & **framework‑friendly** (FastAPI, Flask, aiogram, Django)  
- 🚀 Thread‑safe, high‑performance iterative resolver  
- 🧱 Injectable mixin for explicit DI class creation  
- 🧩 Minimal API surface — explicit and predictable  
- 🧪 Testable, mock‑friendly, and overrides‑safe  

---

## 📦 Installation

```bash
pip install dependo
```

Supports Python ≥ 3.10.

---

## 🧠 Quick Start

```python
from dependo import ServiceCollection, ServiceProvider, inject, scoped_inject

# Example interfaces and implementations
class IMessageService:
    def send(self, text: str): ...

class ConsoleMessageService(IMessageService):
    def send(self, text: str):
        print(f"[Message] {text}")

# Build your service collection
services = (
    ServiceCollection()
    .add_singleton(IMessageService, ConsoleMessageService)
)

provider = ServiceProvider(services)

@provider.injector()
def handler(msg: IMessageService):
    msg.send("Hello from Dependo!")

handler()
```

Output:
```
[Message] Hello from Dependo!
```

---

## 🧱 Scoped Lifetimes

```python
from dependo import ServiceCollection, ServiceProvider

class Session:
    def __init__(self):
        print("Session created")
    def dispose(self):
        print("Session disposed")

services = ServiceCollection().add_scoped(Session)
provider = ServiceProvider(services)

with provider.create_scope() as scope:
    session = scope.get_service(Session)
    another = scope.get_service(Session)
    assert session is another

# Output:
# Session created
# Session disposed
```

---

## 🧩 The `Injectable` Mixin

```python
from dependo import Injectable

class EmailService(Injectable):
    def __init__(self, msg: IMessageService):
        self.msg = msg

    def send_email(self, text: str):
        self.msg.send(f"Email: {text}")

email = EmailService.create(provider)
email.send_email("Hello world!")
```

---

## ⚙️ Framework Integration

In frameworks such as **FastAPI**, **aiogram**, or **Flask**, you often receive parameters (`Request`, `Message`, etc.) that you *don’t* want DI to manage.  
Use `skip_if_not_registered=True`:

```python
provider = ServiceProvider(services, skip_if_not_registered=True)
```

---

## 🪣 Suggested Container Pattern

```python
from dependo import ServiceProvider

class DiContainer:
    def __init__(self):
        self._service_provider: ServiceProvider | None = None

    @property
    def service_provider(self) -> ServiceProvider:
        if not self._service_provider:
            raise ValueError("Service provider not initialized")
        return self._service_provider

    def set_service_provider(self, sp: ServiceProvider) -> None:
        self._service_provider = sp

container = DiContainer()
```

### Chained example setup

```python
from dependo import ServiceCollection, ServiceProvider

services = (
    ServiceCollection()
    .add_singleton(IDatabase, Database)
    .add_scoped(IRepository, Repository)
    .add_transient(EmailService)
)

sp = ServiceProvider(services)
container.set_service_provider(sp)
```

---

## 🧪 Testing Tips

- Re‑register mocks (last wins).
- Create separate containers for each test.
- Supports async and sync tests equally.

```python
from unittest.mock import MagicMock
from dependo import ServiceCollection, ServiceProvider

services = (
    ServiceCollection()
    .add_singleton(IMessageService, ConsoleMessageService)
    .add_singleton(IMessageService, MagicMock())  # overrides
)

provider = ServiceProvider(services)
mock = provider.get_service(IMessageService)
mock.send.assert_not_called()
```

---

## 🔁 Comparison

| Library | Highlights | Dependo Difference |
|----------|-------------|--------------------|
| **python-dependency-injector (ets-labs)** | Very powerful (providers, configs, wiring). | Dependo is smaller, type-hint driven, minimal, no provider graph. |
| **Injector / python-injector** | Stable, Guice-style modules, decorators. | Dependo auto‑injects via type hints, async & per‑call scopes. |
| **py-dependency-injection** | Lightweight but minimal features. | Dependo provides lifetimes, async scopes, decorators, Optional/Union injection. |

If you want a **lightweight, typed, .NET-inspired DI** that just works in **FastAPI**, **Flask**, **Django**, or **aiogram**, Dependo is for you.

---

## ✅ Why Dependo (Features and Design)

- **Typed-first ergonomics**
  - Resolves via type hints.
  - Handles `Union` & `Optional`.
  - Keeps callable signatures for frameworks.
  - ServiceProvider itself is injected by default
  - Supports dataclasses also

- **Clear lifetime model**
  - `Singleton`, `Scoped`, `Transient`.
  - Sync/async disposable scopes.

- **Chainable registration**
  - Build dependencies easily:
    ```python
    ServiceCollection().add_singleton(A).add_scoped(B).add_transient(C)
    ```

- **Automatic injection**
  - Via `provider.injector()`, `@scoped_inject()`, properties (`@inject`), or `Injectable` mixin.

- **Framework ready**
  - Works with FastAPI, Flask, Django, aiogram seamlessly.
  - Honors async handlers and framework-supplied args.

- **Safe, predictable, and fast**
  - Detects circular dependencies.
  - Thread‑safe singletons.
  - Iterative resolver (non‑recursive).

- **Testing and override ready**
  - Mock or override easily.
  - Create isolated providers.

- **Minimal surface**
  - No declarative graphs, configs, or magic globals.
  - Explicit, developer‑controlled DI.

---

## 🧩 Advanced Examples


### 🔸 0. Core Python examples

```python
# app/services.py
from dependo import ServiceCollection, ServiceProvider, scoped_inject

class Config:
    def __init__(self):
        self.env = "production"

class Logger:
    def log(self, text: str):
        print(f"[LOG] {text}")

class UserService:
    def __init__(self, config: Config, logger: Logger):
        self.config = config
        self.logger = logger
    def create_user(self, username: str):
        self.logger.log(f"Creating {username} in {self.config.env}")

# Build provider
services = (
    ServiceCollection()
    .add_singleton(Config)
    .add_singleton(Logger)
    .add_scoped(UserService)
)
provider = ServiceProvider(services)


# handler.py
@scoped_inject(provider)
def create_user(user_service: UserService):
    user_service.create_user("Jane")

create_user()
```

### 🔸 1. Async injection

```python
from dependo import ServiceCollection, ServiceProvider, scoped_inject
import asyncio

class JobRunner:
    async def run(self):
        print("Running async job")

services = ServiceCollection().add_scoped(JobRunner)
provider = ServiceProvider(services)

@scoped_inject(provider)
async def handler(job: JobRunner):
    await job.run()

asyncio.run(handler())
```

---

### 🔸 2. Property injection

```python
from dependo import ServiceCollection, ServiceProvider, inject, scoped_inject

# ------------------------------------------------
# Define services
# ------------------------------------------------

class IMessageService:
    def send(self, text: str) -> None: ...

class HelloMessageService(IMessageService):
    def send(self, text: str) -> None:
        print(f"[HELLO] {text}")

# ------------------------------------------------
# Define business class using property injection
# ------------------------------------------------

class Greeter:
    def __init__(self, sp: ServiceProvider):
        self._provider = sp  # you can store provider here (any name)

    @inject()  # or @inject(provider)
    def message_service(self) -> IMessageService: ...

    def greet(self):
        self.message_service.send("Hi there!")

# ------------------------------------------------
# Build container & define callable injection
# ------------------------------------------------

services = ServiceCollection().add_singleton(IMessageService, HelloMessageService)
provider = ServiceProvider(services)

@scoped_inject(provider)
def greet_user(greeter: Greeter):
    greeter.greet()


if __name__ == "__main__":
    greet_user()
```

---

### 🔸 3. Lifecycle cleanup

```python
class DBConnection:
    def __init__(self):
        print("Connected to DB!")
    def close(self):
        print("Connection closed")

services = ServiceCollection().add_scoped(DBConnection)
sp = ServiceProvider(services)

with sp.create_scope() as scope:
    scope.get_service(DBConnection)

# ⮕ automatically closes on exit
```

---

### 🔸 4. Scoped overrides for testing

```python
mock_db = object()

services = (
    ServiceCollection()
    .add_scoped(DBConnection)
    .add_scoped(DBConnection, lambda: mock_db)  # override
)

provider = ServiceProvider(services)
assert provider.get_service(DBConnection) is mock_db
```

---
### 🔸 5. Named service registrations

```python
from dependo import ServiceCollection, ServiceProvider, scoped_inject

# Define a common interface
class IStorage:
    def save(self, data: str) -> None: ...

# First implementation
class FileStorage(IStorage):
    def save(self, data: str):
        print(f"Saving '{data}' to file.txt")

# Second implementation
class S3Storage(IStorage):
    def save(self, data: str):
        print(f"Uploading '{data}' to AWS S3")

# Register both, but give them names
services = (
    ServiceCollection()
    .add_singleton(IStorage, FileStorage, name="file")
    .add_singleton(IStorage, S3Storage, name="s3")
)
provider = ServiceProvider(services)

# Named resolution — explicitly choose by name
file_storage = provider.get_service(IStorage, name="file")
s3_storage = provider.get_service(IStorage, name="s3")

file_storage.save("local.txt")
s3_storage.save("remote.txt")

```

Named services are great for:

- Multi‑environment backends (e.g., file vs. S3, test vs. prod).
- Integrations (e.g., email vs. SMS notifier, primary vs. secondary DB).

---
### 🔸 6. Property injection with a named service

```python
from dependo import inject, ServiceProvider

class DocumentProcessor:
    def __init__(self, sp: ServiceProvider):
        self._provider = sp

    # specify target implementation by name
    @inject()
    def s3_storage(self) -> IStorage:
        return self._provider.get_service(IStorage, name="s3")

    def process(self, content: str):
        self.s3_storage.save(content)
```
---
### 🔸 7. `get_services()` for all implementations

If you have multiple registrations of the same type (without names),

`get_services()` returns all implementations in registration order.

```python
from dependo import ServiceCollection, ServiceProvider, scoped_inject

# Same interface
class INotifier:
    def send(self, message: str) -> None: ...

class EmailNotifier(INotifier):
    def send(self, message: str):
        print(f"📧 Email: {message}")

class SMSNotifier(INotifier):
    def send(self, message: str):
        print(f"📱 SMS: {message}")

# register multiple implementations (no names)
services = (
    ServiceCollection()
    .add_transient(INotifier, EmailNotifier)
    .add_transient(INotifier, SMSNotifier)
)
provider = ServiceProvider(services)

# Example function injected per scope
@scoped_inject(provider)
def notify_all(notifiers: list[INotifier]):
    # Retrieve all decorated instances manually
    for n in provider.get_services(INotifier):
        n.send("System updated!")

notify_all()
```

Output
```
📧 Email: System updated!
📱 SMS: System updated!
```

You could also write it inside a service or class constructor:

```python
class NotificationHub:
    def __init__(self, sp: ServiceProvider):
        self._provider = sp
        self._channels = sp.get_services(INotifier)

    def broadcast(self, message: str):
        for ch in self._channels:
            ch.send(message)
```

---

## Dataclasses

- Dependo **fully supports dataclasses**, both frozen and mutable.
- Type‑hinted fields are resolved like normal constructor arguments.  
- Default values are left as‑is (respected by `skip_if_default=True`).
- You can freely mix:
  - dataclass constructor injection,
  - property injection (`@inject()`),
  - or explicit scope decorators (`@scoped_inject`).

### 🧩 Example 1 — simple dataclass auto‑injection

```python
from dataclasses import dataclass
from dependo import ServiceCollection, ServiceProvider

class Config:
    def __init__(self):
        self.env = "production"

class Logger:
    def log(self, msg: str):
        print(f"[LOG] {msg}")

@dataclass
class Worker:
    config: Config
    logger: Logger

    def run(self):
        self.logger.log(f"Running worker in {self.config.env} mode")

services = (
    ServiceCollection()
    .add_singleton(Config)
    .add_singleton(Logger)
    .add_transient(Worker)
)
provider = ServiceProvider(services)

worker = provider.get_service(Worker)
worker.run()
```

**Output**
```
[LOG] Running worker in production mode
```

✅  This works because Dependo inspects the dataclass field type hints and automatically provides registered dependencies when constructing it.

---

### 🧱 Example 2 — dataclass with default values and mix of injected and literal args

```python
from dataclasses import dataclass, field
from dependo import ServiceCollection, ServiceProvider

class DB:
    def __init__(self):
        self.name = "main"

@dataclass
class Repo:
    db: DB
    table: str = field(default="users")

    def count(self):
        print(f"Counting records from {self.table} in {self.db.name} DB")

services = (
    ServiceCollection()
    .add_singleton(DB)
    .add_transient(Repo)
)
provider = ServiceProvider(services)

repo = provider.get_service(Repo)
repo.count()
```

**Output**
```
Counting records from users in main DB
```

💡 Fields with default values (`table`) are left untouched because `skip_if_default=True` by default.

---

### 🧠 Example 3 — dataclass inside another injected service (nested injection)

```python
from dataclasses import dataclass
from dependo import ServiceCollection, ServiceProvider, scoped_inject

class Mailer:
    def send(self, to: str, text: str):
        print(f"Email to {to}: {text}")

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
        # Dependo auto‑injects mailer here as well!
        return Notification(self.mailer, "Welcome!")

# Configure container
services = (
    ServiceCollection()
    .add_singleton(Mailer)
    .add_transient(Notification)
    .add_scoped(NotificationService)
)
provider = ServiceProvider(services)

@scoped_inject(provider)
def send_welcome(notification_service: NotificationService):
    notif = notification_service.create_welcome()
    notif.send("user@example.com")

send_welcome()
```

**Output**
```
Email to user@example.com: Welcome!
```

Dependo recursively resolves constructor arguments even when they’re dataclasses, since their generated `__init__` and annotations are available for introspection.

---

### 🧩 Example 4 — dataclass with property injection

```python
from dataclasses import dataclass
from dependo import inject, ServiceCollection, ServiceProvider

class AppConfig:
    def __init__(self):
        self.version = "1.0.0"

class Logger:
    def log(self, msg: str):
        print(f"[LOG] {msg}")

@dataclass
class AppStatus:
    app_name: str
    _provider: ServiceProvider  # stored provider manually (optional)

    @inject()
    def logger(self) -> Logger: ...

    @inject()
    def config(self) -> AppConfig: ...

    def report(self):
        self.logger.log(f"{self.app_name} v{self.config.version} is running")

services = (
    ServiceCollection()
    .add_singleton(Logger)
    .add_singleton(AppConfig)
)
provider = ServiceProvider(services)

status = AppStatus("DependoApp", provider)
status.report()
```

**Output**
```
[LOG] DependoApp v1.0.0 is running
```

✅ Works perfectly fine — dataclasses can include `_provider` fields and use property injection decorators the same way normal classes do.

---

### ⚙️ Example 5 — dataclass as configuration object (scoped usage)

```python
from dataclasses import dataclass
from dependo import ServiceCollection, ServiceProvider, scoped_inject

class DBClient:
    def query(self, q: str):
        print(f"Executing SQL: {q}")

@dataclass
class QueryHandler:
    db: DBClient
    query: str = "SELECT * FROM users"

    def execute(self):
        self.db.query(self.query)

services = (
    ServiceCollection()
    .add_scoped(DBClient)
    .add_scoped(QueryHandler)
)
sp = ServiceProvider(services)

@scoped_inject(sp)
def run_query(handler: QueryHandler):
    handler.execute()

run_query()
```

**Output**
```
Executing SQL: SELECT * FROM users
```

---

## ⚡ Framework‑Specific Advanced Examples

### 🚀 FastAPI Integration

```python
# app/main.py
from fastapi import FastAPI, Request
from dependo import ServiceCollection, ServiceProvider, scoped_inject

class EmailSender:
    def send(self, to: str, body: str):
        print(f"Sending email to {to}: {body}")

class UserService:
    def __init__(self, sender: EmailSender):
        self.sender = sender
    def notify_user(self, email: str):
        self.sender.send(email, "Welcome!")

# build DI provider
services = (
    ServiceCollection()
    .add_singleton(EmailSender)
    .add_scoped(UserService)
)
provider = ServiceProvider(services, skip_if_not_registered=True)

app = FastAPI()

@app.post("/users/{email}")
@scoped_inject(provider)
async def register(email: str, user_service: UserService, request: Request):
    user_service.notify_user(email)
    return {"ok": True}
```

Dependo will inject `Mailer` and let FastAPI handle native params (`Request`, `Response`).

---

### 🌐 Flask Integration

```python
# app/app.py
from flask import Flask, jsonify, request
from dependo import ServiceCollection, ServiceProvider

class Logger:
    def log(self, msg: str):
        print(f"[{request.method}] {msg}")

class AuthService:
    def __init__(self, logger: Logger):
        self.logger = logger
    def login(self, username):
        self.logger.log(f"Login attempt for {username}")

services = (
    ServiceCollection()
    .add_singleton(Logger)
    .add_scoped(AuthService)
)
provider = ServiceProvider(services, skip_if_not_registered=True)

app = Flask(__name__)

@app.route("/login/<user>")
@provider.injector()
def login(user: str, auth: AuthService):
    auth.login(user)
    return jsonify({"status": "ok"})
```

Here, Dependo injects your dependencies while aiogram injects the `Message` object.

---

## 🤖 aiogram integration

```python
# bot/main.py
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from dependo import ServiceCollection, ServiceProvider, scoped_inject
import asyncio

BOT_TOKEN = "YOUR_TOKEN_HERE"
bot = Bot(BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

class MessageLogger:
    def log(self, user: str, text: str):
        print(f"User {user}: {text}")

class GreetingService:
    def __init__(self, logger: MessageLogger):
        self.logger = logger
    async def greet(self, message: types.Message):
        self.logger.log(message.from_user.full_name, message.text)
        await message.answer(f"Hello, {message.from_user.first_name}!")

services = (
    ServiceCollection()
    .add_singleton(MessageLogger)
    .add_scoped(GreetingService)
)
provider = ServiceProvider(services, skip_if_not_registered=True)

@dp.message()
@scoped_inject(provider)
async def greet_user(message: types.Message, service: GreetingService):
    await service.greet(message)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 🏛️ Django Integration Example

```python
# myapp/di.py
from dependo import ServiceCollection, ServiceProvider

class Mailer:
    def send_mail(self, user_email: str, text: str):
        print(f"Mail to {user_email}: {text}")

class Notifier:
    def __init__(self, mailer: Mailer):
        self.mailer = mailer
    def notify(self, user_email):
        self.mailer.send_mail(user_email, "Welcome!")

services = (
    ServiceCollection()
    .add_singleton(Mailer)
    .add_scoped(Notifier)
)
service_provider = ServiceProvider(services)

# myapp/views.py
from django.http import JsonResponse
from .di import service_provider

@service_provider.injector()
def welcome(request, notifier: Notifier):
    notifier.notify("user@example.com")
    return JsonResponse({"ok": True})
```

Django views preserve dependency injection naturally, keeping the `request` argument intact.

---

## 🚀 Development Commands

```bash
poetry install
poetry run pytest
poetry run black dependo/
```

---

## 📄 License

MIT License © 2025 **Sokolov Yury (MightGainer)** — [yukyitchow@gmail.com](mailto:yukyitchow@gmail.com)

---

## 💬 Summary

**Dependo** is a **typed**, **async‑ready**, **production‑grade** dependency injection system —  
clean, thread‑safe, testable, and familiar to developers used to .NET’s `IServiceCollection`.

> Build dependencies, not boilerplate.  
> **Dependo** 🧩 — *simple, fast, and typed.*
