"""Read-only author replay of accepted C05 radio-2/radio-0 native evidence."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CASES = HERE.parent
SOURCE = CASES / "C05-var02-two-resource-types-v1.0.0"
PARENT = CASES / "C05-mission-resource-v1.0.0"
OUT = HERE / "author-validation.json"
CONTRACT_SHA = "1028e32013b7f3b655254d10c0f2cdb40529a73517326e5b5929e32639d2a7de"
CONTRACT_REVIEW_SHA = "32871b4848cf5419d8aeba43b11e800fb58be790ebff29874295495aef63e97b"
REPORT_HASHES = {
    2: {"ProblemDescription": "d4c734fc1f2980fbc6c15e203d43a159c5383c7b4978cb62d93e5ba9bfd41c65", "ResultSummary": "c2d1b8c6337c16a8d03a6cc38afd78814f8bdc4c46fc9951b57ef35e2df3b2a3", "SystemResults": "02d8d87603e9a85807b22de52f57abe28a20c70824561459745834e9eafb82dd", "StockTotalResults": "13058441aa4a0114a46c2b347662619deade171cbebfba11222cb8b4648c1953", "ResourceResults": "33d1e3b03b14dd820d8cb9e92e3aa860b0265f7eaa3894c5b787e110801605dd", "ResourceResultsTotal": "aa789b2271c621e68d3e082700de501849233b3dbe190f77ad2dec84183845b4"},
    0: {"ProblemDescription": "eb2867b3d1d3040cb70e9995b69ea5753209c6e544ff3a1ee07f0c17ac5a3daa", "ResultSummary": "fa66bb5a8c919ce7dae9bbb03b9200c3782de8fca13d991cae17bf11d3e08f0a", "SystemResults": "58c6a460440ff17dd502c555db521821fb66c9339808f3163360854fca706ccb", "StockTotalResults": "13058441aa4a0114a46c2b347662619deade171cbebfba11222cb8b4648c1953", "ResourceResults": "76b9fe890e50ec00da77976b1c24471f94cfd9efa7bb19438a5a99dd1282d76c", "ResourceResultsTotal": "706a348a682b96fff58ee94bab1da1a78dfd6f124cd0ad4768afe53abaa3b5c5"},
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": sha(data)}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path):
    """Remove only native trailing commas from a parser copy."""
    raw = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = escaped = False
    for i, char in enumerate(raw):
        if quoted:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            out.append(char)
        elif char == ",":
            j = i + 1
            while j < len(raw) and raw[j].isspace():
                j += 1
            if j == len(raw) or raw[j] not in "}]":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def tables(doc: dict, root: str) -> dict:
    original = doc[root]["tables"]
    mapped = {t["name"]: t for t in original}
    if len(mapped) != len(original):
        raise ValueError("duplicate table")
    return mapped


def rows(table: dict) -> list:
    return [row for instance in table["instances"] for row in instance["rows"]]


def git_seal(path: Path) -> dict:
    data = subprocess.run(
        ["git", "show", f"HEAD:{path.relative_to(REPO).as_posix()}"],
        cwd=REPO, capture_output=True, check=True,
    ).stdout
    return {"bytes": len(data), "sha256": sha(data)}


class Checks:
    def __init__(self):
        self.total = 0
        self.failures: list[str] = []

    def check(self, condition, label: str):
        self.total += 1
        if not condition:
            self.failures.append(label)

    def pin(self, path: Path, expected: dict, label: str):
        self.check(path.is_file(), f"{label} exists")
        if path.is_file():
            self.check(seal(path) == expected, f"{label} byte/size seal")


def check_published(checks: Checks, package: Path, listed: list, expected_count: int):
    tracked = subprocess.run(
        ["git", "ls-files", "--", package.relative_to(REPO).as_posix()],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    expected = {item["path"]: item for item in listed}
    checks.check(len(tracked) == len(expected) == expected_count,
                 f"{package.name} published source count")
    checks.check({(REPO / item).relative_to(package).as_posix() for item in tracked} == set(expected),
                 f"{package.name} published source path set")
    for name, item in sorted(expected.items()):
        path = package / name
        checks.pin(path, item["local_disk"], f"{package.name}/{name}")
        checks.check(git_seal(path) == item["published_git"],
                     f"{package.name}/{name} Git bytes")


def check_run_seals(checks: Checks, package: Path, record: dict, raw_count: int, label: str):
    folder = package / "runs" / record["run_id"]
    checks.pin(folder / "closure.json", record["closure"], f"{label} closure")
    checks.pin(folder / "invocation.json", record["invocation"], f"{label} invocation")
    closure = read(folder / "closure.json")
    invocation = read(folder / "invocation.json")
    checks.check(closure["run_id"] == invocation["run_id"] == record["run_id"],
                 f"{label} run identity")
    checks.check(closure["invocation_sha256"] == record["invocation"]["sha256"],
                 f"{label} invocation link")
    checks.check(closure["raw"] == record["raw"] and len(record["raw"]) == raw_count,
                 f"{label} complete raw map")
    checks.check(closure["error"] is None and closure["source_hashes_before"] ==
                 closure["source_hashes_after"] == record["source_hashes_before_after"],
                 f"{label} stable source and no closure error")
    for name, item in sorted(record["raw"].items()):
        checks.pin(folder / name, item, f"{label} raw {name}")
    checks.check(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
                 "sshd.exe" in invocation["ssh_ancestor_names"], f"{label} SSH0/sshd")
    checks.check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
                 invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
                 f"{label} original mutex/GUI identity")
    steps = read(folder / "steps.json")
    checks.check([item["name"] for item in steps] ==
                 ["import", "export", "calc", "jsonreport", "check_import_export"],
                 f"{label} five native/replay stages")
    for step in steps:
        checks.check(step["status"] == "completed" and step["exit_code"] == 0 and
                     step["gui_preserved"], f"{label} {step['name']} completed")
    return folder


def check_sources(checks: Checks, contract: dict):
    source = contract["accepted_source"]
    parent = contract["direct_parent"]
    check_published(checks, SOURCE, source["published_source_files"], 16)
    check_published(checks, PARENT, parent["published_source_files"], 17)
    for case, prereq in sorted(contract["prerequisites"].items()):
        package = CASES / prereq["package"]
        for name, item in sorted(prereq["pins"].items()):
            path = package / name
            checks.pin(path, item["local_disk"], f"{case}/{name}")
            checks.check(git_seal(path) == item["published_git"], f"{case}/{name} Git bytes")
    for name, path in [
        ("original_contract", SOURCE / "contract.json"),
        ("original_exact_diff", SOURCE / "exact-diff.json"),
        ("original_signoff", SOURCE / "cli-scope-signoff-2026-09-30.md"),
        ("original_author_verdict", SOURCE / "author-native-validation-2026-09-30.json"),
        ("original_independent_verdict", SOURCE / "review/independent-readonly-2026-09-30.json"),
    ]:
        checks.pin(path, source[name], name)
    parent_model = tables(read(PARENT / "capacity-2-input.json"), "model")
    radio_models = {}
    for capacity in (2, 0):
        name = f"radio-{capacity}-input.json"
        record = source["input_pins"][str(capacity)]
        checks.pin(SOURCE / name, record["local_disk"], f"radio {capacity} input")
        checks.check(git_seal(SOURCE / name) == record["published_git"],
                     f"radio {capacity} input Git bytes")
        model = tables(read(SOURCE / name), "model")
        radio_models[capacity] = model
        changed = {n for n in set(model) | set(parent_model) if model.get(n) != parent_model.get(n)}
        checks.check(changed == set(contract["source_delta"]["direct_parent_to_each_changed_tables"]),
                     f"radio {capacity} exact direct-parent table set")
        checks.check(sum(bool(rows(t)) for t in model.values()) == 16,
                     f"radio {capacity} 16 row-containing authored tables")
        resource_cols = [col["name"] for col in model["ResourceAllocation"]["columns"]]
        allocations = [dict(zip(resource_cols, row)) for row in rows(model["ResourceAllocation"])]
        checks.check(len(allocations) == 2 and
                     [a["RID"] for a in allocations] == ["MISSION-CREW", "MISSION-RADIO"] and
                     [a["RQTY"] for a in allocations] == [2, capacity] and
                     all(a["POINT"] == "AIR_BASIC" and a["STID"] == "BASE-01" for a in allocations),
                     f"radio {capacity} only crew/radio capacities 2/{capacity}")
        checks.check(rows(model["MissionResource"]) ==
                     contract["source_delta"]["common_MissionResource_rows"],
                     f"radio {capacity} one crew and one radio per aircraft")
    changed = {n for n in radio_models[2] if radio_models[2][n] != radio_models[0][n]}
    checks.check(changed == set(contract["source_delta"]["pairwise_changed_tables"]),
                 "radio pair only description and ResourceAllocation differ")
    parent_run = check_run_seals(checks, PARENT, parent["capacity_2_run"], 12,
                                 "direct C05 capacity-2 parent")
    checks.check(seal(parent_run / "input.json") == parent["capacity_2_input"]["local_disk"],
                 "direct parent run input equals pinned source")
    return radio_models


def check_arm(checks: Checks, contract: dict, capacity: int, authored: dict):
    run = check_run_seals(checks, SOURCE, contract["accepted_runs"][str(capacity)], 12,
                          f"radio-{capacity}")
    exported = tables(native(run / "roundtrip-raw.json"), "model")
    for name, table in sorted(authored.items()):
        if rows(table):
            other = exported.get(name)
            checks.check(other is not None and other["columns"] == table["columns"] and
                         rows(other) == rows(table), f"radio-{capacity} exact {name} roundtrip")
    checks.check(read(run / "roundtrip-validation.json")["passed"],
                 f"radio-{capacity} original roundtrip gate")
    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    checks.check(not re.search(r"\berror\s*#\d+", runlog, re.I),
                 f"radio-{capacity} converter no error")
    checks.check(sorted(set(re.findall(r"warning\s*#(\d+)", runlog, re.I))) == ["108", "126"],
                 f"radio-{capacity} only warnings 108/126")
    event = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    checks.check(event.count(f"Time: 7 {mission} mission created:") == 1 and
                 event.count(f"Time: 7 {mission} mission activated, systems requested: 2") == 1,
                 f"radio-{capacity} one h7 two-aircraft mission")
    for resource in ("MISSION-CREW", "MISSION-RADIO"):
        status = "OK" if resource == "MISSION-CREW" or capacity == 2 else "failed"
        typed = f"Availability test on  <{resource} at <BASE-01,0>> request for: 1 {status}"
        checks.check(event.count(typed) == 2,
                     f"radio-{capacity} two typed {resource} {status} tests")
        allocation = f"<{resource} at <BASE-01,0>> allocated to mission assigned: 1"
        release = f"<{resource} at <BASE-01,0>> deallocated from  mission operation: 1"
        checks.check(event.count(allocation) == capacity and event.count(release) == capacity,
                     f"radio-{capacity} {resource} booking/release")
    checks.check(event.count(f"{mission} mission allocates system:") == capacity,
                 f"radio-{capacity} aircraft allocations")
    if capacity == 2:
        for id_number in (0, 1):
            checks.check(f"{mission} mission allocates system: <TEACH-AIR-01,{id_number}>" in event,
                         f"radio-2 aircraft {id_number} allocated")
        checks.check(event.count(f"Time: 8 {mission} mission starting") == 1 and
                     event.count(f"Time: 10 {mission} mission success") == 1 and
                     event.count(f"Time: 10 {mission} mission completed") == 1,
                     "radio-2 h8 launch/h10 success and completion")
        checks.check("mission cancelled:" not in event, "radio-2 no cancellation")
    else:
        checks.check("mission starting" not in event and "mission success" not in event,
                     "radio-0 no launch or success")
        checks.check(event.count(f"Time: 8.33333 {mission} mission cancelled") == 1 and
                     "mission waiting:  timeout at 8.33333" in event,
                     "radio-0 h8.33333 wait timeout/cancellation")
        checks.check("books resources" not in event and "frees resources" not in event,
                     "radio-0 neither resource type booked")
    report = tables(native(run / "report-raw.json"), "report")
    shape = contract["predeclared_replay_gates"]["reports"]["tables"]
    checks.check(set(report) == set(shape) == set(REPORT_HASHES[capacity]),
                 f"radio-{capacity} six report tables")
    values = {}
    for name, size in sorted(shape.items()):
        tab = report[name]
        grid = rows(tab)
        checks.check(len(grid) == size["rows"] and len(tab["columns"]) == size["columns"],
                     f"radio-{capacity} {name} shape")
        for rowno, row in enumerate(grid):
            checks.check(len(row) == size["columns"], f"radio-{capacity} {name} row {rowno}")
        digest = sha(json.dumps(grid, ensure_ascii=False, separators=(",", ":")).encode())
        checks.check(digest == REPORT_HASHES[capacity][name],
                     f"radio-{capacity} {name} all-cell digest")
        values[name] = grid
    checks.check(sum(len(row) for table in values.values() for row in table) == 5210,
                 f"radio-{capacity} 5210 parsed cells")
    def value(table: str, field: str):
        columns = [col["name"] for col in report[table]["columns"]]
        return values[table][0][columns.index(field)]
    checks.check([value("ResultSummary", n) for n in ("MTMF", "MSTF", "MSUF", "STMF")] ==
                 ([1, 1, 1, 1] if capacity == 2 else [0, 0, 0, 0]),
                 f"radio-{capacity} mission summary")
    checks.check(value("ResourceResultsTotal", "NR") == (4 if capacity == 2 else 2),
                 f"radio-{capacity} aggregate resource stock")
    system_columns = [col["name"] for col in report["SystemResults"]["columns"]]
    checks.check(values["SystemResults"][-1][system_columns.index("NSYRY")] == 2,
                 f"radio-{capacity} terminal two ready aircraft")
    stock_columns = [col["name"] for col in report["StockTotalResults"]["columns"]]
    for name in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT"):
        ix = stock_columns.index(name)
        for bin_no, row in enumerate(values["StockTotalResults"]):
            checks.check(row[ix] == 0, f"radio-{capacity} no stock {name} bin {bin_no}")
    return values


def compare(checks: Checks, contract: dict, left: dict, right: dict):
    expected = contract["predeclared_replay_gates"]["reports"]["radio_2_vs_radio_0_difference_counts"]
    for name in left:
        differences = 0
        for row_no, (row_a, row_b) in enumerate(zip(left[name], right[name])):
            for column, (a, b) in enumerate(zip(row_a, row_b)):
                checks.check(not isinstance(a, (list, dict)) and not isinstance(b, (list, dict)),
                             f"{name} scalar report cell {row_no}/{column}")
                differences += a != b
        checks.check(differences == expected[name], f"{name} exact all-cell contrast count")
    for bin_no, (a_row, b_row) in enumerate(zip(left["StockTotalResults"], right["StockTotalResults"])):
        for column, (a, b) in enumerate(zip(a_row, b_row)):
            checks.check(a == b, f"stock pair parity bin {bin_no} col {column}")


def main():
    checks = Checks()
    try:
        checks.pin(HERE / "contract.json", {"bytes": 32574, "sha256": CONTRACT_SHA},
                   "frozen C05.var02 contract")
        checks.check((HERE / "review/independent-contract-go-2026-10-07.md").is_file() and
                     seal(HERE / "review/independent-contract-go-2026-10-07.md")["sha256"] ==
                     CONTRACT_REVIEW_SHA, "independent contract GO pin")
        contract = read(HERE / "contract.json")
        checks.check(contract["variant_id"] == "C05.var02" and
                     not contract["ownership"]["new_native_run_planned"],
                     "source-bound classification only")
        inputs = check_sources(checks, contract)
        reports = {capacity: check_arm(checks, contract, capacity, inputs[capacity])
                   for capacity in (2, 0)}
        compare(checks, contract, reports[2], reports[0])
    except (OSError, ValueError, KeyError, IndexError, TypeError, subprocess.CalledProcessError) as exc:
        checks.check(False, f"replay exception: {type(exc).__name__}: {exc}")
    result = {
        "schema": "simlox-c05-var02-author-readonly-replay/v1",
        "variant_id": "C05.var02",
        "decision": "GO_BOUNDED" if not checks.failures else "NO_GO",
        "passed_checks": checks.total - len(checks.failures),
        "total_checks": checks.total,
        "failures": checks.failures,
        "report_cells_cryptographically_pinned": 10420,
        "reused_child_raw_seals": 24,
        "direct_parent_raw_seals": 12,
        "scope": "Read-only catalog mapping of already accepted C05 radio-2/radio-0 CLI evidence; no native rerun.",
    }
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(f"{result['decision']} {result['passed_checks']}/{result['total_checks']}")
    for failure in checks.failures[:20]:
        print("FAIL", failure)
    return 0 if not checks.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
