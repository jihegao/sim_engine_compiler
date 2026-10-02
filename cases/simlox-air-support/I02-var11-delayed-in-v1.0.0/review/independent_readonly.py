"""Independent read-only replay of one scheduled two-hour IN transfer."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUNS = CASE / "runs"
PARENT = ROOT / "I02-var01-in-transfer-v1.0.2"
PARENT_SOURCE = PARENT / "native-input.json"
NATIVE = RUNS / "i02-var11-in-delay2-v100-ssh-20261002-01"
ITEM = RUNS / "i02-var11-depot-item-v100-ssh-20261002-01"
PARENT_NATIVE = PARENT / "runs/i02-var01-in-v102-ssh-20261002-01"
PARENT_ITEM = PARENT / "runs/i02-var01-item-results-v102-ssh-20261002-01"
OUT = CASE / "review/independent-readonly-2026-10-02.json"
failures: list[str] = []
total = 0


def ck(label: str, value: bool) -> None:
    global total
    total += 1
    if not value:
        failures.append(label)


def sha(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def read(file: Path):
    text = file.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text))


def tables(document, kind="model"):
    return {table["name"]: table for table in document[kind]["tables"]}


def rows(table):
    fields = [column["name"] for column in table["columns"]]
    return [dict(zip(fields, row)) for instance in table["instances"] for row in instance["rows"]]


def business(file: Path):
    return {name: table for name, table in tables(read(file), "report").items()
            if name != "ProblemDescription"}


def raw_seals(directory: Path, closure: dict, label: str) -> int:
    for name, seal in closure["raw"].items():
        file = directory / name
        ck(f"{label} raw {name} exists", file.is_file())
        if file.is_file():
            ck(f"{label} raw {name} bytes", file.stat().st_size == seal["bytes"])
            ck(f"{label} raw {name} SHA", sha(file) == seal["sha256"])
    return len(closure["raw"])


def provenance(invocation: dict, label: str) -> None:
    ck(f"{label} session0 SSH", invocation.get("execution_mode") == "ssh_cli_v1"
       and invocation.get("session_id") == 0 and "sshd.exe" in invocation.get("ssh_ancestor_names", []))
    ck(f"{label} queue mutex", invocation.get("queue_mutex") == r"Global\SimloxIssue18NativeQueue")
    ck(f"{label} GUI identity", invocation.get("gui", {}).get("pid") == 13340
       and invocation.get("gui", {}).get("session_id") == 1)


contract, diff = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
source_file = CASE / "native-input.json"
parent, child = tables(read(PARENT_SOURCE)), tables(read(source_file))
ck("accepted source parent SHA", sha(PARENT_SOURCE) == contract["direct_parent"]["source_sha256"]
   == diff["parent_sha256"])
ck("child source SHA", sha(source_file) == contract["source_sha256"] == diff["child_sha256"])
ck("diff source SHA", sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
changed = {name for name in set(parent) | set(child) if parent.get(name) != child.get(name)}
ck("exact parent delta tables", changed == {"ItemTransfer", "ProblemDescription"}
   == set(diff["changed_tables"]))
before, after = rows(parent["ItemTransfer"])[0], rows(child["ItemTransfer"])[0]
ck("TFDT only on transfer row", before["TFDT"] == 0 and after["TFDT"] == 2
   and {k: v for k, v in before.items() if k != "TFDT"}
   == {k: v for k, v in after.items() if k != "TFDT"})
ck("bounded IN source topology", after["STFID"] == "<OUTSIDE>" and after["STTID"] == "DEPOT-01"
   and after["IID"] == "TEACH-LRU-01" and after["TFTIME"] == 4 and after["TFQTY"] == 1)
ck("description-only other delta", rows(parent["ProblemDescription"])[0]["PDESC"]
   == diff["description_delta"][0] and rows(child["ProblemDescription"])[0]["PDESC"]
   == diff["description_delta"][1])

installed = {
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
for key, pin in (("manual", "manual_pdf"), ("dictionary", "table_dictionary"),
                 ("simlox_exe", "simlox_exe")):
    ck(f"installed {key} SHA", sha(installed[key]) == contract["installed_source_sha256"][pin])

native_inv, native_closure = read(NATIVE / "invocation.json"), read(NATIVE / "closure.json")
ck("native invocation closure SHA", native_closure["invocation_sha256"] == sha(NATIVE / "invocation.json"))
ck("native source frozen before/after", native_inv["source_hashes_before"]
   == native_closure["source_hashes_before"] == native_closure["source_hashes_after"])
provenance(native_inv, "native")
pins = {
    "input": source_file, "parent": PARENT_SOURCE, "contract": CASE / "contract.json",
    "manual": installed["manual"], "dictionary": installed["dictionary"],
    "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
    "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
    "python": installed["python"], "runner_script": CASE / "run_native_ssh.ps1",
    "simlox_exe": installed["simlox_exe"],
}
for key, file in pins.items():
    ck(f"native source seal {key}", native_closure["source_hashes_before"][key] == sha(file))
ck("native input copy", sha(NATIVE / "input.json") == sha(source_file))
seal_count = raw_seals(NATIVE, native_closure, "native")
steps = read(NATIVE / "steps.json")
ck("five native steps", [step["name"] for step in steps]
   == ["import", "export", "calc", "jsonreport", "check_import_export"])
for step in steps:
    ck(f"native {step['name']} successful", step["exit_code"] == 0
       and step["error"] is None and step["gui_preserved"] is True)
ck("valid SXO", (NATIVE / "model.sxo").stat().st_size > 4)
runlog = (NATIVE / "run.log").read_text(encoding="cp1252")
ck("zero conversion errors", "Input conversion completed. Errors: 0, Warnings: 1" in runlog
   and "(warning #108)" in runlog and "(error #" not in runlog)
exported = tables(read(NATIVE / "roundtrip-raw.json"))
populated = {name: table for name, table in child.items() if rows(table)}
ck("22 authored row tables", len(populated) == 22)
for name, table in populated.items():
    ck(f"exact source roundtrip {name}", exported.get(name) == table)

log = (NATIVE / "model.log").read_text(encoding="cp1252")
events = [
    "Time: 4  item transfer task 0 (IN)  created: aiming for <TEACH-LRU-01,0,DEPOT-01,0>",
    "Time: 4  item transfer task 0 (IN)  starts with 1 items, transfer time: 2",
    "Time: 6  item transfer task 0 (IN)  arrives with 1 items",
    "Time: 6 <TEACH-LRU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-LRU-01,0,1>",
    "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
    "Time: 12.3333 <TEACH-AIR-01,BASE-01,0> System ready",
    "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,2>",
]
locations = [log.find(event) for event in events]
for event, location in zip(events, locations):
    ck(f"native event {event[:64]}", location >= 0)
ck("event order", locations == sorted(locations))
ck("no premature arrival at h4", "Time: 4 <TEACH-LRU-01,0,DEPOT-01,0> Replacement item arrives" not in log)
parent_log = (PARENT_NATIVE / "model.log").read_text(encoding="cp1252")
ck("zero-delay control arrival at h4", "Time: 4  item transfer task 0 (IN)  arrives with 1 items" in parent_log)
for mission, launch, completion, outcome in ((0, 8, 10, "aborted mission completed"),
                                             (1, 20, 22, "mission completed"),
                                             (2, 32, 34, "mission completed")):
    identity = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mission}>"
    ck(f"mission {mission} start", f"Time: {launch} {identity} mission starting" in log)
    ck(f"mission {mission} end", f"Time: {completion} {identity} {outcome}" in log)

native_report = business(NATIVE / "report-raw.json")
parent_report = business(PARENT_NATIVE / "report-raw.json")
ck("default business reports equal parent", native_report == parent_report)
ck("default report table set", set(native_report) == {"ResultSummary", "SystemResults", "StockTotalResults"})
for name in ("SystemResults", "StockTotalResults"):
    actual = rows(native_report[name])
    ck(f"72 default {name} bins", len(actual) == 72)
    for i, row in enumerate(actual):
        ck(f"default {name} interval {i}", row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2)
summary = rows(native_report["ResultSummary"])[0]
ck("one-rep two-thirds mission success", summary["NREP"] == 1
   and abs(summary["MSUF"] - 2 / 3) < 1e-6)
ck("terminal aircraft ready", rows(native_report["SystemResults"])[-1]["NSYRY"] == 1)

item_inv, item_closure = read(ITEM / "invocation.json"), read(ITEM / "closure.json")
ck("selected invocation SHA", item_closure["invocation_sha256"] == sha(ITEM / "invocation.json"))
ck("selected SXO provenance", item_inv["source_closure_sha256"] == sha(NATIVE / "closure.json"))
ck("selected source frozen before/after", item_inv["source_hashes_before"]
   == item_closure["source_hashes_before"] == item_closure["source_hashes_after"])
provenance(item_inv, "selected")
selected_pins = {
    "sxo": NATIVE / "model.sxo",
    "settings": RUNS / "report-settings/item-position-results.sxs",
    "exe": installed["simlox_exe"], "runner": CASE / "report_native_ssh.ps1",
}
for key, file in selected_pins.items():
    ck(f"selected source seal {key}", item_closure["source_hashes_before"][key] == sha(file))
ck("selected report command, no fallback", "-rpts" in item_inv["arguments"]
   and "-rjexport" in item_inv["arguments"]
   and str(selected_pins["settings"]) in item_inv["arguments"])
ck("selected export exit", item_closure["exit_code"] == 0 and item_closure["error"] is None)
seal_count += raw_seals(ITEM, item_closure, "selected")
selected = business(ITEM / "item-report-raw.json")
prior = business(PARENT_ITEM / "item-report-raw.json")
ck("selected report tables", set(selected) == set(prior) and "ItemResults" in selected)
for name in selected:
    if name not in ("ItemResults", "ItemResultsTotal"):
        ck(f"selected downstream {name} equals parent", selected[name] == prior[name])
item_rows, parent_rows = rows(selected["ItemResults"]), rows(prior["ItemResults"])
ck("72 depot ItemResults bins", len(item_rows) == len(parent_rows) == 72)
for i, (row, reference) in enumerate(zip(item_rows, parent_rows)):
    ck(f"item bin {i} interval/identity", row["IID"] == "TEACH-LRU-01"
       and row["STID"] == "DEPOT-01" and row["STINT"] == i / 2
       and row["ETINT"] == (i + 1) / 2)
    ck(f"item bin {i} exact parent contrast", (row == reference) == (i not in (8, 9, 10, 11)))
    if i in (8, 9, 10, 11):
        ck(f"item bin {i} nominal/on-hand 1 versus 2", row["STSZ"] == row["STOHA"] == 1
           and reference["STSZ"] == reference["STOHA"] == 2
           and {k: v for k, v in row.items() if k not in ("STSZ", "STOHA")}
           == {k: v for k, v in reference.items() if k not in ("STSZ", "STOHA")})
ck("h6 synchronized nominal/on-hand rise", item_rows[12]["STSZ"] == item_rows[12]["STOHA"] == 2)
ck("depot terminal nominal/on-hand 2", item_rows[-1]["STSZ"] == item_rows[-1]["STOHA"] == 2
   and item_rows[-1]["NBO"] == 0)
ck("14 child raw file seals", seal_count == 14)

result = {
    "schema": "independent-i02-var11-delayed-in-review/v1",
    "passed": not failures,
    "verdict": "GO: bounded one-unit TFDT2 delayed IN versus accepted TFDT0 control" if not failures
               else "NO-GO: independent replay failed",
    "checks_passed": total - len(failures), "checks_total": total, "failures": failures,
    "raw_seals_checked": seal_count,
    "source_sha256": sha(source_file),
    "native_closure_sha256": sha(NATIVE / "closure.json"),
    "selected_report_closure_sha256": sha(ITEM / "closure.json"),
    "observations": {
        "physical": "The h4 IN task starts with one item, physically arrives at depot h6; TFDT0 parent arrives h4.",
        "item_results": "Only depot half-hour bins h4–6 differ: child STSZ/STOHA=1, parent=2; both rise together to2 at h6.",
        "downstream": "Selected business tables outside ItemResults/ItemResultsTotal and all default business tables equal the accepted parent; later mission and repair outcomes coincide.",
        "terminal": "Depot STSZ/STOHA2 and NBO0, one aircraft ready, two of three missions successful.",
    },
    "limits": ["One tracked IID, one depot, one IN, TFDT2 versus TFDT0, one seed and horizon.",
               "No claim about other transfer directions, delays, shortage, reorder, GUI rendering, or cross-engine behavior."],
}
OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                  "checks_total": total, "failures": failures}, ensure_ascii=False))
sys.exit(0 if not failures else 1)
