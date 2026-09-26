"""Registry-routed public compiler for versioned model specifications."""
from __future__ import annotations

from typing import Any

from sim_engine_compiler.compiler.registry import register_compiler, registration_for
from sim_engine_compiler.diagnostics import CompilationError
from sim_engine_compiler.domains.abm_tick import compile_abm_tick
from sim_engine_compiler.ir.abm import (
    ABM_BUSINESS_VERSION, ABM_CORE_VERSION, ABM_PLAN_VERSION, ABM_PROFILE,
)


register_compiler(
    profile=ABM_PROFILE,
    business_version=ABM_BUSINESS_VERSION,
    core_version=ABM_CORE_VERSION,
    plan_version=ABM_PLAN_VERSION,
    compiler=compile_abm_tick,
)


def compile_model(spec: dict[str, Any]):
    if not isinstance(spec, dict):
        raise CompilationError(
            "model specification must be an object", code="invalid_abm_ir", source_path="model"
        )
    return registration_for(spec.get("profile")).compiler(spec)
