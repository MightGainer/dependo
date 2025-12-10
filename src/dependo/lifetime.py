from enum import Enum


class Lifetime(str, Enum):
    """
    Enumeration defining supported dependency lifetimes.

    Attributes
    ----------
    SINGLETON :
        Single global instance reused throughout the application's lifetime.

    SCOPED :
        Instance is reused within a single `ServiceScope`, disposed when the scope ends.

    TRANSIENT :
        Always create a fresh instance each time the dependency is resolved.
    """

    SINGLETON = "singleton"
    SCOPED = "scoped"
    TRANSIENT = "transient"
