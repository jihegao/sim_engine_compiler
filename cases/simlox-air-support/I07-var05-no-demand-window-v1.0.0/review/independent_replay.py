"""Read-only source-bound replay of I07.var02's depot demand-free window."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PARENT = HERE.parent / "I07-var02-rosiz-v1.0.1"
RUN = PARENT / "runs" / "i07-var02-rosiz-v101-ssh-20261005-01"
checks = []


def ck(ok, label):
    checks.append((bool(ok), label))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def doc(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(obj, root, name):
    return next(t for t in obj[root]["tables"] if t["name"] == name)


contract = doc(HERE / "contract.json")
index = doc(PARENT / "evidence-index.json")
closure = doc(RUN / "closure.json")
inv = doc(RUN / "invocation.json")
steps = doc(RUN / "steps.json")
pins = contract["accepted_parent"]
ck(contract["variant_id"] == "I07.var05" and contract["scope"].find("[5,10)") >= 0, "bounded mapping contract")
ck(sha(PARENT / "evidence-index.json") == pins["evidence_index_sha256"], "accepted index pin")
ck(sha(PARENT / "contract.json") == pins["contract_sha256"], "accepted contract pin")
ck(sha(PARENT / "cli-scope-signoff-2026-10-05.md") == pins["signoff_sha256"], "accepted signoff pin")
ck(sha(PARENT / "review" / "independent-readonly-2026-10-05.json") == pins["independent_review_sha256"], "accepted independent verdict pin")
ck(sha(RUN / "closure.json") == pins["run_closure_sha256"], "accepted closure pin")
ck(pins["run_id"] == closure["run_id"] == inv["run_id"] == index["run"]["run_id"], "accepted run identity")
ck(sha(RUN / "invocation.json") == closure["invocation_sha256"] == index["run"]["invocation"]["sha256"], "invocation seal")
ck(closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"], "source before/after parity")
ck(closure["error"] is None, "accepted run closure clean")
donor = HERE.parent / "E15-var07-explicit-istoh-v1.0.1"
closure_files = {
    "contract": PARENT / "contract.json",
    "builder": PARENT / "build.py",
    "parent_input": donor / "native-input-default.json",
    "parent_signoff": donor / "cli-scope-signoff-2026-10-02.md",
    "settings_builder": donor / "make_report_settings.py",
    "default_settings": Path("C:/Users/Public/Documents/Systecon/SIMLOX/Setup/Default.sxs"),
    "selector": donor / "runs" / "report-settings" / "item-position-results.sxs",
    "control": PARENT / "control-input.json",
    "change": PARENT / "change-input.json",
    "exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
    "manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
    "dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
    "runner": PARENT / "run_native_ssh.ps1",
    "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
}
ck(closure_files.keys() == closure["source_hashes_before"].keys(), "all closure source names mapped")
for name, path in closure_files.items():
    ck(path.is_file() and sha(path) == closure["source_hashes_before"][name], f"closure source seal {name}")
ck(len(index["source"]) == 15, "15 indexed source files")
for name, pin in sorted(index["source"].items()):
    path = PARENT / name
    ck(path.is_file() and path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"], f"original source seal {name}")
ck(len(index["run"]["raw"]) == len(closure["raw"]) == 22, "22 original raw seals")
for name, pin in sorted(index["run"]["raw"].items()):
    path = RUN / name
    ck(name in closure["raw"] and closure["raw"][name] == pin and path.is_file() and path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"], f"original raw seal {name}")
ck(inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"], "original SSH session zero")
ck(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "original protected GUI")
ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "original queue guard")
ck(len(steps) == 8 and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "original eight guarded steps")

inputs = {a: doc(PARENT / f"{a}-input.json") for a in ("control", "change")}
ck(sha(PARENT / "control-input.json") == pins["control_input_sha256"], "control source pin")
ck(sha(PARENT / "change-input.json") == pins["change_input_sha256"], "change source pin")
ctrl = {t["name"]: t for t in inputs["control"]["model"]["tables"]}
child = {t["name"]: t for t in inputs["change"]["model"]["tables"]}
ck(ctrl.keys() == child.keys() and all(ctrl[k] == child[k] for k in ctrl if k != "ChangesStockAllocation"), "exact paired table isolation")
ck(ctrl["ChangesStockAllocation"]["instances"][0]["rows"] == [[None] * 6], "control placeholder")
ck(child["ChangesStockAllocation"]["instances"][0]["rows"] == [["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 5.0, 1, None]], "child h5 ROSIZ row")
ck(ctrl["StockAllocation"]["instances"][0]["rows"][1] == ["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 4, 2, None, None, None, None], "depot nominal4/default opening4/ROSIZ2")
ck("ItemTransfer" not in ctrl and "ItemTransfer" not in child, "no authored transfer")

reports = {a: doc(RUN / f"{a}-report-raw.json") for a in inputs}
logs = {a: (RUN / f"{a}.log").read_text(errors="replace") for a in inputs}
for arm, log in logs.items():
    # A mission and an in-flight failure do occur; exclude only item-stock actions.
    current_time = None
    stock_actions = []
    for line in log.splitlines():
        m = re.match(r"Time: ([0-9.eE+-]+) (.*)", line)
        if m:
            current_time = float(m.group(1))
        if current_time is not None and 5 <= current_time < 10 and re.search(r"Item demand arrives|Item transfer demand|item transfer task|reorder task|Delivery with|Take replacement item|Put back replacement item|Stock at: <TEACH-DU-01,0,DEPOT-01", line, re.I):
            stock_actions.append(line)
    ck(not stock_actions, f"{arm} no depot item-stock action in [5,10)")
    ck("Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION" in log and "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in log, f"{arm} unrelated mission/failure events remain")
    ck("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock" in log, f"{arm} first depot issue boundary h10 ID0")
    ck("Time: 5 <TEACH-DU-01,0,DEPOT-01,0> reorder task" not in log, f"{arm} no h5 order")
    ck(("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started" in log) == (arm == "change"), f"{arm} first reorder only at child h10")
    item = table(reports[arm], "report", "ItemResults")
    cols = [c["name"] for c in item["columns"]]
    rows = [dict(zip(cols, raw)) for raw in item["instances"][0]["rows"]]
    ck(len(rows) == 72, f"{arm} full selected depot collection")
    prior = rows[9]
    ck(prior["STINT"] == 4.5 and prior["ETINT"] == 5 and (prior["STSZ"], prior["STOHA"], prior["NBO"], prior["NRO"]) == (4, 4, 0, 0), f"{arm} immediately prior bin")
    for i in range(10, 20):
        row = rows[i]
        ck((row["IID"], row["STID"], row["STINT"], row["ETINT"], row["STSZ"], row["STOHA"], row["NBO"], row["NRO"]) == ("TEACH-DU-01", "DEPOT-01", i / 2, (i + 1) / 2, 4, 4, 0, 0), f"{arm} exact interval bin {i}")
    boundary = rows[20]
    ck((boundary["STINT"], boundary["ETINT"], boundary["STSZ"], boundary["STOHA"], boundary["NBO"], boundary["NRO"]) == (10, 10.5, 4, 3, 0, int(arm == "change")), f"{arm} first h10 boundary bin")

result = {
    "schema": "independent-i07-var05-source-bound-review/v1",
    "decision": "GO_BOUNDED" if all(ok for ok, _ in checks) else "NO_GO",
    "passed": sum(ok for ok, _ in checks),
    "total": len(checks),
    "failures": [label for ok, label in checks if not ok],
    "accepted_run_id": pins["run_id"],
    "accepted_closure_sha256": sha(RUN / "closure.json"),
    "accepted_report_sha256": {a: sha(RUN / f"{a}-report-raw.json") for a in inputs},
    "checker_diagnostic": "The retained first-pass author result failed only its source/raw inventory count (113/114); this replay inventories all 15 indexed source files and 22 sealed raw files directly. No new native run was made.",
    "claim": "In this accepted pair, the child alone schedules ROSIZ1 at h5; both arms have no depot item-stock demand, transfer, order, or movement in [5,10), and ten half-hour depot bins per arm remain nominal4/on-hand4/NBO0/NRO0. The first depot issue occurs at h10.",
    "limits": "No new native run. Mission/system events occur inside [5,10), including mission activation at h7 and failure at h9.8829; the window is item-stock demand-free only. The scheduled change is source-bound because the log does not separately print parameter application. No full-horizon no-demand or general no-spontaneous-order claim.",
}
(HERE / "review" / "independent-verdict.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"{result['decision']} {result['passed']}/{result['total']}")
for label in result["failures"]:
    print("FAIL", label)
