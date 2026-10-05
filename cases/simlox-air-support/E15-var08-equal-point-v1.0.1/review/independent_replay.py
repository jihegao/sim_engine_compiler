"""Independent, standard-library-only replay of sealed E15.var08 report evidence."""
import hashlib
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parents[1]
ROOT = HERE.parent
OLD = ROOT / "E15-var08-equal-point-v1.0.0" / "runs" / "e15-var08-equal-point-v100-ssh-20261005-01"
NEW = HERE / "runs" / "e15-var08-report-only-v101-ssh-20261005-01"
PARENT = ROOT / "E15-var07-explicit-istoh-v1.0.1"
OUT = pathlib.Path(__file__).with_name("independent-verdict.json")
checks = []


def check(label, truth):
    checks.append((label, bool(truth)))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(path):
    return {t["name"]: t for t in read(path)["report"]["tables"]}


def rows(table):
    cols = [x["name"] for x in table["columns"]]
    return [dict(zip(cols, row)) for row in table["instances"][0]["rows"]]


contract = read(HERE / "contract.json")
old_closure = read(OLD / "closure.json")
new_closure = read(NEW / "closure.json")
inv = read(NEW / "invocation.json")
step = read(NEW / "steps.json")[0]
outcome = read(NEW / "outcome.json")
check("contract identifies bounded variant", contract["variant_id"] == "E15.var08" and contract["version"] == "1.0.1-candidate")
check("old frozen error preserved", old_closure["error"] == "frozen equal-point event gate failed")
check("old raw count", len(old_closure["raw"]) == 11)
check("new raw count", len(new_closure["raw"]) == 4)
for root, closure, label in ((OLD, old_closure, "old"), (NEW, new_closure, "new")):
    for name, seal in sorted(closure["raw"].items()):
        path = root / name
        check(f"{label} raw {name} size", path.stat().st_size == seal["bytes"])
        check(f"{label} raw {name} sha", sha(path) == seal["sha256"])

check("old index pin", sha(ROOT / "E15-var08-equal-point-v1.0.0" / "evidence-index.json") == contract["diagnostic_parent"]["evidence_index_sha256"])
check("old closure pin", sha(OLD / "closure.json") == contract["diagnostic_parent"]["closure_sha256"] == new_closure["diagnostic_closure_sha256"])
check("old SXO pin and valid size", sha(OLD / "model.sxo") == contract["diagnostic_parent"]["sxo_sha256"] and (OLD / "model.sxo").stat().st_size > 4)
check("old event pin", sha(OLD / "model.log") == contract["diagnostic_parent"]["event_log_sha256"])
check("invocation seal", sha(NEW / "invocation.json") == new_closure["invocation_sha256"])
paths = {
    "contract": HERE / "contract.json",
    "diagnostic_index": ROOT / "E15-var08-equal-point-v1.0.0" / "evidence-index.json",
    "diagnostic_closure": OLD / "closure.json",
    "diagnostic_sxo": OLD / "model.sxo",
    "diagnostic_event": OLD / "model.log",
    "selector": PARENT / "runs" / "report-settings" / "item-position-results.sxs",
    "selector_builder": PARENT / "make_report_settings.py",
    "exe": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "runner": HERE / "run_report_ssh.ps1",
    "python": pathlib.Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
for name, path in paths.items():
    actual = sha(path)
    check(f"source {name} before", inv["source_hashes_before"][name] == actual)
    check(f"source {name} after", new_closure["source_hashes_after"][name] == actual)
check("report selector contract pin", sha(paths["selector"]) == contract["report_selector"]["settings_sha256"])
check("report selector builder contract pin", sha(paths["selector_builder"]) == contract["report_selector"]["builder_sha256"])
check("manual and exe contract pins", sha(paths["manual"]) == contract["manual_pdf_sha256"] and sha(paths["exe"]) == contract["simlox_exe_sha256"])
check("single SSH0 guarded report", inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
check("GUI identity", inv["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"} and step["gui_preserved"])
cmd = inv["arguments"]
check("report only command", all(x in cmd for x in ("-report", "-rpts", "-rjexport", "-log", "-close")) and not any(x in cmd for x in ("-calc", "-jimport", "-jexport", "-convert")))
check("report step and closure successful", step["name"] == "report_only" and step["status"] == "completed" and step["exit_code"] == 0 and outcome["error"] is None and new_closure["error"] is None)
check("old raw remained sealed", new_closure["source_hashes_before"]["diagnostic_sxo"] == new_closure["source_hashes_after"]["diagnostic_sxo"] and new_closure["source_hashes_before"]["diagnostic_event"] == new_closure["source_hashes_after"]["diagnostic_event"])

log = (OLD / "model.log").read_text(encoding="utf-8-sig")
for phrase in (
    "Time: 0 <TEACH-DU-01,0,DEPOT-01,0> Stock initiated",
    "Level: 2 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>",
    "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0>",
    "Level: 1 Items:<TEACH-DU-01,0,1>",
    "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1",
    "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was 1",
    "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 3 item(s) arrives",
    "Time: 12 <TEACH-DU-01,0,BASE-01,0> Put back replacement item <TEACH-DU-01,0,0>",
):
    check("event: " + phrase[:68], phrase in log)
for item in (4, 5, 6):
    check(f"new physical item {item} stocked at 11", f"Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Put back replacement item <TEACH-DU-01,0,{item}> to stock" in log)
check("no hour zero reorder", not re.search(r"Time: 0 <TEACH-DU-01,0,DEPOT-01,0> reorder task", log))
check("one reorder and delivery", len(re.findall(r"<TEACH-DU-01,0,DEPOT-01,0> reorder task \d+ started", log)) == 1 and log.count("Delivery with 3 item(s) arrives") == 1)

current = tables(NEW / "selected-report-raw.json")
parent = tables(PARENT / "runs" / "e15-var07-explicit-three-item-v101-ssh-20261002-01" / "item-report-raw.json")
expected_names = {"ProblemDescription", "ResultSummary", "MissionResults", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal", "SystemResults", "ItemResults", "ItemResultsTotal", "StockTotalResults"}
check("ten selected tables", set(current) == expected_names == set(parent))
for name in sorted(expected_names - {"ItemResults", "ItemResultsTotal"}):
    check(f"parent table parity {name}", current[name] == parent[name])
item = rows(current["ItemResults"])
check("72 item intervals", len(item) == 72)
for i, row in enumerate(item):
    check(f"item interval {i}", row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2)
    check(f"item identity {i}", row["IID"] == "TEACH-DU-01" and row["STID"] == "DEPOT-01")
    check(f"item STSZ {i}", row["STSZ"] == 4)
    check(f"item STOHA {i}", row["STOHA"] == (2 if i < 20 else 1 if i < 22 else 4))
    check(f"item NBO {i}", row["NBO"] == 0)
    check(f"item NRO {i}", row["NRO"] == (1 if i == 20 else 0))
totals = rows(current["ItemResultsTotal"])
check("one item total", len(totals) == 1)
check("item total mean", abs(totals[0]["STOHA"] - 242 / 72) < 1e-5)
check("item total orders/backorders", totals[0]["NRO"] == 1 and totals[0]["NBO"] == 0)
parent_item = rows(parent["ItemResults"])
diffs = [(i, k) for i, (a, b) in enumerate(zip(item, parent_item)) for k in a if a[k] != b[k]]
check("parent item change only first 22 on-hand bins", diffs == [(i, "STOHA") for i in range(22)])
parent_total = rows(parent["ItemResultsTotal"])[0]
check("parent item total only mean differs", {k for k in totals[0] if totals[0][k] != parent_total[k]} == {"STOHA"})
check("terminal ready in system report", rows(current["SystemResults"])[-1]["NSYRY"] == 1)
check("result summary one replication", rows(current["ResultSummary"])[0]["NREP"] == 1)

failed = [name for name, ok in checks if not ok]
result = {
    "schema": "e15-var08-independent-readonly/v1",
    "decision": "GO_BOUNDED" if not failed else "NO_GO",
    "passed": not failed,
    "checks_passed": len(checks) - len(failed),
    "checks_total": len(checks),
    "failures": failed,
    "diagnostic_closure_sha256": sha(OLD / "closure.json"),
    "report_closure_sha256": sha(NEW / "closure.json"),
    "selected_report_sha256": sha(NEW / "selected-report-raw.json"),
    "scope": "One sealed excluded v1.0.0 SXO, report-only selected export, equal-point ISTOH2, one seed/depot, observed h10 reorder of three; original h0 acceptance failure remains excluded.",
    "limits": "No below-point arm, other demand/stock states, hidden reorder decision rule, population result, GUI behavior, or general E15.var08 acceptance.",
}
OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({"decision": result["decision"], "checks_passed": result["checks_passed"], "checks_total": result["checks_total"], "failures": failed}))
