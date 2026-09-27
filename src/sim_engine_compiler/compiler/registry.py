"""Versioned compiler/runtime registry.

Domain selection happens once at an artifact boundary.  Generic execution code
does not contain domain-name branches.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from sim_engine_compiler.diagnostics import CompilationError


Compiler = Callable[[dict[str, Any]], Any]
RuntimeFactory = Callable[..., Any]


@dataclass(frozen=True)
class DomainRegistration:
    profile: str
    business_version: str
    core_version: str
    plan_version: str
    compiler: Compiler
    runtime_factory: RuntimeFactory | None = None


_REGISTRY: dict[str, DomainRegistration] = {}


def register_compiler(*, profile: str, business_version: str, core_version: str,
                      plan_version: str, compiler: Compiler) -> None:
    existing = _REGISTRY.get(profile)
    if existing is not None and existing.compiler is not compiler:
        raise RuntimeError(f"compiler already registered for {profile}")
    _REGISTRY[profile] = DomainRegistration(
        profile, business_version, core_version, plan_version, compiler,
        None if existing is None else existing.runtime_factory,
    )


def register_runtime(profile: str, factory: RuntimeFactory) -> None:
    existing = _REGISTRY.get(profile)
    if existing is None:
        raise RuntimeError(f"register compiler before runtime for {profile}")
    if existing.runtime_factory is not None and existing.runtime_factory is not factory:
        raise RuntimeError(f"runtime already registered for {profile}")
    _REGISTRY[profile] = DomainRegistration(
        existing.profile, existing.business_version, existing.core_version,
        existing.plan_version, existing.compiler, factory,
    )


def registration_for(profile: str) -> DomainRegistration:
    try:
        return _REGISTRY[profile]
    except (KeyError, TypeError) as exc:
        raise CompilationError(
            "unsupported model profile", code="unsupported_profile", source_path="model.profile"
        ) from exc


def registered_profiles() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))
