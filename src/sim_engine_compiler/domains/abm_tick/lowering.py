"""Source-faithful lowering for the finite ``abm-tick-v1`` language."""
from __future__ import annotations

import copy
from typing import Any, NamedTuple

from sim_engine_compiler.ir.abm import AbmBusinessIR, AbmCoreIR, AbmTickPlan


class AbmCompilation(NamedTuple):
    business: AbmBusinessIR
    core: AbmCoreIR
    plan: AbmTickPlan
    lineage: dict[str, Any]


def compile_abm_tick(spec: dict[str, Any]) -> AbmCompilation:
    """Validate and seal each layer without hiding source input from later passes."""
    business = AbmBusinessIR.create(spec)
    # v1 intentionally has no semantic optimization: Core is the validated,
    # symbolic source model and Plan is its immutable executable projection.
    core = AbmCoreIR.create(copy.deepcopy(business.payload))
    plan = AbmTickPlan.create(copy.deepcopy(core.payload))
    symbols = []
    for index, patch in enumerate(plan.payload["initial_state"]["patches"]):
        symbols.append({"id": patch["id"], "plan_path": f"initial_state.patches[{index}]",
                        "source_path": f"initial_state.patches[{index}]"})
    for index, agent in enumerate(plan.payload["initial_state"]["agents"]):
        symbols.append({"id": agent["id"], "plan_path": f"initial_state.agents[{index}]",
                        "source_path": f"initial_state.agents[{index}]"})
    for index, phase in enumerate(plan.payload["phases"]):
        symbols.append({"id": phase["id"], "plan_path": f"phases[{index}]",
                        "source_path": f"phases[{index}]"})
    source_semantics = plan.payload.get("source_semantics")
    if source_semantics is not None:
        for index, phase in enumerate(source_semantics["initialization"]):
            path = f"source_semantics.initialization[{index}]"
            symbols.append({"id": phase["id"], "plan_path": path, "source_path": path})
    lineage = {
        "version": "abm-compiler-lineage/v1",
        "business_fingerprint": business.fingerprint,
        "core_fingerprint": core.fingerprint,
        "plan_fingerprint": plan.fingerprint,
        "symbols": symbols,
    }
    return AbmCompilation(business, core, plan, lineage)
