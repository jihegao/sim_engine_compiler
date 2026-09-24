"""Explicit domain adapters selected by the caller, without global mutation."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol

from validation import _fail, _identity


class DomainAdapter(Protocol):
    domain: str

    def validate_business(self, raw: dict) -> dict: ...

    def lower_core(self, business: dict) -> dict: ...


@dataclass(frozen=True, init=False)
class DomainRegistry:
    adapters: Mapping[str, DomainAdapter]

    def __init__(self, adapters: Iterable[DomainAdapter]):
        entries = {}
        for adapter in adapters:
            identity = _identity(adapter.domain, "adapter domain")
            if identity in entries:
                _fail(f"duplicate domain adapter {identity}")
            if not callable(getattr(adapter, "validate_business", None)) or not callable(getattr(adapter, "lower_core", None)):
                _fail(f"invalid domain adapter {identity}")
            entries[identity] = adapter
        object.__setattr__(self, "adapters", MappingProxyType(entries))

    def resolve(self, domain: str) -> DomainAdapter:
        _identity(domain, "domain")
        if domain not in self.adapters:
            _fail(f"unsupported domain {domain}")
        return self.adapters[domain]
