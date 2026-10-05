"""Independent, standard-library-only replay of the sealed I07.var06 evidence."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
RUN = HERE / "runs" / "i07-var06-large-first-batch-v100-ssh-20261005-01"
CASES = HERE.parent
checks = []


def ck(condition, label):
    checks.append({"ok": bool(condition), "label": label})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(doc, name, root):
    return next(t for t in doc[root]["tables"] if t["name"] == name)


contract = read(HERE / "contract.json")
closure = read(RUN / "closure.json")
inv = read(RUN / "invocation.json")
steps = read(RUN / "steps.json")
outcome = read(RUN / "outcome.json")
ck(sha(HERE / "contract.json") == "d0f9da136515bab7b4be623de2bd345392a788a77212fc121947101e7d479bbd", "frozen contract SHA")
ck(sha(HERE / "run_native_ssh.ps1") == "f0b42bad5573c3144d4aecf4b05fce061caeb0972bc3b104d3a20f4e4a4b4129", "runner SHA")
ck(closure["run_id"] == contract["run_id"] == inv["run_id"], "run identity")
ck(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
ck(closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"], "before/after source seals")
ck(closure["error"] is None and outcome["error"] is None, "closures without errors")
source_files = {
    "contract": HERE / "contract.json",
    "builder": HERE / "build.py",
    "roundtrip_checker": HERE / "check_roundtrip.py",
    "control": HERE / "control-input.json",
    "change": HERE / "change-input.json",
    "runner": HERE / "run_native_ssh.ps1",
    "parent_input": CASES / "E15-var07-explicit-istoh-v1.0.1" / "native-input-explicit-three.json",
}
for name, path in source_files.items():
    ck(path.is_file() and sha(path) == closure["source_hashes_before"][name], f"source seal {name}")
ck(len(closure["raw"]) == 24, "24 sealed raw files")
for name, seal in sorted(closure["raw"].items()):
    path = RUN / name
    ck(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw seal {name}")
ck(inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"], "SSH session zero")
ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "native queue")
ck(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "protected GUI identity")
ck(len(steps) == 8 and [s["name"] for s in steps] == [f"{arm}_{stage}" for arm in ("control", "change") for stage in ("import", "export", "calc", "report")], "eight ordered native steps")
for step in steps:
    ck(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True, f"successful guarded {step['name']}")

parent = read(source_files["parent_input"])
inputs = {arm: read(HERE / f"{arm}-input.json") for arm in ("control", "change")}
for arm, doc in inputs.items():
    ck(sha(HERE / f"{arm}-input.json") == contract["source"]["inputs_sha256"][arm], f"frozen {arm} input")
    ck(sha(RUN / f"{arm}-input.json") == sha(HERE / f"{arm}-input.json"), f"copied {arm} input")
    ptab = {t["name"]: t for t in parent["model"]["tables"]}
    ctab = {t["name"]: t for t in doc["model"]["tables"]}
    ck(len(ptab) == 31 and len(ctab) == 32, f"{arm} parent/table count")
    ck(all(ctab[n] == t for n, t in ptab.items() if n not in ("ProblemDescription", "StockAllocation")), f"{arm} inherited business tables")
    ck(len([t for t in ctab.values() if any(i["rows"] for i in t["instances"])]) == 22, f"{arm} authored row-containing tables")
    exported = read(RUN / f"{arm}-roundtrip-raw.json")
    xtab = {t["name"]: t for t in exported["model"]["tables"]}
    for name, t in ctab.items():
        if any(i["rows"] for i in t["instances"]):
            ck(name in xtab and [i["rows"] for i in xtab[name]["instances"]] == [i["rows"] for i in t["instances"]], f"{arm} authored row roundtrip {name}")
    calc = (RUN / f"{arm}-run.log").read_text(errors="replace")
    ck("Errors: 0, Warnings: 1, Notes: 0" in calc and re.findall(r"warning #(\d+)", calc) == ["108"], f"{arm} converter gate")
    ck((RUN / f"{arm}.sxo").stat().st_size > 4, f"{arm} valid result")

control_tables = {t["name"]: t for t in inputs["control"]["model"]["tables"]}
change_tables = {t["name"]: t for t in inputs["change"]["model"]["tables"]}
ck(all(control_tables[n] == t for n, t in change_tables.items() if n != "ChangesStockAllocation"), "pair differs only in scheduled ROSIZ row")
ck("ItemTransfer" not in control_tables and "ItemTransfer" not in change_tables, "no scheduled transfer")
ck(table(inputs["control"], "StockAllocation", "model")["instances"][0]["rows"][1] == ["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 4, 3, None, 3, None, None], "common nominal four, ROSIZ three, opening three")
parent_stock = table(parent, "StockAllocation", "model")["instances"][0]["rows"]
child_stock = table(inputs["control"], "StockAllocation", "model")["instances"][0]["rows"]
ck(len(parent_stock) == len(child_stock) == 2 and parent_stock[0] == child_stock[0] and parent_stock[1][:4] == child_stock[1][:4] and parent_stock[1][4] == 2 and parent_stock[1][5:] == child_stock[1][5:], "only shared parent stock delta is ROSIZ two to three")
ck(table(inputs["control"], "ChangesStockAllocation", "model")["instances"][0]["rows"] == [[None] * 6], "control all-null change placeholder")
ck(table(inputs["change"], "ChangesStockAllocation", "model")["instances"][0]["rows"] == [["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 5.0, 1, None]], "child h5 ROSIZ one")

reports = {arm: read(RUN / f"{arm}-report-raw.json") for arm in inputs}
logs = {arm: (RUN / f"{arm}.log").read_text(errors="replace") for arm in inputs}
expected = {
    "control": {"orders": [], "depot_on_hand": [(0, 10, 3), (10, 36, 2)], "reorder_ids": (), "snapshots": [("DEPOT-01", [0, 1, 2]), ("BASE-01", [3]), ("BASE-01", []), ("DEPOT-01", [1, 2]), ("BASE-01", [0])]},
    "change": {"orders": [(10, 0, 11, 2)], "depot_on_hand": [(0, 10, 3), (10, 11, 2), (11, 36, 4)], "reorder_ids": (5, 6), "snapshots": [("DEPOT-01", [0, 1, 2]), ("BASE-01", [3]), ("BASE-01", []), ("DEPOT-01", [1, 2]), ("DEPOT-01", [1, 2, 5]), ("DEPOT-01", [1, 2, 5, 6]), ("BASE-01", [0])]},
}
for arm in inputs:
    log = logs[arm]
    report = reports[arm]
    exp = expected[arm]
    ck("Time: 0 <TEACH-DU-01,0,DEPOT-01,0> Stock initiated" in log and "Level: 3 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>" in log, f"{arm} depot opening IDs")
    ck("Time: 0 <TEACH-DU-01,0,BASE-01,0> Stock initiated" in log and "Level: 1 Items:<TEACH-DU-01,0,3>" in log, f"{arm} base opening ID")
    ck("item transfer task" not in log and "Time: 5 <TEACH-DU-01,0,DEPOT-01,0>" not in log, f"{arm} no h5 movement")
    ck("Time: 10 <TEACH-DU-01,0,BASE-01,0> Take replacement item <TEACH-DU-01,0,3> from stock" in log, f"{arm} base issue ID3")
    ck("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock" in log, f"{arm} depot issue ID0")
    ck("Time: 12 <TEACH-DU-01,0,BASE-01,0> Put back replacement item <TEACH-DU-01,0,0> to stock" in log, f"{arm} base restock ID0")
    for start, task, arrival, qty in exp["orders"]:
        ck(f"Time: {start} <TEACH-DU-01,0,DEPOT-01,0> reorder task {task} started, reorder time: 1" in log, f"{arm} order {task} start")
        ck(f"Time: {arrival} <TEACH-DU-01,0,DEPOT-01,0> reorder task {task} completed, total time was 1" in log and f"Time: {arrival} <TEACH-DU-01,0,DEPOT-01,0> Delivery with {qty} item(s) arrives" in log, f"{arm} order {task} delivery quantity")
    ck(len(re.findall(r"reorder task \d+ started", log)) == len(exp["orders"]), f"{arm} no extra reorder")
    for item_id in exp["reorder_ids"]:
        ck(f"Replacement item arrives <TEACH-DU-01,0,{item_id}>" in log, f"{arm} reorder item ID{item_id}")
    # Every native stock snapshot's declared level must equal its listed physical IDs.
    snapshots = re.findall(r"Stock at: <TEACH-DU-01,0,(DEPOT-01|BASE-01),0> Level: (\d+) Items:([^\r\n]*)", log)
    ck(len(snapshots) >= 5, f"{arm} multiple physical stock snapshots")
    for station, level, items in snapshots:
        ck(int(level) == len(re.findall(r"<TEACH-DU-01,0,\d+>", items)), f"{arm} {station} physical stock conservation")
    actual_snapshots = [(station, [int(x) for x in re.findall(r"<TEACH-DU-01,0,(\d+)>", items)]) for station, _, items in snapshots]
    ck(actual_snapshots == exp["snapshots"], f"{arm} complete depot/base physical ID snapshots")
    item = table(report, "ItemResults", "report")
    cols = [c["name"] for c in item["columns"]]
    rows = [dict(zip(cols, r)) for r in item["instances"][0]["rows"]]
    ck(len(rows) == 72 and all(r["IID"] == "TEACH-DU-01" and r["STID"] == "DEPOT-01" and r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(rows)), f"{arm} depot 72 aligned rows")
    for i, row in enumerate(rows):
        hour = i / 2
        on_hand = next(v for start, end, v in exp["depot_on_hand"] if start <= hour < end)
        ck(row["STSZ"] == 4 and row["STOHA"] == on_hand and row["NBO"] == 0, f"{arm} depot bin {i} nominal/on-hand/backorder")
        ck(row["NRO"] == int(hour in [o[0] for o in exp["orders"]]), f"{arm} depot bin {i} order marker")
    total = table(report, "ItemResultsTotal", "report")
    total_row = dict(zip([c["name"] for c in total["columns"]], total["instances"][0]["rows"][0]))
    ck(abs(total_row["STSZ"] - sum(r["STSZ"] for r in rows) / 72) < 1e-5, f"{arm} depot nominal total integral")
    ck(abs(total_row["STOHA"] - sum(r["STOHA"] for r in rows) / 72) < 1e-5, f"{arm} depot on-hand total integral")
    ck(total_row["NRO"] == len(exp["orders"]), f"{arm} depot total reorder count")
    for name in ("MissionResults", "SystemResults", "StockTotalResults"):
        ck(len(table(report, name, "report")["instances"][0]["rows"]) == 72, f"{arm} {name} 72 bins")

for name in ("ResultSummary", "MissionResults", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal", "SystemResults", "StockTotalResults"):
    ck(table(reports["control"], name, "report")["instances"] == table(reports["change"], name, "report")["instances"], f"paired {name} equality")
control_item = table(reports["control"], "ItemResults", "report")
change_item = table(reports["change"], "ItemResults", "report")
item_cols = [c["name"] for c in control_item["columns"]]
ck(item_cols == [c["name"] for c in change_item["columns"]], "paired depot report schema")
for i, (left, right) in enumerate(zip(control_item["instances"][0]["rows"], change_item["instances"][0]["rows"])):
    ck(all(x == y for name, x, y in zip(item_cols, left, right) if name not in ("STOHA", "NRO")), f"depot paired bin {i} other fields equal")

result = {
    "schema": "independent-i07-var06-review/v1",
    "verdict": "GO_BOUNDED" if all(c["ok"] for c in checks) else "NO_GO",
    "passed": sum(c["ok"] for c in checks),
    "total": len(checks),
    "failures": [c["label"] for c in checks if not c["ok"]],
    "run_id": contract["run_id"],
    "closure_sha256": sha(RUN / "closure.json"),
    "report_sha256": {arm: sha(RUN / f"{arm}-report-raw.json") for arm in inputs},
    "observed": {
        "control": "No h5 order or stock move; h10 depot issue ID0 leaves two on hand, with no reorder through horizon.",
        "change": "No h5 order or stock move; h10 issue ID0 triggers child-only reorder of two, IDs5/6 delivered h11, exceeding changed ROSIZ1.",
        "paired_reports": "ResultSummary, mission, system, and aggregate stock rows match; depot ItemResults differs in h10 order marker and on-hand after h11.",
    },
    "limits": "One fixed-seed stock-based discardable DU with nominal four/opening three, initial ROSIZ3, child ROSIZ1 at h5, and one ordinary h10 demand. This does not establish batch sizes in other stock states, multiple-demand policy, GUI behavior, or a general reorder law.",
}
(HERE / "review" / "independent-review.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"{result['verdict']} {result['passed']}/{result['total']}")
for failure in result["failures"]:
    print("FAIL", failure)
