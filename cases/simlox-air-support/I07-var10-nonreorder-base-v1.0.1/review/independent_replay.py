"""Independent read-only replay of the I07.var10 report-only continuation."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
OLD = HERE.parent / "I07-var10-nonreorder-base-v1.0.0"
OLD_RUN = OLD / "runs" / "i07-var10-nonreorder-base-v100-ssh-20261005-01"
RUN = HERE / "runs" / "i07-var10-report-only-v101-ssh-20261005-01"
E15 = HERE.parent / "E15-var07-explicit-istoh-v1.0.1"
checks = []


def ck(ok, label):
    checks.append((bool(ok), label))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(doc, name):
    return next(t for t in doc["report"]["tables"] if t["name"] == name)


contract = read(HERE / "contract.json")
old_index = read(OLD / "evidence-index.json")
old_closure = read(OLD_RUN / "closure.json")
new_closure = read(RUN / "closure.json")
new_inv = read(RUN / "invocation.json")
new_steps = read(RUN / "steps.json")
new_outcome = read(RUN / "outcome.json")

ck(contract["case_id"] == "I07" and contract["variant_id"] == "I07.var10" and contract["version"] == "1.0.1-candidate", "versioned bounded contract")
ck(sha(HERE / "contract.json") == "8b5bf5cc6938e6f2e4d8e57aa3dc45bf0e1dbc6598b032da7b8a85709245074c", "frozen contract hash")
ck(sha(HERE / "run_report_ssh.ps1") == new_closure["source_hashes_before"]["runner"], "frozen report runner hash")
ck(sha(OLD / "evidence-index.json") == contract["diagnostic_parent"]["evidence_index_sha256"], "diagnostic evidence index pin")
ck(sha(OLD / "contract.json") == contract["diagnostic_parent"]["contract_sha256"], "diagnostic contract pin")
ck(sha(OLD_RUN / "closure.json") == contract["diagnostic_parent"]["closure_sha256"] == new_closure["parent_closure_sha256"], "diagnostic closure pin")
ck(old_closure["error"] == "change unreviewed converter diagnostic" and new_closure["error"] is None, "excluded old, successful new closures")
ck(old_closure["source_hashes_before"] == old_closure["source_hashes_after"], "old source before/after seals")
ck(len(old_index["source"]) == 11, "11 indexed old source files")
for name, seal in sorted(old_index["source"].items()):
    path = OLD / name
    ck(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"old source seal {name}")
ck(len(old_closure["raw"]) == 22, "original 22 raw records")
for name, seal in sorted(old_closure["raw"].items()):
    path = OLD_RUN / name
    ck(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"original raw seal {name}")
ck(len(new_closure["raw"]) == 4, "new report-only raw inventory")
for name, seal in sorted(new_closure["raw"].items()):
    path = RUN / name
    ck(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"new raw seal {name}")
ck(new_closure["invocation_sha256"] == sha(RUN / "invocation.json"), "new invocation seal")
ck(new_closure["source_hashes_before"] == new_closure["source_hashes_after"] == new_inv["source_hashes_before"], "new before/after source seals")
ck(new_closure["run_id"] == contract["run_id"] == new_inv["run_id"] and new_closure["parent_run_id"] == old_closure["run_id"], "report-only lineage IDs")
ck(new_inv["session_id"] == 0 and "sshd.exe" in new_inv["ssh_ancestor_names"] and new_inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "SSH0 and mutex provenance")
ck(new_inv["gui"]["pid"] == 13340 and new_inv["gui"]["session_id"] == 1, "protected GUI provenance")
ck(len(new_steps) == 1 and new_steps[0]["name"] == "child_report_only" and new_steps[0]["status"] == "completed" and new_steps[0]["exit_code"] == 0 and new_steps[0]["gui_preserved"], "one guarded report-only step")
ck(new_outcome == {"status": "completed", "error": None, "exit_code": 0}, "report-only outcome")
args = new_steps[0]["arguments"]
ck(all(flag in args for flag in (" -report", " -rpts ", " -rjexport ", " -log ")) and not any(flag in args for flag in (" -calc", " -jimport", " -jexport", " -save")), "no recalculation/import/model export")
ck(str(OLD_RUN / "change.sxo").lower() in args.lower(), "report uses sealed old child SXO")
ck(sha(OLD_RUN / "change.sxo") == contract["diagnostic_parent"]["child_sxo_sha256"], "child SXO unchanged")
ck(sha(OLD_RUN / "control.sxo") == contract["diagnostic_parent"]["control_sxo_sha256"], "control SXO unchanged")
ck(sha(E15 / "runs" / "report-settings" / "item-position-results.sxs") == contract["report_selector"]["settings_sha256"], "selected settings pin")
ck(sha(OLD_RUN / "control-report-raw.json") == contract["diagnostic_parent"]["control_report_sha256"], "sealed control report pin")

old_outcome = read(OLD_RUN / "outcome.json")
runlog = (OLD_RUN / "change-run.log").read_text(errors="replace")
ck(old_outcome["converter_summaries"]["change"] == [0, 2, 0] and old_outcome["warning_codes"]["change"] == ["108", "172"], "original exact child warning set")
ck(re.findall(r"warning #(\d+)", runlog) == ["108", "172"] and "(warning #172) No reorder data defined. ROSIZ ignored. TEACH-DU-01 / BASE-01" in runlog and "Errors: 0, Warnings: 2, Notes: 0" in runlog, "row-specific ignored-value diagnostic")
ck(read(OLD_RUN / "change-roundtrip-check.json")["passed"] and read(OLD_RUN / "control-roundtrip-check.json")["passed"], "original paired roundtrips")
ck(read(OLD_RUN / "change-roundtrip-check.json")["authored_populated_tables"] == 22, "22 authored row-containing tables")
old_control = read(OLD / "control-input.json")
old_child = read(OLD / "change-input.json")
ct = {t["name"]: t for t in old_control["model"]["tables"]}
dt = {t["name"]: t for t in old_child["model"]["tables"]}
ck(ct.keys() == dt.keys() and all(ct[n] == t for n, t in dt.items() if n != "ChangesStockAllocation"), "one-table paired source isolation")
ck(ct["ChangesStockAllocation"]["instances"][0]["rows"] == [[None] * 6] and dt["ChangesStockAllocation"]["instances"][0]["rows"] == [["AIR_BASIC", "TEACH-DU-01", "BASE-01", 5.0, 1, None]], "child-only BASE h5 ROSIZ1")
ck(ct["StockAllocation"]["instances"][0]["rows"][0][:7] == ["AIR_BASIC", "TEACH-DU-01", "BASE-01", 1, None, None, None] and [r[:3] for r in ct["ItemReorder"]["instances"][0]["rows"]] == [["TEACH-DU-01", "DEPOT-01", 1.0]], "BASE stock present, BASE reorder absent")

control_log = (OLD_RUN / "control.log").read_bytes()
child_log = (OLD_RUN / "change.log").read_bytes()
ck(control_log == child_log and sha(OLD_RUN / "change.log") == contract["diagnostic_parent"]["paired_log_sha256"], "complete native event byte parity")
log = child_log.decode(errors="replace")
expected_snapshots = [
    ("DEPOT-01", [0, 1, 2]), ("BASE-01", [3]), ("BASE-01", []),
    ("DEPOT-01", [1, 2]), ("DEPOT-01", [1, 2, 5]),
    ("DEPOT-01", [1, 2, 5, 6]), ("BASE-01", [0]),
]
snapshots = re.findall(r"Stock at: <TEACH-DU-01,0,(DEPOT-01|BASE-01),0> Level: (\d+) Items:([^\r\n]*)", log)
actual_snapshots = [(station, [int(i) for i in re.findall(r"<TEACH-DU-01,0,(\d+)>", items)]) for station, _, items in snapshots]
ck(actual_snapshots == expected_snapshots, "complete physical depot/base item ID snapshots")
for station, level, items in snapshots:
    ck(int(level) == len(re.findall(r"<TEACH-DU-01,0,\d+>", items)), f"physical {station} snapshot count")
for phrase in (
    "Time: 10 <TEACH-DU-01,0,BASE-01,0> Take replacement item <TEACH-DU-01,0,3>",
    "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0>",
    "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1",
    "Time: 11 <TEACH-DU-01,0,DEPOT-01,0> Delivery with 2 item(s) arrives",
    "Time: 12 <TEACH-DU-01,0,BASE-01,0> Put back replacement item <TEACH-DU-01,0,0>",
):
    ck(phrase in log, f"native item ledger {phrase[:55]}")
ck(len(re.findall(r"reorder task \d+ started", log)) == 1, "one depot reorder task")

control_report = read(OLD_RUN / "control-report-raw.json")
child_report = read(RUN / "child-report-raw.json")
ck(sha(RUN / "child-report-raw.json") == sha(OLD_RUN / "control-report-raw.json"), "selected report byte parity")
ck(len(control_report["report"]["tables"]) == len(child_report["report"]["tables"]) == 10, "ten selected report tables")
for left, right in zip(control_report["report"]["tables"], child_report["report"]["tables"]):
    ck(left == right, f"complete report table parity {left['name']}")
for name in ("MissionResults", "SystemResults", "StockTotalResults", "ItemResults"):
    ck(len(table(child_report, name)["instances"][0]["rows"]) == 72, f"72 {name} rows")
item = table(child_report, "ItemResults")
cols = [c["name"] for c in item["columns"]]
rows = [dict(zip(cols, values)) for values in item["instances"][0]["rows"]]
for i, row in enumerate(rows):
    hour = i / 2
    expected_on_hand = 3 if hour < 10 else (2 if hour < 11 else 4)
    ck((row["IID"], row["STID"], row["STINT"], row["ETINT"], row["STSZ"], row["STOHA"], row["NBO"], row["NRO"]) == ("TEACH-DU-01", "DEPOT-01", hour, hour + .5, 4, expected_on_hand, 0, int(hour == 10)), f"depot selected bin {i}")

result = {
    "schema": "independent-i07-var10-report-only-review/v1",
    "decision": "GO_BOUNDED" if all(ok for ok, _ in checks) else "NO_GO",
    "passed": sum(ok for ok, _ in checks),
    "total": len(checks),
    "failures": [label for ok, label in checks if not ok],
    "diagnostic_closure_sha256": sha(OLD_RUN / "closure.json"),
    "report_extension_closure_sha256": sha(RUN / "closure.json"),
    "selected_report_sha256": sha(RUN / "child-report-raw.json"),
    "observed": "The original child converter emitted exact #172 on the BASE-01 ROSIZ row, yet its complete event log and newly selected 10-table report are byte-identical to control. Both arms issue BASE ID3 and DEPOT ID0 at h10, receive depot IDs5/6 at h11 and base ID0 at h12; all 72 depot bins match.",
    "limits": "The calculation belongs to excluded v1.0.0 and was not rerun. v1.0.1 adds only a report export from that sealed SXO. This supports ignored ROSIZ at this one existing non-reorder BASE stock row; it does not retroactively pass the v1.0.0 warning gate or generalize to other items, stations, or GUI behavior.",
}
(HERE / "review" / "independent-verdict.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"{result['decision']} {result['passed']}/{result['total']}")
for label in result["failures"]:
    print("FAIL", label)
