"""Business, Core, and Plan contracts for the two-server queue profile.

The profile is restricted: exactly two servers, Poisson arrivals, one
non-preemptive priority rule, and a mean-wait reduction. Rates, classes,
priorities, and the horizon are IR parameters. Other disciplines, server
counts, and metrics are rejected rather than defaulted.
"""

from __future__ import annotations

import copy
import math
from typing import Any

from sim_engine_compiler.diagnostics import CompilationError
from sim_engine_compiler.identity.common import content_digest
from sim_engine_compiler.ir.layers import digest

SCHEMA = "multi-server-queue-v1-input-v1"
PROFILE = "multi-server-queue-v1"
DOMAIN = "multi-server-queue"
SEMANTIC_PROFILE = "event-time-queue-v1"
WORK_POLICY = "nonpreemptive-priority"
RNG_PROFILE = "cpython-mt19937-v1"
BUSINESS_VERSION = "multi-server-queue-business-ir/v1"
CORE_VERSION = "multi-server-queue-core-ir/v1"
PLAN_VERSION = "multi-server-queue-plan/v1"
LINEAGE_VERSION = "multi-server-queue-lineage/v1"
PACK_VERSION = "multi-server-queue-pack/v1"
OPERATION_CLASS = "restricted-queue-profile"
ORDERING = ("priority_descending", "arrival_time", "customer_id")
SERVER_CHOICE = "lowest_index_idle"
DISCIPLINE = "nonpreemptive-priority"
MAX_ADMITTED_ARRIVALS = 10000
MAX_LOOP_STEPS = 100000
MAX_HORIZON_MINUTES = 10080
SECTIONS = frozenset({"horizon", "arrivals", "servers", "priority_rule", "metrics"})

OPERATIONS: tuple[dict[str, Any], ...] = (
    {
        "operation": "queue.poisson_arrival/v1",
        "inputs": ["arrival_rate_per_minute", "classes"],
        "outputs": ["customer"],
        "preconditions": ["arrival_time < horizon_minutes"],
        "reads": ["clock", "rng"],
        "writes": ["queue", "rng", "trace", "metrics"],
        "random": ["exponential_interarrival", "weighted_class"],
        "time": "event-scheduled",
        "ordering": "after-service-completion-at-equal-time",
        "preemption": False,
        "backends": ["python-reference", "rust-runtime"],
        "operation_class": OPERATION_CLASS,
    },
    {
        "operation": "queue.nonpreemptive_priority_seize/v1",
        "inputs": ["priority_rule", "servers", "waiting"],
        "outputs": ["service_assignment"],
        "preconditions": ["server_idle", "customer_waiting"],
        "reads": ["queue", "servers"],
        "writes": ["queue", "servers", "rng", "trace", "metrics"],
        "random": ["exponential_service"],
        "time": "immediate-on-arrival-or-completion",
        "preemption": False,
        "backends": ["python-reference", "rust-runtime"],
        "operation_class": OPERATION_CLASS,
    },
    {
        "operation": "queue.exponential_service/v1",
        "inputs": ["service_rate_per_minute"],
        "outputs": ["service_completion"],
        "preconditions": ["service_completion_time <= horizon_minutes"],
        "reads": ["servers", "clock"],
        "writes": ["servers", "trace", "metrics"],
        "random": [],
        "time": "event-scheduled",
        "preemption": False,
        "backends": ["python-reference", "rust-runtime"],
        "operation_class": OPERATION_CLASS,
    },
    {
        "operation": "queue.mean_wait/v1",
        "inputs": ["service_start_waits"],
        "outputs": ["mean_wait"],
        "preconditions": ["horizon_reached"],
        "reads": ["metrics"],
        "writes": ["metrics"],
        "random": [],
        "time": "horizon-reduction",
        "preemption": False,
        "reduction": "arithmetic_mean_of_queue_wait_for_customers_who_started_service",
        "backends": ["python-reference", "rust-runtime"],
        "operation_class": OPERATION_CLASS,
    },
)

EXAMPLE_INPUT: dict[str, Any] = {
    "schema_version": SCHEMA,
    "profile": PROFILE,
    "horizon": {"minutes": 60},
    "arrivals": {
        "process": "poisson",
        "rate_per_minute": 0.25,
        "classes": [
            {"id": "urgent", "priority": 2, "weight": 1},
            {"id": "routine", "priority": 1, "weight": 3},
        ],
    },
    "servers": [
        {"id": "server-a", "service_rate_per_minute": 0.5},
        {"id": "server-b", "service_rate_per_minute": 0.25},
    ],
    "priority_rule": {
        "id": "nonpreemptive-priority",
        "discipline": DISCIPLINE,
        "ordering": list(ORDERING),
        "server_choice": SERVER_CHOICE,
    },
    "metrics": {"names": ["mean_wait"]},
}


def _reject(path: str, message: str, code: str = "invalid_ir") -> None:
    raise CompilationError(message, code=code, source_path=path)


def _exact_keys(value: Any, keys: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        _reject(path, f"expected fields {sorted(keys)}")
    return value


def _identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 128 or any(ord(ch) < 32 for ch in value):
        _reject(path, "expected a nonempty stable business id of at most 128 characters")
    return value


def _int(value: Any, path: str, low: int, high: int) -> int:
    if type(value) is not int or isinstance(value, bool) or not low <= value <= high:
        _reject(path, f"expected an integer in [{low}, {high}]")
    return value


def _rate(value: Any, path: str) -> float:
    if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(value):
        _reject(path, "expected a finite positive rate")
    if not 0.0 < float(value) <= 1_000_000.0:
        _reject(path, "rate must be in (0, 1000000]")
    return float(value)


def _sha256(value: Any, path: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        _reject(path, "expected SHA-256")
    return value


def validate_canonical(inputs: Any) -> dict[str, Any]:
    """Validate a queue canonical document and return a deep copy."""
    if not isinstance(inputs, dict):
        _reject("schema_version", "canonical input must be an object", "unsupported_profile")
    raw = _exact_keys(inputs, {"schema_version", "profile", *SECTIONS}, "$")
    if raw["schema_version"] != SCHEMA:
        _reject(
            "schema_version",
            f"canonical schema {raw['schema_version']!r} is not {SCHEMA}",
            "unsupported_profile",
        )
    if raw["profile"] != PROFILE:
        _reject("profile", f"profile {raw['profile']!r} is not {PROFILE}", "unsupported_profile")
    horizon = _exact_keys(raw["horizon"], {"minutes"}, "horizon")
    minutes = _int(horizon["minutes"], "horizon.minutes", 1, MAX_HORIZON_MINUTES)
    arrivals = _exact_keys(raw["arrivals"], {"process", "rate_per_minute", "classes"}, "arrivals")
    if arrivals["process"] != "poisson":
        _reject("arrivals.process", "only a Poisson arrival process is admitted", "unsupported_profile")
    rate = _rate(arrivals["rate_per_minute"], "arrivals.rate_per_minute")
    if rate * minutes > MAX_ADMITTED_ARRIVALS:
        _reject(
            "arrivals.rate_per_minute",
            "expected arrivals exceed the restricted profile limit",
            "unsupported_profile",
        )
    classes = arrivals["classes"]
    if not isinstance(classes, list) or not 1 <= len(classes) <= 8:
        _reject("arrivals.classes", "expected 1 to 8 arrival classes")
    seen: set[str] = set()
    normalized_classes = []
    for index, item in enumerate(classes):
        path = f"arrivals.classes[{index}]"
        row = _exact_keys(item, {"id", "priority", "weight"}, path)
        identity = _identifier(row["id"], f"{path}.id")
        if identity in seen:
            _reject(f"{path}.id", "duplicate class id")
        seen.add(identity)
        normalized_classes.append({
            "id": identity,
            "priority": _int(row["priority"], f"{path}.priority", -1_000_000, 1_000_000),
            "weight": _int(row["weight"], f"{path}.weight", 1, 1_000_000),
        })
    servers = raw["servers"]
    if not isinstance(servers, list) or len(servers) != 2:
        _reject("servers", "this restricted profile requires exactly two servers", "unsupported_profile")
    normalized_servers = []
    for index, item in enumerate(servers):
        path = f"servers[{index}]"
        row = _exact_keys(item, {"id", "service_rate_per_minute"}, path)
        identity = _identifier(row["id"], f"{path}.id")
        if identity in seen:
            _reject(f"{path}.id", "server id collides with another stable id")
        seen.add(identity)
        normalized_servers.append({
            "id": identity,
            "service_rate_per_minute": _rate(row["service_rate_per_minute"], f"{path}.service_rate_per_minute"),
        })
    rule = _exact_keys(
        raw["priority_rule"],
        {"id", "discipline", "ordering", "server_choice"},
        "priority_rule",
    )
    rule_id = _identifier(rule["id"], "priority_rule.id")
    if rule_id in seen:
        _reject("priority_rule.id", "priority rule id collides with another stable id")
    seen.add(rule_id)
    if rule["discipline"] != DISCIPLINE:
        _reject(
            "priority_rule.discipline",
            f"discipline {rule['discipline']!r} is outside the restricted profile",
            "unsupported_profile",
        )
    if rule["ordering"] != list(ORDERING):
        _reject(
            "priority_rule.ordering",
            "ordering must be priority_descending, arrival_time, customer_id",
            "unsupported_profile",
        )
    if rule["server_choice"] != SERVER_CHOICE:
        _reject(
            "priority_rule.server_choice",
            f"server choice {rule['server_choice']!r} is outside the restricted profile",
            "unsupported_profile",
        )
    metrics = _exact_keys(raw["metrics"], {"names"}, "metrics")
    if metrics["names"] != ["mean_wait"]:
        _reject("metrics.names", "the admitted metric set is exactly ['mean_wait']", "unsupported_profile")
    if "mean_wait" in seen:
        _reject("metrics.names", "metric id collides with another stable id")
    return {
        "schema_version": SCHEMA,
        "profile": PROFILE,
        "horizon": {"minutes": minutes},
        "arrivals": {
            "process": "poisson",
            "rate_per_minute": rate,
            "classes": normalized_classes,
        },
        "servers": normalized_servers,
        "priority_rule": {
            "id": rule_id,
            "discipline": DISCIPLINE,
            "ordering": list(ORDERING),
            "server_choice": SERVER_CHOICE,
        },
        "metrics": {"names": ["mean_wait"]},
    }


def _sections_from_canonical(canonical: dict[str, Any]) -> dict[str, Any]:
    return {name: copy.deepcopy(canonical[name]) for name in sorted(SECTIONS)}


def _reject_unconsumed_sections(sections: Any) -> None:
    if not isinstance(sections, dict):
        _reject("business.sections", "expected section object")
    unknown = sorted(set(sections) - SECTIONS)
    if unknown:
        name = unknown[0]
        _reject(
            f"business.sections.{name}",
            f"Business section {name!r} is not consumed by profile {PROFILE}",
            "unconsumed_business_section",
        )
    missing = sorted(SECTIONS - set(sections))
    if missing:
        _reject(f"business.sections.{missing[0]}", f"Business section {missing[0]!r} is required")


class QueueBusiness:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    @classmethod
    def create(cls, payload: dict[str, Any]) -> "QueueBusiness":
        result = cls(copy.deepcopy(payload))
        result.validate()
        return result

    def validate(self) -> None:
        _exact_keys(self.payload, {"profile", "semantic_profile", "source", "sections"}, "business")
        if self.payload["profile"] != PROFILE:
            _reject("business.profile", f"unsupported profile {self.payload['profile']!r}", "unsupported_profile")
        if self.payload["semantic_profile"] != SEMANTIC_PROFILE:
            _reject(
                "business.semantic_profile",
                f"unsupported semantic profile {self.payload['semantic_profile']!r}",
                "unsupported_profile",
            )
        source = _exact_keys(self.payload["source"], {"schema_version", "canonical_sha256"}, "business.source")
        if source["schema_version"] != SCHEMA:
            _reject(
                "business.source.schema_version",
                f"unsupported input schema {source['schema_version']!r}",
                "unsupported_profile",
            )
        _sha256(source["canonical_sha256"], "business.source.canonical_sha256")
        _reject_unconsumed_sections(self.payload["sections"])
        rebuilt = _sections_from_canonical(validate_canonical({
            "schema_version": SCHEMA,
            "profile": PROFILE,
            **self.payload["sections"],
        }))
        if rebuilt != self.payload["sections"]:
            _reject("business.sections", "queue sections do not match the normalized profile contract")

    @property
    def fingerprint(self) -> str:
        return digest({"version": BUSINESS_VERSION, "payload": self.payload})

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "version": BUSINESS_VERSION,
            "fingerprint": self.fingerprint,
            "payload": copy.deepcopy(self.payload),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "QueueBusiness":
        raw = _exact_keys(value, {"version", "fingerprint", "payload"}, "business")
        if raw["version"] != BUSINESS_VERSION:
            _reject("business.version", f"unsupported Business IR version {raw['version']!r}", "unsupported_business_version")
        result = cls.create(raw["payload"])
        if result.fingerprint != raw["fingerprint"]:
            _reject("business.fingerprint", "Business IR checksum mismatch")
        return result


def import_canonical(inputs: Any) -> QueueBusiness:
    canonical = validate_canonical(inputs)
    return QueueBusiness.create({
        "profile": PROFILE,
        "semantic_profile": SEMANTIC_PROFILE,
        "source": {"schema_version": SCHEMA, "canonical_sha256": digest(canonical)},
        "sections": _sections_from_canonical(canonical),
    })


def _operations() -> list[dict[str, Any]]:
    return copy.deepcopy(list(OPERATIONS))


def lower(business: QueueBusiness) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Lower a validated queue Business revision to Core, Plan, and lineage."""
    business.validate()
    sections = business.payload["sections"]
    canonical = validate_canonical({
        "schema_version": SCHEMA,
        "profile": PROFILE,
        **sections,
    })
    classes = []
    for index, item in enumerate(canonical["arrivals"]["classes"]):
        classes.append({
            "id": item["id"],
            "priority": item["priority"],
            "weight": item["weight"],
            "source_path": f"arrivals.classes[{index}]",
        })
    servers = []
    for index, item in enumerate(canonical["servers"]):
        servers.append({
            "id": item["id"],
            "index": index,
            "service_rate_per_minute": item["service_rate_per_minute"],
            "source_path": f"servers[{index}]",
        })
    rule = {
        **canonical["priority_rule"],
        "source_path": "priority_rule",
    }
    core_payload = {
        "source": {
            "business_fingerprint": business.fingerprint,
            "canonical_sha256": business.payload["source"]["canonical_sha256"],
            "origin_canonical_sha256": business.payload["source"]["canonical_sha256"],
        },
        "contract": {
            "domain": DOMAIN,
            "profile": PROFILE,
            "semantic_profile": SEMANTIC_PROFILE,
            "work_policy": WORK_POLICY,
            "rng_profile": RNG_PROFILE,
            "duration_minutes": canonical["horizon"]["minutes"],
            "operation_class": OPERATION_CLASS,
        },
        "operations": _operations(),
        "arrival": {
            "process": "poisson",
            "rate_per_minute": canonical["arrivals"]["rate_per_minute"],
            "source_path": "arrivals",
        },
        "tables": {
            "classes": classes,
            "servers": servers,
            "rules": [rule],
            "metrics": [{"id": "mean_wait", "source_path": "metrics.names[0]"}],
        },
        "limits": {
            "max_admitted_arrivals": MAX_ADMITTED_ARRIVALS,
            "max_loop_steps": MAX_LOOP_STEPS,
        },
    }
    core = {
        "version": CORE_VERSION,
        "fingerprint": digest({"version": CORE_VERSION, "payload": core_payload}),
        "payload": core_payload,
    }
    plan = {
        "plan_version": PLAN_VERSION,
        "domain": DOMAIN,
        "profile": PROFILE,
        "semantic_profile": SEMANTIC_PROFILE,
        "work_policy": WORK_POLICY,
        "rng_profile": RNG_PROFILE,
        "source_inputs_sha256": core_payload["source"]["canonical_sha256"],
        "business_fingerprint": business.fingerprint,
        "core_fingerprint": core["fingerprint"],
        "duration_minutes": canonical["horizon"]["minutes"],
        "horizon_minutes": canonical["horizon"]["minutes"],
        "arrival_rate_per_minute": canonical["arrivals"]["rate_per_minute"],
        "classes": classes,
        "servers": servers,
        "priority_rule": rule,
        "metrics": ["mean_wait"],
        "operations": _operations(),
        "limits": {
            "max_admitted_arrivals": MAX_ADMITTED_ARRIVALS,
            "max_loop_steps": MAX_LOOP_STEPS,
        },
    }
    symbols = [
        {"id": "arrivals", "plan_path": "arrival_rate_per_minute", "core_path": "arrival", "source_path": "arrivals"},
        {"id": "horizon", "plan_path": "horizon_minutes", "core_path": "contract.duration_minutes", "source_path": "horizon"},
        {"id": rule["id"], "plan_path": "priority_rule", "core_path": "tables.rules[0]", "source_path": "priority_rule"},
        {"id": "mean_wait", "plan_path": "metrics[0]", "core_path": "tables.metrics[0]", "source_path": "metrics.names[0]"},
    ]
    for index, item in enumerate(classes):
        symbols.append({
            "id": item["id"],
            "plan_path": f"classes[{index}]",
            "core_path": f"tables.classes[{index}]",
            "source_path": item["source_path"],
        })
    for index, item in enumerate(servers):
        symbols.append({
            "id": item["id"],
            "plan_path": f"servers[{index}]",
            "core_path": f"tables.servers[{index}]",
            "source_path": item["source_path"],
        })
    lineage = {
        "version": LINEAGE_VERSION,
        "business_fingerprint": business.fingerprint,
        "core_fingerprint": core["fingerprint"],
        "plan_fingerprint": content_digest(plan),
        "canonical_sha256": core_payload["source"]["canonical_sha256"],
        "symbols": symbols,
    }
    validate_plan(plan)
    return core, plan, lineage


def validate_plan(plan: Any) -> dict[str, Any]:
    """Reject plans outside the restricted queue contract. Returns the same object."""
    if not isinstance(plan, dict):
        _reject("plan", "queue plan must be an object")
    _exact_keys(plan, {
        "plan_version", "domain", "profile", "semantic_profile", "work_policy", "rng_profile",
        "source_inputs_sha256", "business_fingerprint", "core_fingerprint", "duration_minutes",
        "horizon_minutes", "arrival_rate_per_minute", "classes", "servers", "priority_rule",
        "metrics", "operations", "limits",
    }, "plan")
    if plan["plan_version"] != PLAN_VERSION:
        _reject("plan.plan_version", f"unsupported plan version {plan['plan_version']!r}", "unsupported_profile")
    if plan["domain"] != DOMAIN or plan["profile"] != PROFILE:
        _reject("plan.profile", "queue plan profile does not match the restricted contract", "unsupported_profile")
    if plan["semantic_profile"] != SEMANTIC_PROFILE or plan["work_policy"] != WORK_POLICY or plan["rng_profile"] != RNG_PROFILE:
        _reject("plan.semantic_profile", "unsupported queue execution contract", "unsupported_profile")
    _sha256(plan["source_inputs_sha256"], "plan.source_inputs_sha256")
    _sha256(plan["business_fingerprint"], "plan.business_fingerprint")
    _sha256(plan["core_fingerprint"], "plan.core_fingerprint")
    horizon = _int(plan["duration_minutes"], "plan.duration_minutes", 1, MAX_HORIZON_MINUTES)
    if plan["horizon_minutes"] != horizon:
        _reject("plan.horizon_minutes", "horizon_minutes must equal duration_minutes")
    rate = _rate(plan["arrival_rate_per_minute"], "plan.arrival_rate_per_minute")
    if rate * horizon > MAX_ADMITTED_ARRIVALS:
        _reject("plan.arrival_rate_per_minute", "expected arrivals exceed the restricted profile limit", "unsupported_profile")
    if plan["operations"] != _operations():
        _reject("plan.operations", "unknown or incomplete queue operation contract", "unsupported_operation")
    if plan["limits"] != {"max_admitted_arrivals": MAX_ADMITTED_ARRIVALS, "max_loop_steps": MAX_LOOP_STEPS}:
        _reject("plan.limits", "queue resource limits are fixed by the restricted profile", "unsupported_profile")
    if plan["metrics"] != ["mean_wait"]:
        _reject("plan.metrics", "the admitted metric set is exactly ['mean_wait']", "unsupported_profile")
    classes = plan["classes"]
    servers = plan["servers"]
    if not isinstance(classes, list) or not 1 <= len(classes) <= 8:
        _reject("plan.classes", "expected 1 to 8 arrival classes")
    if not isinstance(servers, list) or len(servers) != 2:
        _reject("plan.servers", "this restricted profile requires exactly two servers", "unsupported_profile")
    seen: set[str] = set()
    for index, item in enumerate(classes):
        path = f"plan.classes[{index}]"
        _exact_keys(item, {"id", "priority", "weight", "source_path"}, path)
        identity = _identifier(item["id"], f"{path}.id")
        if identity in seen:
            _reject(f"{path}.id", "duplicate class id")
        seen.add(identity)
        _int(item["priority"], f"{path}.priority", -1_000_000, 1_000_000)
        _int(item["weight"], f"{path}.weight", 1, 1_000_000)
        if item["source_path"] != f"arrivals.classes[{index}]":
            _reject(f"{path}.source_path", "class source path does not match its position")
    for index, item in enumerate(servers):
        path = f"plan.servers[{index}]"
        _exact_keys(item, {"id", "index", "service_rate_per_minute", "source_path"}, path)
        identity = _identifier(item["id"], f"{path}.id")
        if identity in seen or item["index"] != index:
            _reject(path, "invalid or duplicate server identity")
        seen.add(identity)
        _rate(item["service_rate_per_minute"], f"{path}.service_rate_per_minute")
        if item["source_path"] != f"servers[{index}]":
            _reject(f"{path}.source_path", "server source path does not match its position")
    rule = _exact_keys(
        plan["priority_rule"],
        {"id", "discipline", "ordering", "server_choice", "source_path"},
        "plan.priority_rule",
    )
    if rule["id"] in seen or rule["discipline"] != DISCIPLINE or rule["ordering"] != list(ORDERING):
        _reject("plan.priority_rule", "unsupported priority rule", "unsupported_profile")
    if rule["server_choice"] != SERVER_CHOICE or rule["source_path"] != "priority_rule":
        _reject("plan.priority_rule", "unsupported priority rule", "unsupported_profile")
    return plan


class QueuePlanView:
    """Attribute view used by the product manifest. The persisted body is the plan dict."""

    def __init__(self, document: dict[str, Any]):
        self.document = validate_plan(document)
        self.semantic_profile = document["semantic_profile"]
        self.rng_profile = document["rng_profile"]
        self.work_policy = document["work_policy"]
        self.source_inputs_sha256 = document["source_inputs_sha256"]
        self.fingerprint = content_digest(document)

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self.document)
