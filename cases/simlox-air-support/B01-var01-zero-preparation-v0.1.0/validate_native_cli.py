"""Frozen read-only native behavior gate for B01.var01 zero preparation.

This script reads the accepted B01 control and one immutable child run. It does
not create a run, invoke SIMLOX, or alter a native report's original bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parent
ROOT = CASE.parent
PARENT = ROOT / "B01-fixed-preparation-v1.0.1"
PARENT_RUN = Path(
    "C:/Users/user/dev/sim_engine_compiler-b01-v101/cases/simlox-air-support/"
    "B01-fixed-preparation-v1.0.1/runs/b01-v101-ssh-20260929-06"
)
A01 = ROOT / "A01-single-aircraft-single-mission"
A01_RAW_ROOT = Path(
    "C:/Users/user/Documents/Codex/2026-09-27/"
    "simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1/A01"
)
A01_RUNS = ("a01-bound-final-20260927-03", "a01-bound-replay-20260927-04")
RUN_ID = "b01-var01-zero-prep-v010-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
CONTRACT_SHA = "57fdc32138535c4982e50265c0a57e8e72b79ced8c3710c6ea00df861ef42399"
INPUT_SHA = "5e2d473cdd617955e2920da0a473854a7576a041aa2653e65397dfc1746f1aee"
MISSION = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
AIRCRAFT = "<TEACH-AIR-01,0>"
EXPECTED_RAW = {
    "input.json", "import.log", "model.sxi", "export.log", "roundtrip-raw.json",
    "roundtrip-validation.json", "run.log", "model.sxo", "model.log",
    "report-export.log", "report-raw.json", "steps.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    """Parse native trailing commas from an in-memory copy only."""
    content = path.read_text(encoding="utf-8-sig")
    result = []
    quoted = escaped = False
    for index, char in enumerate(content):
        if quoted:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            result.append(char)
        elif char == ",":
            following = index + 1
            while following < len(content) and content[following].isspace():
                following += 1
            if following == len(content) or content[following] not in "]}":
                result.append(char)
        else:
            result.append(char)
    return json.loads("".join(result))


def table_map(document: dict, section: str) -> dict[str, dict]:
    entries = document[section]["tables"]
    result = {entry["name"]: entry for entry in entries}
    if len(result) != len(entries):
        raise ValueError(f"duplicate {section} table")
    return result


def grid(table: dict):
    fields = [field["name"] for field in table["columns"]]
    if len(fields) != len(set(fields)):
        raise ValueError("duplicate column")
    rows = []
    for instance in table["instances"]:
        for values in instance["rows"]:
            if len(values) != len(fields):
                raise ValueError("nonrectangular table")
            rows.append(dict(zip(fields, values)))
    return fields, rows


def cells(document: dict):
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


class Audit:
    def __init__(self):
        self.count = 0
        self.failures: list[str] = []
        self.categories: dict[str, int] = {}

    def equal(self, group: str, label: str, actual, expected):
        self.count += 1
        self.categories[group] = self.categories.get(group, 0) + 1
        if actual != expected:
            self.failures.append(f"{group}/{label}: {actual!r} != {expected!r}")

    def near(self, group: str, label: str, actual, expected: float, tolerance=1e-6):
        good = isinstance(actual, (int, float)) and not isinstance(actual, bool)
        self.equal(group, label, good and abs(actual - expected) <= tolerance, True)


def verify_raw(audit: Audit, folder: Path, closure: dict, count: int, group: str):
    audit.equal(group, "raw count", len(closure["raw"]), count)
    for name, seal in sorted(closure["raw"].items()):
        path = folder / name
        audit.equal(group, f"{name} bytes", path.stat().st_size, seal["bytes"])
        audit.equal(group, f"{name} SHA", sha(path), seal["sha256"])


def verify_a01_raw(audit: Audit):
    index = read_json(A01 / "evidence-index.json")
    audit.equal("a01_raw", "two indexed runs", len(index["runs"]), 2)
    for entry, run_id in zip(index["runs"], A01_RUNS):
        audit.equal("a01_raw", f"{run_id} identity", entry["run_id"], run_id)
        audit.equal("a01_raw", f"{run_id} artifact count", len(entry["artifacts"]), 17)
        audit.equal("a01_raw", f"{run_id} directory", Path(entry["directory"]), A01_RAW_ROOT / run_id)
        for name, seal in sorted(entry["artifacts"].items()):
            path = A01_RAW_ROOT / run_id / name
            audit.equal("a01_raw", f"{run_id}/{name} bytes", path.stat().st_size, seal["bytes"])
            audit.equal("a01_raw", f"{run_id}/{name} SHA", sha(path), seal["sha256"])


def source_gate(audit: Audit, contract: dict):
    audit.equal("source", "contract SHA", sha(CASE / "contract.json"), CONTRACT_SHA)
    audit.equal("source", "input SHA", sha(CASE / "native-input.json"), INPUT_SHA)
    audit.equal("source", "run reservation", contract["ownership"]["native_run_id_reserved"], RUN_ID)
    parent = contract["accepted_parent"]
    for key, path in {
        "input_sha256": PARENT / "native-input.json",
        "contract_sha256": PARENT / "contract.json",
        "publication_sha256": PARENT / "evidence-2026-09-29.md",
        "independent_review_sha256": PARENT / "review/independent-readonly-rerun-2026-09-29.json",
        "closure_sha256": PARENT_RUN / "closure.json",
    }.items():
        audit.equal("parent", key, sha(path), parent[key])
    prior_closure = read_json(PARENT_RUN / "closure.json")
    audit.equal("parent", "run ID", prior_closure["run_id"], parent["run_id"])
    audit.equal("parent", "input SHA", prior_closure["input_sha256"], parent["input_sha256"])
    verify_raw(audit, PARENT_RUN, prior_closure, 11, "parent_raw")
    prerequisite = contract["instructional_prerequisite"]
    audit.equal("prerequisite", "A01 input", sha(A01 / "native-input.json"), prerequisite["input_sha256"])
    audit.equal("prerequisite", "A01 signoff", sha(A01 / "cli-scope-signoff-2026-09-29.md"),
                prerequisite["signoff_sha256"])
    verify_a01_raw(audit)
    audit.equal("manual", "installed PDF", sha(Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf")),
                contract["manual"]["installed_pdf_sha256"])
    old = read_json(PARENT / "native-input.json")
    new = read_json(CASE / "native-input.json")
    old_tables, new_tables = table_map(old, "model"), table_map(new, "model")
    audit.equal("model", "table names/order", list(new_tables), list(old_tables))
    audit.equal("model", "31 tables", len(new_tables), 31)
    before, after = cells(old), cells(new)
    audit.equal("model", "167 cells", len(before), 167)
    audit.equal("model", "same positional keys", list(after), list(before))
    audit.equal("model", "sole DURN delta",
                {key: (before[key], after[key]) for key in before if before[key] != after[key]},
                {("MissionPreparation", 0, 0, "DURN"): (0.5, 0)})
    for name in old_tables:
        audit.equal("model", f"{name} columns", new_tables[name]["columns"], old_tables[name]["columns"])
        audit.equal("model", f"{name} instance labels",
                    [x["instance_name"] for x in new_tables[name]["instances"]],
                    [x["instance_name"] for x in old_tables[name]["instances"]])
    prep = grid(new_tables["MissionPreparation"])[1]
    tasks = grid(new_tables["Tasks"])[1]
    audit.equal("model", "zero-duration linked row",
                (len(prep), prep[0]["MTID"], prep[0]["SID"], prep[0]["STID"],
                 prep[0]["DURN"], prep[0]["TID"]),
                (1, "BASIC-MISSION", "TEACH-AIR-01", "BASE-01", 0, "PREP-FIXED"))
    audit.equal("model", "retained task row", (len(tasks), tasks[0]["TID"]), (1, "PREP-FIXED"))
    return old_tables, new_tables


def provenance_gate(audit: Audit):
    closure = read_json(RUN / "closure.json")
    invocation = read_json(RUN / "invocation.json")
    stages = read_json(RUN / "steps.json")
    audit.equal("run", "run ID", closure["run_id"], RUN_ID)
    audit.equal("run", "no closure error", closure.get("error"), None)
    audit.equal("run", "invocation seal", sha(RUN / "invocation.json"), closure["invocation_sha256"])
    audit.equal("run", "source stable", closure["source_hashes_before"], closure["source_hashes_after"])
    audit.equal("run", "invocation sources", invocation["source_hashes_before"], closure["source_hashes_before"])
    audit.equal("run", "raw names", set(closure["raw"]), EXPECTED_RAW)
    audit.equal("run", "no failure seal", (RUN / "failure-seal.json").exists(), False)
    verify_raw(audit, RUN, closure, 12, "child_raw")
    audit.equal("run", "frozen copied input", sha(RUN / "input.json"), INPUT_SHA)
    audit.equal("run", "invocation input", invocation["input_sha256"], INPUT_SHA)
    audit.equal("run", "invocation contract", invocation["contract_sha256"], CONTRACT_SHA)
    audit.equal("guard", "SSH session", invocation["session_id"], 0)
    audit.equal("guard", "SSH connection", invocation["ssh_connection_present"], True)
    audit.equal("guard", "sshd ancestry", "sshd.exe" in invocation["ssh_ancestor_names"], True)
    audit.equal("guard", "global mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
    gui = invocation["gui"]
    audit.equal("guard", "protected GUI PID/session/start",
                (gui["pid"], gui["session_id"], gui["start_unix_ms"]), (13340, 1, 1790590196826))
    audit.equal("guard", "stage sequence", [step["name"] for step in stages],
                ["import", "export", "check_import_export", "calc", "jsonreport"])
    for number, step in enumerate(stages):
        audit.equal("guard", f"stage {number} exit", step["exit_code"], 0)
        audit.equal("guard", f"stage {number} complete", step["status"], "completed")
        audit.equal("guard", f"stage {number} GUI", step["gui_preserved"], True)
    source_paths = {
        "child_input": CASE / "native-input.json", "child_contract": CASE / "contract.json",
        "contract_review": CASE / "review/independent-contract-go-2026-10-06.md",
        "builder": CASE / "build.py", "parent_diff_checker": CASE / "check_parent_diff.py",
        "roundtrip_checker": CASE / "check_roundtrip.py", "shared_parser": ROOT / "tools/validate_native.py",
        "behavior_validator": CASE / "validate_native_cli.py", "runner_script": CASE / "run_native_ssh.ps1",
        "accepted_input": PARENT / "native-input.json", "accepted_contract": PARENT / "contract.json",
        "accepted_diff": PARENT / "parent-diff.json",
        "accepted_evidence": PARENT / "evidence-2026-09-29.md",
        "accepted_verdict": PARENT / "review/independent-readonly-rerun-2026-09-29.json",
        "accepted_closure": PARENT_RUN / "closure.json",
        "prereq_input": A01 / "native-input.json",
        "prereq_contract": A01 / "contract.json",
        "prereq_signoff": A01 / "cli-scope-signoff-2026-09-29.md",
        "prereq_index": A01 / "evidence-index.json",
        "prereq_final_closure": A01_RAW_ROOT / A01_RUNS[0] / "closure.json",
        "prereq_replay_closure": A01_RAW_ROOT / A01_RUNS[1] / "closure.json",
        "installed_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
        "installed_manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "installed_dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
        "python": Path(sys.executable),
        "prelaunch_approval": CASE / "review/independent-prelaunch-go.json",
    }
    for label, path in sorted(source_paths.items()):
        audit.equal("source_seal", f"{label} present", label in closure["source_hashes_before"], True)
        if label in closure["source_hashes_before"]:
            audit.equal("source_seal", label, closure["source_hashes_before"][label], sha(path))
    audit.equal("source_seal", "all source labels reviewed", set(closure["source_hashes_before"]),
                set(source_paths))


def roundtrip_and_converter(audit: Audit):
    authored = table_map(read_json(RUN / "input.json"), "model")
    returned = table_map(read_json(RUN / "roundtrip-raw.json"), "model")
    populated = [name for name, table in authored.items() if any(x["rows"] for x in table["instances"])]
    audit.equal("roundtrip", "15 row-containing tables", len(populated), 15)
    for name in populated:
        audit.equal("roundtrip", f"{name} columns", returned[name]["columns"], authored[name]["columns"])
        audit.equal("roundtrip", f"{name} instances", returned[name]["instances"], authored[name]["instances"])
    audit.equal("roundtrip", "checker passed", read_json(RUN / "roundtrip-validation.json")["passed"], True)
    log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    audit.equal("converter", "0/2/0 summary",
                "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log, True)
    audit.equal("converter", "only warnings 108/126", sorted(re.findall(r"\(warning #(\d+)\)", log)),
                ["108", "126"])
    audit.equal("converter", "no errors", re.findall(r"\(error #(\d+)\)", log), [])
    audit.equal("converter", "substantive SXO", (RUN / "model.sxo").stat().st_size > 4, True)


def event_gate(audit: Audit):
    lines = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    audit.equal("event", "36-hour log", lines[:2], ["SIMLOX LOG FILE", "36"])

    def matching(pattern: str):
        return [line for line in lines if re.search(pattern, line)]

    def at(hour: float, line: str):
        match = re.match(r"Time: (\d+(?:\.\d+)?)\s", line)
        return match is not None and abs(float(match.group(1)) - hour) < 1e-4

    def one(label: str, pattern: str, hour: float, aircraft=True):
        found = matching(pattern)
        audit.equal("event", f"one {label}", len(found), 1)
        if found:
            audit.equal("event", f"{label} at h{hour}", at(hour, found[0]), True)
            if aircraft:
                audit.equal("event", f"{label} on ID0", AIRCRAFT in found[0], True)
        return found

    one("h0 ready", r"^Time: 0 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>$", 0)
    one("notice", r"mission ordered: BASIC-MISSION", 7, aircraft=False)
    one("mission creation", re.escape(MISSION) + r" mission created:", 7, aircraft=False)
    one("one-aircraft demand", re.escape(MISSION) + r" mission activated, systems requested: 1", 7,
        aircraft=False)
    one("physical allocation", re.escape(MISSION) + r" mission allocates system: <TEACH-AIR-01,0>", 7)
    one("preparation start", re.escape(AIRCRAFT) + r" preparation started, mission:", 7)
    one("system preparation task start",
        r"^Time: 7  system preparation task 0 on <TEACH-AIR-01,0> started$", 7)
    one("subtask start",
        r"subtask 0 seqno 0 within system preparation task 0 on <TEACH-AIR-01,0> started$", 7)
    one("zero-hour work", r"subtask 0 seqno 0 within system preparation task 0 on "
        r"<TEACH-AIR-01,0> starts performing, planned to last for 0 hours$", 7)
    one("subtask complete",
        r"subtask 0 seqno 0 within system preparation task 0 on <TEACH-AIR-01,0> completed$", 7)
    one("system preparation task complete",
        r"^Time: 7  system preparation task 0 on <TEACH-AIR-01,0> completed$", 7)
    one("preparation end", re.escape(AIRCRAFT) + r" preparation ended, mission:", 7)
    one("h8 launch", re.escape(MISSION) + r" mission starting, duration: 2 : <TEACH-AIR-01,0>$", 8)
    one("h8.5 task", re.escape(MISSION) + r" task starting: <TEACH-AIR-01,0>$", 8.5)
    one("h9.5 task completion", re.escape(MISSION) + r" task completed: <TEACH-AIR-01,0>$", 9.5)
    one("h10 mission success", re.escape(MISSION) + r" mission success:", 10, aircraft=False)
    one("h10 mission completion", re.escape(MISSION) + r" mission completed: <TEACH-AIR-01,0>$", 10)
    one("h10 physical return", r"System arrives <TEACH-AIR-01,0>, mission success", 10)
    one("h10 ready", r"^Time: 10 <TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>$", 10)
    for label, pattern in (
        ("extra preparation", r"preparation started, mission:|preparation ended, mission:"),
        ("extra system task", r"^Time: \d+(?:\.\d+)?  system preparation task "
         r"\d+ on <TEACH-AIR-01,\d+> (?:started|completed)$"),
        ("extra subtask", r"^Time: \d+(?:\.\d+)?  subtask \d+ seqno \d+ within "
         r"system preparation task \d+ on <TEACH-AIR-01,\d+> (?:started|completed)$"),
    ):
        audit.equal("event", f"{label} lifecycle count", len(matching(pattern)), 2)
    audit.equal("event", "one work interval", len(matching(r"starts performing, planned to last for")), 1)
    for label, pattern in (
        ("resource wait", r"waiting for resource|resource wait"),
        ("cancel", r"mission cancelled|mission aborted"),
        ("fault", r"failure occurs|system failure"),
        ("stock demand", r"backorder|stock issued|item issued"),
        ("positive preparation work", r"planned to last for (?!0(?:\.0*)? hours)\d"),
    ):
        audit.equal("event", f"no {label}", len(matching(pattern)), 0)


def report_gate(audit: Audit):
    current = table_map(read_json(RUN / "report-raw.json"), "report")
    parent = table_map(read_json(PARENT_RUN / "report-raw.json"), "report")
    audit.equal("report", "table order", list(current), list(parent))
    fields, rows = grid(current["SystemResults"])
    prior_fields, previous = grid(parent["SystemResults"])
    audit.equal("report", "72x40 System", (len(rows), len(fields)), (72, 40))
    audit.equal("report", "System fields", fields, prior_fields)
    exceptions = {(14, "NSYMP"): (1, 0), (14, "NSYMR"): (0, 1),
                  (14, "NPSUC"): (0, 1), (15, "NPSUC"): (1, 0)}
    for number, (row, prior) in enumerate(zip(rows, previous)):
        audit.near("system", f"{number}.STINT", row["STINT"], number / 2)
        audit.near("system", f"{number}.ETINT", row["ETINT"], (number + 1) / 2)
        for field in fields:
            before, after = exceptions.get((number, field), (prior[field], prior[field]))
            if (number, field) in exceptions:
                audit.equal("system", f"{number}.{field} parent", prior[field], before)
            audit.equal("system", f"{number}.{field}", row[field], after)
    for field, expected in (("NSYMP", 0), ("NSYMR", 1), ("NSYMO", 2), ("NSYRY", 33)):
        audit.near("report", f"{field} aircraft-hour integral",
                   sum(row[field] * 0.5 for row in rows), expected)
    for field, expected in (("NPSTA", 1), ("NPSUC", 1)):
        audit.equal("report", f"{field} count", sum(row[field] for row in rows), expected)
    audit.equal("report", "terminal ready", rows[-1]["NSYRY"], 1)
    stock_fields, stock = grid(current["StockTotalResults"])
    old_stock_fields, old_stock = grid(parent["StockTotalResults"])
    audit.equal("report", "72x16 Stock", (len(stock), len(stock_fields)), (72, 16))
    audit.equal("report", "Stock fields", stock_fields, old_stock_fields)
    for number in range(72):
        for field in stock_fields:
            audit.equal("stock", f"{number}.{field}", stock[number][field], old_stock[number][field])
    summary_fields, summary = grid(current["ResultSummary"])
    old_summary_fields, old_summary = grid(parent["ResultSummary"])
    audit.equal("report", "11 summary fields and one row", (len(summary_fields), len(summary)), (11, 1))
    audit.equal("report", "summary fields", summary_fields, old_summary_fields)
    for field in summary_fields:
        audit.equal("summary", field, summary[0][field], old_summary[0][field])
    for field in ("NREP", "MTMF", "MSTF", "MSUF", "STMF"):
        audit.equal("summary", f"{field}=1", summary[0][field], 1)
    audit.equal("report", "description columns", current["ProblemDescription"]["columns"],
                parent["ProblemDescription"]["columns"])
    audit.equal("report", "description instances", current["ProblemDescription"]["instances"],
                parent["ProblemDescription"]["instances"])


def result(audit: Audit, schema: str):
    return {
        "schema": schema, "run_id": RUN_ID, "contract_sha256": CONTRACT_SHA,
        "input_sha256": INPUT_SHA,
        "decision": "GO_STATIC" if schema.endswith("self-check/v1") and not audit.failures else
                    "GO_BOUNDED" if not audit.failures else "NO_GO",
        "passed": not audit.failures, "checks": audit.count,
        "categories": dict(sorted(audit.categories.items())), "failures": audit.failures,
        "scope": "one fixed-seed zero-duration PREP-FIXED mission-preparation row",
        "limits": [
            "Only this linked zero-duration row and one deterministic 36-hour mission are exercised.",
            "The retained Tasks.DESCR text '30-minute' is stale; native duration is established by DURN and the event log.",
            "No generalized zero-duration, resource, alternate seed, GUI-visual or full Issue18 claim.",
        ],
    }


def self_check():
    audit = Audit()
    try:
        contract = read_json(CASE / "contract.json")
        source_gate(audit, contract)
        report = table_map(read_json(PARENT_RUN / "report-raw.json"), "report")
        fields, rows = grid(report["SystemResults"])
        audit.equal("parent_report", "72x40 System", (len(rows), len(fields)), (72, 40))
        for index, field, expected in ((14, "NSYMP", 1), (14, "NSYMR", 0),
                                       (14, "NPSUC", 0), (15, "NPSUC", 1)):
            audit.equal("parent_report", f"{index}.{field}", rows[index][field], expected)
        audit.equal("parent_report", "72x16 Stock",
                    (len(grid(report["StockTotalResults"])[1]),
                     len(grid(report["StockTotalResults"])[0])), (72, 16))
        audit.equal("parent_report", "11 summary fields", len(grid(report["ResultSummary"])[0]), 11)
        audit.equal("run", "new run absent", RUN.exists(), False)
    except Exception as exc:
        audit.failures.append(f"self-check exception: {type(exc).__name__}: {exc}")
    return result(audit, "simlox-b01-var01-zero-preparation-self-check/v1")


def validate():
    audit = Audit()
    try:
        contract = read_json(CASE / "contract.json")
        source_gate(audit, contract)
        provenance_gate(audit)
        roundtrip_and_converter(audit)
        event_gate(audit)
        report_gate(audit)
    except Exception as exc:
        audit.failures.append(f"validator exception: {type(exc).__name__}: {exc}")
    return result(audit, "simlox-b01-var01-zero-preparation-author-validation/v1")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    output = self_check() if args.self_check else validate()
    print(json.dumps(output, indent=2, ensure_ascii=False))
    raise SystemExit(0 if output["passed"] else 1)
