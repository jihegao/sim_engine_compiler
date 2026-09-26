"""Public, JSON-only identity inspection for persisted model artifacts.

The functions in this module do not compile canonical input and do not infer a
missing layer.  A bundle association is reported as verified only after the
persisted artifacts have independently reloaded and the existing compiler has
reproduced the Business -> Core and Core -> Plan relationships.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from typing import Any

from sim_engine_compiler.compiler.layout import TABLE_TYPES, _record, compile_core
from sim_engine_compiler.compiler.layout import lineage as make_lineage
from sim_engine_compiler.diagnostics import CompilationError
from sim_engine_compiler.domains.aircraft_support.lowering import lower_business
from sim_engine_compiler.identity.common import content_digest, diagnostic, json_value
from sim_engine_compiler.ir.layers import (
    BUSINESS_VERSION,
    CORE_VERSION,
    PROFILES,
    TABLE_IDS,
    BusinessIR,
    CoreIR,
)
from sim_engine_compiler.ir.plan import (
    LEGACY_MINUTE_PHASES,
    PLAN_VERSION,
    ExecutionPlan,
)

ARTIFACT_SCHEMA = "model-artifact-identity/v1"
BUNDLE_SCHEMA = "model-bundle-identity/v1"
LINEAGE_VERSION = "compiler-lineage/v2"
_SHA256_LENGTH = 64
_VALUE_PROVENANCE = ["explicit", "default", "normalized", "derived", "unknown"]
_ELEMENT_CATEGORIES = [
    "business_entity", "domain_rule_definition", "compiler_operation",
    "runtime_process_instance",
]
_VALIDATION_ERRORS = (
    AttributeError, CompilationError, IndexError, KeyError, RecursionError,
    TypeError, ValueError,
)


def _status(diagnostics: list[dict[str, Any]], *, partial: bool = False) -> str:
    if any(item["severity"] == "error" for item in diagnostics):
        if any(item["code"].startswith("unsupported_") for item in diagnostics):
            return "unsupported"
        return "invalid"
    return "partial" if partial else "valid"


def _base(layer: str, value: Any) -> dict[str, Any]:
    return {
        "schema_version": ARTIFACT_SCHEMA,
        "status": "invalid",
        "layer": layer,
        "identity": {
            "content_digest": content_digest(value),
            "producer": {
                "compiler_version": None,
                "domain_package_version": None,
                "status": "unknown",
            },
            "revision_id": None,
            "revision_status": "unknown",
        },
        "elements": [],
        "coverage": {
            "level": "none", "operations": [],
            "value_provenance_vocabulary": _VALUE_PROVENANCE,
            "element_category_vocabulary": _ELEMENT_CATEGORIES,
        },
        "diagnostics": [],
    }


def _source(source_path: Any) -> dict[str, Any]:
    if isinstance(source_path, str) and source_path:
        return {"kind": "source-mapped", "source_path": source_path,
                "value_origin": "unknown"}
    return {"kind": "unknown", "source_path": None, "value_origin": "unknown"}


def _business_elements(business: BusinessIR) -> list[dict[str, Any]]:
    elements = []
    for section in sorted(business.payload["sections"]):
        collections = business.payload["sections"][section]["collections"]
        for collection in sorted(collections):
            for entity in collections[collection]:
                elements.append({
                    "element_id": entity["business_id"],
                    "category": "business_entity",
                    "kind": f"{section}.{collection}",
                    "provenance": _source(entity.get("source_path")),
                })
    return elements


def _core_elements(core: CoreIR) -> list[dict[str, Any]]:
    elements = []
    for table, rows in core.payload["tables"].items():
        for row in rows:
            elements.append({
                "element_id": f"{table}/{row['id']}",
                "raw_id": row["id"],
                "category": "business_entity",
                "kind": table,
                "core_path": f"tables.{table}.{row['id']}",
                "provenance": _source(row.get("source_path")),
            })
            if table == "activities":
                for step in row["steps"]:
                    elements.append({
                        "element_id": f"activities/{row['id']}/steps/{step['id']}",
                        "raw_id": step["id"],
                        "category": "compiler_operation",
                        "kind": "activity_step",
                        "core_path": f"tables.activities.{row['id']}.steps.{step['id']}",
                        "provenance": _source(step["attributes"].get("source_path")),
                    })
    return elements


def _plan_elements(plan: ExecutionPlan) -> list[dict[str, Any]]:
    value = plan.to_dict()
    identity_fields = {
        "aircraft": "tail_number",
        "missions": "mission_id",
        "activities": "activity_id",
        "resource_nodes": "node_id",
        "components": "component_id",
        "supply_routes": "route_id",
    }
    elements = []
    for table, identity_field in identity_fields.items():
        for index, row in enumerate(value[table]):
            elements.append({
                "element_id": row[identity_field],
                "category": "business_entity",
                "kind": table,
                "plan_path": f"{table}[{index}]",
                "provenance": _source(row.get("source_path")),
            })
            if table == "activities":
                for step_index, step in enumerate(row["steps"]):
                    elements.append({
                        "element_id": f"activities/{row[identity_field]}/steps/{step['code']}",
                        "category": "compiler_operation",
                        "kind": "activity_step",
                        "plan_path": f"activities[{index}].steps[{step_index}]",
                        "provenance": _source(step.get("source_path")),
                    })
    # The compatibility Plan does not persist the stable preventive-cycle
    # symbol.  Keep its source, but explicitly decline to invent an identity.
    for index, row in enumerate(value["preventive_cycles"]):
        elements.append({
            "element_id": None,
            "identity_status": "unavailable-in-plan",
            "category": "business_entity",
            "kind": "preventive_cycles",
            "plan_path": f"preventive_cycles[{index}]",
            "provenance": _source(row.get("source_path")),
        })
    return elements


def _operation_coverage(core: CoreIR) -> list[dict[str, Any]]:
    return [
        {
            "operation": operation["operation"],
            "category": "compiler_operation",
            "status": "partial",
            "precision": operation["effect_precision"],
            "limitation": "compatibility phase operation is coarser than a domain-rule mapping",
        }
        for operation in core.payload["operations"]
    ]


def _lineage(value: Mapping[str, Any]) -> dict[str, Any]:
    result = _base("lineage", value)
    required = {
        "version", "business_fingerprint", "core_fingerprint",
        "plan_fingerprint", "canonical_sha256", "symbols",
    }
    if set(value) != required or value.get("version") != LINEAGE_VERSION:
        result["diagnostics"].append(diagnostic(
            "unsupported_lineage_schema", "expected compiler-lineage/v2",
            stage="lineage", path="version",
        ))
        result["status"] = _status(result["diagnostics"])
        return result
    for field in required - {"version", "symbols"}:
        item = value[field]
        if (not isinstance(item, str) or len(item) != _SHA256_LENGTH
                or any(character not in "0123456789abcdef" for character in item)):
            result["diagnostics"].append(diagnostic(
                "invalid_lineage_fingerprint", "expected SHA-256",
                stage="lineage", path=field,
            ))
    symbols = value["symbols"]
    if not isinstance(symbols, dict) or set(symbols) != set(TABLE_IDS):
        result["diagnostics"].append(diagnostic(
            "invalid_lineage_symbols", "symbols must contain exactly the supported Core tables",
            stage="lineage", path="symbols",
        ))
    else:
        for table, rows in symbols.items():
            if not isinstance(rows, list):
                result["diagnostics"].append(diagnostic(
                    "invalid_lineage_symbols", "symbol table must be a list",
                    stage="lineage", path=f"symbols.{table}",
                ))
                continue
            seen_ids: set[str] = set()
            seen_paths: set[str] = set()
            for index, row in enumerate(rows):
                path = f"symbols.{table}[{index}]"
                expected_path = f"{table}[{index}]"
                if (not isinstance(row, dict)
                        or set(row) != {"id", "plan_path", "source_path"}
                        or not all(isinstance(row.get(key), str) and row[key]
                                   for key in ("id", "plan_path", "source_path"))
                        or row.get("plan_path") != expected_path
                        or row.get("id") in seen_ids
                        or row.get("plan_path") in seen_paths):
                    result["diagnostics"].append(diagnostic(
                        "invalid_lineage_symbol", "invalid, duplicate, or non-canonical symbol entry",
                        stage="lineage", path=path,
                    ))
                    continue
                seen_ids.add(row["id"])
                seen_paths.add(row["plan_path"])
    result["identity"].update({
        "schema_version": value["version"],
        "business_fingerprint": value["business_fingerprint"],
        "core_fingerprint": value["core_fingerprint"],
        "plan_fingerprint": value["plan_fingerprint"],
        "input_fingerprint": value["canonical_sha256"],
    })
    result["coverage"] = {
        "level": "identity-only", "operations": [],
        "value_provenance_vocabulary": _VALUE_PROVENANCE,
        "element_category_vocabulary": _ELEMENT_CATEGORIES,
    }
    result["status"] = _status(result["diagnostics"])
    return result


def _plan_contract_diagnostics(raw: dict[str, Any], plan: ExecutionPlan) -> list[dict[str, Any]]:
    diagnostics = []
    round_tripped = json.loads(json.dumps(plan.to_dict(), ensure_ascii=False, allow_nan=False))
    if content_digest(round_tripped) != content_digest(raw):
        diagnostics.append(diagnostic(
            "artifact_validation_failed",
            "Plan fields or JSON types do not round-trip through the persisted contract",
            stage="validation", path="$",
        ))
    if plan.domain != "aircraft-support":
        diagnostics.append(diagnostic(
            "unsupported_plan_domain", f"unsupported Plan domain {plan.domain!r}",
            stage="validation", path="domain",
        ))
    if plan.semantic_profile not in PROFILES:
        diagnostics.append(diagnostic(
            "unsupported_semantic_profile", f"unsupported semantic profile {plan.semantic_profile!r}",
            stage="validation", path="semantic_profile",
        ))
    if (plan.work_policy != "stable-topological-serial"
            or plan.rng_profile != "legacy-sequential-v1"
            or plan.phases != LEGACY_MINUTE_PHASES
            or plan.unsupported_features):
        diagnostics.append(diagnostic(
            "unsupported_plan_contract", "unsupported work, RNG, phase, or feature contract",
            stage="validation", path="$",
        ))
    if (type(raw.get("duration_minutes")) is not int
            or raw["duration_minutes"] <= 0
            or type(raw.get("natural_completion_enabled")) is not bool
            or not isinstance(plan.source_inputs_sha256, str)
            or len(plan.source_inputs_sha256) != _SHA256_LENGTH
            or any(character not in "0123456789abcdef" for character in plan.source_inputs_sha256)):
        diagnostics.append(diagnostic(
            "artifact_validation_failed", "invalid Plan scalar or input fingerprint",
            stage="validation", path="$",
        ))
    if "resource_dispatch_index" in raw:
        diagnostics.append(diagnostic(
            "unsupported_resource_dispatch_index_identity_contract",
            "resource dispatch index integrity is outside model-artifact-identity/v1",
            stage="validation", path="resource_dispatch_index",
        ))
    try:
        _validate_plan_tables(raw)
    except _VALIDATION_ERRORS as exc:
        diagnostics.append(diagnostic(
            "artifact_validation_failed", str(exc), stage="validation",
            path=getattr(exc, "source_path", None),
        ))
    return diagnostics


def _validate_plan_tables(raw: dict[str, Any]) -> None:
    """Apply the compiler's typed layout checks plus reference integrity."""
    identity_fields = {
        "aircraft": "tail_number",
        "missions": "mission_id",
        "activities": "activity_id",
        "resource_nodes": "node_id",
        "components": "component_id",
        "preventive_cycles": None,
        "supply_routes": "route_id",
    }
    tables: dict[str, list[dict[str, Any]]] = {}
    for table, identity_field in identity_fields.items():
        rows = raw.get(table)
        if not isinstance(rows, list):
            raise TypeError(f"{table} must be a list")
        tables[table] = rows
        seen: set[str] = set()
        for index, row in enumerate(rows):
            _record(row, TABLE_TYPES[table], f"plan.{table}[{index}]")
            if type(row["index"]) is not int or row["index"] != index:
                raise ValueError(f"plan.{table}[{index}].index must equal its persisted position")
            if "source_path" in row and (
                not isinstance(row["source_path"], str) or not row["source_path"]
            ):
                raise ValueError(f"plan.{table}[{index}].source_path is required")
            if identity_field is not None:
                identity = row[identity_field]
                if not isinstance(identity, str) or not identity or identity in seen:
                    raise ValueError(f"plan.{table}[{index}] has invalid or duplicate stable identity")
                seen.add(identity)

    def reference(table: str, row: int, field: str, target: str, *, optional: bool = False) -> None:
        value = tables[table][row][field]
        if type(value) is not int or (optional and value == -1):
            if optional and value == -1:
                return
            raise ValueError(f"plan.{table}[{row}].{field} must be an integer reference")
        if not 0 <= value < len(tables[target]):
            raise ValueError(f"plan.{table}[{row}].{field} is out of range")

    nonnegative_fields = {
        "aircraft": ("initial_calendar_days", "initial_cycles"),
        "missions": (
            "planned_start", "preparation_start", "duration_minutes", "required_aircraft",
            "min_required_aircraft", "priority", "cancel_minutes",
        ),
        "activities": ("priority",),
        "resource_nodes": ("personnel_capacity", "equipment_capacity"),
        "components": ("quantity", "failure_threshold", "repair_duration_minutes"),
        "preventive_cycles": (
            "calendar_days", "landing_cycles", "initial_calendar_days", "initial_landing_cycles",
        ),
        "supply_routes": ("capacity", "transport_minutes"),
    }
    for table, fields in nonnegative_fields.items():
        for index, row in enumerate(tables[table]):
            for field in fields:
                if type(row[field]) is not int or row[field] < 0:
                    raise ValueError(f"plan.{table}[{index}].{field} must be a nonnegative integer")

    for index, activity in enumerate(tables["activities"]):
        reference("activities", index, "resource_node_index", "resource_nodes")
        reference("activities", index, "equipment_component_index", "components", optional=True)
        seen_steps: set[str] = set()
        for step_index, step in enumerate(activity["steps"]):
            if type(step["index"]) is not int or step["index"] != step_index:
                raise ValueError(f"plan.activities[{index}].steps[{step_index}].index is not canonical")
            if not step["code"] or step["code"] in seen_steps:
                raise ValueError(f"plan.activities[{index}] has invalid or duplicate step code")
            seen_steps.add(step["code"])
            for field in ("duration_minutes", "personnel", "equipment"):
                if type(step[field]) is not int or step[field] < 0:
                    raise ValueError(f"plan.activities[{index}].steps[{step_index}].{field} is invalid")
            if any(type(quantity) is not int or quantity < 0 for _, quantity in step["spares"]):
                raise ValueError(f"plan.activities[{index}].steps[{step_index}].spares is invalid")
            if (len(set(step["predecessors"])) != len(step["predecessors"])
                    or any(type(value) is not int or not 0 <= value < step_index
                           for value in step["predecessors"])):
                raise ValueError(f"plan.activities[{index}].steps[{step_index}].predecessors is invalid")
    for index, node in enumerate(tables["resource_nodes"]):
        if any(type(quantity) is not int or quantity < 0 for _, quantity in node["inventory"]):
            raise ValueError(f"plan.resource_nodes[{index}].inventory is invalid")
    for index, component in enumerate(tables["components"]):
        reference("components", index, "parent_index", "components", optional=True)
        reference("components", index, "repair_activity_index", "activities", optional=True)
        aircraft = component["aircraft_indexes"]
        if (len(set(aircraft)) != len(aircraft)
                or any(type(value) is not int or not 0 <= value < len(tables["aircraft"])
                       for value in aircraft)):
            raise ValueError(f"plan.components[{index}].aircraft_indexes is invalid")
    for index in range(len(tables["preventive_cycles"])):
        reference("preventive_cycles", index, "aircraft_index", "aircraft")
        reference("preventive_cycles", index, "activity_index", "activities")
    for index in range(len(tables["supply_routes"])):
        reference("supply_routes", index, "source_node_index", "resource_nodes")
        reference("supply_routes", index, "destination_node_index", "resource_nodes")


def inspect_artifact(value: Mapping[str, Any]) -> dict[str, Any]:
    """Inspect one persisted Business, Core, Plan, or lineage JSON object."""
    try:
        raw = json_value(value)
    except (RecursionError, TypeError, ValueError) as exc:
        result = {
            "schema_version": ARTIFACT_SCHEMA, "status": "invalid", "layer": "unknown",
            "identity": {}, "elements": [],
            "coverage": {"level": "none", "operations": [],
                         "value_provenance_vocabulary": _VALUE_PROVENANCE,
                         "element_category_vocabulary": _ELEMENT_CATEGORIES},
            "diagnostics": [diagnostic("invalid_json_value", str(exc), path="$")],
        }
        return result
    if not isinstance(raw, dict):
        result = _base("unknown", raw)
        result["diagnostics"].append(diagnostic(
            "invalid_artifact_envelope", "artifact must be a JSON object", path="$",
        ))
        result["status"] = "invalid"
        return result

    version = raw.get("version")
    plan_version = raw.get("plan_version")
    if version == LINEAGE_VERSION:
        return _lineage(raw)
    if isinstance(version, str) and version.startswith(("abm-", "production-")):
        result = _base("unknown", raw)
        result["diagnostics"].append(diagnostic(
            "unsupported_artifact_domain", f"artifact schema {version!r} is not supported by this contract",
            path="version",
        ))
        result["status"] = "unsupported"
        return result
    if isinstance(plan_version, str) and plan_version.startswith(("abm-", "production-")):
        result = _base("plan", raw)
        result["diagnostics"].append(diagnostic(
            "unsupported_artifact_domain", f"Plan schema {plan_version!r} is not supported by this contract",
            path="plan_version",
        ))
        result["status"] = "unsupported"
        return result
    if (isinstance(raw.get("domain"), str) and raw.get("domain") != "aircraft-support"
            and isinstance(raw.get("schema"), str)):
        result = _base("unknown", raw)
        result["diagnostics"].append(diagnostic(
            "unsupported_artifact_domain",
            f"domain {raw['domain']!r} with schema {raw['schema']!r} is outside this contract",
            path="domain",
        ))
        result["status"] = "unsupported"
        return result
    payload = raw.get("payload")
    if version == BUSINESS_VERSION and isinstance(payload, dict):
        profile = payload.get("semantic_profile")
        source = payload.get("source")
        input_schema = source.get("schema_version") if isinstance(source, dict) else None
        if isinstance(profile, str) and profile not in PROFILES:
            result = _base("business", raw)
            result["diagnostics"].append(diagnostic(
                "unsupported_semantic_profile", f"unsupported semantic profile {profile!r}",
                stage="validation", path="payload.semantic_profile",
            ))
            result["status"] = "unsupported"
            return result
        if isinstance(input_schema, str) and input_schema != "aircraft-support-v1-input-v1":
            result = _base("business", raw)
            result["diagnostics"].append(diagnostic(
                "unsupported_input_schema", f"unsupported input schema {input_schema!r}",
                stage="validation", path="payload.source.schema_version",
            ))
            result["status"] = "unsupported"
            return result
    if version == CORE_VERSION and isinstance(payload, dict):
        contract = payload.get("contract")
        if isinstance(contract, dict):
            domain = contract.get("domain")
            profile = contract.get("semantic_profile")
            if isinstance(domain, str) and domain != "aircraft-support":
                result = _base("core", raw)
                result["diagnostics"].append(diagnostic(
                    "unsupported_core_domain", f"unsupported Core domain {domain!r}",
                    stage="validation", path="payload.contract.domain",
                ))
                result["status"] = "unsupported"
                return result
            if isinstance(profile, str) and profile not in PROFILES:
                result = _base("core", raw)
                result["diagnostics"].append(diagnostic(
                    "unsupported_semantic_profile", f"unsupported semantic profile {profile!r}",
                    stage="validation", path="payload.contract.semantic_profile",
                ))
                result["status"] = "unsupported"
                return result

    try:
        if version == BUSINESS_VERSION:
            business = BusinessIR.from_dict(raw)
            result = _base("business", raw)
            result["identity"].update({
                "schema_version": version,
                "artifact_fingerprint": business.fingerprint,
                "profile": business.payload["semantic_profile"],
                "input_fingerprint": business.payload["source"]["canonical_sha256"],
                "input_schema": business.payload["source"]["schema_version"],
            })
            result["elements"] = _business_elements(business)
            result["coverage"] = {
                "level": "complete-for-persisted-business", "operations": [],
                "value_provenance_vocabulary": _VALUE_PROVENANCE,
                "element_category_vocabulary": _ELEMENT_CATEGORIES,
            }
            result["status"] = "valid"
            return result
        if version == CORE_VERSION:
            core = CoreIR.from_dict(raw)
            result = _base("core", raw)
            operations = _operation_coverage(core)
            result["identity"].update({
                "schema_version": version,
                "artifact_fingerprint": core.fingerprint,
                "profile": core.payload["contract"]["semantic_profile"],
                "domain": core.payload["contract"]["domain"],
                "input_fingerprint": core.payload["source"]["canonical_sha256"],
                "business_fingerprint": core.payload["source"]["business_fingerprint"],
            })
            result["elements"] = _core_elements(core)
            result["coverage"] = {
                "level": "partial", "operations": operations,
                "value_provenance_vocabulary": _VALUE_PROVENANCE,
                "element_category_vocabulary": _ELEMENT_CATEGORIES,
            }
            result["diagnostics"].append(diagnostic(
                "coarse_operation_mapping", "Core operations are compatibility phases, not complete domain-rule mappings",
                stage="coverage", severity="warning",
            ))
            result["status"] = "partial"
            return result
        if plan_version == PLAN_VERSION:
            plan = ExecutionPlan.from_dict(raw)
            result = _base("plan", raw)
            result["diagnostics"].extend(_plan_contract_diagnostics(raw, plan))
            if result["diagnostics"]:
                result["status"] = _status(result["diagnostics"])
                return result
            result["identity"].update({
                "schema_version": plan_version,
                "plan_fingerprint": plan.fingerprint,
                "artifact_fingerprint": plan.fingerprint,
                "profile": plan.semantic_profile,
                "domain": plan.domain,
                "input_fingerprint": plan.source_inputs_sha256,
            })
            result["elements"] = _plan_elements(plan)
            result["coverage"] = {
                "level": "partial", "operations": [],
                "value_provenance_vocabulary": _VALUE_PROVENANCE,
                "element_category_vocabulary": _ELEMENT_CATEGORIES,
            }
            result["diagnostics"].append(diagnostic(
                "plan_rule_mapping_unavailable", "Plan has stable entities but no complete domain-rule mapping",
                stage="coverage", severity="warning",
            ))
            result["status"] = "partial"
            return result
    except _VALIDATION_ERRORS as exc:
        layer = "business" if version == BUSINESS_VERSION else "core" if version == CORE_VERSION else "plan"
        result = _base(layer, raw)
        code = getattr(exc, "code", None)
        stable_code = "unsupported_operation" if code == "unsupported_operation" else "artifact_validation_failed"
        result["diagnostics"].append(diagnostic(
            stable_code, str(exc), stage="validation",
            path=getattr(exc, "source_path", None),
        ))
        result["status"] = "unsupported" if stable_code == "unsupported_operation" else "invalid"
        return result

    result = _base("unknown", raw)
    result["diagnostics"].append(diagnostic(
        "unsupported_artifact_schema", "unrecognized or missing artifact schema version",
        path="version" if "version" in raw else "plan_version",
    ))
    result["status"] = "unsupported"
    return result


def _mapping_by_source(business: BusinessIR, core: CoreIR) -> list[dict[str, Any]]:
    business_elements = _business_elements(business)
    core_elements = _core_elements(core)
    mappings = []
    for source in business_elements:
        source_path = source["provenance"]["source_path"]
        targets = sorted({
            (item["kind"], item["raw_id"], item["element_id"]) for item in core_elements
            if source_path is not None
            and item["provenance"]["source_path"] is not None
            and (item["provenance"]["source_path"] == source_path
                 or item["provenance"]["source_path"].startswith(source_path + "."))
        })
        if targets:
            mappings.append({
                "business_element_id": source["element_id"],
                "core_elements": [
                    {"table": table, "element_id": raw_id, "qualified_id": qualified_id}
                    for table, raw_id, qualified_id in targets
                ],
                "basis": "persisted-source-path",
            })
    return mappings


def _core_plan_mappings(lineage: Mapping[str, Any]) -> list[dict[str, Any]]:
    mappings = []
    for table in sorted(lineage["symbols"]):
        for symbol in lineage["symbols"][table]:
            mappings.append({
                "core_element": {
                    "table": table,
                    "element_id": symbol["id"],
                    "qualified_id": f"{table}/{symbol['id']}",
                },
                "plan_path": symbol["plan_path"],
                "source_path": symbol["source_path"],
                "basis": "verified-compiler-lineage/v2",
            })
    return mappings


def _core_identity_normal_form(core: CoreIR) -> dict[str, Any]:
    """Compare row layout separately without normalizing semantic sub-order."""
    value = copy.deepcopy(core.payload)
    for rows in value["tables"].values():
        rows.sort(key=lambda row: row["id"])
    return value


def inspect_bundle(*, business: Mapping[str, Any] | None = None,
                   core: Mapping[str, Any] | None = None,
                   plan: Mapping[str, Any] | None = None,
                   lineage: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Validate associations among independently persisted model artifacts."""
    supplied = {"business": business, "core": core, "plan": plan, "lineage": lineage}
    reports = {name: inspect_artifact(value) for name, value in supplied.items() if value is not None}
    diagnostics: list[dict[str, Any]] = []
    try:
        bundle_digest = content_digest({name: value for name, value in supplied.items() if value is not None})
    except (RecursionError, TypeError, ValueError):
        bundle_digest = None
    result: dict[str, Any] = {
        "schema_version": BUNDLE_SCHEMA,
        "status": "partial",
        "identity": {
            "bundle_digest": bundle_digest,
            "verified_artifact_digests": {
                name: report["identity"].get("content_digest") for name, report in reports.items()
                if report["status"] in ("valid", "partial")
            },
        },
        "layers": reports,
        "association_status": "unverified",
        "mappings": {"business_to_core": [], "core_to_plan": []},
        "coverage": {
            "level": "none", "operations": [],
            "value_provenance_vocabulary": _VALUE_PROVENANCE,
            "element_category_vocabulary": _ELEMENT_CATEGORIES,
        },
        "diagnostics": diagnostics,
    }
    if not reports:
        diagnostics.append(diagnostic("bundle_empty", "at least one persisted artifact is required", path="$"))
        result["status"] = "invalid"
        return result
    for name, report in reports.items():
        if report["layer"] != name:
            diagnostics.append(diagnostic(
                "bundle_layer_mismatch",
                f"{name} slot contains a {report['layer']} artifact",
                stage="bundle", path=name,
            ))
        if report["status"] in ("invalid", "unsupported"):
            diagnostics.extend(copy.deepcopy(report["diagnostics"]))
            diagnostics.append(diagnostic(
                "bundle_layer_not_valid", f"{name} layer is {report['status']}",
                stage="bundle", path=name,
            ))
    if diagnostics:
        result["status"] = "invalid" if (
            any(item["code"] == "bundle_layer_mismatch" for item in diagnostics)
            or any(report["status"] == "invalid" for report in reports.values())
        ) else "unsupported"
        return result

    missing = [name for name in ("business", "core", "plan", "lineage") if supplied[name] is None]
    for name in missing:
        diagnostics.append(diagnostic(
            f"{name}_missing", f"{name} layer was not supplied; association is incomplete",
            stage="bundle", path=name, severity="warning",
        ))

    try:
        business_obj = BusinessIR.from_dict(json_value(business)) if business is not None else None
        core_obj = CoreIR.from_dict(json_value(core)) if core is not None else None
        plan_obj = ExecutionPlan.from_dict(json_value(plan)) if plan is not None else None
        lineage_value = json_value(lineage) if lineage is not None else None
    except _VALIDATION_ERRORS as exc:
        diagnostics.append(diagnostic(
            "bundle_association_validation_failed", str(exc), stage="association", path="$",
        ))
        result["status"] = "invalid"
        return result

    if business_obj is not None and core_obj is not None:
        try:
            expected_core = lower_business(business_obj)
        except _VALIDATION_ERRORS as exc:
            diagnostics.append(diagnostic(
                "business_core_association_unavailable", str(exc),
                stage="association", path="business",
            ))
            result["status"] = "invalid"
            return result
        if expected_core.fingerprint != core_obj.fingerprint:
            if _core_identity_normal_form(expected_core) == _core_identity_normal_form(core_obj):
                diagnostics.append(diagnostic(
                    "business_core_layout_order_changed",
                    "stable Core symbols match but ordered-table semantics require separate review",
                    stage="association", path="core.tables", severity="warning",
                ))
            else:
                diagnostics.append(diagnostic(
                    "business_core_revision_mismatch",
                    "persisted Core is not the compiler result for the supplied Business revision",
                    stage="association", path="core",
                ))
        elif (core_obj.payload["source"]["business_fingerprint"] != business_obj.fingerprint
              or core_obj.payload["source"]["canonical_sha256"] != content_digest(business_obj.canonical_view())
              or core_obj.payload["source"]["origin_canonical_sha256"]
              != business_obj.payload["source"]["canonical_sha256"]):
            diagnostics.append(diagnostic(
                "business_core_source_mismatch", "Business/Core source identities disagree",
                stage="association", path="core.source",
            ))
        else:
            result["mappings"]["business_to_core"] = _mapping_by_source(business_obj, core_obj)

    if core_obj is not None and plan_obj is not None:
        try:
            expected_plan = compile_core(core_obj)
        except _VALIDATION_ERRORS as exc:
            diagnostics.append(diagnostic(
                "core_plan_association_unavailable", str(exc),
                stage="association", path="core",
            ))
            result["status"] = "invalid"
            return result
        if expected_plan.fingerprint != plan_obj.fingerprint:
            diagnostics.append(diagnostic(
                "core_plan_revision_mismatch", "Plan is not the layout result for the supplied Core revision",
                stage="association", path="plan",
            ))
        if (plan_obj.domain != core_obj.payload["contract"]["domain"]
                or plan_obj.semantic_profile != core_obj.payload["contract"]["semantic_profile"]
                or plan_obj.source_inputs_sha256 != core_obj.payload["source"]["canonical_sha256"]):
            diagnostics.append(diagnostic(
                "core_plan_contract_mismatch", "Core and Plan domain/profile/input identities disagree",
                stage="association", path="plan",
            ))

    if lineage_value is not None:
        identities = {
            "business_fingerprint": business_obj.fingerprint if business_obj else None,
            "core_fingerprint": core_obj.fingerprint if core_obj else None,
            "plan_fingerprint": plan_obj.fingerprint if plan_obj else None,
            "canonical_sha256": core_obj.payload["source"]["canonical_sha256"] if core_obj else None,
        }
        for field, expected in identities.items():
            if expected is not None and lineage_value[field] != expected:
                diagnostics.append(diagnostic(
                    "lineage_fingerprint_mismatch", f"lineage {field} does not match persisted layer",
                    stage="lineage", path=field,
                ))
        if business_obj is not None and core_obj is not None and plan_obj is not None:
            expected_lineage = make_lineage(business_obj, core_obj, plan_obj)
            if lineage_value != expected_lineage:
                diagnostics.append(diagnostic(
                    "lineage_symbol_mismatch", "lineage symbols or paths do not match the persisted bundle",
                    stage="lineage", path="symbols",
                ))
            else:
                result["mappings"]["core_to_plan"] = _core_plan_mappings(lineage_value)

    if any(item["severity"] == "error" for item in diagnostics):
        result["status"] = "invalid"
        return result

    if not missing:
        result["association_status"] = "verified"
        result["coverage"] = {
            "level": "partial",
            "operations": _operation_coverage(core_obj),
            "limitation": "artifact association is verified; domain-rule coverage remains coarse",
            "value_provenance_vocabulary": _VALUE_PROVENANCE,
            "element_category_vocabulary": _ELEMENT_CATEGORIES,
        }
        if any(item["code"] == "business_core_layout_order_changed" for item in diagnostics):
            result["association_status"] = "partial"
        result["status"] = "partial"
    else:
        result["association_status"] = "partial"
        result["coverage"] = {
            "level": "partial", "operations": [],
            "value_provenance_vocabulary": _VALUE_PROVENANCE,
            "element_category_vocabulary": _ELEMENT_CATEGORIES,
        }
        result["status"] = "partial"
    return result
