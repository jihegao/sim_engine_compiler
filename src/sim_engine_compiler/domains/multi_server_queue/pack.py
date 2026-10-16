"""Product pack for the restricted two-server queue profile."""

from __future__ import annotations

from typing import Any

from sim_engine_compiler.domains.multi_server_queue.model import (
    BUSINESS_VERSION,
    CORE_VERSION,
    DOMAIN,
    LINEAGE_VERSION,
    OPERATIONS,
    PACK_VERSION,
    PLAN_VERSION,
    PROFILE,
    RNG_PROFILE,
    SCHEMA,
    SEMANTIC_PROFILE,
    WORK_POLICY,
    QueueBusiness,
    import_canonical,
    lower,
)


class MultiServerQueuePack:
    name = DOMAIN
    version = PACK_VERSION
    domain_profile = PROFILE
    input_schema = SCHEMA
    business_version = BUSINESS_VERSION
    core_version = CORE_VERSION
    plan_version = PLAN_VERSION
    lineage_version = LINEAGE_VERSION
    profiles = (SEMANTIC_PROFILE,)
    work_policy = WORK_POLICY
    rng_profile = RNG_PROFILE

    def import_canonical(self, inputs: dict[str, Any]) -> QueueBusiness:
        return import_canonical(inputs)

    def load_payload(self, payload: dict[str, Any]) -> QueueBusiness:
        return QueueBusiness.create(payload)

    def load_envelope(self, raw: dict[str, Any]) -> QueueBusiness:
        return QueueBusiness.from_dict(raw)

    def compile(self, business: QueueBusiness):
        core, plan, lineage = lower(business)
        from sim_engine_compiler.domains.multi_server_queue.model import QueuePlanView

        return _Core(core), QueuePlanView(plan), lineage

    def associate(self, layers: dict[str, Any]) -> dict[str, Any]:
        business = QueueBusiness.from_dict(layers["business.json"])
        core, plan, lineage = lower(business)
        diagnostics = []
        if layers["core.json"] != core:
            diagnostics.append(_diagnostic(
                "business_core_revision_mismatch",
                "persisted Core is not the compiler result for the supplied Business revision",
                "core",
            ))
        if layers["plan.json"] != plan:
            diagnostics.append(_diagnostic(
                "core_plan_revision_mismatch",
                "Plan is not the layout result for the supplied Core revision",
                "plan",
            ))
        if layers["lineage.json"] != lineage:
            diagnostics.append(_diagnostic(
                "lineage_symbol_mismatch",
                "lineage symbols or fingerprints do not match the persisted bundle",
                "lineage",
            ))
        status = "invalid" if diagnostics else "partial"
        return {
            "schema_version": "multi-server-queue-bundle-association/v1",
            "status": status,
            "association_status": "unverified" if diagnostics else "verified",
            "diagnostics": diagnostics,
            "coverage": {
                "level": "none" if diagnostics else "complete-for-declared-range",
                "operations": [item["operation"] for item in OPERATIONS],
                "limitation": "restricted two-server queue profile; not a general queue algebra",
            },
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "domain": self.name,
            "domain_profile": self.domain_profile,
            "version": self.version,
            "input_schema": self.input_schema,
            "business_version": self.business_version,
            "core_version": self.core_version,
            "plan_version": self.plan_version,
            "semantic_profiles": list(self.profiles),
            "work_policy": self.work_policy,
            "rng_profile": self.rng_profile,
            "operation_class": "restricted-queue-profile",
            "operations": [item["operation"] for item in OPERATIONS],
            "backends": ["python-reference", "rust-runtime"],
            "fixed_assumptions": [
                "exactly two servers",
                "Poisson arrivals and exponential service",
                "nonpreemptive priority, then arrival time, then customer id",
                "lowest-index idle server",
                "mean wait over customers who start service at or before the horizon",
                "cpython-mt19937-v1 exponential draws",
                "max_admitted_arrivals=10000 and max_loop_steps=100000",
            ],
        }


class _Core:
    def __init__(self, document: dict[str, Any]):
        self.document = document
        self.fingerprint = document["fingerprint"]

    def to_dict(self) -> dict[str, Any]:
        return self.document


def _diagnostic(code: str, message: str, path: str) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "error",
        "stage": "association",
        "path": path,
        "message": message,
    }


PACK = MultiServerQueuePack()
