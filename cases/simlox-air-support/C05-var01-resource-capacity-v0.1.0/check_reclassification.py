"""Read-only author replay of the three accepted C05 mission-crew runs."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CASES = HERE.parent
ACCEPTED = CASES / "C05-mission-resource-v1.0.0"
OUT = HERE / "author-validation.json"
CONTRACT_SHA = "096c4a6d23079c46416e06b8d79229033a13ecc23db29eb1ea6c2bf2524390ad"
REVIEW_SHA = "af1005ad25d1ca9905ef74f127c050bf630e06adf33bf798b594d062f9f088f0"
TABLE_DIGESTS = {
    2: {"ProblemDescription": "020179276a66bd44bb3b22870415d8fc8d6b11c6106012ac813420a9de31a701", "ResultSummary": "c2d1b8c6337c16a8d03a6cc38afd78814f8bdc4c46fc9951b57ef35e2df3b2a3", "SystemResults": "02d8d87603e9a85807b22de52f57abe28a20c70824561459745834e9eafb82dd", "StockTotalResults": "13058441aa4a0114a46c2b347662619deade171cbebfba11222cb8b4648c1953", "ResourceResults": "3897baae44cee35b8d2d5ba8c1de69a6a64615492b613bb28e4ba8c602574e6f", "ResourceResultsTotal": "2dd5a0f7aa183c3b6a6879bb0713385ed117c38fac8eb5c4ca13609a94ddf8a2"},
    1: {"ProblemDescription": "8ed683b1991f1db50b4e3dbfeb259f3312fd0ca3e8062597ff042dd2e8544cea", "ResultSummary": "fa66bb5a8c919ce7dae9bbb03b9200c3782de8fca13d991cae17bf11d3e08f0a", "SystemResults": "b7cb8c19c851d3a012d81c66e8fd829c2b231cb1aa301549b20b57513fc956c9", "StockTotalResults": "13058441aa4a0114a46c2b347662619deade171cbebfba11222cb8b4648c1953", "ResourceResults": "bc5ed2b1ff7755741c4ecd4080df466efbf17dcf43e619be3e26f5973ddd7b24", "ResourceResultsTotal": "d949d532652493bacadbfa93bddf0ef0517a9d76b9e37e761facf1caab60e352"},
    0: {"ProblemDescription": "2f14b4f74c6b7bfc07c3aedfdcc4307b2153c509eb294eab15eec939429d6428", "ResultSummary": "fa66bb5a8c919ce7dae9bbb03b9200c3782de8fca13d991cae17bf11d3e08f0a", "SystemResults": "58c6a460440ff17dd502c555db521821fb66c9339808f3163360854fca706ccb", "StockTotalResults": "13058441aa4a0114a46c2b347662619deade171cbebfba11222cb8b4648c1953", "ResourceResults": "78de4b7081bb4a6e82ea2622fe48c2c5a5980357da1651f6e43bc3de35bd0a28", "ResourceResultsTotal": "ce5a27a8025db202356dc13d2eb590eb449b5e411102fb426fa805061e0fccc7"},
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": digest(data)}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path):
    """Parse native trailing commas in memory without changing sealed bytes."""
    raw = path.read_text(encoding="utf-8-sig")
    output = []
    quoted = escaped = False
    for index, char in enumerate(raw):
        if quoted:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            output.append(char)
        elif char == ",":
            next_index = index + 1
            while next_index < len(raw) and raw[next_index].isspace():
                next_index += 1
            if next_index == len(raw) or raw[next_index] not in "}]":
                output.append(char)
        else:
            output.append(char)
    return json.loads("".join(output))


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def table_map(document: dict, root: str) -> dict[str, dict]:
    tables = document[root]["tables"]
    result = {table["name"]: table for table in tables}
    if len(result) != len(tables):
        raise ValueError("duplicate table name")
    return result


def git_seal(path: Path) -> dict:
    rel = path.relative_to(REPO).as_posix()
    data = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=REPO,
                          check=True, capture_output=True).stdout
    return {"bytes": len(data), "sha256": digest(data)}


class Checks:
    def __init__(self):
        self.count = 0
        self.failures: list[str] = []

    def check(self, condition, label: str):
        self.count += 1
        if not condition:
            self.failures.append(label)


def verify_pin(checks: Checks, path: Path, pin: dict, label: str):
    checks.check(path.is_file(), f"{label} exists")
    if path.is_file():
        checks.check(seal(path) == pin, f"{label} SHA and size")


def verify_source(checks: Checks, contract: dict):
    accepted = contract["accepted_source"]
    listed = subprocess.run(["git", "ls-files", "--", ACCEPTED.relative_to(REPO).as_posix()],
                            cwd=REPO, check=True, capture_output=True, text=True).stdout.splitlines()
    checks.check(len(listed) == accepted["published_source_file_count"] == 17,
                 "17 accepted source Git files")
    pinned = {item["path"]: item for item in accepted["published_source_files"]}
    checks.check({(REPO / item).relative_to(ACCEPTED).as_posix() for item in listed} == set(pinned),
                 "accepted source path set")
    for name, record in sorted(pinned.items()):
        path = ACCEPTED / name
        verify_pin(checks, path, record["local_disk"], f"accepted source {name}")
        checks.check(git_seal(path) == record["published_git"], f"published Git {name}")
    for case, prerequisite in sorted(contract["prerequisites"].items()):
        package = CASES / prerequisite["package"]
        for name, record in sorted(prerequisite["pins"].items()):
            verify_pin(checks, package / name, record["local_disk"], f"{case} {name}")
            checks.check(git_seal(package / name) == record["published_git"],
                         f"{case} published Git {name}")
    for name, path in [
        ("original_contract", ACCEPTED / "contract.json"),
        ("original_exact_diff", ACCEPTED / "exact-diff.json"),
        ("original_signoff", ACCEPTED / "cli-scope-signoff-2026-09-30.md"),
        ("original_independent_verdict", ACCEPTED / "review/independent-readonly-2026-09-30.json"),
        ("original_author_verdict", ACCEPTED / "author-native-validation-2026-09-30.json"),
    ]:
        verify_pin(checks, path, accepted[name], name)
    parent = table_map(read_json(CASES / "A03-two-aircraft-formation-v1.0.1/native-input.json"), "model")
    inputs = {}
    for capacity in (2, 1, 0):
        name = f"capacity-{capacity}-input.json"
        pin = accepted["input_pins"][str(capacity)]
        verify_pin(checks, ACCEPTED / name, pin["local_disk"], f"source {capacity}")
        checks.check(git_seal(ACCEPTED / name) == pin["published_git"],
                     f"source {capacity} published Git")
        tables = table_map(read_json(ACCEPTED / name), "model")
        inputs[capacity] = tables
        changed = {key for key in set(tables) | set(parent) if tables.get(key) != parent.get(key)}
        checks.check(changed == set(contract["source_delta"]["A03_to_C05_common_changed_tables"]),
                     f"parent-to-C05 changed table set {capacity}")
        populated = {key for key, table in tables.items() if rows(table)}
        checks.check(len(populated) == 16, f"source {capacity} row-containing tables")
        allocation = rows(tables["ResourceAllocation"])
        columns = [column["name"] for column in tables["ResourceAllocation"]["columns"]]
        mapping = dict(zip(columns, allocation[0]))
        checks.check(len(allocation) == 1 and
                     [mapping[key] for key in ("POINT", "RID", "STID", "RQTY")] ==
                     ["AIR_BASIC", "MISSION-CREW", "BASE-01", capacity],
                     f"source {capacity} exact ResourceAllocation")
        checks.check(rows(tables["MissionResource"]) ==
                     [contract["source_delta"]["MissionResource_common_row"]],
                     f"source {capacity} one per-aircraft crew row")
    for capacity in (1, 0):
        changed = {key for key in inputs[2] if inputs[2][key] != inputs[capacity][key]}
        checks.check(changed == set(contract["source_delta"]["pairwise_changed_tables"]),
                     f"2-vs-{capacity} changed tables")
    return inputs


def verify_run(checks: Checks, contract: dict, capacity: int, source_tables: dict) -> dict:
    record = contract["accepted_runs"][str(capacity)]
    run = ACCEPTED / "runs" / record["run_id"]
    verify_pin(checks, run / "closure.json", record["closure"], f"run {capacity} closure")
    verify_pin(checks, run / "invocation.json", record["invocation"], f"run {capacity} invocation")
    closure = read_json(run / "closure.json")
    invocation = read_json(run / "invocation.json")
    checks.check(closure["run_id"] == record["run_id"] == invocation["run_id"],
                 f"run {capacity} identity")
    checks.check(closure["raw"] == record["raw"] and len(record["raw"]) == 12,
                 f"run {capacity} 12 raw map")
    checks.check(closure["invocation_sha256"] == record["invocation"]["sha256"],
                 f"run {capacity} invocation link")
    checks.check(closure["source_hashes_before"] == closure["source_hashes_after"] ==
                 record["source_hashes_before_after"], f"run {capacity} immutable source")
    checks.check(closure["error"] is None, f"run {capacity} no closure error")
    for name, pin in sorted(record["raw"].items()):
        verify_pin(checks, run / name, pin, f"run {capacity} raw {name}")
    checks.check(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
                 "sshd.exe" in invocation["ssh_ancestor_names"], f"run {capacity} SSH0 ancestry")
    checks.check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
                 invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
                 f"run {capacity} original mutex and protected GUI identity")
    steps = read_json(run / "steps.json")
    checks.check([step["name"] for step in steps] ==
                 ["import", "export", "calc", "jsonreport", "check_import_export"],
                 f"run {capacity} five steps")
    for step in steps:
        checks.check(step["status"] == "completed" and step["exit_code"] == 0 and
                     step["gui_preserved"], f"run {capacity} step {step['name']}")
    exported = table_map(native_json(run / "roundtrip-raw.json"), "model")
    populated = {key for key, table in source_tables.items() if rows(table)}
    checks.check(len(populated) == 16, f"run {capacity} 16 authored tables")
    for key in sorted(populated):
        before, after = source_tables[key], exported.get(key)
        checks.check(after is not None and before["columns"] == after["columns"] and
                     rows(before) == rows(after), f"run {capacity} {key} exact native roundtrip")
    checks.check(read_json(run / "roundtrip-validation.json")["passed"],
                 f"run {capacity} original roundtrip gate")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    checks.check(not re.search(r"\berror\s*#\d+", run_log, re.I),
                 f"run {capacity} converter no errors")
    checks.check(sorted(set(re.findall(r"warning\s*#(\d+)", run_log, re.I))) == ["108", "126"],
                 f"run {capacity} converter warnings 108/126 only")
    text = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    checks.check(text.count(f"{mission} mission created:") == 1 and
                 text.count(f"{mission} mission activated, systems requested: 2") == 1,
                 f"run {capacity} one two-aircraft demand h7")
    assigned = re.findall(r"Time: 7\s+<MISSION-CREW at <BASE-01,0>> allocated to mission assigned: 1\s+available now: (\d+)", text)
    released = re.findall(r"Time: (?:10|8\.33333)\s+<MISSION-CREW at <BASE-01,0>> deallocated from\s+mission (?:operation|assigned): 1\s+available now: (\d+)", text)
    checks.check(len(assigned) == len(released) == capacity,
                 f"run {capacity} crew reservation and release conservation")
    checks.check(text.count(f"{mission} mission allocates system:") == capacity,
                 f"run {capacity} aircraft assignment count")
    checks.check(text.count("request for: 1 failed") >= 2 - capacity,
                 f"run {capacity} typed availability failures")
    if capacity == 2:
        checks.check(assigned == ["1", "0"] and released == ["1", "2"],
                     "capacity 2 crew allocation/release sequence")
        checks.check(text.count(f"Time: 8 {mission} mission starting") == 1 and
                     text.count(f"Time: 10 {mission} mission success") == 1 and
                     text.count(f"Time: 10 {mission} mission completed") == 1,
                     "capacity 2 launch, success and completion")
        checks.check("mission cancelled:" not in text, "capacity 2 no cancellation")
    else:
        checks.check(text.count(f"Time: 8.33333 {mission} mission cancelled") == 1 and
                     "mission waiting:  timeout at 8.33333" in text,
                     f"capacity {capacity} timeout and cancellation")
        checks.check("mission starting" not in text and "mission success" not in text,
                     f"capacity {capacity} no launch/success")
        if capacity == 1:
            checks.check(assigned == ["0"] and released == ["1"] and
                         f"{mission} mission allocates system: <TEACH-AIR-01,0>" in text,
                         "capacity 1 ID0 partially assigned before cancellation")
        else:
            checks.check(not assigned and not released and
                         f"{mission} mission allocates system:" not in text,
                         "capacity 0 no booking or aircraft assignment")
    checks.check("systems ready: 2 :" in text and "System ready" in text if capacity else
                 "systems ready: 2 :" in text, f"run {capacity} two ready aircraft terminal")
    report = table_map(native_json(run / "report-raw.json"), "report")
    shape = contract["predeclared_replay_gates"]["reports"]["tables"]
    checks.check(set(report) == set(shape) == set(TABLE_DIGESTS[capacity]),
                 f"run {capacity} six report table names")
    extracted = {}
    for key, dimensions in sorted(shape.items()):
        table_rows = rows(report[key])
        checks.check(len(table_rows) == dimensions["rows"] and
                     len(report[key]["columns"]) == dimensions["columns"],
                     f"run {capacity} {key} row/column shape")
        for index, row in enumerate(table_rows):
            checks.check(len(row) == dimensions["columns"],
                         f"run {capacity} {key} row {index} width")
        canonical = json.dumps(table_rows, ensure_ascii=False, separators=(",", ":")).encode()
        checks.check(digest(canonical) == TABLE_DIGESTS[capacity][key],
                     f"run {capacity} {key} all-cell accepted table digest")
        extracted[key] = table_rows
    checks.check(sum(len(row) for value in extracted.values() for row in value) == 5210,
                 f"run {capacity} 5210 report cells")
    def report_value(table: str, column: str):
        names = [c["name"] for c in report[table]["columns"]]
        return extracted[table][0][names.index(column)]
    checks.check([report_value("ResultSummary", name) for name in
                 ("MTMF", "MSTF", "MSUF", "STMF")] ==
                 ([1] * 4 if capacity == 2 else [0] * 4),
                 f"run {capacity} four mission summary fields")
    checks.check(report_value("ResourceResultsTotal", "NR") == capacity,
                 f"run {capacity} resource capacity total")
    sys_cols = [c["name"] for c in report["SystemResults"]["columns"]]
    checks.check(extracted["SystemResults"][-1][sys_cols.index("NSYRY")] == 2,
                 f"run {capacity} terminal ready two")
    stock_cols = [c["name"] for c in report["StockTotalResults"]["columns"]]
    for field in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT"):
        ix = stock_cols.index(field)
        for index, row in enumerate(extracted["StockTotalResults"]):
            checks.check(row[ix] == 0, f"run {capacity} stock {field} bin {index} zero")
    return extracted


def compare_reports(checks: Checks, contract: dict, reports: dict[int, dict]):
    expected = contract["predeclared_replay_gates"]["reports"]["pairwise_difference_counts_vs_capacity_2"]
    for capacity in (1, 0):
        for table in reports[2]:
            left = reports[2][table]
            right = reports[capacity][table]
            difference = 0
            for index, (a_row, b_row) in enumerate(zip(left, right)):
                for col, (a, b) in enumerate(zip(a_row, b_row)):
                    checks.check(type(a) is type(b) or a != b,
                                 f"2-vs-{capacity} {table} cell {index}/{col} typed comparison")
                    difference += a != b
            checks.check(difference == expected[f"2_vs_{capacity}"][table],
                         f"2-vs-{capacity} {table} exact all-cell contrast count")
    for capacity in (1, 0):
        for index, (a, b) in enumerate(zip(reports[2]["StockTotalResults"],
                                           reports[capacity]["StockTotalResults"])):
            for col, (x, y) in enumerate(zip(a, b)):
                checks.check(x == y, f"2-vs-{capacity} stock bin {index} col {col} parity")


def main():
    checks = Checks()
    verify_pin(checks, HERE / "contract.json", {"bytes": 26914, "sha256": CONTRACT_SHA},
               "frozen C05.var01 contract")
    verify_pin(checks, HERE / "review/independent-contract-go-2026-10-07.md",
               {"bytes": (HERE / "review/independent-contract-go-2026-10-07.md").stat().st_size,
                "sha256": REVIEW_SHA}, "independent contract GO")
    contract = read_json(HERE / "contract.json")
    checks.check(contract["variant_id"] == "C05.var01" and
                 contract["ownership"]["native_child_planned"] is False,
                 "read-only C05.var01 scope")
    sources = verify_source(checks, contract)
    reports = {capacity: verify_run(checks, contract, capacity, sources[capacity])
               for capacity in (2, 1, 0)}
    compare_reports(checks, contract, reports)
    result = {"schema": "simlox-c05-var01-author-readonly-replay/v1",
              "variant_id": "C05.var01", "decision": "GO_BOUNDED" if not checks.failures else "NO_GO",
              "passed_checks": checks.count - len(checks.failures), "total_checks": checks.count,
              "failures": checks.failures, "report_cells_cryptographically_pinned": 3 * 5210,
              "accepted_run_ids": [contract["accepted_runs"][str(n)]["run_id"] for n in (2, 1, 0)],
              "scope": "Read-only source-bound classification of existing C05 mission-crew capacity 2/1/0 runs; no native rerun or new behavior."}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(f"{result['decision']} {result['passed_checks']}/{result['total_checks']}")
    for failure in checks.failures[:15]:
        print("FAIL", failure)
    return 0 if not checks.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
