"""Built-in composition; callers may inject a different DomainRegistry."""
from .registry import DomainAdapter, DomainRegistry


def builtin_registry() -> DomainRegistry:
    # The composition boundary knows installed packages; generic.py does not.
    from .aircraft import ADAPTER as aircraft
    from .production import ADAPTER as production
    return DomainRegistry((aircraft, production))
