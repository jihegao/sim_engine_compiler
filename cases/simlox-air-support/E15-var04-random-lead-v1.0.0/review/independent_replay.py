"""Read-only independent replay of E15.var04 sealed native evidence."""
import hashlib
import json
import pathlib
import re
import copy

CASE = pathlib.Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / "runs" / "e15-var04-random-lead-v100-ssh-20261005-01"
PARENT = ROOT / "E15-var07-explicit-istoh-v1.0.1"
VERDICT = pathlib.Path(__file__).with_name("independent-verdict.json")
checks = []


def check(label, value):
    checks.append((label, bool(value)))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report_tables(path):
    return {t["name"]: t for t in read(path)["report"]["tables"]}


def report_rows(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, r)) for r in table["instances"][0]["rows"]]


contract = read(CASE / "contract.json")
inv = read(RUN / "invocation.json")
closure = read(RUN / "closure.json")
outcome = read(RUN / "outcome.json")
steps = read(RUN / "steps.json")
check("frozen contract", contract["case_id"] == "E15" and contract["variant_id"] == "E15.var04" and contract["run_id"] == closure["run_id"])
check("sealed closure success", closure["error"] is None and outcome["error"] is None and outcome["result"] == "native_run_completed")
check("13 raw seals", len(closure["raw"]) == 13)
for name, seal in sorted(closure["raw"].items()):
    p = RUN / name
    check(f"raw {name} bytes", p.stat().st_size == seal["bytes"])
    check(f"raw {name} sha", sha(p) == seal["sha256"])
check("invocation sealed", sha(RUN / "invocation.json") == closure["invocation_sha256"])
paths = {
    "contract": CASE / "contract.json",
    "input": CASE / "native-input.json",
    "builder": CASE / "build.py",
    "roundtrip_checker": CASE / "check_roundtrip.py",
    "parent_input": PARENT / "native-input-explicit-three.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-10-02.md",
    "parent_index": PARENT / "evidence-index.json",
    "parent_event": PARENT / "runs/e15-var07-explicit-three-v101-ssh-20261002-01/model.log",
    "parent_report": PARENT / "runs/e15-var07-explicit-three-item-v101-ssh-20261002-01/item-report-raw.json",
    "selector": PARENT / "runs/report-settings/item-position-results.sxs",
    "selector_builder": PARENT / "make_report_settings.py",
    "exe": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": CASE / "run_native_ssh.ps1",
    "python": pathlib.Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
for key, path in paths.items():
    digest = sha(path)
    check(f"source {key} before", inv["source_hashes_before"][key] == digest)
    check(f"source {key} after", closure["source_hashes_after"][key] == digest)
check("input copied unchanged", sha(RUN / "input.json") == contract["source"]["input_sha256"])
check("manual/exe source pins", sha(paths["manual"]) == contract["source"]["manual_pdf_sha256"] and sha(paths["exe"]) == contract["source"]["simlox_exe_sha256"])
for key, field in (("parent_input", "input_sha256"), ("parent_signoff", "signoff_sha256"), ("parent_index", "evidence_index_sha256"), ("parent_event", "event_log_sha256"), ("parent_report", "selected_report_sha256")):
    check(f"accepted parent {key}", sha(paths[key]) == contract["accepted_parent"][field])
check("SSH0 and mutex", inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
check("protected GUI identity", inv["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"})
check("four ordered stages", [s["name"] for s in steps] == ["import", "export", "calc", "report"])
for step in steps:
    check(f"{step['name']} success and GUI", step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] and step["error"] is None)
check("converter exact warning", outcome["converter_summary"] == [0, 1, 0] and outcome["warning_codes"] == ["108"])
runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
check("converter native text", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and "(warning #108)" in runlog)
check("valid SXO", (RUN / "model.sxo").stat().st_size > 1000)

src = read(paths["parent_input"])
child = read(paths["input"])
model_a, model_b = src["model"]["tables"], child["model"]["tables"]
check("31 matching tables", len(model_a) == len(model_b) == 31 and [t["name"] for t in model_a] == [t["name"] for t in model_b])
diff = []
for t0, t1 in zip(model_a, model_b):
    for i, (inst0, inst1) in enumerate(zip(t0["instances"], t1["instances"])):
        for j, (row0, row1) in enumerate(zip(inst0["rows"], inst1["rows"])):
            for k, (a, b) in enumerate(zip(row0, row1)):
                if a != b:
                    diff.append((t0["name"], i, j, t0["columns"][k]["name"], a, b))
check("sole LEADTD delta", diff == [("ItemReorder", 0, 0, "LEADTD", None, "<EXP>")])
expected_child = copy.deepcopy(src)
expected_child["model"]["tables"][12]["instances"][0]["rows"][0][9] = "<EXP>"
check("complete source object differs by that cell only", expected_child == child)
export = read(RUN / "roundtrip-raw.json")["model"]["tables"]
check("export table count", len(export) == 31)
row_tables = 0
for authored, native in zip(model_b, export):
    check(f"roundtrip table {authored['name']}", authored["name"] == native["name"])
    if any(x["rows"] for x in authored["instances"]):
        row_tables += 1
    check(f"roundtrip instance count {authored['name']}", len(authored["instances"]) == len(native["instances"]))
    for i, (a, b) in enumerate(zip(authored["instances"], native["instances"])):
        if a["rows"]:
            check(f"roundtrip row count {authored['name']} {i}", len(a["rows"]) == len(b["rows"]))
        else:
            check(f"empty table canonicalization {authored['name']} {i}", not b["rows"] or (len(b["rows"]) == 1 and all(v is None for v in b["rows"][0])))
        for j, (ra, rb) in enumerate(zip(a["rows"], b["rows"])):
            for k, value in enumerate(ra):
                if value is not None:
                    check(f"roundtrip populated {authored['name']} {i}.{j}.{k}", value == rb[k])
check("21 authored row-containing tables", row_tables == 21)

log = (RUN / "model.log").read_text(encoding="utf-8-sig")
for phrase in (
    "Level: 3 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>",
    "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0>",
    "Level: 2 Items:<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>",
    "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1.12383",
    "Time: 11.1238 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was 1.12383",
    "Time: 11.1238 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives",
    "Time: 12 <TEACH-DU-01,0,BASE-01,0> Put back replacement item <TEACH-DU-01,0,0>",
):
    check("event " + phrase[:65], phrase in log)
for item in (5, 6):
    check(f"delivered ID {item}", f"Time: 11.1238 <TEACH-DU-01,0,DEPOT-01,0> Put back replacement item <TEACH-DU-01,0,{item}> to stock" in log)
for phrase in (
    "Time: 10 <TEACH-DU-01,0,BASE-01,0> Take replacement item <TEACH-DU-01,0,3> from stock",
    "Time: 10.1667 <TEACH-DU-01,0,BASE-01,0> Item discarded: <TEACH-DU-01,0,4>",
    "Time: 10.5  system SURP task 0 on <TEACH-AIR-01,0> completed",
    "Time: 12  transport task 0 arrives with 1 items/systems",
    "Time: 11.1238 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,5>",
    "Time: 11.1238 <TEACH-DU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-DU-01,0,6>",
):
    check("physical ledger " + phrase[:62], phrase in log)
check("physical event ordering", log.index("Item discarded: <TEACH-DU-01,0,4>") < log.index("Delivery with 2 item(s) arrives") < log.index("Time: 12  transport task 0 arrives"))
check("no h0 reorder", "Time: 0 <TEACH-DU-01,0,DEPOT-01,0> reorder task" not in log)
check("one order and delivery", len(re.findall(r"reorder task \d+ started", log)) == 1 and log.count("Delivery with 2 item(s) arrives") == 1)
check("draw positive and nonparent", 0 < 1.12383 < 26 and abs(1.12383 - 1) > 0.01)

tables = report_tables(RUN / "selected-report-raw.json")
parent = report_tables(paths["parent_report"])
expected = {"ProblemDescription", "ResultSummary", "MissionResults", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal", "SystemResults", "ItemResults", "ItemResultsTotal", "StockTotalResults"}
check("ten selected report tables", set(tables) == expected == set(parent))
for name in sorted(expected - {"ItemResults", "ItemResultsTotal"}):
    check(f"parent report parity {name}", tables[name] == parent[name])
item = report_rows(tables["ItemResults"])
check("72 depot item bins", len(item) == 72)
for i, row in enumerate(item):
    check(f"interval {i}", row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2)
    check(f"identity {i}", row["IID"] == "TEACH-DU-01" and row["STID"] == "DEPOT-01")
    check(f"nominal {i}", row["STSZ"] == 4)
    target = 3 if i < 20 else 2 if i < 22 else 4 - 2 * 0.12383 / 0.5 if i == 22 else 4
    check(f"on hand {i}", abs(row["STOHA"] - target) < 3e-5)
    check(f"backorder {i}", row["NBO"] == 0)
    check(f"orders {i}", row["NRO"] == (1 if i == 20 else 0))
total = report_rows(tables["ItemResultsTotal"])
check("one item total", len(total) == 1)
weighted_mean = sum(row["STOHA"] for row in item) / 72
check("mean of 72 bins", abs(total[0]["STOHA"] - weighted_mean) < 2e-5)
check("one order, zero BO total", total[0]["NRO"] == 1 and total[0]["NBO"] == 0)
parent_item = report_rows(parent["ItemResults"])
differences = [(i, k) for i, (a, b) in enumerate(zip(item, parent_item)) for k in a if a[k] != b[k]]
check("only fractional delivery bin differs from parent", differences == [(22, "STOHA")])
parent_total = report_rows(parent["ItemResultsTotal"])[0]
check("total only mean differs", {k for k in total[0] if total[0][k] != parent_total[k]} == {"STOHA"})
check("terminal ready", report_rows(tables["SystemResults"])[-1]["NSYRY"] == 1)
check("one replication", report_rows(tables["ResultSummary"])[0]["NREP"] == 1)

failures = [name for name, ok in checks if not ok]
result = {
    "schema": "e15-var04-independent-replay/v1",
    "verdict": "GO_BOUNDED" if not failures else "NO_GO",
    "passed": not failures,
    "checks_passed": len(checks) - len(failures),
    "checks_total": len(checks),
    "failures": failures,
    "closure_sha256": sha(RUN / "closure.json"),
    "event_log_sha256": sha(RUN / "model.log"),
    "selected_report_sha256": sha(RUN / "selected-report-raw.json"),
    "scope": "One fixed-seed DU/depot reorder using LEADTD=<EXP>, sampled 1.12383-hour lead, two-item h11.1238 delivery; source-bound observation only.",
    "limits": "No exponential-law or population inference, other stock states/seeds, multiple orders, GUI behavior, cross-engine result, or full E15.var04/E15 acceptance.",
}
VERDICT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"verdict": result["verdict"], "checks_passed": result["checks_passed"], "checks_total": result["checks_total"], "failures": failures}))
