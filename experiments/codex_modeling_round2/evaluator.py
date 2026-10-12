"""Private requirement-based scoring. This module never executes a model.

Cases are supplied by the controller. Reference models are positive controls,
never a whole-model equality oracle. Language responses receive an explicitly
limited automatic concept screen and require separate blind semantic review.
"""
from __future__ import annotations

import copy
import math
import re
from sim_engine_compiler.ir.bounded import digest, TICKS_PER_HOUR
from experiments.codex_modeling_pilot.runner import validate_candidate

PROFILE = "aircraft-bounded-events/v1"
SELECTOR = re.compile(r"^([^\[\]]+)\[id=([^\[\]]+)\]$")


def equal(actual, expected):
    if type(expected) in (int, float):
        return type(actual) in (int, float) and math.isfinite(actual) and abs(actual - expected) <= 1e-9
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all(equal(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(equal(a, b) for a, b in zip(actual, expected))
    return type(actual) is type(expected) and actual == expected


def by_id(rows, sid):
    matches = [row for row in rows if isinstance(row, dict) and row.get("id") == sid]
    if len(matches) != 1:
        raise ValueError(f"selector requires exactly one identity: {sid}")
    return matches[0]


def select(model, path):
    """Read a fixed data selector; never evaluates expressions or Python code."""
    value = model
    for token in path.split("/"):
        match = SELECTOR.fullmatch(token)
        if match:
            table, sid = match.groups()
            if table == "mission_process":
                mission = by_id(model["missions"], sid)
                value = by_id(model["processes"], mission["process"])
            else:
                value = by_id(value[table], sid)
        elif isinstance(value, list):
            value = value[int(token)]
        else:
            value = value[token]
    return value


def apply_changes(model, changes):
    updated = copy.deepcopy(model)
    for change in changes:
        path, value = change["select"], copy.deepcopy(change["value"])
        parent_path, separator, token = path.rpartition("/")
        parent = select(updated, parent_path) if separator else updated
        match = SELECTOR.fullmatch(token)
        if match:
            table, sid = match.groups()
            if table == "mission_process":
                mission = by_id(updated["missions"], sid)
                rows, sid = updated["processes"], mission["process"]
            else:
                rows = parent[table]
            row = by_id(rows, sid)
            rows[rows.index(row)] = value
        elif isinstance(parent, list):
            parent[int(token)] = value
        else:
            if token not in parent:
                raise ValueError(f"assignment target absent: {path}")
            parent[token] = value
    return updated


def normalized_work(steps):
    normalized = []
    for step in steps:
        item = {"duration_hours": step["duration_hours"], "demands": step["demands"]}
        if item["duration_hours"] == 0 and not item["demands"]:
            continue
        # Resource-bearing boundaries release/reacquire; merging them could
        # change competition with other jobs. Only resource-free work merges.
        if normalized and not normalized[-1]["demands"] and not item["demands"]:
            normalized[-1]["duration_hours"] += item["duration_hours"]
        else:
            normalized.append(copy.deepcopy(item))
    return normalized


def concept_groups_match(text, groups):
    text = text.casefold()
    return all(any(word.casefold() in text for word in group) for group in groups)


def evaluate(candidate, result, case, *, behavior_only=False):
    checks = []
    category = case["category"]
    expected_status = category if category in ("clarify", "unsupported") else "model"
    task_id = candidate.get("task_id") if isinstance(candidate, dict) else None

    def check(cid, expected, actual, passed=None):
        checks.append({"id": cid, "passed": bool(equal(actual, expected) if passed is None else passed),
                       "expected": expected, "actual": actual})

    def finish():
        return {"task_id": task_id, "category": category,
                "accepted": bool(checks) and all(c["passed"] for c in checks),
                "assessment_kind": "automatic_concept_screen" if expected_status != "model" else "requirement_behavior_checks",
                "semantic_review_required": expected_status != "model", "checks": checks}

    try:
        validate_candidate(candidate)
    except Exception as exc:
        check("candidate.envelope", True, False)
        checks[-1]["diagnostic"] = str(exc)
        return finish()
    check("candidate.envelope", True, True)
    check("candidate.task_id", case["task_id"], task_id)
    check("candidate.status", expected_status, candidate["status"])
    if candidate["status"] != expected_status:
        return finish()

    if expected_status == "clarify":
        for requirement in case["clarification"]["questions"]:
            # Field aliases provide extra evidence but are not essential: users
            # receive ordinary-language tasks and need not know schema paths.
            actual = any(concept_groups_match(q["question"] + " " + candidate["reason"],
                                              requirement["keyword_groups"])
                         for q in candidate["questions"])
            check("clarification.concept." + requirement["concept"], True, actual)
        return finish()
    if expected_status == "unsupported":
        for i, alternatives in enumerate(case["unsupported"]["keyword_groups"]):
            check(f"unsupported.concept.{i}", True,
                  concept_groups_match(candidate["reason"], [alternatives]))
        return finish()

    model = candidate["model"]
    if not behavior_only:
        for rule in case["constraints"]:
            try:
                op = rule["op"]
                if op == "eq":
                    actual, expected = select(model, rule["select"]), rule["expected"]
                elif op == "ids_eq":
                    actual = sorted(row["id"] for row in select(model, rule["select"]))
                    expected = sorted(rule["expected"])
                elif op == "process_work":
                    process = select(model, f"mission_process[id={rule['mission']}]")
                    steps = process["steps"] or [{"duration_hours": process["scalar_hours"], "demands": {}}]
                    actual, expected = normalized_work(steps), normalized_work(rule["expected"])
                else:
                    raise ValueError(f"unknown private assertion operation: {op}")
                check(rule["id"], expected, actual)
            except (KeyError, TypeError, ValueError, IndexError) as exc:
                check(rule["id"], rule.get("expected"), {"selector_error": str(exc)}, False)

    check("execution.result_present", True, isinstance(result, dict))
    if not isinstance(result, dict):
        return finish()
    canonical = {"schema_version": "aircraft-bounded-input/v1", "semantic_profile": PROFILE, "model": model}
    check("execution.input_binding", digest(canonical), result.get("source_inputs_sha256"))
    check("execution.schema", "aircraft-bounded-result/v1", result.get("schema"))
    check("execution.profile", PROFILE, result.get("profile"))
    check("execution.rng_profile", model.get("rng_profile"), result.get("rng_profile"))
    check("execution.no_random_requests", [], result.get("random_requests"))
    trace = result.get("trace")
    check("execution.trace_present", True, isinstance(trace, list))
    if not isinstance(trace, list):
        return finish()
    check("execution.trace_sequence", list(range(len(trace))), [e.get("sequence") for e in trace])
    check("execution.trace_clock", True, all(type(e.get("time_ticks")) is int
          and type(e.get("hour")) in (int, float)
          and round(e["hour"] * TICKS_PER_HOUR) == e["time_ticks"] for e in trace))
    for rule in case["behavior"]:
        matching = [e for e in trace if e.get("kind") == rule["kind"]
                    and all(equal(e.get(k), v) for k, v in rule.get("where", {}).items())]
        actual = [[e.get(field) for field in rule["project"]] for e in matching]
        expected = rule["expected"]
        if rule.get("unordered"):
            # repr is a deterministic order for these simple JSON projections;
            # sorting never changes per-row value or tick comparisons.
            actual, expected = sorted(actual, key=repr), sorted(expected, key=repr)
        check(rule["id"], expected, actual)
        if "hour" in rule["project"]:
            index = rule["project"].index("hour")
            expected_ticks = [round(row[index] * TICKS_PER_HOUR) for row in rule["expected"]]
            actual_ticks = [e.get("time_ticks") for e in matching]
            if rule.get("unordered"):
                expected_ticks, actual_ticks = sorted(expected_ticks), sorted(actual_ticks)
            check(rule["id"] + ".ticks", expected_ticks, actual_ticks)

    capacities = {r["id"]: r["capacity"] for r in model.get("resources", [])}
    used, leases, errors = dict.fromkeys(capacities, 0), {}, []
    for event in trace:
        if event.get("kind") not in ("resource_acquired", "resource_released"):
            continue
        rid, quantity, owner = event.get("resource"), event.get("quantity"), event.get("owner")
        if rid not in capacities or type(quantity) is not int or quantity <= 0 or type(owner) is not str:
            errors.append("unknown resource/invalid quantity/owner")
            continue
        key = (owner, rid)
        if event["kind"] == "resource_acquired":
            if key in leases:
                errors.append("duplicate owned acquisition")
            leases[key] = quantity
            used[rid] += quantity
        else:
            if leases.pop(key, None) != quantity:
                errors.append("unmatched owned release")
            used[rid] -= quantity
        if not 0 <= used[rid] <= capacities[rid]:
            errors.append("capacity exceeded or negative")
    check("ledger.independent", [], errors)
    check("ledger.no_outstanding_leases", 0, len(leases))
    invariants = result.get("invariants", {})
    expected_invariants = {"resource_capacity", "resource_ledger", "unique_aircraft_reservations",
                           "physical_item_conservation", "installed_item_ownership"}
    check("execution.runtime_invariants", True, isinstance(invariants, dict)
          and set(invariants) == expected_invariants and all(v is True for v in invariants.values()))
    terminal = result.get("terminal", {})
    aircraft = terminal.get("aircraft", [])
    check("terminal.aircraft_identities", sorted(a["id"] for a in model["aircraft"]),
          sorted(a.get("id", "") for a in aircraft))
    check("terminal.ready_healthy_unassigned", True, bool(aircraft) and all(
        a.get("ready") is True and a.get("failed") is False and a.get("assigned") is False for a in aircraft))
    check("terminal.no_active_jobs", 0, terminal.get("active_jobs"))
    check("terminal.no_backorders", 0, terminal.get("backorders"))
    resources = terminal.get("resources", [])
    check("terminal.resource_identities", sorted(capacities), sorted(r.get("id", "") for r in resources))
    check("terminal.resource_ledger", used, {r.get("id"): r.get("used") for r in resources})
    check("terminal.resources_free", True, all(r.get("used") == 0 for r in resources))
    return finish()
