"""Offline run, sample, and recorded-event identity contracts.

This module identifies existing aircraft-support results.  It does not collect
new trace evidence, infer causes, or alter runtime observation defaults.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from sim_engine_compiler.identity.common import content_digest, diagnostic, json_value
from sim_engine_compiler.ir.plan import PLAN_VERSION, ExecutionPlan

RUN_IDENTITY_VERSION = "simulation-run-identity/v1"
EVENT_REFERENCES_VERSION = "simulation-event-references/v1"
EVENT_RESOLUTION_VERSION = "simulation-event-reference-resolution/v1"
SUPPORTED_PROFILES = frozenset(("legacy-minute-v1", "event-time-v2"))
SUPPORTED_OBSERVATIONS = frozenset(("full", "summary"))
I64_MAX = 2**63 - 1
U64_MAX = 2**64 - 1


def _sealed(value: dict[str, Any]) -> dict[str, Any]:
    result = json_value(value)
    result["content_digest"] = content_digest(result)
    return result


def _report(version: str, status: str, diagnostics: list[dict[str, Any]],
            **fields: Any) -> dict[str, Any]:
    return _sealed({"schema_version": version, "status": status,
                    **fields, "diagnostics": diagnostics})


def _invalid(version: str, code: str, message: str, *, path: str | None = None,
             **fields: Any) -> dict[str, Any]:
    return _report(version, "invalid",
                   [diagnostic(code, message, stage="run_identity", path=path)],
                   **fields)


def _sha256(value: Any) -> bool:
    return (type(value) is str and len(value) == 64
            and all(character in "0123456789abcdef" for character in value))


def _nonnegative_time(value: Any) -> bool:
    return (type(value) in (int, float) and value >= 0
            and (type(value) is int or value < float("inf")))


def _plan(value: Any) -> tuple[ExecutionPlan | None, dict[str, Any] | None]:
    if isinstance(value, ExecutionPlan):
        raw = json.loads(json.dumps(value.to_dict(), ensure_ascii=False, allow_nan=False))
    elif isinstance(value, Mapping):
        try:
            raw = json_value(value)
        except ValueError as error:
            return None, diagnostic("invalid_plan", str(error), stage="run_identity",
                                    path="plan")
    else:
        return None, diagnostic("invalid_plan", "expected ExecutionPlan or JSON object",
                                stage="run_identity", path="plan")
    if isinstance(raw.get("domain"), str) and raw["domain"] != "aircraft-support":
        return None, diagnostic("unsupported_domain",
                                "run identity first slice supports aircraft-support only",
                                stage="run_identity", path="plan.domain")
    from sim_engine_compiler.identity.artifacts import inspect_artifact
    artifact = inspect_artifact(raw)
    if artifact["status"] not in ("valid", "partial") or artifact.get("layer") != "plan":
        first = artifact.get("diagnostics", [{}])[0]
        code = first.get("code", "invalid_plan")
        if artifact["status"] == "unsupported" and not code.startswith("unsupported_"):
            code = "unsupported_plan"
        return None, diagnostic(code, first.get("message", "Plan did not validate"),
                                stage="run_identity", path="plan")
    try:
        plan = ExecutionPlan.from_dict(raw)
    except (KeyError, TypeError, ValueError) as error:
        return None, diagnostic("invalid_plan", str(error), stage="run_identity", path="plan")
    return plan, None


def _sample_id(run_id: str, sample_index: int) -> str:
    return "sample:" + content_digest({"schema_version": RUN_IDENTITY_VERSION,
                                       "run_id": run_id,
                                       "sample_index": sample_index})


def _event_id(sample_id: str, sequence: int) -> str:
    sample_digest = sample_id.removeprefix("sample:")
    event_digest = content_digest({"schema_version": EVENT_REFERENCES_VERSION,
                                   "sample_id": sample_id,
                                   "recorded_sequence": sequence})
    return f"event:{sample_digest}:{event_digest}"


def _bundle_binding(bundle: Any, plan: ExecutionPlan) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    if bundle is None:
        return ({"status": "not_supplied", "basis": "plan_only",
                 "bundle_digest": None}, [], "valid")
    if not isinstance(bundle, Mapping):
        return ({"status": "invalid", "basis": "raw_artifacts_revalidated",
                 "bundle_digest": None},
                [diagnostic("invalid_bundle", "bundle must contain raw artifacts",
                            stage="run_identity", path="bundle")], "invalid")
    try:
        from sim_engine_compiler.identity.artifacts import inspect_bundle
        report = inspect_bundle(business=bundle.get("business"), core=bundle.get("core"),
                                plan=bundle.get("plan"), lineage=bundle.get("lineage"))
    except (ImportError, TypeError, ValueError) as error:
        return ({"status": "invalid", "basis": "raw_artifacts_revalidated",
                 "bundle_digest": None},
                [diagnostic("invalid_bundle", str(error), stage="run_identity",
                            path="bundle")], "invalid")
    bundle_status = report.get("status")
    identity = report.get("identity", {})
    layers = report.get("layers", {})
    plan_identity = layers.get("plan", {}).get("identity", {})
    reported_plan = (plan_identity.get("plan_fingerprint")
                     or plan_identity.get("content_digest")
                     or identity.get("plan_fingerprint"))
    diagnostics = []
    status = "valid"
    if bundle_status not in ("valid", "partial"):
        diagnostics.append(diagnostic("invalid_bundle", "raw artifact bundle did not validate",
                                      stage="run_identity", path="bundle"))
        status = "invalid"
    if reported_plan != plan.fingerprint:
        diagnostics.append(diagnostic("plan_fingerprint_mismatch",
                                      "bundle Plan does not match the requested Plan",
                                      stage="run_identity", path="bundle.plan"))
        status = "invalid"
    elif bundle_status == "partial":
        diagnostics.append(diagnostic("bundle_evidence_partial",
                                      "bundle association is only partially verified",
                                      stage="run_identity", path="bundle", severity="warning"))
        status = "partial"
    return ({"status": "matched" if status != "invalid" else "invalid",
             "basis": "raw_artifacts_revalidated",
             "bundle_digest": identity.get("bundle_digest")}, diagnostics, status)


def build_run_identity(run_id: str, sample_index: int, seed: int, plan: Any, *,
                       bundle: Mapping[str, Any] | None = None,
                       observation: str = "full", horizon: int | None = None,
                       parameters: Mapping[str, Any] | None = None,
                       engine_version: str | None = None,
                       domain_package_version: str | None = None) -> dict[str, Any]:
    """Create an identity for one requested sample without claiming it executed."""
    if type(run_id) is not str or not run_id:
        return _invalid(RUN_IDENTITY_VERSION, "invalid_run_id",
                        "run_id must be a non-empty string", path="run_id")
    if type(sample_index) is not int or not 0 <= sample_index <= I64_MAX:
        return _invalid(RUN_IDENTITY_VERSION, "invalid_sample_index",
                        "sample_index must be a nonnegative signed integer",
                        path="sample_index")
    if type(seed) is not int or not 0 <= seed <= U64_MAX:
        return _invalid(RUN_IDENTITY_VERSION, "invalid_seed",
                        "seed must be an unsigned 64-bit integer", path="seed")
    if type(observation) is not str or observation not in SUPPORTED_OBSERVATIONS:
        return _invalid(RUN_IDENTITY_VERSION, "unsupported_observation",
                        "observation must be full or summary", path="observation")
    if horizon is not None and (type(horizon) is not int
                                or not 0 <= horizon <= I64_MAX):
        return _invalid(RUN_IDENTITY_VERSION, "invalid_horizon",
                        "horizon must be a nonnegative integer", path="horizon")
    if engine_version is not None and (type(engine_version) is not str or not engine_version):
        return _invalid(RUN_IDENTITY_VERSION, "invalid_engine_version",
                        "engine_version must be a non-empty string", path="engine_version")
    if (domain_package_version is not None
            and (type(domain_package_version) is not str or not domain_package_version)):
        return _invalid(RUN_IDENTITY_VERSION, "invalid_domain_package_version",
                        "domain_package_version must be a non-empty string",
                        path="domain_package_version")
    try:
        parameter_value = json_value({} if parameters is None else parameters)
    except ValueError as error:
        return _invalid(RUN_IDENTITY_VERSION, "invalid_parameters", str(error),
                        path="parameters")
    if not isinstance(parameter_value, dict):
        return _invalid(RUN_IDENTITY_VERSION, "invalid_parameters",
                        "parameters must be an object", path="parameters")
    loaded, error = _plan(plan)
    if error is not None:
        status = "unsupported" if error["code"].startswith("unsupported_") else "invalid"
        return _report(RUN_IDENTITY_VERSION, status, [error])
    assert loaded is not None
    binding, bundle_diagnostics, binding_status = _bundle_binding(bundle, loaded)
    sample_id = _sample_id(run_id, sample_index)
    fields = {
        "identity": {"run_id": run_id, "sample_index": sample_index,
                     "sample_id": sample_id},
        "execution_contract": {
            "plan_schema_version": loaded.plan_version,
            "plan_fingerprint": loaded.fingerprint,
            "domain": loaded.domain,
            "semantic_profile": loaded.semantic_profile,
            "work_policy": loaded.work_policy,
            "rng_profile": loaded.rng_profile,
            "engine_version": engine_version,
            "domain_package_version": domain_package_version,
        },
        "request": {"seed": seed, "parameters": parameter_value,
                    "observation": observation,
                    "horizon": loaded.duration_minutes if horizon is None else horizon},
        "bundle_binding": binding,
        "execution_evidence": {"status": "caller_asserted",
                               "proves_runtime_consumed_plan": False},
    }
    return _report(RUN_IDENTITY_VERSION, binding_status, bundle_diagnostics, **fields)


def inspect_run_identity(value: Any) -> dict[str, Any]:
    """Revalidate a serialized run identity; never trust its status field alone."""
    try:
        raw = json_value(value)
    except ValueError as error:
        return _invalid(RUN_IDENTITY_VERSION, "invalid_run_identity", str(error))
    if not isinstance(raw, dict) or raw.get("schema_version") != RUN_IDENTITY_VERSION:
        return _report(RUN_IDENTITY_VERSION, "unsupported",
                       [diagnostic("unsupported_run_identity_schema",
                                   "unsupported run identity schema",
                                   stage="run_identity", path="schema_version")])
    supplied_digest = raw.pop("content_digest", None)
    if not _sha256(supplied_digest) or content_digest(raw) != supplied_digest:
        return _invalid(RUN_IDENTITY_VERSION, "run_identity_digest_mismatch",
                        "run identity content digest does not match", path="content_digest")
    expected_fields = {"schema_version", "status", "identity", "execution_contract",
                       "request", "bundle_binding", "execution_evidence", "diagnostics"}
    if set(raw) != expected_fields:
        return _invalid(RUN_IDENTITY_VERSION, "invalid_run_identity",
                        "run identity contains unknown or missing fields")
    identity = raw.get("identity")
    contract = raw.get("execution_contract")
    request = raw.get("request")
    if not all(isinstance(item, dict) for item in (identity, contract, request)):
        return _invalid(RUN_IDENTITY_VERSION, "invalid_run_identity",
                        "identity, execution_contract, and request are required")
    if set(identity) != {"run_id", "sample_index", "sample_id"}:
        return _invalid(RUN_IDENTITY_VERSION, "invalid_run_identity",
                        "identity contains unknown or missing fields", path="identity")
    run_id = identity.get("run_id")
    sample_index = identity.get("sample_index")
    if (type(run_id) is not str or not run_id or type(sample_index) is not int
            or not 0 <= sample_index <= I64_MAX):
        return _invalid(RUN_IDENTITY_VERSION, "invalid_run_identity",
                        "invalid run or sample identity", path="identity")
    if identity.get("sample_id") != _sample_id(run_id, sample_index):
        return _invalid(RUN_IDENTITY_VERSION, "sample_identity_mismatch",
                        "sample_id does not match run_id and sample_index",
                        path="identity.sample_id")
    if (set(contract) != {"plan_schema_version", "plan_fingerprint", "domain",
                          "semantic_profile", "work_policy", "rng_profile",
                          "engine_version", "domain_package_version"}
            or contract.get("plan_schema_version") != PLAN_VERSION
            or contract.get("domain") != "aircraft-support"
            or type(contract.get("semantic_profile")) is not str
            or contract.get("semantic_profile") not in SUPPORTED_PROFILES
            or contract.get("work_policy") != "stable-topological-serial"
            or contract.get("rng_profile") != "legacy-sequential-v1"
            or not _sha256(contract.get("plan_fingerprint"))):
        return _report(RUN_IDENTITY_VERSION, "unsupported",
                       [diagnostic("unsupported_execution_contract",
                                   "unsupported or malformed execution contract",
                                   stage="run_identity", path="execution_contract")])
    if (contract["engine_version"] is not None
            and (type(contract["engine_version"]) is not str
                 or not contract["engine_version"])):
        return _invalid(RUN_IDENTITY_VERSION, "invalid_run_identity",
                        "invalid engine version", path="execution_contract.engine_version")
    if (contract["domain_package_version"] is not None
            and (type(contract["domain_package_version"]) is not str
                 or not contract["domain_package_version"])):
        return _invalid(RUN_IDENTITY_VERSION, "invalid_run_identity",
                        "invalid domain package version",
                        path="execution_contract.domain_package_version")
    seed = request.get("seed")
    horizon = request.get("horizon")
    if (set(request) != {"seed", "parameters", "observation", "horizon"}
            or type(seed) is not int or not 0 <= seed <= U64_MAX
            or type(horizon) is not int or not 0 <= horizon <= I64_MAX
            or type(request.get("observation")) is not str
            or request.get("observation") not in SUPPORTED_OBSERVATIONS
            or not isinstance(request.get("parameters"), dict)):
        return _invalid(RUN_IDENTITY_VERSION, "invalid_run_request",
                        "invalid seed, horizon, observation, or parameters", path="request")
    binding = raw.get("bundle_binding")
    evidence = raw.get("execution_evidence")
    if (not isinstance(binding, dict)
            or set(binding) != {"status", "basis", "bundle_digest"}
            or type(binding.get("status")) is not str
            or binding.get("status") not in {"not_supplied", "matched"}
            or evidence != {"status": "caller_asserted",
                            "proves_runtime_consumed_plan": False}):
        return _invalid(RUN_IDENTITY_VERSION, "invalid_run_identity_evidence",
                        "serialized identity cannot upgrade bundle or execution evidence",
                        path="execution_evidence")
    expected_basis = ("plan_only" if binding["status"] == "not_supplied"
                      else "raw_artifacts_revalidated")
    if binding.get("basis") != expected_basis:
        return _invalid(RUN_IDENTITY_VERSION, "invalid_run_identity_evidence",
                        "bundle binding basis is inconsistent", path="bundle_binding.basis")
    if (binding["status"] == "not_supplied" and binding.get("bundle_digest") is not None
            or binding["status"] == "matched" and not _sha256(binding.get("bundle_digest"))):
        return _invalid(RUN_IDENTITY_VERSION, "invalid_run_identity_evidence",
                        "bundle digest is inconsistent with binding status",
                        path="bundle_binding.bundle_digest")
    fields = {key: raw[key] for key in ("identity", "execution_contract", "request",
                                        "bundle_binding", "execution_evidence")}
    diagnostics = []
    status = "valid"
    if binding["status"] == "matched":
        status = "partial"
        diagnostics.append(diagnostic(
            "bundle_revalidation_unavailable",
            "serialized run identity does not contain the raw bundle needed for revalidation",
            stage="run_identity", path="bundle_binding", severity="warning",
        ))
    return _report(RUN_IDENTITY_VERSION, status, diagnostics, **fields)


def _projection_invalid(code: str, message: str, *, path: str | None = None) -> dict[str, Any]:
    return _invalid(EVENT_REFERENCES_VERSION, code, message, path=path,
                    coverage={"level": "none", "reason": "evidence_insufficient"},
                    events=[], omitted_event_ids=[], omitted_events=[])


def project_event_references(run_identity: Any, result: Any, *,
                             selected_sequences: Sequence[int] | None = None,
                             truncated: bool = False) -> dict[str, Any]:
    """Project stable references from already-recorded full trace evidence."""
    inspected = inspect_run_identity(run_identity)
    if inspected["status"] in ("invalid", "unsupported"):
        return _projection_invalid("invalid_run_identity",
                                   "run identity failed revalidation",
                                   path="run_identity")
    if type(truncated) is not bool:
        return _projection_invalid("invalid_truncation_flag", "truncated must be boolean",
                                   path="truncated")
    try:
        raw_result = json_value(result)
    except ValueError as error:
        return _projection_invalid("invalid_result", str(error), path="result")
    if not isinstance(raw_result, dict):
        return _projection_invalid("invalid_result", "result must be an object", path="result")
    contract = inspected["execution_contract"]
    request = inspected["request"]
    identity = inspected["identity"]
    diagnostics: list[dict[str, Any]] = []
    missing_bindings = [field for field in ("plan_fingerprint", "seed", "sample_index",
                                             "semantic_profile")
                        if field not in raw_result]
    for field, expected, code in (
        ("plan_fingerprint", contract["plan_fingerprint"], "result_plan_mismatch"),
        ("seed", request["seed"], "result_seed_mismatch"),
        ("sample_index", identity["sample_index"], "result_sample_mismatch"),
        ("semantic_profile", contract["semantic_profile"], "result_profile_mismatch"),
    ):
        if (field in raw_result
                and (type(raw_result[field]) is not type(expected)
                     or raw_result[field] != expected)):
            return _projection_invalid(code, f"result {field} does not match run identity",
                                       path=f"result.{field}")
    if missing_bindings:
        diagnostics.append(diagnostic(
            "evidence_insufficient",
            "result omits required self-reported Plan or seed binding",
            stage="run_identity", path="result", severity="warning",
        ))
    result_time = raw_result.get("time")
    if "time" in raw_result and not _nonnegative_time(result_time):
        return _projection_invalid("invalid_result_time",
                                   "result time must be finite and nonnegative",
                                   path="result.time")
    if result_time is not None and result_time > request["horizon"]:
        return _projection_invalid("result_horizon_mismatch",
                                   "result time exceeds the requested horizon",
                                   path="result.time")
    if result_time is None:
        diagnostics.append(diagnostic(
            "result_time_missing", "result omits its observed end time",
            stage="run_identity", path="result.time", severity="warning",
        ))
    binding_value = {
        "plan_fingerprint": contract["plan_fingerprint"],
        "verified_result_fields": sorted(
            field for field in ("plan_fingerprint", "seed", "sample_index",
                                "semantic_profile") if field in raw_result
        ),
        "binding_strength": ("result_self_report_cross_checked"
                             if not missing_bindings else "caller_asserted"),
        "proves_runtime_consumed_plan": False,
        "time_binding": {"request_horizon": request["horizon"],
                         "result_time": result_time},
    }
    if request["observation"] != "full":
        return _report(EVENT_REFERENCES_VERSION, "partial",
                       [diagnostic("evidence_insufficient",
                                   "summary observation does not contain event evidence",
                                   stage="run_identity", path="result.trace")],
                       run_identity={"run_id": identity["run_id"],
                                     "sample_index": identity["sample_index"],
                                     "sample_id": identity["sample_id"]},
                       evidence_binding=binding_value,
                       coverage={"level": "none", "reason": "summary_observation",
                                 "recorded_event_count": 0,
                                 "projected_event_count": 0},
                       events=[], omitted_event_ids=[], omitted_events=[])
    if "trace" not in raw_result:
        return _report(EVENT_REFERENCES_VERSION, "partial",
                       [diagnostic("evidence_insufficient", "trace was not captured",
                                   stage="run_identity", path="result.trace")],
                       run_identity={"run_id": identity["run_id"],
                                     "sample_index": identity["sample_index"],
                                     "sample_id": identity["sample_id"]},
                       evidence_binding=binding_value,
                       coverage={"level": "none", "reason": "trace_not_captured",
                                 "recorded_event_count": 0,
                                 "projected_event_count": 0},
                       events=[], omitted_event_ids=[], omitted_events=[])
    trace = raw_result["trace"]
    if not isinstance(trace, list):
        return _projection_invalid("unparseable_trace", "trace must be a list",
                                   path="result.trace")
    selected: set[int] | None = None
    if selected_sequences is not None:
        if (not isinstance(selected_sequences, Sequence)
                or isinstance(selected_sequences, (str, bytes))):
            return _projection_invalid("invalid_event_filter",
                                       "selected_sequences must be a sequence of integers")
        selected = set()
        for sequence in selected_sequences:
            if type(sequence) is not int or sequence <= 0 or sequence in selected:
                return _projection_invalid("invalid_event_filter",
                                           "selected sequences must be unique positive integers")
            selected.add(sequence)
    all_events: list[dict[str, Any]] = []
    seen: set[int] = set()
    for index, event in enumerate(trace):
        if not isinstance(event, dict):
            return _projection_invalid("unparseable_trace", "trace event must be an object",
                                       path=f"result.trace[{index}]")
        sequence = event.get("sequence")
        if type(sequence) is not int or sequence <= 0 or sequence in seen:
            return _projection_invalid("unparseable_trace",
                                       "event sequence must be a unique positive integer",
                                       path=f"result.trace[{index}].sequence")
        seen.add(sequence)
        recorded = {}
        for field in ("rule_id", "entity", "source_path"):
            value = event.get(field)
            if value is not None and type(value) is not str:
                return _projection_invalid("unparseable_trace",
                                           f"event {field} must be string or null",
                                           path=f"result.trace[{index}].{field}")
            recorded[field] = value
        time = event.get("time")
        if type(time) not in (int, float) or type(time) is bool:
            return _projection_invalid("unparseable_trace",
                                       "event time must be a finite number",
                                       path=f"result.trace[{index}].time")
        if type(time) is float and not (-float("inf") < time < float("inf")):
            return _projection_invalid("unparseable_trace",
                                       "event time must be a finite number",
                                       path=f"result.trace[{index}].time")
        if time < 0 or time > request["horizon"]:
            return _projection_invalid("event_horizon_mismatch",
                                       "event time is outside the requested horizon",
                                       path=f"result.trace[{index}].time")
        if result_time is not None and time > result_time:
            return _projection_invalid("event_result_time_mismatch",
                                       "event time exceeds the observed result end time",
                                       path=f"result.trace[{index}].time")
        for field in ("phase", "kind"):
            if type(event.get(field)) is not str or not event[field]:
                return _projection_invalid("unparseable_trace",
                                           f"event {field} must be a non-empty string",
                                           path=f"result.trace[{index}].{field}")
        details = event.get("details")
        if details is not None and not isinstance(details, dict):
            return _projection_invalid("unparseable_trace",
                                       "event details must be an object or null",
                                       path=f"result.trace[{index}].details")
        event_id = _event_id(identity["sample_id"], sequence)
        all_events.append({
            "event_id": event_id,
            "recorded_sequence": sequence,
            "time": time,
            "phase": event.get("phase"),
            "kind": event.get("kind"),
            "recorded_references": recorded,
            "reference_scope": {
                "business_rule": "recorded" if recorded["rule_id"] else "unknown",
                "entity_role": "unknown",
                "process_instance": "unknown",
                "core_plan_element": "unknown",
            },
            "trigger_relation": {"status": "unknown", "event_ids": [],
                                 "reason": "runtime_did_not_record_direct_trigger"},
        })
    sequences = [event["recorded_sequence"] for event in all_events]
    sequence_reason = None
    if sorted(sequences) != list(range(1, len(sequences) + 1)):
        sequence_reason = "trace_sequence_incomplete"
        diagnostics.append(diagnostic(
            sequence_reason, "recorded sequences expose missing trace events",
            stage="run_identity", path="result.trace", severity="warning",
        ))
    if sequences != sorted(sequences):
        sequence_reason = "trace_sequence_reordered"
        diagnostics.append(diagnostic(
            sequence_reason, "recorded trace is not in original sequence order",
            stage="run_identity", path="result.trace", severity="warning",
        ))
    if selected is not None and not selected <= seen:
        return _projection_invalid("event_reference_unresolved",
                                   "selected sequence was not present in the recorded trace")
    included = [event for event in all_events
                if selected is None or event["recorded_sequence"] in selected]
    omitted_events = [{"event_id": event["event_id"],
                       "recorded_sequence": event["recorded_sequence"]}
                      for event in all_events
                      if selected is not None and event["recorded_sequence"] not in selected]
    omitted = [event["event_id"] for event in omitted_events]
    if omitted:
        diagnostics.append(diagnostic(
            "evidence_insufficient", "event filter omitted recorded evidence",
            stage="run_identity", path="selected_sequences", severity="warning",
        ))
    if truncated:
        diagnostics.append(diagnostic("evidence_insufficient",
                                      "trace is declared truncated; omitted events are unknown",
                                      stage="run_identity", path="result.trace",
                                      severity="warning"))
    incomplete = (truncated or omitted or missing_bindings
                  or result_time is None or sequence_reason is not None)
    status = ("partial" if incomplete
              or inspected["status"] == "partial" else "valid")
    level = "partial" if incomplete else "complete"
    return _report(EVENT_REFERENCES_VERSION, status, diagnostics,
                   run_identity={"run_id": identity["run_id"],
                                 "sample_index": identity["sample_index"],
                                 "sample_id": identity["sample_id"]},
                   evidence_binding=binding_value,
                   coverage={"level": level,
                             "reason": ("trace_truncated" if truncated else
                                        sequence_reason if sequence_reason else
                                        "result_binding_incomplete" if missing_bindings else
                                        "result_time_missing" if result_time is None else
                                        "event_filter" if omitted else "full_trace"),
                             "recorded_event_count": len(all_events),
                             "projected_event_count": len(included)},
                   events=included, omitted_event_ids=omitted,
                   omitted_events=omitted_events)


def resolve_event_reference(projection: Any, event_id: str) -> dict[str, Any]:
    """Resolve one projected event without guessing missing or filtered evidence."""
    if type(event_id) is not str or not event_id.startswith("event:"):
        return _invalid(EVENT_RESOLUTION_VERSION, "invalid_event_id",
                        "event_id must be a stable event reference", path="event_id")
    try:
        raw = json_value(projection)
    except ValueError as error:
        return _invalid(EVENT_RESOLUTION_VERSION, "invalid_projection", str(error))
    if not isinstance(raw, dict) or raw.get("schema_version") != EVENT_REFERENCES_VERSION:
        return _report(EVENT_RESOLUTION_VERSION, "unsupported",
                       [diagnostic("unsupported_event_reference_schema",
                                   "unsupported event reference schema",
                                   stage="run_identity", path="schema_version")])
    supplied_digest = raw.pop("content_digest", None)
    if not _sha256(supplied_digest) or content_digest(raw) != supplied_digest:
        return _invalid(EVENT_RESOLUTION_VERSION, "event_projection_digest_mismatch",
                        "event projection content digest does not match")
    expected_fields = {"schema_version", "status", "run_identity", "evidence_binding",
                       "coverage", "events", "omitted_event_ids", "omitted_events",
                       "diagnostics"}
    if set(raw) != expected_fields:
        return _invalid(EVENT_RESOLUTION_VERSION, "invalid_event_projection",
                        "event projection contains unknown or missing fields")
    run_identity = raw.get("run_identity")
    events = raw.get("events")
    omitted = raw.get("omitted_events")
    coverage = raw.get("coverage")
    evidence_binding = raw.get("evidence_binding")
    if (not isinstance(run_identity, dict)
            or raw.get("status") not in {"valid", "partial"}
            or not isinstance(raw.get("diagnostics"), list)
            or type(run_identity.get("run_id")) is not str
            or not run_identity.get("run_id")
            or type(run_identity.get("sample_index")) is not int
            or not 0 <= run_identity.get("sample_index") <= I64_MAX
            or type(run_identity.get("sample_id")) is not str
            or run_identity.get("sample_id") != _sample_id(
                run_identity.get("run_id"), run_identity.get("sample_index")
            )
            or not isinstance(events, list) or not isinstance(omitted, list)
            or not isinstance(coverage, dict)
            or set(coverage) != {"level", "reason", "recorded_event_count",
                                 "projected_event_count"}
            or coverage.get("level") not in {"complete", "partial", "none"}
            or type(coverage.get("recorded_event_count")) is not int
            or type(coverage.get("projected_event_count")) is not int
            or coverage.get("recorded_event_count") < coverage.get("projected_event_count")
            or coverage.get("projected_event_count") != len(events)
            or not isinstance(evidence_binding, dict)
            or set(evidence_binding) != {"plan_fingerprint", "verified_result_fields",
                                         "binding_strength",
                                         "proves_runtime_consumed_plan", "time_binding"}
            or not _sha256(evidence_binding.get("plan_fingerprint"))
            or not isinstance(evidence_binding.get("verified_result_fields"), list)
            or any(field not in {"plan_fingerprint", "seed", "sample_index",
                                 "semantic_profile"}
                   for field in evidence_binding.get("verified_result_fields"))
            or evidence_binding.get("binding_strength") not in {
                "result_self_report_cross_checked", "caller_asserted"
            }
            or evidence_binding.get("proves_runtime_consumed_plan") is not False):
        return _invalid(EVENT_RESOLUTION_VERSION, "invalid_event_projection",
                        "projection identity and event collections are required")
    verified_fields = evidence_binding["verified_result_fields"]
    required_fields = ["plan_fingerprint", "sample_index", "seed", "semantic_profile"]
    complete_binding = verified_fields == required_fields
    time_binding = evidence_binding["time_binding"]
    if (not isinstance(time_binding, dict)
            or set(time_binding) != {"request_horizon", "result_time"}
            or type(time_binding.get("request_horizon")) is not int
            or not 0 <= time_binding["request_horizon"] <= I64_MAX
            or (time_binding.get("result_time") is not None
                and (not _nonnegative_time(time_binding["result_time"])
                     or time_binding["result_time"] > time_binding["request_horizon"]))):
        return _invalid(EVENT_RESOLUTION_VERSION, "invalid_event_projection",
                        "projection time binding is invalid")
    result_time = time_binding["result_time"]
    if (verified_fields != sorted(set(verified_fields))
            or (evidence_binding["binding_strength"] == "result_self_report_cross_checked")
            != complete_binding
            or coverage["recorded_event_count"] != len(events) + len(omitted)
            or (coverage["level"] == "none"
                and (coverage["reason"] not in {"summary_observation",
                                                "trace_not_captured"}
                     or events or omitted))
            or (coverage["level"] == "complete"
                and (coverage["reason"] != "full_trace" or omitted
                     or not complete_binding or result_time is None))
            or (coverage["level"] == "partial"
                and coverage["reason"] not in {"trace_truncated", "event_filter",
                                               "result_binding_incomplete",
                                               "result_time_missing",
                                               "trace_sequence_incomplete",
                                               "trace_sequence_reordered"})
            or (coverage["reason"] == "event_filter" and not omitted)
            or (coverage["reason"] == "result_binding_incomplete" and complete_binding)
            or (coverage["reason"] == "result_time_missing" and result_time is not None)
            or (coverage["level"] != "complete" and raw["status"] != "partial")):
        return _invalid(EVENT_RESOLUTION_VERSION, "invalid_event_projection",
                        "projection coverage exceeds or contradicts recorded evidence")
    seen_ids: set[str] = set()
    for path, items in (("events", events), ("omitted_events", omitted)):
        for index, event in enumerate(items):
            if not isinstance(event, dict):
                return _invalid(EVENT_RESOLUTION_VERSION, "invalid_event_projection",
                                "event reference must be an object",
                                path=f"{path}[{index}]")
            sequence = event.get("recorded_sequence")
            if path == "omitted_events" and set(event) != {
                    "event_id", "recorded_sequence"}:
                return _invalid(EVENT_RESOLUTION_VERSION, "invalid_event_projection",
                                "omitted event reference has unknown fields",
                                path=f"{path}[{index}]")
            expected = (_event_id(run_identity["sample_id"], sequence)
                        if type(sequence) is int and sequence > 0 else None)
            if event.get("event_id") != expected or expected in seen_ids:
                return _invalid(EVENT_RESOLUTION_VERSION, "event_identity_mismatch",
                                "event ID does not match sample and recorded sequence",
                                path=f"{path}[{index}].event_id")
            seen_ids.add(expected)
            if path == "events":
                expected_fields = {
                    "event_id", "recorded_sequence", "time", "phase", "kind",
                    "recorded_references", "reference_scope", "trigger_relation",
                }
                references = event.get("recorded_references")
                scope = event.get("reference_scope")
                trigger = event.get("trigger_relation")
                time = event.get("time")
                if (set(event) != expected_fields
                        or type(time) not in (int, float) or type(time) is bool
                        or (type(time) is float
                            and not -float("inf") < time < float("inf"))
                        or time < 0 or time > time_binding["request_horizon"]
                        or (result_time is not None and time > result_time)
                        or type(event.get("phase")) is not str or not event["phase"]
                        or type(event.get("kind")) is not str or not event["kind"]
                        or not isinstance(references, dict)
                        or set(references) != {"rule_id", "entity", "source_path"}
                        or any(value is not None and type(value) is not str
                               for value in references.values())
                        or scope != {
                            "business_rule": ("recorded" if references.get("rule_id")
                                              else "unknown"),
                            "entity_role": "unknown",
                            "process_instance": "unknown",
                            "core_plan_element": "unknown",
                        }
                        or trigger != {
                            "status": "unknown", "event_ids": [],
                            "reason": "runtime_did_not_record_direct_trigger",
                        }):
                    return _invalid(EVENT_RESOLUTION_VERSION,
                                    "invalid_event_projection",
                                    "projected event content exceeds recorded evidence",
                                    path=f"{path}[{index}]")
    if (coverage["level"] == "complete"
            and [event["recorded_sequence"] for event in events]
            != list(range(1, len(events) + 1))):
        return _invalid(EVENT_RESOLUTION_VERSION, "invalid_event_projection",
                        "complete trace must contain sequences 1 through N in order")
    omitted_ids = [item["event_id"] for item in omitted]
    if raw.get("omitted_event_ids") != omitted_ids:
        return _invalid(EVENT_RESOLUTION_VERSION, "invalid_event_projection",
                        "omitted event index is inconsistent",
                        path="omitted_event_ids")
    expected_prefix = "event:" + run_identity["sample_id"].removeprefix("sample:") + ":"
    if not event_id.startswith(expected_prefix):
        return _invalid(EVENT_RESOLUTION_VERSION, "cross_sample_event_reference",
                        "event reference belongs to another run or sample",
                        path="event_id")
    matches = [event for event in raw.get("events", [])
               if isinstance(event, dict) and event.get("event_id") == event_id]
    if len(matches) == 1:
        return _report(EVENT_RESOLUTION_VERSION, "valid", [], event=matches[0],
                       run_identity=raw.get("run_identity"),
                       projection_coverage=raw.get("coverage"),
                       evidence_binding=raw.get("evidence_binding"))
    reason = "event_filtered" if event_id in omitted_ids else "reference_unresolved"
    return _report(EVENT_RESOLUTION_VERSION, "partial",
                   [diagnostic("evidence_insufficient",
                               "event target is not available in this projection",
                               stage="run_identity", element_id=event_id)],
                   event=None, reason=reason, run_identity=raw.get("run_identity"),
                   projection_coverage=raw.get("coverage"),
                   evidence_binding=raw.get("evidence_binding"))
