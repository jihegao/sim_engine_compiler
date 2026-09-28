"""Static A09 source/graph checks; this does not validate native SIMLOX behavior."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import build


HERE = Path(__file__).resolve().parent
CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
PARAMETERS = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))


def expand_hypothesis(document: dict) -> list[tuple[str, float]]:
    """Expand the declared candidate interpretation, not a proven native rule."""
    profiles: dict[str, list[dict]] = {}
    for row in build.rows(document, "OperationProfile"):
        profiles.setdefault(row["PRID"], []).append(row)
    missions = {row["MTID"] for row in build.rows(document, "MissionType")}
    operations = build.rows(document, "Operations")
    if len(operations) != 1:
        raise ValueError("candidate requires one Operations root")
    root = operations[0]["PRID"]
    if root not in profiles:
        raise ValueError(f"Operations root {root} is missing")
    if set(profiles) & missions:
        raise ValueError("profile and mission IDs overlap")
    result: list[tuple[str, float]] = []

    def visit(profile: str, origin: float, ancestors: frozenset[str]) -> None:
        if profile in ancestors:
            raise ValueError(f"cyclic OperationProfile reference at {profile}")
        for row in profiles[profile]:  # preserve duplicate PRID rows and their order
            count, period, offset = row["IQTY"], row["IPER"], row["STIM"]
            if (row["ITYPE"] != "SCHEDULED" or type(count) is not int or count <= 0 or count > 100
                    or type(period) not in (int, float) or not math.isfinite(period) or period < 0
                    or type(offset) not in (int, float) or not math.isfinite(offset) or offset < 0):
                raise ValueError("unsupported candidate profile row")
            child = row["SPRID"]
            if child not in profiles and child not in missions:
                raise ValueError(f"unresolved OperationProfile.SPRID {child}")
            for repetition in range(count):
                when = origin + offset + repetition * period
                if child in missions:
                    result.append((child, when))
                else:
                    visit(child, when, ancestors | {profile})

    visit(root, 0.0, frozenset())
    if set(profiles) - {root} - {row["SPRID"] for rows in profiles.values() for row in rows}:
        raise ValueError("unreachable OperationProfile")
    return sorted(result, key=lambda item: item[1])


def check_candidate(parent: dict, document: dict, variant: str) -> list[str]:
    if variant not in ("flat", "nested"):
        raise ValueError("unknown A09 candidate variant")
    errors: list[str] = []
    expected_tables = set(CONTRACT["expected_changed_tables"][f"a02_to_{variant}"])
    try:
        changes = build.changed_tables(parent, document)
        if set(changes) != expected_tables:
            errors.append(f"A02 changed tables: expected {sorted(expected_tables)}, got {sorted(changes)}")
        if build.rows(document, "ProblemDescription") != [{"PDESC": PARAMETERS["description"]}]:
            errors.append("A09 ProblemDescription.PDESC differs")
        control = build.rows(document, "Control")
        if len(control) != 1 or (control[0]["SIMPE"], control[0]["RCSTA"], control[0]["RCEND"], control[0]["RCINT"], control[0]["NREPS"]) != (48.0, 0, 48.0, 0.5, 1):
            errors.append("A09 Control horizon/repetition differs")
        collection = build.rows(document, "ResultCollection")
        if (len(collection) != 2 or {row["RTYPE"] for row in collection} != {"MISSION", "SYSTEM"}
                or any((row["RCSTA"], row["RCEND"], row["RCINT"]) != (0, 48.0, 0.5) for row in collection)):
            errors.append("A09 ResultCollection grid differs")
        profiles = build.rows(document, "OperationProfile")
        if len(profiles) != CONTRACT[variant]["operation_profile_rows"]:
            errors.append("A09 OperationProfile row multiplicity differs")
        if build.rows(document, "Operations") != build.rows(parent, "Operations"):
            errors.append("Operations root changed")
        expanded = expand_hypothesis(document)
        expected = [("BASIC-MISSION", hour) for hour in CONTRACT["flat"]["scheduled_start_hours"]]
        if expanded != expected:
            errors.append(f"candidate expansion hypothesis differs: {expanded!r}")
    except (KeyError, TypeError, ValueError, RecursionError) as exc:
        errors.append(str(exc))
    return errors


def validate() -> dict:
    errors: list[str] = []
    if build.sha256(build.PARENT) != CONTRACT["parent_input_sha256"]:
        errors.append("frozen A02 SHA differs from contract")
    regenerated = build.artifacts(PARAMETERS)
    for name, expected in regenerated.items():
        path = HERE / name
        if not path.is_file() or path.read_bytes() != expected:
            errors.append(f"{name} differs from pinned-source builder")
    parent = json.loads(build.PARENT.read_bytes())
    candidates = {}
    for variant in ("flat", "nested"):
        path = HERE / f"native-{variant}.json"
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != CONTRACT["candidate_input_sha256"][variant]:
            errors.append(f"{variant} input SHA differs from contract")
        document = json.loads(raw)
        errors.extend(f"{variant}: {error}" for error in check_candidate(parent, document, variant))
        candidates[variant] = document
    if set(build.changed_tables(candidates["flat"], candidates["nested"])) != set(CONTRACT["expected_changed_tables"]["flat_to_nested"]):
        errors.append("flat-to-nested table diff differs")
    return {"schema": "simlox-a09-local-static-validation/v1", "passed": not errors,
            "differences": errors, "scope": "local_static_candidate_only",
            "native_behavior_status": "not_run", "gui_status": "not_run",
            "publication_state": "not_published"}


def main() -> None:
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
