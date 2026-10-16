"""Restricted v0.1 aircraft domain pack used by the public product boundary."""

from __future__ import annotations

from dataclasses import dataclass

from sim_engine_compiler.compiler.layout import compile_core, lineage
from sim_engine_compiler.domains.aircraft_support.lowering import lower_business
from sim_engine_compiler.integrations.spare_mvp.importer import import_business_ir
from sim_engine_compiler.ir.layers import (
    BUSINESS_VERSION,
    CORE_VERSION,
    BusinessIR,
    operation_contracts,
)
from sim_engine_compiler.ir.plan import PLAN_VERSION


@dataclass(frozen=True)
class AircraftSupportPack:
    name: str = "aircraft-support"
    version: str = "aircraft-support-pack/v0.1"
    domain_profile: str = "aircraft-support-v1"
    input_schema: str = "aircraft-support-v1-input-v1"
    business_version: str = BUSINESS_VERSION
    core_version: str = CORE_VERSION
    plan_version: str = PLAN_VERSION
    lineage_version: str = "compiler-lineage/v2"
    profiles: tuple[str, ...] = ("legacy-minute-v1", "event-time-v2")
    work_policy: str = "stable-topological-serial"
    rng_profile: str = "legacy-sequential-v1"

    def import_canonical(self, inputs, *, semantic_profile: str = "legacy-minute-v1"):
        return import_business_ir(inputs, semantic_profile=semantic_profile)

    def load_payload(self, payload):
        return BusinessIR.create(payload)

    def load_envelope(self, raw):
        return BusinessIR.from_dict(raw)

    def associate(self, layers):
        from sim_engine_compiler.identity import inspect_bundle

        return inspect_bundle(
            business=layers["business.json"],
            core=layers["core.json"],
            plan=layers["plan.json"],
            lineage=layers["lineage.json"],
        )

    def compile(self, business: BusinessIR):
        business.validate()
        core = lower_business(business)
        plan = compile_core(core)
        return core, plan, lineage(business, core, plan)

    def capabilities(self) -> dict:
        return {
            "domain": self.name,
            "version": self.version,
            "business_version": self.business_version,
            "core_version": self.core_version,
            "plan_version": self.plan_version,
            "semantic_profiles": list(self.profiles),
            "work_policy": self.work_policy,
            "rng_profile": self.rng_profile,
            "resource_dispatch_index": "unsupported-in-v0.1-bundle",
            "operation_class": "restricted-aircraft-compatibility",
            "operations": [item["operation"] for item in operation_contracts()],
            "backends": ["python-reference", "rust-runtime"],
        }


PACK = AircraftSupportPack()
