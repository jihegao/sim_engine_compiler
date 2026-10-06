"""Read-only B01.var03 explicit task-route and full-ledger native gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "B03-explicit-cold-hot-v1.0.2"
PARENT_RUN = Path(
    "C:/Users/user/dev/sim_engine_compiler-b03-v102/cases/simlox-air-support/"
    "B03-explicit-cold-hot-v1.0.2/runs/b03-v102-ssh-20260929-02"
)
PREVIOUS = ROOT / "B01-var03-task-route-v0.1.0"
A02 = ROOT / "A02-single-aircraft-repeated-missions"
RUN_ID = "b01-var03-task-route-v011-ssh-20261006-01"
RUN = HERE / "runs" / RUN_ID
INPUT_SHA = "0cdb2bb68dcd49197988caba76b8d41e700b774139da98f33296c74c0d0d3c7b"
CONTRACT_SHA = "c06ef07a090403ca77f04189f49251bffec3c79cff5e77d5ae19cad10df426bc"
RAW = {
    "input.json", "import.log", "model.sxi", "export.log", "roundtrip-raw.json",
    "roundtrip-validation.json", "run.log", "model.sxo", "model.log",
    "report-export.log", "report-raw.json", "steps.json",
}
OWNER = "<TEACH-AIR-01,0>"
TIMED = re.compile(r"^Time:\s*([\d.eE+\-]+)\s+(.*)$", re.M)

sys.path.insert(0, str(ROOT / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(remove_trailing_commas(path.read_bytes()))


def table_map(doc: dict, section: str) -> dict:
    tables = doc[section]["tables"]
    result = {table["name"]: table for table in tables}
    if len(result) != len(tables):
        raise ValueError(f"duplicate {section} table")
    return result


def grid(table: dict):
    fields = [column["name"] for column in table["columns"]]
    if len(fields) != len(set(fields)):
        raise ValueError("duplicate table field")
    rows = []
    for instance in table["instances"]:
        for row in instance["rows"]:
            if len(row) != len(fields):
                raise ValueError("nonrectangular row")
            rows.append(dict(zip(fields, row, strict=True)))
    return fields, rows


class Audit:
    def __init__(self):
        self.count = 0
        self.failures = []
        self.categories = {}

    def equal(self, group: str, label: str, actual, expected):
        self.count += 1
        self.categories[group] = self.categories.get(group, 0) + 1
        if actual != expected:
            self.failures.append(f"{group}/{label}: {actual!r} != {expected!r}")

    def near(self, group: str, label: str, actual, expected, tolerance=1e-5):
        good = isinstance(actual, (int, float)) and not isinstance(actual, bool)
        self.equal(group, label, good and abs(actual - expected) <= tolerance, True)


def verify_raw(audit: Audit, folder: Path, closure: dict, expected: int, group: str):
    audit.equal(group, "raw count", len(closure["raw"]), expected)
    for name, seal in sorted(closure["raw"].items()):
        file = folder / name
        audit.equal(group, f"{name} bytes", file.stat().st_size, seal["bytes"])
        audit.equal(group, f"{name} SHA", sha(file), seal["sha256"])


def source_gate(audit: Audit):
    audit.equal("source", "input SHA", sha(HERE / "native-input.json"), INPUT_SHA)
    audit.equal("source", "contract SHA", sha(HERE / "contract.json"), CONTRACT_SHA)
    contract = read_json(HERE / "contract.json")
    audit.equal("source", "run reservation", contract["ownership"]["native_run_id_reserved"], RUN_ID)
    parent = contract["accepted_parent"]
    for key, path in {
        "input_sha256": PARENT / "native-input.json",
        "contract_sha256": PARENT / "contract.json",
        "closure_sha256": PARENT_RUN / "closure.json",
    }.items():
        audit.equal("parent", key, sha(path), parent[key])
    audit.equal("parent", "accepted run ID", parent["accepted_run_id"], "b03-v102-ssh-20260929-02")
    old_closure = read_json(PARENT_RUN / "closure.json")
    audit.equal("parent", "closure run ID", old_closure["run_id"], parent["accepted_run_id"])
    audit.equal("parent", "closure input", old_closure["input_sha256"], parent["input_sha256"])
    verify_raw(audit, PARENT_RUN, old_closure, 11, "parent_raw")
    audit.equal("prerequisite", "A02 signed scope",
                sha(A02 / "cli-scope-signoff-2026-09-29.md"),
                contract["instructional_prerequisite"]["signed_scope_sha256"])
    audit.equal("history", "preserved NO_GO contract", sha(PREVIOUS / "contract.json"),
                "0432b529385d20f26d93ca7d75545e8d2490050a94b61286334cd68a52385ca9")
    audit.equal("history", "NO_GO independent review",
                sha(PREVIOUS / "review/independent-contract-nogo-2026-10-06.md"),
                "c4bd04d5132e126f7ee79fa1d1b8c4562e004b336395876744a6020109124ca7")
    audit.equal("review", "corrected contract GO",
                sha(HERE / "review/independent-contract-go-2026-10-06.md"),
                "78843be6fbde1f8e9dc4388ad5bf0fa5595daf19cd6e389493fdc85f64bca0df")
    audit.equal("manual", "installed PDF",
                sha(Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf")),
                contract["manual"]["installed_pdf_sha256"])
    old, new = read_json(PARENT / "native-input.json"), read_json(HERE / "native-input.json")
    audit.equal("model", "only exact byte replacement",
                (PARENT / "native-input.json").read_bytes().replace(
                    b'"COLD-FIRST",\n                8.0,',
                    b'"HOT-SORTIE",\n                8.0,'),
                (HERE / "native-input.json").read_bytes())
    before, after = table_map(old, "model"), table_map(new, "model")
    audit.equal("model", "table names/order", list(after), list(before))
    audit.equal("model", "table count", len(after), 31)
    for name in before:
        audit.equal("model", f"{name} columns", after[name]["columns"], before[name]["columns"])
    profile = grid(after["OperationProfile"])[1]
    audit.equal("model", "three hot profile rows",
                [(row["SPRID"], row["STIM"]) for row in profile],
                [("HOT-SORTIE", 8.0), ("HOT-SORTIE", 12.0), ("HOT-SORTIE", 16.0)])
    audit.equal("model", "cold and hot recipes retained",
                after["MissionPreparation"], before["MissionPreparation"])
    audit.equal("model", "cold and hot breakdown retained",
                after["TaskBreakDown"], before["TaskBreakDown"])


def provenance_gate(audit: Audit):
    closure = read_json(RUN / "closure.json")
    invocation = read_json(RUN / "invocation.json")
    stages = read_json(RUN / "steps.json")
    audit.equal("run", "ID", closure["run_id"], RUN_ID)
    audit.equal("run", "closure error", closure.get("error"), None)
    audit.equal("run", "invocation SHA", sha(RUN / "invocation.json"), closure["invocation_sha256"])
    audit.equal("run", "sources stable", closure["source_hashes_before"], closure["source_hashes_after"])
    audit.equal("run", "invocation source hashes", invocation["source_hashes_before"],
                closure["source_hashes_before"])
    audit.equal("run", "raw names", set(closure["raw"]), RAW)
    audit.equal("run", "failure seal absent", (RUN / "failure-seal.json").exists(), False)
    verify_raw(audit, RUN, closure, 12, "child_raw")
    audit.equal("run", "copied input", sha(RUN / "input.json"), INPUT_SHA)
    audit.equal("run", "invocation input", invocation["input_sha256"], INPUT_SHA)
    audit.equal("run", "invocation contract", invocation["contract_sha256"], CONTRACT_SHA)
    audit.equal("guard", "SSH session", invocation["session_id"], 0)
    audit.equal("guard", "SSH connection", invocation["ssh_connection_present"], True)
    audit.equal("guard", "sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"], True)
    audit.equal("guard", "mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
    gui = invocation["gui"]
    audit.equal("guard", "GUI PID/session/start",
                (gui["pid"], gui["session_id"], gui["start_unix_ms"]),
                (13340, 1, 1790590196826))
    audit.equal("guard", "stage names", [step["name"] for step in stages],
                ["import", "export", "check_import_export", "calc", "jsonreport"])
    for number, step in enumerate(stages):
        audit.equal("guard", f"stage{number} exit", step["exit_code"], 0)
        audit.equal("guard", f"stage{number} status", step["status"], "completed")
        audit.equal("guard", f"stage{number} GUI", step["gui_preserved"], True)
    paths = {
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
        "accepted_diff": PARENT / "parent-diff.json",
        "accepted_evidence": PARENT / "evidence-2026-09-29.md",
        "accepted_verdict": PARENT / "review/independent-readonly-2026-09-29.json",
        "accepted_closure": PARENT_RUN / "closure.json",
        "prereq_scope": A02 / "cli-scope-signoff-2026-09-29.md",
        "previous_contract": PREVIOUS / "contract.json",
        "previous_nogo_review": PREVIOUS / "review/independent-contract-nogo-2026-10-06.md",
        "installed_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
        "installed_manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "installed_dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
        "python": Path(sys.executable),
        "prelaunch_approval": HERE / "review/independent-prelaunch-go.json",
    }
    for label, path in paths.items():
        audit.equal("source_seal", f"{label} present", label in closure["source_hashes_before"], True)
        if label in closure["source_hashes_before"]:
            audit.equal("source_seal", label, closure["source_hashes_before"][label], sha(path))
    audit.equal("source_seal", "complete path set", set(closure["source_hashes_before"]), set(paths))


def native_input_gate(audit: Audit):
    authored = table_map(read_json(RUN / "input.json"), "model")
    returned = table_map(read_json(RUN / "roundtrip-raw.json"), "model")
    populated = [name for name, table in authored.items()
                 if any(instance["rows"] for instance in table["instances"])]
    audit.equal("roundtrip", "17 populated tables", len(populated), 17)
    for name in populated:
        audit.equal("roundtrip", f"{name} columns", returned[name]["columns"], authored[name]["columns"])
        audit.equal("roundtrip", f"{name} instances", returned[name]["instances"], authored[name]["instances"])
    audit.equal("roundtrip", "checker passed",
                read_json(RUN / "roundtrip-validation.json")["passed"], True)
    log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    audit.equal("converter", "zero errors, two warnings, zero notes",
                "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log, True)
    audit.equal("converter", "only warning IDs 108 and 126",
                sorted(re.findall(r"\(warning #(\d+)\)", log)), ["108", "126"])
    audit.equal("converter", "no error IDs", re.findall(r"\(error #(\d+)\)", log), [])
    audit.equal("converter", "substantive SXO", (RUN / "model.sxo").stat().st_size > 4, True)


def event_gate(audit: Audit):
    text = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    audit.equal("event", "36-hour log", lines[:2], ["SIMLOX LOG FILE", "36"])
    events = [(float(hour), body.strip()) for hour, body in TIMED.findall(text)]
    audit.equal("event", "event order", all(a[0] <= b[0] + 1e-9 for a, b in zip(events, events[1:])), True)
    created = [(hour, body) for hour, body in events if body.endswith(" mission created:")]
    audit.equal("event", "three created missions", len(created), 3)
    if len(created) != 3:
        return
    tags = [body.removesuffix(" mission created:") for _, body in created]
    for index, ((hour, _), tag, notice) in enumerate(zip(created, tags, (7, 11, 15), strict=True)):
        audit.near("event", f"created{index} hour", hour, notice)
        audit.equal("event", f"created{index} identity",
                    bool(re.fullmatch(r"<HOT-SORTIE,TEACH-UNIT,0,0,\d+>", tag)), True)
    audit.equal("event", "distinct identities", len(set(tags)), 3)
    expected = {
        "ordered": [], "allocated": [], "prep_start": [], "prep_end": [],
        "task": [], "subtask": [], "launch": [], "success": [], "completion": [],
        "return": [],
    }
    for index, (tag, notice, launch) in enumerate(zip(tags, (7, 11, 15), (8, 12, 16), strict=True)):
        end = notice + 1 / 6
        prefix = f"subtask {index} seqno 1 within system preparation task {index} on {OWNER}"
        expected["ordered"].append((notice, "<TEACH-UNIT> mission ordered: HOT-SORTIE"))
        expected["allocated"].append((notice, f"{tag} mission allocates system: {OWNER}"))
        expected["prep_start"].append((notice, f"{OWNER} preparation started, mission: {tag}"))
        expected["prep_end"].append((end, f"{OWNER} preparation ended, mission: {tag}"))
        expected["task"].extend([
            (notice, f"system preparation task {index} on {OWNER} started"),
            (end, f"system preparation task {index} on {OWNER} completed"),
        ])
        expected["subtask"].extend([
            (notice, prefix + " started"),
            (notice, prefix + " requests resources: no resources needed"),
            (notice, prefix + " resource availability test"),
            (notice, prefix + " starts performing, planned to last for 0.166667 hours"),
            (end, prefix + " completed"),
        ])
        expected["launch"].append((launch, f"{tag} mission starting, duration: 2 : {OWNER}"))
        expected["success"].append((launch + 2, f"{tag} mission success:"))
        expected["completion"].append((launch + 2, f"{tag} mission completed: {OWNER}"))
        expected["return"].append((launch + 2,
                                   f"<TEACH-AIR-01,BASE-01,0> System arrives {OWNER}, mission success,"))
    filters = {
        "ordered": lambda b: " mission ordered:" in b,
        "allocated": lambda b: " mission allocates system:" in b,
        "prep_start": lambda b: " preparation started," in b,
        "prep_end": lambda b: " preparation ended," in b,
        "task": lambda b: b.startswith("system preparation task "),
        "subtask": lambda b: b.startswith("subtask "),
        "launch": lambda b: " mission starting, duration:" in b,
        "success": lambda b: " mission success:" in b,
        "completion": lambda b: " mission completed:" in b,
        "return": lambda b: " System arrives " in b,
    }
    for label, predicate in filters.items():
        actual = [(hour, body) for hour, body in events if predicate(body)]
        wanted = expected[label]
        audit.equal("event", f"{label} count", len(actual), len(wanted))
        for number, ((hour, body), (at, phrase)) in enumerate(zip(actual, wanted)):
            audit.near("event", f"{label}{number} time", hour, at, 1e-4)
            audit.equal("event", f"{label}{number} text", body, phrase)
    for label, marker in (
        ("cold recipe", "INSPECT"), ("cold recipe 2", "SERVICE"),
        ("cancel", " mission cancelled:"), ("abort", " mission aborted:"),
        ("resource wait", "waiting for resource"), ("failure", "failure occurs"),
    ):
        audit.equal("event", f"no {label}", marker in text, False)


def report_gate(audit: Audit):
    current = table_map(read_json(RUN / "report-raw.json"), "report")
    parent = table_map(read_json(PARENT_RUN / "report-raw.json"), "report")
    audit.equal("report", "table order", list(current), list(parent))
    fields, rows = grid(current["SystemResults"])
    old_fields, before = grid(parent["SystemResults"])
    audit.equal("report", "72x40 System", (len(rows), len(fields)), (72, 40))
    audit.equal("report", "System fields", fields, old_fields)
    exceptions = {
        (14, "NSYMP"): (1, 1 / 3),
        (14, "NSYMR"): (0, 2 / 3),
        (14, "NPSUC"): (0, 1),
        (15, "NPSUC"): (1, 0),
    }
    for number, (row, prior) in enumerate(zip(rows, before)):
        audit.near("system", f"{number}.STINT", row["STINT"], number / 2)
        audit.near("system", f"{number}.ETINT", row["ETINT"], (number + 1) / 2)
        for field in fields:
            expected_before, expected_after = exceptions.get((number, field), (prior[field], prior[field]))
            if (number, field) in exceptions:
                audit.equal("system", f"{number}.{field} parent", prior[field], expected_before)
                audit.near("system", f"{number}.{field}", row[field], expected_after)
            else:
                audit.equal("system", f"{number}.{field}", row[field], expected_after)
    for field, expected in (("NSYMP", 0.5), ("NSYMO", 6), ("NPSTA", 3), ("NPSUC", 3)):
        scale = 0.5 if field.startswith("NSY") else 1
        audit.near("report", f"{field} integral", sum(row[field] * scale for row in rows), expected)
    audit.equal("report", "terminal ready", rows[-1]["NSYRY"], 1)
    stock_fields, stock = grid(current["StockTotalResults"])
    old_stock_fields, old_stock = grid(parent["StockTotalResults"])
    audit.equal("report", "72x16 Stock", (len(stock), len(stock_fields)), (72, 16))
    audit.equal("report", "Stock fields", stock_fields, old_stock_fields)
    for number, (row, prior) in enumerate(zip(stock, old_stock)):
        for field in stock_fields:
            audit.equal("stock", f"{number}.{field}", row[field], prior[field])
    summary_fields, summary = grid(current["ResultSummary"])
    old_summary_fields, old_summary = grid(parent["ResultSummary"])
    audit.equal("report", "11 summary fields", (len(summary_fields), len(summary)), (11, 1))
    audit.equal("report", "summary fields", summary_fields, old_summary_fields)
    for field in summary_fields:
        audit.equal("summary", field, summary[0][field], old_summary[0][field])
    audit.equal("report", "description", current["ProblemDescription"], parent["ProblemDescription"])


def result(audit: Audit, static: bool) -> dict:
    return {
        "schema": "simlox-b01-var03-task-route-self-check/v1" if static else
                  "simlox-b01-var03-task-route-author-validation/v1",
        "run_id": RUN_ID,
        "contract_sha256": CONTRACT_SHA,
        "input_sha256": INPUT_SHA,
        "decision": ("GO_STATIC" if static else "GO_BOUNDED") if not audit.failures else "NO_GO",
        "passed": not audit.failures,
        "checks": audit.count,
        "categories": dict(sorted(audit.categories.items())),
        "failures": audit.failures,
        "scope": "one fixed-seed explicit HOT-SORTIE route at h8; h12/h16 hot routes retained",
        "limits": ["No history-driven switching, aircraft/site mapping, GUI visual, cross-engine, performance or full Issue18 claim."],
    }


def self_check() -> dict:
    audit = Audit()
    try:
        source_gate(audit)
        parent = table_map(read_json(PARENT_RUN / "report-raw.json"), "report")
        fields, rows = grid(parent["SystemResults"])
        audit.equal("parent_report", "72x40 System", (len(rows), len(fields)), (72, 40))
        for number, field, value in ((14, "NSYMP", 1), (14, "NSYMR", 0),
                                     (14, "NPSUC", 0), (15, "NPSUC", 1)):
            audit.equal("parent_report", f"{number}.{field}", rows[number][field], value)
        audit.equal("parent_report", "72x16 Stock",
                    (len(grid(parent["StockTotalResults"])[1]),
                     len(grid(parent["StockTotalResults"])[0])), (72, 16))
        audit.equal("parent_report", "11 summary fields", len(grid(parent["ResultSummary"])[0]), 11)
        audit.equal("run", "new run absent", RUN.exists(), False)
    except Exception as exc:
        audit.failures.append(f"self-check exception: {type(exc).__name__}: {exc}")
    return result(audit, True)


def validate() -> dict:
    audit = Audit()
    try:
        source_gate(audit)
        provenance_gate(audit)
        native_input_gate(audit)
        event_gate(audit)
        report_gate(audit)
    except Exception as exc:
        audit.failures.append(f"validation exception: {type(exc).__name__}: {exc}")
    return result(audit, False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    output = self_check() if args.self_check else validate()
    print(json.dumps(output, ensure_ascii=False, indent=2))
    raise SystemExit(0 if output["passed"] else 1)
