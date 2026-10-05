"""Independent read-only replay of the E15.var09 converter rejection."""
import copy
import hashlib
import json
import pathlib
import re

CASE = pathlib.Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / "runs/e15-var09-istoh-below-v100-ssh-20261005-01"
PARENT = ROOT / "E15-var01-time-based-cycle-v1.0.1"
PARENT_INPUT = ROOT / "E15-var01-time-based-cycle-v1.0.0"
E02 = ROOT / "E02-zero-stock-local-backorder-v1.0.0"
OUTPUT = pathlib.Path(__file__).with_name("independent-verdict.json")
checks = []


def check(name, value):
    checks.append((name, bool(value)))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


contract = read(CASE / "contract.json")
inv = read(RUN / "invocation.json")
closure = read(RUN / "closure.json")
outcome = read(RUN / "outcome.json")
steps = read(RUN / "steps.json")
check("contract/run identity", contract["case_id"] == "E15" and contract["variant_id"] == "E15.var09" and contract["run_id"] == closure["run_id"])
check("closure accepted negative", closure["expected_negative"] and closure["error"] is None and outcome["expected_negative"] and outcome["error"] is None)
check("10 sealed raw records", len(closure["raw"]) == 10)
for name, record in sorted(closure["raw"].items()):
    path = RUN / name
    check(f"raw {name} length", path.stat().st_size == record["bytes"])
    check(f"raw {name} sha", sha(path) == record["sha256"])
check("invocation seal", sha(RUN / "invocation.json") == closure["invocation_sha256"])
paths = {
    "contract": CASE / "contract.json",
    "input": CASE / "native-input.json",
    "builder": CASE / "build.py",
    "roundtrip_checker": CASE / "check_roundtrip.py",
    "parent_input": PARENT_INPUT / "native-input.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-10-05.md",
    "parent_index": PARENT / "evidence-index.json",
    "parent_event": PARENT_INPUT / "runs/e15-var01-timecycle-v100-ssh-20261005-01/model.log",
    "parent_report": PARENT / "runs/e15-var01-timecycle-report-v101-ssh-20261005-01/selected-report-raw.json",
    "e02_input": E02 / "native-input.json",
    "e02_signoff": E02 / "cli-scope-signoff-2026-09-29.md",
    "exe": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": CASE / "run_native_ssh.ps1",
    "python": pathlib.Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
for name, path in paths.items():
    digest = sha(path)
    check(f"source {name} before", inv["source_hashes_before"][name] == digest)
    check(f"source {name} after", closure["source_hashes_after"][name] == digest)
for name, field in (("parent_input", "input_sha256"), ("parent_signoff", "signoff_sha256"), ("parent_index", "evidence_index_sha256"), ("parent_event", "event_log_sha256"), ("parent_report", "selected_report_sha256")):
    check(f"parent contract {name}", sha(paths[name]) == contract["accepted_parent"][field])
for name, field in (("e02_input", "input_sha256"), ("e02_signoff", "signoff_sha256")):
    check(f"E02 contract {name}", sha(paths[name]) == contract["prerequisite_E02"][field])
check("installed pins", sha(paths["manual"]) == contract["source"]["manual_pdf_sha256"] and sha(paths["exe"]) == contract["source"]["simlox_exe_sha256"])
check("copied input", sha(RUN / "input.json") == contract["source"]["input_sha256"])
check("SSH0/mutex", inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
check("GUI identity", inv["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"})
check("three ordered steps", [s["name"] for s in steps] == ["import", "export", "calc_converter_gate"])
for step in steps:
    check(f"{step['name']} completed and GUI kept", step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] and step["error"] is None)
check("no report command", all("-report" not in s["arguments"] and "-rjexport" not in s["arguments"] for s in steps))

parent = read(paths["parent_input"])
child = read(paths["input"])
expected = copy.deepcopy(parent)
stock = expected["model"]["tables"][25]
check("StockAllocation target table", stock["name"] == "StockAllocation" and stock["columns"][6]["name"] == "ISTOH")
check("parent ISTOH absent", stock["instances"][0]["rows"][1][6] is None)
stock["instances"][0]["rows"][1][6] = 3
check("complete one-cell source delta", expected == child)
check("31 table structures", len(child["model"]["tables"]) == 31)
authored = child["model"]["tables"]
export = read(RUN / "roundtrip-raw.json")["model"]["tables"]
check("31 exported tables", len(export) == 31)
check("21 row-containing tables", sum(any(instance["rows"] for instance in table["instances"]) for table in authored) == 21)
for a, b in zip(authored, export):
    check(f"roundtrip table {a['name']}", a["name"] == b["name"] and len(a["instances"]) == len(b["instances"]))
    for i, (ai, bi) in enumerate(zip(a["instances"], b["instances"])):
        if ai["rows"]:
            check(f"row count {a['name']}.{i}", len(ai["rows"]) == len(bi["rows"]))
        else:
            check(f"empty canonicalization {a['name']}.{i}", not bi["rows"] or (len(bi["rows"]) == 1 and all(v is None for v in bi["rows"][0])))
        for j, (ar, br) in enumerate(zip(ai["rows"], bi["rows"])):
            for k, value in enumerate(ar):
                if value is not None:
                    check(f"cell {a['name']}.{i}.{j}.{k}", value == br[k])

log = (RUN / "run.log").read_text(encoding="utf-8-sig")
check("native converter 1/2/0", "Input conversion completed. Errors: 1, Warnings: 2, Notes: 0" in log and outcome["converter_summary"] == [1, 2, 0])
check("single exact error code", re.findall(r"\(error #(\d+)\)", log) == ["377"] and outcome["error_codes"] == ["377"])
check("exact warning codes", re.findall(r"\(warning #(\d+)\)", log) == ["108", "376"])
check("row and target attribution", "Form: StockAllocation\nrec 2: (error #377) Initial stock on hand too small (ISTOH < STSIZ): TEACH-DU-01 / DEPOT-01" in log.replace("\r\n", "\n"))
check("warning same row", "rec 2: (warning #376) ROSIZ not used at location with time-based reorder strategy: TEACH-DU-01 / DEPOT-01" in log)
check("4-byte invalid SXO", (RUN / "model.sxo").stat().st_size == 4)
for absent in ("model.log", "report-raw.json", "selected-report-raw.json", "report-export.log"):
    check(f"no usable {absent}", not (RUN / absent).exists())
check("no simulation/result raw recorded", not any(name in closure["raw"] for name in ("model.log", "report-raw.json", "selected-report-raw.json")))

failures = [name for name, ok in checks if not ok]
result = {
    "schema": "e15-var09-independent-negative-replay/v1",
    "verdict": "GO_BOUNDED_REJECTION" if not failures else "NO_GO",
    "passed": not failures,
    "checks_passed": len(checks) - len(failures),
    "checks_total": len(checks),
    "failures": failures,
    "closure_sha256": sha(RUN / "closure.json"),
    "run_log_sha256": sha(RUN / "run.log"),
    "scope": "Installed CLI rejects one time-based DU depot ISTOH3 below STSIZ4 with StockAllocation rec2 error #377; accepted effective ISTOH4 parent unchanged.",
    "limits": "No general lower-bound proof across items or strategies, no valid simulation behavior, no GUI/cross-engine/full E15 acceptance.",
}
OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"verdict": result["verdict"], "checks_passed": result["checks_passed"], "checks_total": result["checks_total"], "failures": failures}))
