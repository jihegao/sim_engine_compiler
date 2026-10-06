"""Frozen, read-only CLI behavior gate for the A03 three-available arm.

The accepted A03 two-aircraft run is read as a sealed control. The child run is
never created or changed here. This module does not invoke SIMLOX.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "A03-two-aircraft-formation-v1.0.1"
PARENT_RUN = Path(
    "C:/Users/user/Documents/Codex/2026-09-28/simlox-issue18-ssh-current/"
    "cases/simlox-air-support/A03-two-aircraft-formation-v1.0.1/"
    "runs/a03-v101-ssh-gui-20260929-01"
)
A02 = ROOT / "A02-single-aircraft-repeated-missions"
RUN_ID = "a03-var01-three-avail-v010-ssh-20261006-01"
RUN = HERE / "runs" / RUN_ID
CONTRACT_SHA = "a466a9faab28b518e037f56b90be7a8c1cfce7be99b1fb542c6de3828b17994e"
INPUT_SHA = "6fc81a5a5ce9304c007a2087a0116cb585bf3fe70312649937e43d0576be0e71"
MISSION = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
AIRCRAFT = re.compile(r"<TEACH-AIR-01,(\d+)>")
FTMO_TOL = 1e-5


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path: Path):
    """Parse a normalized copy while leaving native trailing-comma bytes intact."""
    source = path.read_text(encoding="utf-8-sig")
    out: list[str] = []
    quoted = escaped = False
    for index, char in enumerate(source):
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
            following = index + 1
            while following < len(source) and source[following].isspace():
                following += 1
            if following >= len(source) or source[following] not in "]}":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def table_map(document: dict, section: str) -> dict[str, dict]:
    entries = document[section]["tables"]
    result = {entry["name"]: entry for entry in entries}
    if len(result) != len(entries):
        raise ValueError(f"duplicate {section} table")
    return result


def table_rows(table: dict) -> tuple[list[str], list[dict]]:
    fields = [field["name"] for field in table["columns"]]
    if len(fields) != len(set(fields)):
        raise ValueError("duplicate table column")
    result = []
    for instance in table["instances"]:
        for row in instance["rows"]:
            if len(row) != len(fields):
                raise ValueError("nonrectangular table")
            result.append(dict(zip(fields, row)))
    return fields, result


def source_cells(document: dict) -> dict[tuple[str, int, int, str], object]:
    result = {}
    for table in document["model"]["tables"]:
        fields = [field["name"] for field in table["columns"]]
        for ii, instance in enumerate(table["instances"]):
            for ri, row in enumerate(instance["rows"]):
                if len(row) != len(fields):
                    raise ValueError("nonrectangular authored row")
                for field, value in zip(fields, row):
                    key = (table["name"], ii, ri, field)
                    if key in result:
                        raise ValueError(f"duplicate authored cell {key}")
                    result[key] = value
    return result


def source_paths() -> dict[str, Path]:
    """Known reviewed source labels; a runner may seal additional labeled inputs."""
    return {
        "child_input": HERE / "native-input.json",
        "child_contract": HERE / "contract.json",
        "contract_review": HERE / "review/independent-contract-go-2026-10-06.md",
        "builder": HERE / "build.py",
        "parent_diff_checker": HERE / "check_parent_diff.py",
        "roundtrip_checker": HERE / "check_roundtrip.py",
        "shared_parser": ROOT / "tools/validate_native.py",
        "behavior_validator": HERE / "validate_native_cli.py",
        "runner_script": HERE / "run_native_ssh.ps1",
        "accepted_input": PARENT / "native-input.json",
        "accepted_contract": PARENT / "contract.json",
        "accepted_signoff": PARENT / "cli-scope-signoff-2026-09-29.md",
        "accepted_verdict": PARENT / "review/independent-readonly-2026-09-29.json",
        "accepted_closure": PARENT_RUN / "closure.json",
        "a02_input": A02 / "native-input.json",
        "a02_signoff": A02 / "cli-scope-signoff-2026-09-29.md",
        "installed_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
        "installed_manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "installed_dictionary": Path(
            "C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"
        ),
        "python": Path(sys.executable),
        "prelaunch_approval": HERE / "review/independent-prelaunch-go.json",
    }


class Checks:
    def __init__(self):
        self.count = 0
        self.failures: list[str] = []
        self.groups: dict[str, int] = {}

    def eq(self, group: str, label: str, actual, expected):
        self.count += 1
        self.groups[group] = self.groups.get(group, 0) + 1
        if actual != expected:
            self.failures.append(f"{group}/{label}: got {actual!r}; expected {expected!r}")

    def near(self, group: str, label: str, actual, expected: float, tol: float = FTMO_TOL):
        good = isinstance(actual, (int, float)) and not isinstance(actual, bool)
        self.eq(group, label, good and abs(actual - expected) <= tol, True)


def check_seals(checks: Checks, folder: Path, closure: dict, expected_count: int):
    checks.eq("parent", "raw count", len(closure["raw"]), expected_count)
    for name, seal in sorted(closure["raw"].items()):
        path = folder / name
        checks.eq("parent_raw", f"{name} SHA", sha(path), seal["sha256"])
        checks.eq("parent_raw", f"{name} bytes", path.stat().st_size, seal["bytes"])


def source_gate(checks: Checks, contract: dict):
    accepted = contract["accepted_parent"]
    checks.eq("source", "contract SHA", sha(HERE / "contract.json"), CONTRACT_SHA)
    checks.eq("source", "input SHA", sha(HERE / "native-input.json"), INPUT_SHA)
    for key, path in {
        "input_sha256": PARENT / "native-input.json",
        "contract_sha256": PARENT / "contract.json",
        "signoff_sha256": PARENT / "cli-scope-signoff-2026-09-29.md",
        "independent_review_sha256": PARENT / "review/independent-readonly-2026-09-29.json",
        "closure_sha256": PARENT_RUN / "closure.json",
    }.items():
        checks.eq("parent", key, sha(path), accepted[key])
    parent_closure = native_json(PARENT_RUN / "closure.json")
    checks.eq("parent", "run ID", parent_closure["run_id"], accepted["run_id"])
    checks.eq("parent", "input SHA", parent_closure["input_sha256"], accepted["input_sha256"])
    check_seals(checks, PARENT_RUN, parent_closure, 11)
    prerequisite = contract["instructional_prerequisite"]
    checks.eq("prerequisite", "A02 input", sha(A02 / "native-input.json"), prerequisite["input_sha256"])
    checks.eq("prerequisite", "A02 signoff", sha(A02 / "cli-scope-signoff-2026-09-29.md"), prerequisite["signoff_sha256"])
    checks.eq("installed", "manual", sha(Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf")),
              contract["manual"]["installed_pdf_sha256"])
    checks.eq("source", "reserved run", contract["ownership"]["native_run_id_reserved"], RUN_ID)

    parent = native_json(PARENT / "native-input.json")
    child = native_json(HERE / "native-input.json")
    parent_tables = table_map(parent, "model")
    child_tables = table_map(child, "model")
    checks.eq("model", "table order", list(child_tables), list(parent_tables))
    checks.eq("model", "31 tables", len(child_tables), 31)
    old_cells, new_cells = source_cells(parent), source_cells(child)
    checks.eq("model", "155 parent cells", len(old_cells), 155)
    checks.eq("model", "same cell keys", list(new_cells), list(old_cells))
    changes = {key: (old_cells[key], new_cells[key]) for key in old_cells if old_cells[key] != new_cells[key]}
    checks.eq("model", "one QTYPS edit", changes, {("SystemDeployment", 0, 0, "QTYPS"): (2, 3)})
    for name, prior in parent_tables.items():
        checks.eq("model", f"{name} columns", child_tables[name]["columns"], prior["columns"])
        checks.eq("model", f"{name} instance metadata", [x["instance_name"] for x in child_tables[name]["instances"]],
                  [x["instance_name"] for x in prior["instances"]])
    mission = table_rows(child_tables["MissionType"])[1]
    checks.eq("model", "nominal/minimum aircraft", (mission[0]["NOS"], mission[0]["MNOS"]), (2, 2))
    profile = table_rows(child_tables["OperationProfile"])[1]
    checks.eq("model", "sole h8 wave", (len(profile), profile[0]["STIM"], profile[0]["IQTY"]), (1, 8, 1))
    return parent_tables, child_tables


def event_gate(checks: Checks, path: Path):
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    checks.eq("events", "36-hour horizon", lines[1], "36")

    def matches(pattern: str):
        return [(index, line) for index, line in enumerate(lines) if re.search(pattern, line)]

    def at(hour: float, line: str):
        match = re.match(r"Time: ([0-9]+(?:\.[0-9]+)?)\s", line)
        return match is not None and abs(float(match.group(1)) - hour) < 1e-4

    ready_zero = matches(r"^Time: 0 <TEACH-UNIT at <BASE-01,0>> systems ready: 3 :")
    checks.eq("events", "one h0 ready-three snapshot", len(ready_zero), 1)
    deployed = set(AIRCRAFT.findall(ready_zero[0][1])) if ready_zero else set()
    checks.eq("events", "three distinct h0 IDs", len(deployed), 3)
    checks.eq("events", "h0 ready count/identity", len(AIRCRAFT.findall(ready_zero[0][1])) if ready_zero else 0, 3)
    order = matches(r"mission ordered: BASIC-MISSION")
    created = matches(re.escape(MISSION) + r" mission created:")
    request = matches(re.escape(MISSION) + r" mission activated, systems requested: 2")
    checks.eq("events", "one h7 order", len(order), 1)
    checks.eq("events", "one h7 creation", len(created), 1)
    checks.eq("events", "one h7 request-two", len(request), 1)
    for label, found in (("order", order), ("creation", created), ("request", request)):
        if found:
            checks.eq("events", f"{label} at h7", at(7, found[0][1]), True)

    allocations = matches(re.escape(MISSION) + r" mission allocates system: <TEACH-AIR-01,\d+>")
    allocated = [AIRCRAFT.search(line).group(1) for _, line in allocations]
    checks.eq("events", "two allocations", len(allocated), 2)
    checks.eq("events", "two distinct IDs", len(set(allocated)), 2)
    checks.eq("events", "allocations among deployed", set(allocated).issubset(deployed), True)
    checks.eq("events", "both allocated h7", all(at(7, line) for _, line in allocations), True)
    unused = deployed - set(allocated)
    checks.eq("events", "one unused third ID", len(unused), 1)
    for identity in unused:
        checks.eq("events", f"unused {identity} never loses ready", bool(matches(
            rf"<TEACH-AIR-01,{re.escape(identity)}> nbr ready decreased")), False)
    decreases = matches(r"<TEACH-AIR-01,\d+> nbr ready decreased at unit")
    checks.eq("events", "h7 decrease IDs", {AIRCRAFT.search(line).group(1) for _, line in decreases}, set(allocated))
    checks.eq("events", "exactly two decreases", len(decreases), 2)
    checks.eq("events", "decreases at h7", all(at(7, line) for _, line in decreases), True)

    launch = matches(re.escape(MISSION) + r" mission starting, duration: 2 :")
    checks.eq("events", "one h8 launch", len(launch), 1)
    if launch:
        checks.eq("events", "launch time", at(8, launch[0][1]), True)
        checks.eq("events", "launch pair", set(AIRCRAFT.findall(launch[0][1])), set(allocated))
        checks.eq("events", "launch exactly two entries", len(AIRCRAFT.findall(launch[0][1])), 2)
    for label, pattern, hour in (
        ("task start", re.escape(MISSION) + r" task starting:", 8.5),
        ("task end", re.escape(MISSION) + r" task completed:", 9.5),
        ("mission completed", re.escape(MISSION) + r" mission completed:", 10),
    ):
        found = matches(pattern)
        checks.eq("events", f"one {label}", len(found), 1)
        if found:
            checks.eq("events", f"{label} time", at(hour, found[0][1]), True)
            checks.eq("events", f"{label} pair", set(AIRCRAFT.findall(found[0][1])), set(allocated))
            checks.eq("events", f"{label} exactly two", len(AIRCRAFT.findall(found[0][1])), 2)
    success = matches(re.escape(MISSION) + r" mission success:")
    checks.eq("events", "one h10 success", len(success), 1)
    if success:
        checks.eq("events", "success time", at(10, success[0][1]), True)
    arrivals = matches(r"System arrives <TEACH-AIR-01,\d+>, mission success")
    arrival_ids = [re.search(r"System arrives <TEACH-AIR-01,(\d+)>", line).group(1) for _, line in arrivals]
    checks.eq("events", "two h10 arrivals", len(arrivals), 2)
    checks.eq("events", "arrival IDs", set(arrival_ids), set(allocated))
    checks.eq("events", "arrivals h10", all(at(10, line) for _, line in arrivals), True)
    ready_end = matches(r"^Time: 10 <TEACH-UNIT at <BASE-01,0>> systems ready: 3 :")
    checks.eq("events", "one terminal ready-three snapshot", len(ready_end), 1)
    if ready_end:
        checks.eq("events", "terminal three IDs", set(AIRCRAFT.findall(ready_end[0][1])), deployed)
        checks.eq("events", "terminal IDs distinct", len(AIRCRAFT.findall(ready_end[0][1])), 3)
    for label, pattern in (
        ("second mission", r" mission created:"),
        ("waiting", r" mission waiting:"),
        ("cancellation", r" mission cancelled:"),
        ("failure", r"failure occurs|system failure"),
        ("maintenance", r"PM task starting|Repair task starting"),
        ("stock movement", r"backorder|Delivery|stock issued|item issued|transport started"),
    ):
        found = matches(pattern)
        checks.eq("events", f"{label} count", len(found), 1 if label == "second mission" else 0)
    return deployed, set(allocated)


def report_gate(checks: Checks, child: Path):
    report = table_map(native_json(child), "report")
    parent = table_map(native_json(PARENT_RUN / "report-raw.json"), "report")
    checks.eq("report", "four table names/order", list(report), list(parent))
    sf, sr = table_rows(report["SystemResults"])
    pf, pr = table_rows(parent["SystemResults"])
    checks.eq("report", "System field names", sf, pf)
    checks.eq("report", "40 System fields", len(sf), 40)
    checks.eq("report", "72 System rows", len(sr), 72)
    checks.eq("report", "72 parent System rows", len(pr), 72)
    for index, (row, prior) in enumerate(zip(sr, pr)):
        checks.near("report", f"System[{index}].STINT", row["STINT"], index / 2)
        checks.near("report", f"System[{index}].ETINT", row["ETINT"], (index + 1) / 2)
        for field in sf:
            if field in ("NSYA", "NSYRY"):
                checks.near("report", f"System[{index}].{field}+1", row[field], prior[field] + 1)
            elif field == "FTMO":
                checks.near("report", f"System[{index}].FTMO", row[field], 2 / 3 if 16 <= index < 20 else 0)
            else:
                checks.eq("report", f"System[{index}].{field}", row[field], prior[field])
    for field, expected in (("NSYRY", 102), ("NSYMR", 2), ("NSYMO", 4), ("NSYA", 108)):
        checks.near("report", f"{field} integral", sum(row[field] * 0.5 for row in sr), expected)
    checks.eq("report", "terminal three ready", sr[-1]["NSYRY"], 3)
    stock_fields, stock = table_rows(report["StockTotalResults"])
    old_fields, old_stock = table_rows(parent["StockTotalResults"])
    checks.eq("report", "Stock columns", stock_fields, old_fields)
    checks.eq("report", "16 Stock fields", len(stock_fields), 16)
    checks.eq("report", "72 Stock rows", len(stock), 72)
    for index, (new, prior) in enumerate(zip(stock, old_stock)):
        for field in stock_fields:
            checks.eq("report", f"Stock[{index}].{field}", new[field], prior[field])
    summary_fields, summary = table_rows(report["ResultSummary"])
    parent_summary_fields, parent_summary = table_rows(parent["ResultSummary"])
    checks.eq("report", "11 summary fields", len(summary_fields), 11)
    checks.eq("report", "summary field names", summary_fields, parent_summary_fields)
    checks.eq("report", "one summary row", len(summary), 1)
    for field in summary_fields:
        checks.eq("report", f"Summary.{field}", summary[0][field], parent_summary[0][field])
    for field in ("NREP", "MTMF", "MSTF", "MSUF", "STMF"):
        checks.eq("report", f"summary target {field}", summary[0][field], 1)
    pd_fields, pd_rows = table_rows(report["ProblemDescription"])
    old_pd_fields, old_pd_rows = table_rows(parent["ProblemDescription"])
    checks.eq("report", "description columns", pd_fields, old_pd_fields)
    checks.eq("report", "description rows", pd_rows, old_pd_rows)


def validate() -> dict:
    checks = Checks()
    try:
        contract = native_json(HERE / "contract.json")
        source_gate(checks, contract)
        closure = native_json(RUN / "closure.json")
        invocation = native_json(RUN / "invocation.json")
        steps = native_json(RUN / "steps.json")
        checks.eq("closure", "run ID", closure["run_id"], RUN_ID)
        checks.eq("closure", "no runner error", closure.get("error"), None)
        checks.eq("closure", "invocation SHA", sha(RUN / "invocation.json"), closure["invocation_sha256"])
        checks.eq("closure", "stable sources", closure["source_hashes_before"], closure["source_hashes_after"])
        checks.eq("closure", "invocation source map", invocation["source_hashes_before"], closure["source_hashes_before"])
        checks.eq("closure", "exact raw set", set(closure["raw"]), {
            "input.json", "import.log", "model.sxi", "export.log",
            "roundtrip-raw.json", "roundtrip-validation.json", "run.log",
            "model.sxo", "model.log", "report-export.log", "report-raw.json",
            "steps.json",
        })
        checks.eq("closure", "no failure seal", (RUN / "failure-seal.json").exists(), False)
        for name, seal in sorted(closure["raw"].items()):
            path = RUN / name
            checks.eq("child_raw", f"{name} SHA", sha(path), seal["sha256"])
            checks.eq("child_raw", f"{name} bytes", path.stat().st_size, seal["bytes"])
        known = source_paths()
        checks.eq("source_seal", "exact reviewed source labels",
                  set(closure["source_hashes_before"]), set(known))
        for label, path in sorted(known.items()):
            checks.eq("source_seal", f"{label} present", label in closure["source_hashes_before"], True)
            if label in closure["source_hashes_before"]:
                checks.eq("source_seal", f"{label} SHA", closure["source_hashes_before"][label], sha(path))
        checks.eq("closure", "copied input", sha(RUN / "input.json"), INPUT_SHA)
        checks.eq("closure", "invocation input", invocation["input_sha256"], INPUT_SHA)
        checks.eq("closure", "invocation contract", invocation["contract_sha256"], CONTRACT_SHA)
        checks.eq("closure", "runner identity", invocation["runner_script_sha256"],
                  closure["source_hashes_before"]["runner_script"])
        if "validator_sha256" in invocation:
            checks.eq("closure", "invocation validator", invocation["validator_sha256"],
                      sha(HERE / "validate_native_cli.py"))
        checks.eq("guard", "SSH session", invocation["session_id"], 0)
        checks.eq("guard", "SSH connection", invocation["ssh_connection_present"], True)
        checks.eq("guard", "sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
        checks.eq("guard", "queue mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
        gui = invocation.get("gui", invocation.get("coexisting_gui", {}))
        checks.eq("guard", "GUI PID", gui.get("pid"), 13340)
        checks.eq("guard", "GUI session", gui.get("session_id"), 1)
        checks.eq("guard", "GUI start", gui.get("start_unix_ms", gui.get("process_start_utc")),
                  1790590196826 if "start_unix_ms" in gui else "2026-09-28T10:09:56.8261381Z")
        checks.eq("guard", "five ordered steps", [s["name"] for s in steps],
                  ["import", "export", "check_import_export", "calc", "jsonreport"])
        for index, step in enumerate(steps):
            checks.eq("guard", f"step {index} exit", step["exit_code"], 0)
            checks.eq("guard", f"step {index} complete", step.get("status", "completed"), "completed")
            checks.eq("guard", f"step {index} GUI", step.get("gui_preserved", step.get("coexisting_gui_present_after")), True)

        authored = table_map(native_json(RUN / "input.json"), "model")
        exported = table_map(native_json(RUN / "roundtrip-raw.json"), "model")
        row_tables = [name for name, table in authored.items() if any(i["rows"] for i in table["instances"])]
        checks.eq("roundtrip", "13 authored row tables", len(row_tables), 13)
        for name in row_tables:
            checks.eq("roundtrip", f"{name} columns", exported[name]["columns"], authored[name]["columns"])
            checks.eq("roundtrip", f"{name} instances", exported[name]["instances"], authored[name]["instances"])
        if (RUN / "roundtrip-validation.json").exists():
            check = native_json(RUN / "roundtrip-validation.json")
            checks.eq("roundtrip", "checker pass", check["passed"], True)

        converter = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        checks.eq("converter", "exact 0/2/0", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter, True)
        checks.eq("converter", "warnings #108/#126", sorted(re.findall(r"\(warning #(\d+)\)", converter)), ["108", "126"])
        checks.eq("converter", "no error", re.findall(r"\(error #(\d+)\)", converter), [])
        checks.eq("converter", "no notice", re.findall(r"\(notice #(\d+)\)", converter), [])
        checks.eq("converter", "valid SXO", (RUN / "model.sxo").stat().st_size > 4, True)

        event_gate(checks, RUN / "model.log")
        report_gate(checks, RUN / "report-raw.json")
    except Exception as exc:
        checks.failures.append(f"validator exception: {type(exc).__name__}: {exc}")
    return {
        "schema": "simlox-a03-var01-three-available-author-validation/v1",
        "run_id": RUN_ID,
        "contract_sha256": CONTRACT_SHA,
        "input_sha256": INPUT_SHA,
        "decision": "GO_BOUNDED" if not checks.failures else "NO_GO",
        "passed": not checks.failures,
        "checks": checks.count,
        "categories": dict(sorted(checks.groups.items())),
        "failures": checks.failures,
        "scope": "one fixed-seed three-available/two-required scheduled mission, 36-hour CLI run",
        "limits": [
            "No selected pair is assumed in advance; only distinct physical IDs and their conservation are tested.",
            "FTMO=2/3 during flight is an analytic prediction for this three-system denominator.",
            "No larger fleet, alternative priority, GUI visual, cross-engine or full Issue18 claim.",
        ],
    }


def self_check() -> dict:
    checks = Checks()
    try:
        contract = native_json(HERE / "contract.json")
        source_gate(checks, contract)
        parent = table_map(native_json(PARENT_RUN / "report-raw.json"), "report")
        checks.eq("parent_report", "four tables", list(parent),
                  ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"])
        checks.eq("parent_report", "72 System rows", len(table_rows(parent["SystemResults"])[1]), 72)
        checks.eq("parent_report", "40 System fields", len(table_rows(parent["SystemResults"])[0]), 40)
        checks.eq("parent_report", "72 Stock rows", len(table_rows(parent["StockTotalResults"])[1]), 72)
        checks.eq("parent_report", "16 Stock fields", len(table_rows(parent["StockTotalResults"])[0]), 16)
        checks.eq("parent_report", "11 Summary fields", len(table_rows(parent["ResultSummary"])[0]), 11)
        checks.eq("run absent", "run exists", RUN.exists(), False)
    except Exception as exc:
        checks.failures.append(f"self-check exception: {type(exc).__name__}: {exc}")
    return {"schema": "simlox-a03-var01-three-available-self-check/v1",
            "decision": "GO_STATIC" if not checks.failures else "NO_GO",
            "checks": checks.count, "failures": checks.failures}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true", help="check frozen source and parent only")
    args = parser.parse_args()
    result = self_check() if args.self_check else validate()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(0 if result["decision"] in ("GO_STATIC", "GO_BOUNDED") else 1)
