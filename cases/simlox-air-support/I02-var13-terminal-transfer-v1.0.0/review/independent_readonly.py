"""Independent read-only replay of two I02.var13 endpoint transfer states."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUNS = CASE / "runs"
OUT = CASE / "review/independent-readonly-2026-10-02.json"
ARMS = {"transit": (7, 14), "backorder": (3, 6)}
STATIONS = ("base", "depot")
failures: list[str] = []
checks = 0


def ck(label: str, okay: bool) -> None:
    global checks
    checks += 1
    if not okay:
        failures.append(label)


def sha(file: Path) -> str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def load(file: Path):
    raw = file.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", raw))


def table_map(doc, kind="model"):
    return {table["name"]: table for table in doc[kind]["tables"]}


def records(table):
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def report(file: Path):
    return {name: table for name, table in table_map(load(file), "report").items()
            if name != "ProblemDescription"}


def guard(invocation: dict, label: str) -> None:
    ck(f"{label} session0 SSH", invocation.get("execution_mode") == "ssh_cli_v1"
       and invocation.get("session_id") == 0 and "sshd.exe" in invocation.get("ssh_ancestor_names", []))
    ck(f"{label} native queue", invocation.get("queue_mutex") == r"Global\SimloxIssue18NativeQueue")
    ck(f"{label} GUI identity", invocation.get("gui", {}).get("pid") == 13340
       and invocation.get("gui", {}).get("session_id") == 1)


def raw(directory: Path, closure: dict, label: str) -> int:
    for filename, pin in closure["raw"].items():
        file = directory / filename
        ck(f"{label} {filename} exists", file.is_file())
        if file.is_file():
            ck(f"{label} {filename} bytes", file.stat().st_size == pin["bytes"])
            ck(f"{label} {filename} SHA", sha(file) == pin["sha256"])
    return len(closure["raw"])


contract, diff = load(CASE / "contract.json"), load(CASE / "exact-diff.json")
inputs = {arm: CASE / f"{arm}-input.json" for arm in ARMS}
parent_files = {arm: ROOT / contract["arms"][arm]["accepted_parent"] for arm in ARMS}
children = {arm: table_map(load(file)) for arm, file in inputs.items()}
parents = {arm: table_map(load(file)) for arm, file in parent_files.items()}
installed = {
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
ck("distinct accepted source parents", parent_files["transit"] != parent_files["backorder"])
for arm, (endpoint, bins) in ARMS.items():
    parent, child = parents[arm], children[arm]
    ck(f"{arm} parent SHA", sha(parent_files[arm]) == contract["arms"][arm]["parent_sha256"]
       == diff[arm]["parent_sha256"])
    ck(f"{arm} child SHA", sha(inputs[arm]) == contract["arms"][arm]["input_sha256"]
       == diff[arm]["input_sha256"])
    changed = {name for name in set(parent) | set(child) if parent.get(name) != child.get(name)}
    ck(f"{arm} exact four changed tables", changed == {"Control", "OperationProfile",
       "ProblemDescription", "ResultCollection"} == set(diff[arm]["changed_tables"]))
    ck(f"{arm} transfer business source unchanged", child["ItemTransfer"] == parent["ItemTransfer"]
       and child["StockAllocation"] == parent["StockAllocation"]
       and child["Item"] == parent["Item"])
    transfer = records(child["ItemTransfer"])
    ck(f"{arm} request timing", any(row["STFID"] == "DEPOT-01"
       and row["STTID"] == "BASE-01" and row["TFTIME"] == contract["arms"][arm]["schedule_hour"]
       and row["TFDT"] == contract["arms"][arm]["transfer_duration_hours"]
       for row in transfer))
    before_control, after_control = records(parent["Control"])[0], records(child["Control"])[0]
    ck(f"{arm} Control endpoint-only fields", before_control["SIMPE"] == before_control["RCEND"] == 36
       and after_control["SIMPE"] == after_control["RCEND"] == endpoint
       and {key: value for key, value in before_control.items() if key not in ("SIMPE", "RCEND")}
       == {key: value for key, value in after_control.items() if key not in ("SIMPE", "RCEND")})
    original_rc, child_rc = records(parent["ResultCollection"]), records(child["ResultCollection"])
    ck(f"{arm} all result collection endpoints", len(original_rc) == len(child_rc) == 3
       and all(before["RCEND"] == 36 and after["RCEND"] == endpoint
       and {key: value for key, value in before.items() if key != "RCEND"}
       == {key: value for key, value in after.items() if key != "RCEND"}
       for before, after in zip(original_rc, child_rc)))
    ck(f"{arm} zero-initiation profile", child["OperationProfile"]["instances"][0]["rows"]
       == diff[arm]["operation_profile_after"]
       and parent["OperationProfile"]["instances"][0]["rows"]
       == diff[arm]["operation_profile_before"])
for key, pin in (("manual", "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"),
                 ("dictionary", "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0"),
                 ("simlox_exe", "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0")):
    ck(f"installed {key} fingerprint", sha(installed[key]) == pin)

native_dirs = {arm: RUNS / f"i02-var13-{arm}-v100-ssh-20261002-01" for arm in ARMS}
native_reports = {}
logs = {}
seals = 0
for arm, directory in native_dirs.items():
    endpoint, bins = ARMS[arm]
    inv, closure = load(directory / "invocation.json"), load(directory / "closure.json")
    ck(f"{arm} invocation seal", closure["invocation_sha256"] == sha(directory / "invocation.json"))
    ck(f"{arm} source stability", inv["source_hashes_before"]
       == closure["source_hashes_before"] == closure["source_hashes_after"])
    guard(inv, arm)
    source_pins = {
        "input": inputs[arm], "parent": parent_files[arm], "contract": CASE / "contract.json",
        "manual": installed["manual"], "dictionary": installed["dictionary"],
        "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
        "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
        "python": installed["python"], "runner_script": CASE / "run_native_ssh.ps1",
        "simlox_exe": installed["simlox_exe"],
    }
    for name, file in source_pins.items():
        ck(f"{arm} source pin {name}", closure["source_hashes_before"][name] == sha(file))
    ck(f"{arm} raw input copy", sha(directory / "input.json") == sha(inputs[arm]))
    seals += raw(directory, closure, arm)
    steps = load(directory / "steps.json")
    ck(f"{arm} five native steps", [step["name"] for step in steps]
       == ["import", "export", "calc", "jsonreport", "check_import_export"])
    for step in steps:
        ck(f"{arm} {step['name']} success/GUI", step["exit_code"] == 0
           and step["error"] is None and step["gui_preserved"] is True)
    runlog = (directory / "run.log").read_text(encoding="cp1252")
    ck(f"{arm} zero converter errors", "Input conversion completed. Errors: 0, Warnings: 1" in runlog
       and "(warning #108)" in runlog and "(error #" not in runlog)
    ck(f"{arm} valid SXO", (directory / "model.sxo").stat().st_size > 4)
    exported = table_map(load(directory / "roundtrip-raw.json"))
    populated = {name: table for name, table in children[arm].items() if records(table)}
    ck(f"{arm} 22 populated authored tables", len(populated) == 22)
    for name, table in populated.items():
        ck(f"{arm} exact native row roundtrip {name}", exported.get(name) == table)
    logs[arm] = (directory / "model.log").read_text(encoding="cp1252")
    native_reports[arm] = report(directory / "report-raw.json")
    ck(f"{arm} default report tables", set(native_reports[arm])
       == {"ResultSummary", "SystemResults", "StockTotalResults"})
    summary = records(native_reports[arm]["ResultSummary"])[0]
    ck(f"{arm} zero-mission summary", summary["NREP"] == 1 and summary["RTIUP"] == endpoint
       and all(summary[key] == 0 for key in ("MTMF", "MSTF", "MSUF", "STMF")))
    for name in ("SystemResults", "StockTotalResults"):
        series = records(native_reports[arm][name])
        ck(f"{arm} {bins} {name} bins", len(series) == bins)
        for i, row in enumerate(series):
            ck(f"{arm} {name} bin {i}", row["STINT"] == i / 2
               and row["ETINT"] == (i + 1) / 2)
    ck(f"{arm} terminal ready aircraft", records(native_reports[arm]["SystemResults"])[-1]["NSYRY"] == 1)
    ck(f"{arm} aggregate reported NBO zero", all(row["NBO"] == 0
       for row in records(native_reports[arm]["StockTotalResults"])))
    ck(f"{arm} no mission event", "mission ordered" not in logs[arm]
       and "mission starting" not in logs[arm])

transit = logs["transit"]
ck("transit h4 IN before h6 BETWEEN", "Time: 4  item transfer task 0 (IN)  arrives with 1 items" in transit
   and "Time: 6  item transfer task 1 (BETWEEN)  starts with 1 items, transfer time: 2" in transit)
ck("transit depot ID0 removed at h6", "Time: 6 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in transit)
ck("transit no target arrival by h7", "item transfer task 1 (BETWEEN)  arrives with" not in transit
   and "Time: 8 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives" not in transit)
backorder = logs["backorder"]
ck("backorder h2 empty source", "Time: 0 <TEACH-LRU-01,0,DEPOT-01,0> Stock initiated" in backorder
   and "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 0 Items:" in backorder)
ck("backorder h2 transfer queue one", "Time: 2 <TEACH-LRU-01,0,DEPOT-01,0> Item transfer backorder added" in backorder
   and "Item transfer backorders at: <TEACH-LRU-01,0,DEPOT-01,0> Nbr: 1" in backorder)
ck("backorder zero-item task", "Time: 2  item transfer task 0 (BETWEEN)  starts with 0 items, transfer time: 0" in backorder
   and "Time: 2  item transfer task 0 (BETWEEN)  arrives with 0 items" in backorder)
ck("backorder no h4 IN inside horizon", "item transfer task 1 (IN)" not in backorder
   and "Time: 4  item transfer task" not in backorder)

selected = {}
for arm, native_dir in native_dirs.items():
    endpoint, bins = ARMS[arm]
    for station in STATIONS:
        label = f"{arm}/{station}"
        directory = RUNS / f"i02-var13-{arm}-{station}-item-v100-ssh-20261002-01"
        inv, closure = load(directory / "invocation.json"), load(directory / "closure.json")
        ck(f"{label} invocation seal", closure["invocation_sha256"] == sha(directory / "invocation.json"))
        ck(f"{label} native closure binding", inv["source_closure_sha256"] == sha(native_dir / "closure.json"))
        ck(f"{label} source stability", inv["source_hashes_before"]
           == closure["source_hashes_before"] == closure["source_hashes_after"])
        guard(inv, label)
        settings = RUNS / "report-settings" / ("base-item-position-results.sxs" if station == "base"
                                               else "item-position-results.sxs")
        report_pins = {"sxo": native_dir / "model.sxo", "settings": settings,
                       "exe": installed["simlox_exe"], "runner": CASE / "report_native_ssh.ps1"}
        for name, file in report_pins.items():
            ck(f"{label} source pin {name}", closure["source_hashes_before"][name] == sha(file))
        ck(f"{label} selected command", "-rpts" in inv["arguments"]
           and "-rjexport" in inv["arguments"] and str(settings) in inv["arguments"])
        ck(f"{label} report exit", closure["exit_code"] == 0 and closure["error"] is None)
        seals += raw(directory, closure, label)
        selected[arm, station] = report(directory / "item-report-raw.json")
        item = records(selected[arm, station]["ItemResults"])
        ck(f"{label} {bins} ItemResults rows", len(item) == bins)
        station_id = "BASE-01" if station == "base" else "DEPOT-01"
        for i, row in enumerate(item):
            ck(f"{label} item bin {i} identity/interval", row["IID"] == "TEACH-LRU-01"
               and row["STID"] == station_id and row["STINT"] == i / 2
               and row["ETINT"] == (i + 1) / 2)
            ck(f"{label} item NBO bin {i} zero", row["NBO"] == 0)
        for name in ("SystemResults", "StockTotalResults"):
            ck(f"{label} {bins} {name} rows", len(records(selected[arm, station][name])) == bins)
        if arm == "transit" and station == "depot":
            ck("transit depot initial1, after IN2, after departure1", all(item[i]["STSZ"] == item[i]["STOHA"] == 1
               for i in range(8)) and all(item[i]["STSZ"] == item[i]["STOHA"] == 2
               for i in range(8, 12)) and all(item[i]["STSZ"] == item[i]["STOHA"] == 1
               for i in range(12, 14)))
        if arm == "transit" and station == "base":
            ck("transit base no arrival by endpoint", all(row["STSZ"] == row["STOHA"] == 0
               for row in item))
        if arm == "backorder" and station == "depot":
            ck("backorder depot physically and nominally zero", all(row["STSZ"] == row["STOHA"] == 0
               for row in item))
        if arm == "backorder" and station == "base":
            ck("backorder base target nominal1 onhand0 at h2", all(item[i]["STSZ"] == 0
               for i in range(4)) and all(item[i]["STSZ"] == 1 and item[i]["STOHA"] == 0
               for i in (4, 5)))

ck("32 raw seals across six closures", seals == 32)
result = {
    "schema": "independent-i02-var13-terminal-transfer-review/v1",
    "passed": not failures,
    "verdict": "GO: bounded in-transit and transfer-backorder terminal classifications" if not failures
               else "NO-GO: independent replay failed",
    "checks_passed": checks - len(failures), "checks_total": checks, "failures": failures,
    "raw_seals_checked": seals,
    "source_sha256": {arm: sha(file) for arm, file in inputs.items()},
    "native_closure_sha256": {arm: sha(directory / "closure.json") for arm, directory in native_dirs.items()},
    "observations": {
        "transit": "At h7 endpoint depot has one item; ID0 left h6 in a 2h BETWEEN and has not arrived at base. The h4 IN supplied a second item.",
        "backorder": "At h3 endpoint h2 BETWEEN moved zero items; physical transfer backorder1 remains, base nominal STSZ1/on-hand0, depot0.",
        "report_caveat": "ItemResults.NBO and StockTotalResults.NBO remain zero in the backorder arm despite the explicit transfer backorder in model.log; ordinary NBO does not expose that queue.",
        "missions": "Zero initiation profile, zero mission summary metrics, aircraft ready1 in both arms.",
    },
    "limits": ["Separately parented probes, one IID/two stations/seed, endpoints h7 and h3.",
               "No active aircraft demand, general priority, other horizon, GUI visual or cross-engine claim."],
}
OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                  "checks_total": checks, "failures": failures}, ensure_ascii=False))
sys.exit(0 if not failures else 1)
