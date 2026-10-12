"""Private, requirement-derived assessment; never expose to generation agents.

This module does not execute candidates. The controller supplies a fresh result
from the unmodified bounded runtime. Static constraints prevent shrinking a
problem to obtain a passing trace; source fingerprints bind result to input.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROFILE = "aircraft-bounded-events/v1"
TICKS_PER_HOUR = 3_600_000_000
TABLES = {"aircraft", "resources", "processes", "missions", "nodes", "routes", "external_events"}


def _equal(actual, expected):
    if isinstance(expected, bool) or expected is None:
        return type(actual) is type(expected) and actual == expected
    if type(expected) in (int, float):
        return type(actual) in (int, float) and math.isfinite(actual) and abs(actual - expected) <= 1e-10
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all(
            _equal(actual[k], value) for k, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            _equal(a, e) for a, e in zip(actual, expected))
    return type(actual) is type(expected) and actual == expected


def _table(value):
    """Ignore table row order, but preserve serial step and dependency lists."""
    if not isinstance(value, list) or not all(isinstance(r, dict) and isinstance(r.get("id"), str) for r in value):
        return value
    return sorted(value, key=lambda row: row["id"])


def evaluate(candidate, result=None):
    """Return JSON {task_id, accepted, checks}; no implicit execution or repair.

    A model submission without a runtime result never passes. Clarification and
    unsupported submissions are separate task types, not executable successes.
    """
    checks = []
    task_id = candidate.get("task_id") if isinstance(candidate, dict) else None

    def check(cid, expected, actual, passed=None):
        checks.append({"id": cid, "passed": bool(_equal(actual, expected) if passed is None else passed),
                       "expected": expected, "actual": actual})

    def finish():
        return {"task_id": task_id, "accepted": bool(checks) and all(c["passed"] for c in checks), "checks": checks}

    check("candidate.object", True, isinstance(candidate, dict))
    if not isinstance(candidate, dict):
        return finish()
    fields = {"task_id", "status", "model", "questions", "reason"}
    check("candidate.fields", sorted(fields), sorted(candidate))
    oracles = json.loads((ROOT / "private/oracles.json").read_text())["tasks"]
    check("candidate.task_id", True, task_id in oracles)
    if task_id not in oracles:
        return finish()
    oracle = oracles[task_id]
    check(f"{task_id}-status", oracle["expected_status"], candidate.get("status"))
    check("candidate.reason_type", True, isinstance(candidate.get("reason"), str))
    questions = candidate.get("questions")
    valid_questions = isinstance(questions, list) and all(
        isinstance(q, dict) and set(q) == {"field", "question"}
        and isinstance(q["field"], str) and isinstance(q["question"], str)
        and bool(q["question"].strip()) for q in questions)
    check("candidate.questions_shape", True, valid_questions)
    if oracle["expected_status"] == "clarify":
        check("T07-R02-no_guessed_model", None, candidate.get("model"))
        aliases = {oracle["question_field"], *oracle["accepted_field_aliases"]}
        asked = [q["field"] for q in questions] if valid_questions else []
        check("T07-R01-missing_capacity", True, any(field in aliases for field in asked))
        check("T07-R02-minimal_question", 1, len(asked))
        return finish()
    if oracle["expected_status"] == "unsupported":
        check("T08-R03-no_silent_downgrade", None, candidate.get("model"))
        check("T08-R03-no_unnecessary_questions", [], questions)
        reason = candidate.get("reason", "")
        reason = reason.lower() if isinstance(reason, str) else ""
        for i, alternatives in enumerate(oracle["reason_concepts"]):
            check(f"T08-R02-reason-concept-{i}", True, any(w in reason for w in alternatives))
        return finish()

    check("candidate.model_questions", [], questions)
    model = candidate.get("model")
    check("candidate.model_object", True, isinstance(model, dict))
    if not isinstance(model, dict):
        return finish()
    expected_keys = {rule["field"] for rule in oracle["structural"]}
    check(f"{task_id}-STRUCT-exact_fields", sorted(expected_keys), sorted(model))
    for rule in oracle["structural"]:
        actual = model.get(rule["field"])
        expected = rule["expected"]
        if rule["field"] in TABLES:
            actual, expected = _table(actual), _table(expected)
        check(rule["id"], expected, actual)
    check("execution.result_present", True, isinstance(result, dict))
    if not isinstance(result, dict):
        return finish()
    canonical = {"schema_version": "aircraft-bounded-input/v1", "semantic_profile": PROFILE, "model": model}
    try:
        expected_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                                                 ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    except (TypeError, ValueError):
        expected_hash = "invalid-model-json"
    check("execution.input_binding", expected_hash, result.get("source_inputs_sha256"))
    check("execution.schema", "aircraft-bounded-result/v1", result.get("schema"))
    check("execution.profile", PROFILE, result.get("profile"))
    check("execution.rng_profile", model.get("rng_profile"), result.get("rng_profile"))
    check("execution.no_random_requests", [], result.get("random_requests"))
    trace = result.get("trace")
    check("execution.trace_present", True, isinstance(trace, list))
    if not isinstance(trace, list):
        return finish()
    for rule in oracle["behavior"]:
        matching = [e for e in trace if e.get("kind") == rule["kind"]
                    and all(e.get(k) == v for k, v in rule["where"].items())]
        actual = [[e.get(field) for field in rule["fields"]] for e in matching]
        check(rule["id"], rule["expected"], actual)
        if "hour" in rule["fields"]:
            index = rule["fields"].index("hour")
            check(rule["id"] + "-ticks", [round(row[index] * TICKS_PER_HOUR) for row in rule["expected"]],
                  [e.get("time_ticks") for e in matching])
    if not any(r["kind"] == "mission_cancelled" for r in oracle["behavior"]):
        check(f"{task_id}-no_cancellation", [], [e for e in trace if e.get("kind") == "mission_cancelled"])

    # Reconstruct resource leases from observable events, independent of the
    # runtime's self-reported invariant flags and snapshots.
    capacities = {r["id"]: r["capacity"] for r in model.get("resources", [])}
    used = {key: 0 for key in capacities}
    leases = {}
    ledger_errors = []
    for event in trace:
        kind = event.get("kind")
        if kind not in {"resource_acquired", "resource_released"}:
            continue
        rid, q, owner = event.get("resource"), event.get("quantity"), event.get("owner")
        key = (owner, rid)
        if rid not in capacities or type(q) is not int or q <= 0:
            ledger_errors.append("unknown resource/invalid quantity")
            continue
        if kind == "resource_acquired":
            if key in leases:
                ledger_errors.append("duplicate acquisition")
            leases[key] = q
            used[rid] += q
        else:
            if leases.pop(key, None) != q:
                ledger_errors.append("release without matching owned lease")
            used[rid] -= q
        if not 0 <= used[rid] <= capacities[rid]:
            ledger_errors.append("capacity exceeded or negative")
    check(f"{task_id}-resource-ledger-independent", [], ledger_errors)
    check(f"{task_id}-resource-leases-released", 0, len(leases))
    invariants = result.get("invariants", {})
    check("execution.runtime_invariants", True, isinstance(invariants, dict) and len(invariants) == 5
          and all(v is True for v in invariants.values()))
    terminal = result.get("terminal", {})
    terminal_aircraft = terminal.get("aircraft", [])
    check(f"{task_id}-terminal-aircraft-identities", sorted(a["id"] for a in model["aircraft"]),
          sorted(a.get("id", "") for a in terminal_aircraft))
    check(f"{task_id}-terminal-ready", True, bool(terminal_aircraft) and all(
        a.get("ready") is True and a.get("failed") is False and a.get("assigned") is False
        for a in terminal_aircraft))
    check(f"{task_id}-terminal-no_active_jobs", 0, terminal.get("active_jobs"))
    check(f"{task_id}-terminal-resource-free", True, all(r.get("used") == 0 for r in terminal.get("resources", [])))
    return finish()
