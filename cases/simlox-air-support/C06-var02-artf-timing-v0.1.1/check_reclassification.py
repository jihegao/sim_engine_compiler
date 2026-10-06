"""Read-only author replay of the accepted C06 ARTF-one/ARTF-two pair."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CASES = HERE.parent
SOURCE = CASES / "C06-alternative-resource-v1.0.0"
PARENT = CASES / "C03-shared-crew-formation-v1.0.2"
CONTRACT_SHA = "6e1f264128919e2282442de5528d67d69ea651ebe1707b81a97408badde3720d"
REVIEW_SHA = "7752b3f90f9894ad205860d28e4cffafda63b8711d74d8f1098cbb2a59c94f4f"
OUT = HERE / "author-validation.json"


def seal_bytes(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def seal(path: Path) -> dict:
    return seal_bytes(path.read_bytes())


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path):
    """Parse native trailing commas in memory, preserving the sealed raw file."""
    text = path.read_text(encoding="utf-8-sig")
    output = []
    quoted = escaped = False
    for index, char in enumerate(text):
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
            ahead = index + 1
            while ahead < len(text) and text[ahead].isspace():
                ahead += 1
            if ahead == len(text) or text[ahead] not in "]}":
                output.append(char)
        else:
            output.append(char)
    return json.loads("".join(output))


def git_seal(path: Path) -> dict:
    data = subprocess.run(
        ["git", "show", "HEAD:" + path.relative_to(REPO).as_posix()],
        cwd=REPO, check=True, capture_output=True,
    ).stdout
    return seal_bytes(data)


def table_map(document: dict, root: str) -> dict:
    tables = document[root]["tables"]
    result = {table["name"]: table for table in tables}
    if len(result) != len(tables):
        raise ValueError("duplicate table names")
    return result


def rows(table: dict) -> list:
    return [row for instance in table["instances"] for row in instance["rows"]]


class Checks:
    def __init__(self):
        self.count = 0
        self.failures = []

    def yes(self, result, label: str):
        self.count += 1
        if not result:
            self.failures.append(label)

    def pin(self, path: Path, expected: dict, label: str):
        self.yes(path.is_file(), label + " exists")
        if path.is_file():
            self.yes(seal(path) == expected, label + " SHA/size")


def check_sources(c: Checks, record: dict, package: Path, expected_count: int):
    tracked = subprocess.run(
        ["git", "ls-files", "--", package.relative_to(REPO).as_posix()],
        cwd=REPO, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    pins = record["source_files"]
    c.yes(len(tracked) == len(pins) == expected_count, package.name + " source count")
    c.yes({(REPO / name).relative_to(package).as_posix() for name in tracked} == set(pins),
          package.name + " exact published source paths")
    for name, pin in sorted(pins.items()):
        path = package / name
        c.pin(path, pin["local_disk"], package.name + "/" + name)
        c.yes(git_seal(path) == pin["published_git"], package.name + "/" + name + " published bytes")


def check_run(c: Checks, record: dict, expected_count: int, label: str) -> Path:
    folder = Path(record["path"])
    c.pin(folder / "closure.json", record["closure"], label + " closure")
    c.pin(folder / "invocation.json", record["invocation"], label + " invocation")
    closure = read(folder / "closure.json")
    invocation = read(folder / "invocation.json")
    c.yes(closure["run_id"] == invocation["run_id"] == folder.name, label + " run ID")
    c.yes(closure["invocation_sha256"].lower() == record["invocation"]["sha256"],
          label + " invocation link")
    c.yes(closure["raw"] == record["raw"] and len(record["raw"]) == expected_count,
          label + " complete raw map")
    for name, pin in sorted(record["raw"].items()):
        c.pin(folder / name, pin, label + " raw " + name)
    c.yes(invocation["session_id"] == 0 and invocation["ssh_connection_present"]
          and "sshd.exe" in invocation["ssh_ancestor_names"], label + " SSH0 ancestry")
    c.yes(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue",
          label + " native mutex")
    if expected_count == 12:
        c.yes(closure["source_hashes_before"] == closure["source_hashes_after"]
              == invocation["source_hashes_before"] == record["source_hashes_before"],
              label + " stable source hashes")
        c.yes(closure["error"] is None, label + " no closure error")
        gui = invocation["gui"]
        c.yes(gui["pid"] == 13340 and gui["session_id"] == 1, label + " protected GUI")
        steps = read(folder / "steps.json")
        c.yes([step["name"] for step in steps] ==
              ["import", "export", "calc", "jsonreport", "check_import_export"],
              label + " five steps")
        for step in steps:
            c.yes(step["status"] == "completed" and step["exit_code"] == 0
                  and step["gui_preserved"], label + " step " + step["name"])
    else:
        c.yes(closure["input_sha256"] == invocation["input_sha256"]
              == record["input_sha256"], label + " C03 input link")
        gui = invocation["coexisting_gui"]
        c.yes(gui["pid"] == 13340 and gui["session_id"] == 1,
              label + " C03 protected GUI")
    return folder


def compare_authored(c: Checks, contract: dict):
    parent = contract["accepted_C03_parent"]
    source = contract["accepted_C06_source"]
    check_sources(c, parent, PARENT, 16)
    check_sources(c, source, SOURCE, 17)
    diagnostic = contract["excluded_diagnostic"]
    c.yes(diagnostic["classification"] == "NO_GO_CONTRACT"
          and diagnostic["native_run_count"] == 0,
          "v0.1.0 contract exclusion")
    for name in ("frozen_contract", "independent_no_go_memo"):
        item = diagnostic[name]
        c.pin(CASES / item["path"], {"bytes": item["bytes"], "sha256": item["sha256"]},
              "v0.1.0 " + name)
    for name, item in sorted(contract["published_C06_var01_context"]["pins"].items()):
        path = CASES / contract["published_C06_var01_context"]["package"] / name
        c.pin(path, item["local_disk"], "published C06.var01 " + name)
        c.yes(git_seal(path) == item["published_git"],
              "published C06.var01 " + name + " Git")
    for name, actual in [
        ("contract", "contract.json"), ("exact_diff", "exact-diff.json"),
        ("signoff", "cli-scope-signoff-2026-09-30.md"),
        ("author_validation", "author-native-validation-2026-09-30.json"),
        ("independent_verdict", "review/independent-readonly-2026-09-30.json"),
    ]:
        path = SOURCE / actual
        c.pin(path, source[name]["local_disk"], "C06 " + name)
        c.yes(git_seal(path) == source[name]["published_git"], "C06 " + name + " Git")
    parent_input = PARENT / "inputs/staffing-2.json"
    c.pin(parent_input, parent["staffing_2_input"]["local_disk"], "C03 parent input")
    c.yes(git_seal(parent_input) == parent["staffing_2_input"]["published_git"],
          "C03 parent Git input")
    check_run(c, parent["staffing_2_run"], 11, "C03 staffing2")
    models = {}
    for label, name in [("artf_1", "primary-0-artf-1-input.json"),
                        ("artf_2", "primary-0-artf-2-input.json")]:
        pin = source["pair_inputs"][label]
        c.pin(SOURCE / name, pin["local_disk"], label + " input")
        c.yes(git_seal(SOURCE / name) == pin["published_git"], label + " Git input")
        model = table_map(read(SOURCE / name), "model")
        models[label] = model
        c.yes(sum(bool(rows(table)) for table in model.values()) == 20,
              label + " 20 row-containing tables")
        parent_model = table_map(read(parent_input), "model")
        c.yes({n for n in model if model[n] != parent_model[n]} ==
              set(contract["pair_source_delta"]["C03_to_C06_changed_tables"]),
              label + " C03 to C06 exact table set")
        allocation = model["ResourceAllocation"]
        entries = [dict(zip([col["name"] for col in allocation["columns"]], row))
                   for row in rows(allocation)]
        c.yes(len(entries) == 2 and [item["RID"] for item in entries] == ["P-CREW", "P-ALT"]
              and [item["RQTY"] for item in entries] == [0, 2],
              label + " fixed alternative and primary capacities")
        subtask = model["SubTaskResource"]
        subentries = [dict(zip([col["name"] for col in subtask["columns"]], row))
                      for row in rows(subtask)]
        expected = contract["pair_source_delta"]["SubTaskResource_common_except_ARTF"]
        c.yes(len(subentries) == 1 and all(subentries[0][k] == v for k, v in expected.items())
              and subentries[0]["ARTF"] == contract["pair_source_delta"]["ARTF"][label],
              label + " common P-CREW/P-ALT/ARTF row")
    left = read(SOURCE / "primary-0-artf-1-input.json")
    right = read(SOURCE / "primary-0-artf-2-input.json")
    actual = []
    for ta, tb in zip(left["model"]["tables"], right["model"]["tables"]):
        c.yes(ta["name"] == tb["name"] and ta["columns"] == tb["columns"],
              ta["name"] + " aligned source schema")
        for ia, ib in zip(ta["instances"], tb["instances"]):
            c.yes(ia["instance_name"] == ib["instance_name"], ta["name"] + " instance")
            for row_index, (ra, rb) in enumerate(zip(ia["rows"], ib["rows"])):
                for col_index, (a, b) in enumerate(zip(ra, rb)):
                    if a != b:
                        actual.append({"table": ta["name"], "instance": ia["instance_name"],
                                       "row_index_zero_based": row_index,
                                       "column": ta["columns"][col_index]["name"],
                                       "artf_1": a, "artf_2": b})
    c.yes(actual == contract["pair_source_delta"]["exact_changed_cells"],
          "exact two-cell pair diff")
    return models


def arm(c: Checks, contract: dict, label: str, model: dict):
    folder = check_run(c, contract["accepted_C06_runs"][label], 12, label)
    c.yes(seal(folder / "input.json") ==
          contract["accepted_C06_source"]["pair_inputs"][label]["local_disk"],
          label + " run input equals authored source")
    exported = table_map(native(folder / "roundtrip-raw.json"), "model")
    for name, authored in sorted(model.items()):
        if rows(authored):
            actual = exported.get(name)
            c.yes(actual is not None and actual["columns"] == authored["columns"]
                  and rows(actual) == rows(authored), label + " exact table " + name)
    c.yes(read(folder / "roundtrip-validation.json")["passed"],
          label + " original roundtrip passed")
    runlog = (folder / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    c.yes("Errors: 0, Warnings: 2, Notes: 0" in runlog,
          label + " converter 0/2/0")
    c.yes(sorted(set(re.findall(r"warning\s*#(\d+)", runlog, re.I))) == ["108", "126"]
          and not re.search(r"error\s*#\d+", runlog, re.I),
          label + " exact warnings")
    event = (folder / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    factor_one = label == "artf_1"
    chosen, other = "P-ALT", "P-CREW"
    end = "7.83333" if factor_one else "8.16667"
    launch = "8" if factor_one else "8.16667"
    finish = "9" if factor_one else "9.16667"
    mission = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    c.yes(event.count(f"Time: 7.5 {mission} mission activated, systems requested: 2") == 1,
          label + " one two-aircraft mission")
    for system in (0, 1):
        c.yes(f"{mission} mission allocates system: <TEACH-AIR-01,{system}>" in event,
              label + f" ID{system} allocated")
        c.yes(f"Time: 7.5 <TEACH-AIR-01,{system}> preparation started" in event,
              label + f" ID{system} preparation starts")
        c.yes(f"Time: {end} <TEACH-AIR-01,{system}> preparation ended" in event,
              label + f" ID{system} preparation ends")
        c.yes(f"System arrives <TEACH-AIR-01,{system}>, mission success" in event,
              label + f" ID{system} returns")
    c.yes(event.count(f"<{chosen} at <BASE-01,0>> allocated to maintenance task: 1") == 2
          and event.count(f"<{chosen} at <BASE-01,0>> deallocated from  maintenance task: 1") == 2,
          label + " selected resource two books/releases")
    c.yes(event.count(f"Availability test on  <{chosen} at <BASE-01,0>> request for: 1 OK") == 2,
          label + " two typed selected-resource availability passes")
    c.yes(event.count("Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed") == 2,
          label + " two primary-resource availability failures")
    c.yes(event.count(f"Time: 7.5  <{chosen} at <BASE-01,0>> allocated to maintenance task: 1") == 2
          and event.count(f"Time: {end}  <{chosen} at <BASE-01,0>> deallocated from  maintenance task: 1") == 2,
          label + " two selected-resource timed bookings/releases")
    c.yes(f"<{other} at <BASE-01,0>> allocated to maintenance task: 1" not in event,
          label + " other resource never booked")
    planned = "0.333333" if factor_one else "0.666667"
    c.yes(event.count(f"starts performing, planned to last for {planned} hours") == 2,
          label + " both physical subtask durations")
    c.yes(event.count(f"Time: {launch} {mission} mission starting") == 1 and
          event.count(f"Time: {finish} {mission} mission success") == 1 and
          event.count(f"Time: {finish} {mission} mission completed") == 1,
          label + " launch/success/completion timeline")
    c.yes("mission cancelled:" not in event and "mission aborted:" not in event,
          label + " no cancellation/abort")
    c.yes("backorder" not in event.lower() and "failure mode" not in event.lower(),
          label + " no physical stock failure")
    report = table_map(native(folder / "report-raw.json"), "report")
    sizes = contract["predeclared_gates"]["reports"]["table_cells_per_arm"]
    c.yes(set(report) == set(sizes), label + " six report tables")
    values = {}
    count = 0
    for name, table in sorted(report.items()):
        grid = rows(table)
        count += sum(len(row) for row in grid)
        c.yes(len(grid) * len(table["columns"]) == sizes[name],
              label + " shape " + name)
        for row_index, row in enumerate(grid):
            c.yes(len(row) == len(table["columns"]),
                  label + f" {name} row {row_index} width")
            for col_index, value in enumerate(row):
                c.yes(not isinstance(value, (list, dict)),
                      label + f" {name} scalar {row_index}/{col_index}")
        values[name] = grid
    c.yes(count == 5210, label + " all 5210 report cells")
    c.yes(len(values["SystemResults"]) == len(values["StockTotalResults"])
          == len(values["ResourceResults"]) == 72, label + " all 72 bins")
    columns = [col["name"] for col in report["SystemResults"]["columns"]]
    c.yes(values["SystemResults"][-1][columns.index("NSYRY")] == 2,
          label + " terminal ready2")
    for name in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT"):
        cols = [col["name"] for col in report["StockTotalResults"]["columns"]]
        for index, row in enumerate(values["StockTotalResults"]):
            c.yes(row[cols.index(name)] == 0, label + f" stock {name} bin {index}")
    return values


def main() -> int:
    c = Checks()
    try:
        c.pin(HERE / "contract.json", {"bytes": 36029, "sha256": CONTRACT_SHA},
              "frozen contract")
        c.yes(seal(HERE / "review/independent-contract-go-2026-10-07.md")["sha256"]
              == REVIEW_SHA, "independent contract GO")
        contract = read(HERE / "contract.json")
        c.yes(contract["variant_id"] == "C06.var02" and
              not contract["ownership"]["native_run_planned"], "read-only classification")
        models = compare_authored(c, contract)
        left = arm(c, contract, "artf_1", models["artf_1"])
        right = arm(c, contract, "artf_2", models["artf_2"])
        differences = contract["predeclared_gates"]["reports"]["pair_difference_counts"]
        for name in sorted(differences):
            found = 0
            for row_index, (a_row, b_row) in enumerate(zip(left[name], right[name])):
                for col_index, (a, b) in enumerate(zip(a_row, b_row)):
                    found += a != b
                    if name in ("StockTotalResults", "ResultSummary"):
                        c.yes(a == b, f"pair {name} {row_index}/{col_index} parity")
            c.yes(found == differences[name], "pair " + name + " exact difference count")
    except (OSError, ValueError, KeyError, IndexError, TypeError,
            subprocess.CalledProcessError) as exc:
        c.yes(False, f"exception: {type(exc).__name__}: {exc}")
    verdict = {
        "schema": "simlox-c06-var02-author-readonly-replay/v1",
        "variant_id": "C06.var02",
        "decision": "GO_BOUNDED" if not c.failures else "NO_GO",
        "passed_checks": c.count - len(c.failures),
        "total_checks": c.count,
        "failures": c.failures,
        "report_cells_checked": 10420,
        "accepted_C06_raw_seals": 24,
        "accepted_C03_parent_raw_seals": 11,
        "scope": "Read-only classification of accepted C06 ARTF-one/ARTF-two pair; no native rerun.",
    }
    OUT.write_bytes((json.dumps(verdict, ensure_ascii=False, indent=2) + "\n").encode())
    print(verdict["decision"], f"{verdict['passed_checks']}/{verdict['total_checks']}")
    for failure in c.failures[:20]:
        print("FAIL", failure)
    return 0 if not c.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
