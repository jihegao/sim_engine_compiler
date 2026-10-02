"""Independent read-only replay of the I02.var12 OUT TFDT counterexample."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUNS = CASE / "runs"
PARENT = ROOT / "I02-var02-out-transfer-v1.0.0"
PARENT_SOURCE = PARENT / "native-input.json"
NATIVE = RUNS / "i02-var12-out-delay2-v100-ssh-20261002-01"
ITEM = RUNS / "i02-var12-depot-item-v100-ssh-20261002-01"
PARENT_NATIVE = PARENT / "runs/i02-var02-out-v100-ssh-20261002-01"
PARENT_ITEM = PARENT / "runs/i02-var02-item-results-v100-ssh-20261002-01"
OUT = CASE / "review/independent-readonly-2026-10-02.json"
failures: list[str] = []
checks = 0


def ck(label: str, condition: bool) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def sha(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def js(file: Path):
    raw = file.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", raw))


def table_map(doc, kind="model"):
    return {table["name"]: table for table in doc[kind]["tables"]}


def rows(table):
    columns = [column["name"] for column in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def report(file: Path):
    return {name: table for name, table in table_map(js(file), "report").items()
            if name != "ProblemDescription"}


def guard(invocation: dict, label: str) -> None:
    ck(f"{label} session0 SSH", invocation.get("execution_mode") == "ssh_cli_v1"
       and invocation.get("session_id") == 0 and "sshd.exe" in invocation.get("ssh_ancestor_names", []))
    ck(f"{label} mutex", invocation.get("queue_mutex") == r"Global\SimloxIssue18NativeQueue")
    ck(f"{label} GUI identity", invocation.get("gui", {}).get("pid") == 13340
       and invocation.get("gui", {}).get("session_id") == 1)


def sealed(directory: Path, closure: dict, label: str) -> int:
    for filename, seal in closure["raw"].items():
        file = directory / filename
        ck(f"{label} {filename} exists", file.is_file())
        if file.is_file():
            ck(f"{label} {filename} size", file.stat().st_size == seal["bytes"])
            ck(f"{label} {filename} SHA", sha(file) == seal["sha256"])
    return len(closure["raw"])


contract, exact = js(CASE / "contract.json"), js(CASE / "exact-diff.json")
source_file = CASE / "native-input.json"
parent, child = table_map(js(PARENT_SOURCE)), table_map(js(source_file))
ck("accepted OUT parent SHA", sha(PARENT_SOURCE) == contract["direct_parent"]["source_sha256"]
   == exact["parent_sha256"])
ck("child source SHA", sha(source_file) == contract["source_sha256"] == exact["child_sha256"])
ck("exact diff SHA", sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
actual_diff = {name for name in set(parent) | set(child) if parent.get(name) != child.get(name)}
ck("exact source table delta", actual_diff == {"ItemTransfer", "ProblemDescription"}
   == set(exact["changed_tables"]))
parent_rows, child_rows = rows(parent["ItemTransfer"]), rows(child["ItemTransfer"])
ck("h4 IN row fixed", parent_rows[0] == child_rows[0] and list(child["ItemTransfer"]["instances"][0]["rows"][0])
   == exact["fixed_in_row"])
ck("OUT TFDT-only row delta", len(parent_rows) == len(child_rows) == 2
   and parent_rows[1]["TFDT"] == 0 and child_rows[1]["TFDT"] == 2
   and {k: v for k, v in parent_rows[1].items() if k != "TFDT"}
   == {k: v for k, v in child_rows[1].items() if k != "TFDT"})
ck("OUT geometry", child_rows[1]["STFID"] == "DEPOT-01" and child_rows[1]["STTID"] == "<OUTSIDE>"
   and child_rows[1]["IID"] == "TEACH-LRU-01" and child_rows[1]["TFTIME"] == 6
   and child_rows[1]["TFQTY"] == 1)
ck("description-only other delta", rows(parent["ProblemDescription"])[0]["PDESC"]
   == exact["description_delta"][0] and rows(child["ProblemDescription"])[0]["PDESC"]
   == exact["description_delta"][1])

installed = {
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
for key, pin in (("manual", "manual_pdf"), ("dictionary", "table_dictionary"),
                 ("simlox_exe", "simlox_exe")):
    ck(f"installed {key} fingerprint", sha(installed[key]) == contract["installed_source_sha256"][pin])

native_inv, closure = js(NATIVE / "invocation.json"), js(NATIVE / "closure.json")
ck("native invocation SHA", closure["invocation_sha256"] == sha(NATIVE / "invocation.json"))
ck("native stable source hashes", native_inv["source_hashes_before"]
   == closure["source_hashes_before"] == closure["source_hashes_after"])
guard(native_inv, "native")
pins = {
    "input": source_file, "parent": PARENT_SOURCE, "contract": CASE / "contract.json",
    "manual": installed["manual"], "dictionary": installed["dictionary"],
    "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
    "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
    "python": installed["python"], "runner_script": CASE / "run_native_ssh.ps1",
    "simlox_exe": installed["simlox_exe"],
}
for key, file in pins.items():
    ck(f"native source seal {key}", closure["source_hashes_before"][key] == sha(file))
ck("native original source copy", sha(NATIVE / "input.json") == sha(source_file))
raw_count = sealed(NATIVE, closure, "native")
steps = js(NATIVE / "steps.json")
ck("five guarded native steps", [step["name"] for step in steps]
   == ["import", "export", "calc", "jsonreport", "check_import_export"])
for step in steps:
    ck(f"native {step['name']} success", step["exit_code"] == 0
       and step["error"] is None and step["gui_preserved"] is True)
ck("valid model SXO", (NATIVE / "model.sxo").stat().st_size > 4)
runlog = (NATIVE / "run.log").read_text(encoding="cp1252")
ck("zero converter errors", "Input conversion completed. Errors: 0, Warnings: 1" in runlog
   and "(warning #108)" in runlog and "(error #" not in runlog)
exported = table_map(js(NATIVE / "roundtrip-raw.json"))
populated = {name: table for name, table in child.items() if rows(table)}
ck("22 authored tables with rows", len(populated) == 22)
for name, table in populated.items():
    ck(f"exact import/export {name}", exported.get(name) == table)

child_log = (NATIVE / "model.log").read_text(encoding="cp1252")
parent_log = (PARENT_NATIVE / "model.log").read_text(encoding="cp1252")
events = [
    "Time: 4  item transfer task 0 (IN)  arrives with 1 items",
    "Time: 6  item transfer task 1 (OUT)  created: starting from <TEACH-LRU-01,0,DEPOT-01,0>",
    "Time: 6 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
    "Time: 6  item transfer task 1 (OUT)  starts with 1 items, transfer time: 2",
    "Time: 8  item transfer task 1 (OUT)  arrives with 1 items",
    "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,1> from stock",
    "Time: 12.3333 <TEACH-AIR-01,BASE-01,0> System ready",
    "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,2>",
]
positions = [child_log.find(event) for event in events]
for event, position in zip(events, positions):
    ck(f"native event {event[:63]}", position >= 0)
ck("native physical event order", positions == sorted(positions))
ck("no child OUT arrival h6", "Time: 6  item transfer task 1 (OUT)  arrives with 1 items" not in child_log)
ck("accepted zero-delay OUT arrives h6", "Time: 6  item transfer task 1 (OUT)  arrives with 1 items" in parent_log)
ck("parent OUT starts transfer time zero", "Time: 6  item transfer task 1 (OUT)  starts with 1 items, transfer time: 0" in parent_log)
for mission, start, end, outcome in ((0, 8, 10, "aborted mission completed"),
                                     (1, 20, 22, "mission completed"),
                                     (2, 32, 34, "mission completed")):
    ident = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mission}>"
    ck(f"mission {mission} launch", f"Time: {start} {ident} mission starting" in child_log)
    ck(f"mission {mission} end", f"Time: {end} {ident} {outcome}" in child_log)

native_report = report(NATIVE / "report-raw.json")
parent_report = report(PARENT_NATIVE / "report-raw.json")
ck("default business report table equality", native_report == parent_report)
ck("default report tables", set(native_report) == {"ResultSummary", "SystemResults", "StockTotalResults"})
for name in ("SystemResults", "StockTotalResults"):
    series = rows(native_report[name])
    ck(f"default {name} 72 bins", len(series) == 72)
    for i, row in enumerate(series):
        ck(f"default {name} bin {i} interval", row["STINT"] == i / 2
           and row["ETINT"] == (i + 1) / 2)
summary = rows(native_report["ResultSummary"])[0]
ck("one replication and two-thirds missions", summary["NREP"] == 1
   and abs(summary["MSUF"] - 2 / 3) < 1e-6)
ck("one ready terminal aircraft", rows(native_report["SystemResults"])[-1]["NSYRY"] == 1)

item_inv, item_closure = js(ITEM / "invocation.json"), js(ITEM / "closure.json")
ck("selected invocation SHA", item_closure["invocation_sha256"] == sha(ITEM / "invocation.json"))
ck("selected native closure binding", item_inv["source_closure_sha256"] == sha(NATIVE / "closure.json"))
ck("selected stable source hashes", item_inv["source_hashes_before"]
   == item_closure["source_hashes_before"] == item_closure["source_hashes_after"])
guard(item_inv, "selected")
item_pins = {
    "sxo": NATIVE / "model.sxo",
    "settings": RUNS / "report-settings/item-position-results.sxs",
    "exe": installed["simlox_exe"], "runner": CASE / "report_native_ssh.ps1",
}
for key, file in item_pins.items():
    ck(f"selected source seal {key}", item_closure["source_hashes_before"][key] == sha(file))
ck("selected report command", "-rpts" in item_inv["arguments"]
   and "-rjexport" in item_inv["arguments"]
   and str(item_pins["settings"]) in item_inv["arguments"])
ck("selected export success", item_closure["exit_code"] == 0 and item_closure["error"] is None)
raw_count += sealed(ITEM, item_closure, "selected")
selected = report(ITEM / "item-report-raw.json")
prior = report(PARENT_ITEM / "item-report-raw.json")
ck("all selected business report tables equal parent", selected == prior)
item_rows = rows(selected["ItemResults"])
ck("72 depot item bins", len(item_rows) == 72)
for i, row in enumerate(item_rows):
    ck(f"item bin {i} interval and position", row["IID"] == "TEACH-LRU-01"
       and row["STID"] == "DEPOT-01" and row["STINT"] == i / 2
       and row["ETINT"] == (i + 1) / 2)
ck("h4 IN stock rise", item_rows[7]["STSZ"] == item_rows[7]["STOHA"] == 1
   and item_rows[8]["STSZ"] == item_rows[8]["STOHA"] == 2)
ck("h6 physical issue despite OUT completion h8", item_rows[11]["STSZ"] == item_rows[11]["STOHA"] == 2
   and item_rows[12]["STSZ"] == item_rows[12]["STOHA"] == 1
   and item_rows[16]["STSZ"] == item_rows[16]["STOHA"] == 1)
ck("ordinary h10 issue and h13 repair return", item_rows[19]["STOHA"] == 1
   and item_rows[20]["STOHA"] == 0 and item_rows[27]["STOHA"] == 1)
ck("terminal depot level and no backorder", item_rows[-1]["STSZ"] == item_rows[-1]["STOHA"] == 1
   and item_rows[-1]["NBO"] == 0)
ck("14 child raw seals", raw_count == 14)

result = {
    "schema": "independent-i02-var12-out-delay-review/v1",
    "passed": not failures,
    "verdict": ("RESTRICTED GO for bounded OUT timing counterexample; NO-GO for literal TFDT-ignored completion claim"
                if not failures else "NO-GO: independent replay failed"),
    "checks_passed": checks - len(failures), "checks_total": checks, "failures": failures,
    "raw_seals_checked": raw_count,
    "source_sha256": sha(source_file),
    "native_closure_sha256": sha(NATIVE / "closure.json"),
    "selected_report_closure_sha256": sha(ITEM / "closure.json"),
    "observations": {
        "physical_out": "Depot ID0 is issued at h6 in both arms. TFDT2 child OUT task starts h6 and arrives outside h8; TFDT0 parent arrives outside h6.",
        "depot_counter": "Native depot ItemResults.STSZ/STOHA fall 2 to1 in h6 bin in both arms; all 72 item bins and selected business tables match.",
        "downstream": "Ordinary h10 issue, h13.1667 repair return, all default business tables, mission outcomes and terminal ready1/depot stock1 match parent.",
    },
    "limits": [
        "The installed manual p478 literal 'ignored for OUT' is contradicted for task completion time in this one TFDT2 run, while depot issue timing is unchanged.",
        "One available unit OUT after h4 IN, one IID/depot, fixed seed; no shortage, other duration, standalone OUT, GUI visual or cross-engine claim.",
    ],
}
OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                  "checks_total": checks, "failures": failures}, ensure_ascii=False))
sys.exit(0 if not failures else 1)
