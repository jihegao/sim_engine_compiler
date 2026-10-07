"""Reviewer-owned, read-only C09.var02 source/pin gate. Standard library only.

This checks a prospective authored pair against the frozen contract and accepted
C09 remote source. It does not import author code or approve native behavior.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[2]
CONTRACT_SHA = "1ebec1583966b0a2c70043a4ba54e076763eb8d6b091192823b65c5e977e6653"
PARENT_SHA = "c0602d0a6bb3ee4603ac3be636ba81474dfbde33837f6a368ecdc6ded7e29ba1"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve(raw: str) -> Path:
    path = Path(raw)
    return path.resolve() if path.is_absolute() else (PACKAGE / path).resolve()


def git_blob(path: Path) -> bytes:
    relative = path.relative_to(REPO).as_posix()
    return subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=REPO,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout


def check_record(path: Path, record: dict, label: str, failures: list[str], counts: Counter) -> None:
    try:
        data = path.read_bytes()
    except OSError as exc:
        failures.append(f"missing {label}: {path}: {exc}")
        return
    counts[label] += 1
    if len(data) != record["bytes"] or digest(data) != record["sha256"]:
        failures.append(f"pin mismatch {label}: {path}")


def check_contract_pins(contract: dict, failures: list[str], counts: Counter) -> None:
    """Traverse all direct and dual pins plus accepted run raw/closure chains."""

    def walk(value: object) -> None:
        if isinstance(value, list):
            for child in value:
                walk(child)
            return
        if not isinstance(value, dict):
            return

        if isinstance(value.get("path"), str):
            path = resolve(value["path"])
            if "sha256" in value and "bytes" in value:
                check_record(path, value, "direct", failures, counts)

            if "local_disk" in value and "published_git" in value:
                check_record(path, value["local_disk"], "dual_disk", failures, counts)
                try:
                    git_bytes = git_blob(path)
                except (OSError, subprocess.CalledProcessError, ValueError) as exc:
                    failures.append(f"missing Git blob: {path}: {exc}")
                else:
                    counts["dual_git"] += 1
                    record = value["published_git"]
                    if len(git_bytes) != record["bytes"] or digest(git_bytes) != record["sha256"]:
                        failures.append(f"Git pin mismatch: {path}")

            if "raw" in value and path.is_dir():
                raw = value["raw"]
                if isinstance(raw, dict):
                    for name, record in raw.items():
                        check_record(path / name, record, "run_raw", failures, counts)
                else:
                    for record in raw:
                        check_record(resolve(record["path"]), record, "run_raw", failures, counts)
                for name in ("closure", "invocation"):
                    record = value.get(name)
                    if isinstance(record, dict) and "sha256" in record:
                        item = resolve(record["path"]) if "path" in record else path / (name + ".json")
                        check_record(item, record, "run_" + name, failures, counts)

        for child in value.values():
            walk(child)

    walk(contract)
    excluded = contract["excluded_v100"]["records"]
    for name, record in excluded.items():
        path = resolve(record["path"])
        data = path.read_bytes()
        counts["excluded_v100"] += 1
        if len(data) != record["size_bytes"] or digest(data) != record["sha256"]:
            failures.append(f"excluded v100 pin mismatch: {name}")


def table(model: dict, name: str) -> dict:
    matches = [entry for entry in model["model"]["tables"] if entry["name"] == name]
    if len(matches) != 1:
        raise AssertionError(f"expected one table {name}, got {len(matches)}")
    return matches[0]


def set_cell(model: dict, name: str, index: int, field: str, before: object, after: object) -> None:
    entry = table(model, name)
    fields = [column["name"] for column in entry["columns"]]
    position = fields.index(field)
    rows = entry["instances"][0]["rows"]
    assert rows[index][position] == before, (name, index, field, rows[index][position], before)
    rows[index][position] = after


def add_row(model: dict, name: str, values: dict[str, object]) -> None:
    entry = table(model, name)
    fields = [column["name"] for column in entry["columns"]]
    assert set(values) <= set(fields), (name, set(values) - set(fields))
    entry["instances"][0]["rows"].append([values.get(field) for field in fields])


def expected_arm(parent: dict, contract: dict, arm: str) -> dict:
    result = copy.deepcopy(parent)
    for change in contract["common_source_delta_from_C09_remote"]:
        name = change["table"]
        if "add" in change:
            add_row(result, name, change["add"])
        elif "cells" in change:
            for field, (before, after) in change["cells"].items():
                set_cell(result, name, 0, field, before, after)
        elif "cell" in change:
            field, (before, after) = next(iter(change["cell"].items()))
            count = len(table(result, name)["instances"][0]["rows"])
            for index in range(count):
                set_cell(result, name, index, field, before, after)
        else:
            raise AssertionError(f"unclassified source change: {change}")
    for change in contract["pair"]["only_pair_deltas"]:
        field = change["field"]
        name = change["table"]
        before = 0.125 if field == "TTRSS" else "C09.var04 primary system maintenance remote resource remote"
        set_cell(result, name, 0, field, before, change[arm])
    return result


def compare_models(actual: dict, expected: dict, arm: str, failures: list[str], counts: Counter) -> None:
    actual_tables = actual["model"]["tables"]
    expected_tables = expected["model"]["tables"]
    counts["table_topology"] += len(expected_tables)
    if len(actual_tables) != 32 or actual.get("model", {}).get("database_version") != expected["model"]["database_version"]:
        failures.append(f"{arm} table count/database version mismatch")
        return
    for index, (left, right) in enumerate(zip(actual_tables, expected_tables)):
        if left["name"] != right["name"] or left["columns"] != right["columns"]:
            failures.append(f"{arm} table {index} metadata mismatch")
        counts["table_rows"] += len(right["instances"][0]["rows"])
        if left["instances"] != right["instances"]:
            failures.append(f"{arm} table {index} {right['name']} rows mismatch")


def mutation_probes(actual: dict, expected: dict) -> int:
    """Reject changed source cells, topology, and a null-to-zero substitution."""
    altered: list[dict] = []
    changed = copy.deepcopy(actual)
    table(changed, "ResourceRemoteSupport")["instances"][0]["rows"][0][
        [c["name"] for c in table(changed, "ResourceRemoteSupport")["columns"]].index("TTRSS")
    ] = 0.125
    altered.append(changed)
    changed = copy.deepcopy(actual)
    table(changed, "ResourceAllocation")["instances"][0]["rows"][0][0] = "WRONG"
    altered.append(changed)
    changed = copy.deepcopy(actual)
    table(changed, "System")["instances"][0]["rows"].pop()
    altered.append(changed)
    changed = copy.deepcopy(actual)
    table(changed, "Unit")["columns"][0]["name"] = "WRONG"
    altered.append(changed)
    changed = copy.deepcopy(actual)
    for entry in changed["model"]["tables"]:
        for instance in entry["instances"]:
            for row in instance["rows"]:
                if None in row:
                    row[row.index(None)] = 0
                    altered.append(changed)
                    break
            if changed in altered:
                break
        if changed in altered:
            break
    assert len(altered) == 5, "no nullable authored cell found for probe"
    for index, mutant in enumerate(altered):
        errors: list[str] = []
        compare_models(mutant, expected, f"probe-{index}", errors, Counter())
        assert errors, f"source mutation accepted: {index}"
    return len(altered)


def main() -> dict:
    failures: list[str] = []
    counts: Counter = Counter()
    contract_bytes = (PACKAGE / "contract.json").read_bytes()
    if digest(contract_bytes) != CONTRACT_SHA:
        failures.append("frozen contract SHA mismatch")
    contract = json.loads(contract_bytes)
    check_contract_pins(contract, failures, counts)

    parent_path = resolve(contract["accepted_direct_parent"]["source_files"]["remote-input.json"]["path"])
    parent_bytes = parent_path.read_bytes()
    if digest(parent_bytes) != PARENT_SHA:
        failures.append("accepted remote parent input SHA mismatch")
    parent = json.loads(parent_bytes)
    for arm in ("ordinary", "shortage"):
        name = f"{arm}-input.json"
        path = PACKAGE / name
        if not path.is_file():
            failures.append(f"missing prospective input: {name}")
            continue
        actual = json.loads(path.read_bytes())
        expected = expected_arm(parent, contract, arm)
        compare_models(actual, expected, arm, failures, counts)
        if arm == "ordinary" and not failures:
            counts["adversarial_rejections"] += mutation_probes(actual, expected)
    for arm in ("ordinary", "shortage"):
        if (PACKAGE / contract["pair"]["arms"][arm]["run_dir"]).exists():
            failures.append(f"reserved run path exists before native: {arm}")
    return {
        "schema": "independent-c09-var02-v101-source-gate/v1",
        "decision": "GO_SOURCE_ONLY" if not failures else "NO_GO_SOURCE",
        "contract_sha256": digest(contract_bytes),
        "counts": dict(sorted(counts.items())),
        "failures": failures,
        "native_process_started": False,
    }


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, sort_keys=True, indent=2))
