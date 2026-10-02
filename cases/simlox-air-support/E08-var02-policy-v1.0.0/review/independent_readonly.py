"""Independent, read-only replay of the E08.var02 EXTENDED/ADJACENT evidence."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUNS = CASE / "runs"
PARENT = ROOT / "E08-var01-immediate-lateral-v1.0.2"
OUT = CASE / "review/independent-readonly-2026-10-02.json"
IDS = {v: f"e08-{v}-v100-ssh-20261002-01" for v in ("extended", "adjacent")}
STATIONS = {"base-01": "base01", "base-02": "base02", "depot": "depot"}
errors: list[str] = []
count = 0


def check(label: str, condition: bool) -> None:
    global count
    count += 1
    if not condition:
        errors.append(label)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    # Native exports sometimes include trailing commas.
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text))


def table_map(doc, kind="model"):
    return {t["name"]: t for t in doc[kind]["tables"]}


def records(table):
    keys = [column["name"] for column in table["columns"]]
    return [dict(zip(keys, row)) for instance in table["instances"] for row in instance["rows"]]


def semantic_report(path: Path):
    return {name: table for name, table in table_map(load(path), "report").items()
            if name != "ProblemDescription"}


def sealed_files(directory: Path, closure: dict, prefix: str) -> int:
    for name, seal in closure["raw"].items():
        path = directory / name
        check(f"{prefix} raw {name} exists", path.is_file())
        if path.is_file():
            check(f"{prefix} raw {name} bytes", path.stat().st_size == seal["bytes"])
            check(f"{prefix} raw {name} SHA", digest(path) == seal["sha256"])
    return len(closure["raw"])


def guard(invocation: dict, label: str) -> None:
    check(f"{label} session-zero SSH", invocation.get("execution_mode") == "ssh_cli_v1"
          and invocation.get("session_id") == 0 and "sshd.exe" in invocation.get("ssh_ancestor_names", []))
    check(f"{label} exclusive queue", invocation.get("queue_mutex") == r"Global\SimloxIssue18NativeQueue")
    gui = invocation.get("gui", {})
    check(f"{label} preserved GUI identity", gui.get("pid") == 13340 and gui.get("session_id") == 1)


contract = load(CASE / "contract.json")
diff = load(CASE / "exact-diff.json")
parent_source = PARENT / "on-input.json"
source_files = {v: CASE / f"{v}-input.json" for v in IDS}
parent_tables = table_map(load(parent_source))
source_tables = {v: table_map(load(path)) for v, path in source_files.items()}
check("accepted IMMEDIATE ON parent SHA", digest(parent_source) == contract["parent_source_sha256"] == diff["parent_sha256"])
check("frozen exact-diff SHA", digest(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
check("installed manual SHA", digest(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) == contract["manual_pdf_sha256"])
check("installed dictionary SHA", digest(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")) == contract["dictionary_sha256"])
for variant in IDS:
    source = source_tables[variant]
    check(f"{variant} source SHA", digest(source_files[variant]) == contract[f"{variant}_source_sha256"]
          == diff["children"][variant]["source_sha256"])
    changes = {name for name in set(source) | set(parent_tables) if source.get(name) != parent_tables.get(name)}
    check(f"{variant} exact table delta", changes == {"LateralSupport", "ProblemDescription"}
          == set(diff["children"][variant]["changed_tables"]))
    before, after = records(parent_tables["LateralSupport"])[0], records(source["LateralSupport"])[0]
    check(f"{variant} LSRUL isolated", before["LSRUL"] == "IMMEDIATE" and after["LSRUL"] == variant.upper()
          and {k: x for k, x in before.items() if k != "LSRUL"} == {k: x for k, x in after.items() if k != "LSRUL"})
    check(f"{variant} source geometry retained", records(source["StationLateralSupport"]) == records(parent_tables["StationLateralSupport"])
          and records(source["StockAllocation"]) == records(parent_tables["StockAllocation"])
          and records(source["Control"]) == records(parent_tables["Control"]))
    check(f"{variant} description only", records(source["ProblemDescription"])[0]["PDESC"]
          == diff["children"][variant]["description_delta"][0][2])
check("policy pair only LSRUL and description", {name for name in source_tables["extended"]
      if source_tables["extended"][name] != source_tables["adjacent"][name]}
      == {"LateralSupport", "ProblemDescription"})

installed = {
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
}
source_paths = {
    "parent": parent_source, "contract": CASE / "contract.json", "manual": installed["manual"],
    "dictionary": installed["dictionary"], "builder": CASE / "build.py",
    "exact_diff": CASE / "exact-diff.json", "diff_checker": CASE / "describe_diff.py",
    "checker": CASE / "check_roundtrip.py", "python": installed["python"],
    "runner_script": CASE / "run_native_ssh.ps1", "simlox_exe": installed["simlox_exe"],
}
parent_off = PARENT / "runs/e08-immediate-off-v102-ssh-20261002-01"
parent_on = PARENT / "runs/e08-immediate-on-v102-ssh-20261002-01"
off_default = semantic_report(parent_off / "report-raw.json")
on_default = semantic_report(parent_on / "report-raw.json")
native_reports = {}
raw_seals = 0
closure_sha = {}

for variant, run_id in IDS.items():
    directory = RUNS / run_id
    invocation, closure = load(directory / "invocation.json"), load(directory / "closure.json")
    closure_sha[variant] = digest(directory / "closure.json")
    check(f"{variant} invocation seal", closure["invocation_sha256"] == digest(directory / "invocation.json"))
    check(f"{variant} stable source closure", invocation["source_hashes_before"]
          == closure["source_hashes_before"] == closure["source_hashes_after"])
    guard(invocation, variant)
    for key, path in {"input": source_files[variant], **source_paths}.items():
        check(f"{variant} source pin {key}", closure["source_hashes_before"][key] == digest(path))
    check(f"{variant} original input copy", digest(directory / "input.json") == digest(source_files[variant]))
    raw_seals += sealed_files(directory, closure, variant)
    steps = load(directory / "steps.json")
    check(f"{variant} five steps", [step["name"] for step in steps]
          == ["import", "export", "calc", "jsonreport", "check_import_export"])
    for step in steps:
        check(f"{variant} step {step['name']} success/GUI", step["exit_code"] == 0
              and step["error"] is None and step["gui_preserved"] is True)
    check(f"{variant} substantive SXO", (directory / "model.sxo").stat().st_size > 4)
    run_log = (directory / "run.log").read_text(encoding="cp1252")
    check(f"{variant} conversion errors zero", "Input conversion completed. Errors: 0, Warnings: 1" in run_log
          and "(error #" not in run_log and "(warning #108)" in run_log)
    original = source_tables[variant]
    exported = table_map(load(directory / "roundtrip-raw.json"))
    populated = {name: table for name, table in original.items() if records(table)}
    check(f"{variant} 24 populated tables", len(populated) == 24)
    for name, table in populated.items():
        check(f"{variant} exact native row roundtrip {name}", exported.get(name) == table)
    report = semantic_report(directory / "report-raw.json")
    native_reports[variant] = report
    check(f"{variant} default report table set", set(report) == {"ResultSummary", "SystemResults", "StockTotalResults"})
    for name in report:
        check(f"{variant} default {name} equals accepted OFF", report[name] == off_default[name])
    check(f"{variant} default differs from accepted ON", report["SystemResults"] != on_default["SystemResults"])
    for name in ("SystemResults", "StockTotalResults"):
        entries = records(report[name])
        check(f"{variant} 72 {name} bins", len(entries) == 72)
        for i, row in enumerate(entries):
            check(f"{variant} {name} bin {i} interval", row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2)
    summary = records(report["ResultSummary"])[0]
    check(f"{variant} one-rep summary success", summary["NREP"] == 1 and abs(summary["MSUF"] - 2 / 3) < 1e-6)
    system = records(report["SystemResults"])
    check(f"{variant} h10–11 not ready, h11.5 ready", system[20]["NSYRY"] == 0
          and system[21]["NSYRY"] == 0 and system[23]["NSYRY"] == 1 and system[-1]["NSYRY"] == 1)

    log = (directory / "model.log").read_text(encoding="cp1252")
    events = [
        "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Lateral support check, cancelled due to free items in chain",
        "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
        "Time: 10  transport task 0 created from <DEPOT-01,0> to <BASE-01,0>",
        "Time: 10  transport task 0 starts with 1 items/systems, transport time: 1",
        "Time: 11  transport task 0 arrives with 1 items/systems",
        "Time: 11 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>",
        "Time: 11 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 1",
        "Time: 11.3333 <TEACH-AIR-01,BASE-01,0> System ready",
        "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,2>",
        "Time: 14.1667 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,2>",
    ]
    positions = [log.find(event) for event in events]
    for event, position in zip(events, positions):
        check(f"{variant} event {event[:60]}", position >= 0)
    check(f"{variant} event chronology", positions == sorted(positions))
    check(f"{variant} no peer stock issue/route", "Take replacement item <TEACH-LRU-01,0,1> from stock" not in log
          and "transport task 0 created from <BASE-02,0>" not in log)
    for mission_id, start, end, outcome in ((0, 8, 10, "aborted mission completed"),
                                             (1, 20, 22, "mission completed"),
                                             (2, 32, 34, "mission completed")):
        identity = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mission_id}>"
        check(f"{variant} mission {mission_id} launch", f"Time: {start} {identity} mission starting" in log)
        check(f"{variant} mission {mission_id} completion", f"Time: {end} {identity} {outcome}" in log)

selected = {}
for variant, run_id in IDS.items():
    native_dir = RUNS / run_id
    native_closure = load(native_dir / "closure.json")
    for station, parent_station in STATIONS.items():
        label = f"{variant}/{station}"
        directory = RUNS / f"e08-{variant}-{station}-report-v100-ssh-20261002-01"
        invocation, closure = load(directory / "invocation.json"), load(directory / "closure.json")
        check(f"{label} invocation seal", closure["invocation_sha256"] == digest(directory / "invocation.json"))
        check(f"{label} source closure binding", invocation["source_closure_sha256"] == digest(native_dir / "closure.json"))
        check(f"{label} stable source hashes", invocation["source_hashes_before"]
              == closure["source_hashes_before"] == closure["source_hashes_after"])
        guard(invocation, label)
        pins = {
            "sxo": native_dir / "model.sxo", "settings": RUNS / "report-settings" / f"{station}-item.sxs",
            "exe": installed["simlox_exe"], "runner": CASE / "report_native_ssh.ps1",
        }
        for key, path in pins.items():
            check(f"{label} selected source {key}", closure["source_hashes_before"][key] == digest(path))
        check(f"{label} selected command", "-rpts" in invocation["arguments"]
              and "-rjexport" in invocation["arguments"] and str(pins["settings"]) in invocation["arguments"])
        check(f"{label} report exit", closure["exit_code"] == 0 and closure["error"] is None)
        raw_seals += sealed_files(directory, closure, label)
        report = semantic_report(directory / "item-report-raw.json")
        selected[variant, station] = report
        check(f"{label} ItemResults present", "ItemResults" in report and "ItemResultsTotal" in report)
        item_rows = records(report["ItemResults"])
        check(f"{label} 72 station bins", len(item_rows) == 72)
        station_id = {"base-01": "BASE-01", "base-02": "BASE-02", "depot": "DEPOT-01"}[station]
        check(f"{label} station identity", all(row["IID"] == "TEACH-LRU-01"
              and row["STID"] == station_id for row in item_rows))
        for i, row in enumerate(item_rows):
            check(f"{label} bin {i} interval", row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2)
        off_dir = PARENT / "runs" / f"e08-off-{parent_station}-report-v102-ssh-20261002-01"
        on_dir = PARENT / "runs" / f"e08-on-{parent_station}-report-v102-ssh-20261002-01"
        off_report = semantic_report(off_dir / "item-report-raw.json")
        on_report = semantic_report(on_dir / "item-report-raw.json")
        for name in report:
            check(f"{label} full {name} equals accepted OFF", report[name] == off_report[name])
        if station in ("base-01", "base-02"):
            check(f"{label} differs from accepted ON ItemResults", report["ItemResults"] != on_report["ItemResults"])
        if station == "base-01":
            check(f"{label} ordinary one-hour backorder", all(item_rows[i]["NBO"] == 1 for i in (20, 21))
                  and all(item_rows[i]["NBO"] == 0 for i in list(range(20)) + list(range(22, 72))))
            check(f"{label} no spare on hand", all(row["STSZ"] == row["STOHA"] == 0 for row in item_rows))
        elif station == "base-02":
            check(f"{label} stocked peer untouched", all(row["STSZ"] == row["STOHA"] == 1 for row in item_rows))
        else:
            check(f"{label} depot spare issue and return", item_rows[19]["STOHA"] == 1
                  and item_rows[20]["STOHA"] == 0 and item_rows[-1]["STOHA"] == 1
                  and all(row["STSZ"] == 1 for row in item_rows))

check("36 child raw seals", raw_seals == 36)
check("EXTENDED and ADJACENT default reports equal", native_reports["extended"] == native_reports["adjacent"])
for station in STATIONS:
    check(f"EXTENDED and ADJACENT {station} selected reports equal",
          selected["extended", station] == selected["adjacent", station])

result = {
    "schema": "independent-e08-var02-policy-review/v1",
    "passed": not errors,
    "verdict": ("GO: bounded EXTENDED/ADJACENT ordinary depot route versus IMMEDIATE lateral route"
                if not errors else "NO-GO: independent replay failed"),
    "checks_passed": count - len(errors), "checks_total": count, "failures": errors,
    "raw_seals_checked": raw_seals,
    "native_closure_sha256": closure_sha,
    "source_sha256": {v: digest(path) for v, path in source_files.items()},
    "observations": {
        "policy_event": "At h10 both logs say lateral check cancelled due to free items in ordinary chain.",
        "physical_route": "Depot ID0 departs h10, arrives BASE-01 h11; BASE-02 ID1 remains in stock.",
        "control_contrast": "Both policy reports equal accepted ENLAT=N OFF tables except description and differ from IMMEDIATE ENLAT=Y ON; ON draws peer ID1 over 0.5 hours.",
        "mission_and_terminal": "First mission aborts at h9.8829, completes h10; later missions succeed h22/h34; one aircraft ready, BASE-02 and DEPOT each retain one spare at h36.",
    },
    "limits": [
        "One stocked next ordinary depot, one stocked lateral peer, one LRU, fixed seed and schedule.",
        "The observed cancellation does not prove behavior with no free ordinary stock, a deeper chain, multiple peers, delayed lateral support, or other failure timing.",
        "No GUI visual rendering or cross-engine parity claim.",
    ],
}
OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                  "checks_total": count, "failures": errors, "output": str(OUT)}, ensure_ascii=False))
sys.exit(0 if not errors else 1)
