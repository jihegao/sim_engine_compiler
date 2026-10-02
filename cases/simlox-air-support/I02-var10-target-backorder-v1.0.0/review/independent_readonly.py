"""Independent read-only replay of I02.var10 target-backorder timing pair."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUNS = CASE / "runs"
PARENT = ROOT / "I02-var03-between-transfer-v1.0.0/native-input.json"
OUT = CASE / "review/independent-readonly-2026-10-02.json"
ARMS = ("early", "late")
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


def tables(document, kind="model"):
    return {table["name"]: table for table in document[kind]["tables"]}


def records(table):
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def business(file: Path):
    return {name: table for name, table in tables(load(file), "report").items()
            if name != "ProblemDescription"}


def guard(invocation: dict, label: str) -> None:
    ck(f"{label} SSH session0", invocation.get("execution_mode") == "ssh_cli_v1"
       and invocation.get("session_id") == 0 and "sshd.exe" in invocation.get("ssh_ancestor_names", []))
    ck(f"{label} mutex", invocation.get("queue_mutex") == r"Global\SimloxIssue18NativeQueue")
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
parent = tables(load(PARENT))
input_files = {arm: CASE / f"{arm}-input.json" for arm in ARMS}
source = {arm: tables(load(file)) for arm, file in input_files.items()}
ck("accepted BETWEEN parent SHA", sha(PARENT) == contract["direct_parent"]["source_sha256"]
   == diff["parent_sha256"])
ck("frozen diff SHA", sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
for arm in ARMS:
    ck(f"{arm} source SHA", sha(input_files[arm]) == contract["arm_sha256"][arm]
       == diff["arm_sha256"][arm])
    actual = {name for name in set(parent) | set(source[arm])
              if parent.get(name) != source[arm].get(name)}
    ck(f"{arm} exact parent tables changed", actual == {"ItemTransfer", "ProblemDescription"}
       == set(diff["changed_tables_per_arm"]))
    source_rows, parent_rows = records(source[arm]["ItemTransfer"]), records(parent["ItemTransfer"])
    ck(f"{arm} h4 IN fixed", source_rows[0] == parent_rows[0]
       and source[arm]["ItemTransfer"]["instances"][0]["rows"][0] == diff["fixed_in_row"])
    ck(f"{arm} BETWEEN TFTIME only", len(source_rows) == len(parent_rows) == 2
       and parent_rows[1]["TFTIME"] == 6
       and source_rows[1]["TFTIME"] == diff["arm_between_time"][arm]
       and {key: value for key, value in source_rows[1].items() if key != "TFTIME"}
       == {key: value for key, value in parent_rows[1].items() if key != "TFTIME"})
    ck(f"{arm} zero-duration one-unit transfer", source_rows[1]["TFDT"] == 0
       and source_rows[1]["TFQTY"] == 1 and source_rows[1]["STFID"] == "DEPOT-01"
       and source_rows[1]["STTID"] == "BASE-01")
ck("arms TFTIME-only business contrast", {name for name in source["early"]
   if source["early"][name] != source["late"][name]} == {"ItemTransfer", "ProblemDescription"}
   and {key: value for key, value in records(source["early"]["ItemTransfer"])[1].items()
        if key != "TFTIME"} == {key: value for key, value in records(source["late"]["ItemTransfer"])[1].items()
                              if key != "TFTIME"})

installed = {
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
for key, contract_field in (("manual", "manual_pdf"), ("dictionary", "table_dictionary"),
                            ("simlox_exe", "simlox_exe")):
    ck(f"installed {key} fingerprint", sha(installed[key])
       == contract["installed_source_sha256"][contract_field])
native_dirs = {arm: RUNS / f"i02-var10-{arm}-v100-ssh-20261002-01" for arm in ARMS}
reports = {}
logs = {}
seals = 0
for arm, directory in native_dirs.items():
    invocation, closure = load(directory / "invocation.json"), load(directory / "closure.json")
    ck(f"{arm} invocation seal", closure["invocation_sha256"] == sha(directory / "invocation.json"))
    ck(f"{arm} source stable", invocation["source_hashes_before"]
       == closure["source_hashes_before"] == closure["source_hashes_after"])
    guard(invocation, arm)
    source_pins = {
        "input": input_files[arm], "parent": PARENT, "contract": CASE / "contract.json",
        "manual": installed["manual"], "dictionary": installed["dictionary"],
        "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
        "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
        "python": installed["python"], "runner_script": CASE / "run_native_ssh.ps1",
        "simlox_exe": installed["simlox_exe"],
    }
    for name, file in source_pins.items():
        ck(f"{arm} source seal {name}", closure["source_hashes_before"][name] == sha(file))
    ck(f"{arm} copied input", sha(directory / "input.json") == sha(input_files[arm]))
    seals += raw(directory, closure, arm)
    steps = load(directory / "steps.json")
    ck(f"{arm} five native steps", [step["name"] for step in steps]
       == ["import", "export", "calc", "jsonreport", "check_import_export"])
    for step in steps:
        ck(f"{arm} {step['name']} success/GUI", step["exit_code"] == 0
           and step["error"] is None and step["gui_preserved"] is True)
    ck(f"{arm} valid SXO", (directory / "model.sxo").stat().st_size > 4)
    runlog = (directory / "run.log").read_text(encoding="cp1252")
    ck(f"{arm} converter errors zero", "Input conversion completed. Errors: 0, Warnings: 1" in runlog
       and "(warning #108)" in runlog and "(error #" not in runlog)
    exported = tables(load(directory / "roundtrip-raw.json"))
    populated = {name: table for name, table in source[arm].items() if records(table)}
    ck(f"{arm} 22 row-containing source tables", len(populated) == 22)
    for name, table in populated.items():
        ck(f"{arm} exact source roundtrip {name}", exported.get(name) == table)
    logs[arm] = (directory / "model.log").read_text(encoding="cp1252")
    reports[arm] = business(directory / "report-raw.json")
    ck(f"{arm} default report table set", set(reports[arm])
       == {"ResultSummary", "SystemResults", "StockTotalResults"})
    for name in ("SystemResults", "StockTotalResults"):
        series = records(reports[arm][name])
        ck(f"{arm} 72 {name} bins", len(series) == 72)
        for i, row in enumerate(series):
            ck(f"{arm} {name} interval {i}", row["STINT"] == i / 2
               and row["ETINT"] == (i + 1) / 2)
    summary = records(reports[arm]["ResultSummary"])[0]
    ck(f"{arm} 2/3 mission summary", summary["NREP"] == 1
       and abs(summary["MSUF"] - 2 / 3) < 1e-6)
    ck(f"{arm} terminal ready one", records(reports[arm]["SystemResults"])[-1]["NSYRY"] == 1)

ck("matched mission summary", reports["early"]["ResultSummary"] == reports["late"]["ResultSummary"])
ck("different readiness ledgers", reports["early"]["SystemResults"] != reports["late"]["SystemResults"])
ck("different aggregate stock ledgers", reports["early"]["StockTotalResults"]
   != reports["late"]["StockTotalResults"])
for arm, transfer_hour in (("early", 9), ("late", 11)):
    log = logs[arm]
    event = (f"Time: {transfer_hour}  item transfer task 1 (BETWEEN)  created: starting from "
             "<TEACH-LRU-01,0,DEPOT-01,0> aiming for <TEACH-LRU-01,0,BASE-01,0>")
    ck(f"{arm} scheduled transfer", event in log)
    ck(f"{arm} transfer zero duration", f"Time: {transfer_hour}  item transfer task 1 (BETWEEN)  starts with 1 items, transfer time: 0" in log
       and f"Time: {transfer_hour}  item transfer task 1 (BETWEEN)  arrives with 1 items" in log)
    ck(f"{arm} fixed IN h4", "Time: 4  item transfer task 0 (IN)  arrives with 1 items" in log)
    ck(f"{arm} fixed first failure", "Time: 9.8829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted" in log)
    ck(f"{arm} later missions success", all(f"Time: {time} <BASIC-MISSION,TEACH-UNIT,0,0,{n}> mission success" in log
       for n, time in ((1, 22), (2, 34))))
ck("early physical preposition ID0", "Time: 9 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,0> to stock" in logs["early"]
   and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in logs["early"]
   and "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added" not in logs["early"])
ck("late h10 base ordinary backorder", "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added" in logs["late"])
ck("late transfer ID1 clears base BO directly", "Time: 11 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,1> from stock" in logs["late"]
   and "Time: 11 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 1" in logs["late"]
   and "Time: 11  system SURP task 0 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,1>" in logs["late"])
ck("late ordinary ID0 stocks base h12", "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in logs["late"]
   and "Time: 12 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,0> to stock" in logs["late"])
ck("readiness contrast h10.5 versus h11.3333", "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready" in logs["early"]
   and "Time: 11.3333 <TEACH-AIR-01,BASE-01,0> System ready" in logs["late"])

selected = {}
for arm, native_dir in native_dirs.items():
    for station in STATIONS:
        label = f"{arm}/{station}"
        directory = RUNS / f"i02-var10-{arm}-{station}-item-v100-ssh-20261002-01"
        inv, closure = load(directory / "invocation.json"), load(directory / "closure.json")
        ck(f"{label} invocation seal", closure["invocation_sha256"] == sha(directory / "invocation.json"))
        ck(f"{label} native closure link", inv["source_closure_sha256"] == sha(native_dir / "closure.json"))
        ck(f"{label} source stable", inv["source_hashes_before"]
           == closure["source_hashes_before"] == closure["source_hashes_after"])
        guard(inv, label)
        settings = RUNS / "report-settings" / ("base-item-position-results.sxs" if station == "base"
                                               else "item-position-results.sxs")
        pins = {"sxo": native_dir / "model.sxo", "settings": settings,
                "exe": installed["simlox_exe"], "runner": CASE / "report_native_ssh.ps1"}
        for name, file in pins.items():
            ck(f"{label} source {name}", closure["source_hashes_before"][name] == sha(file))
        ck(f"{label} selected command", "-rpts" in inv["arguments"] and "-rjexport" in inv["arguments"]
           and str(settings) in inv["arguments"])
        ck(f"{label} report exit", closure["exit_code"] == 0 and closure["error"] is None)
        seals += raw(directory, closure, label)
        report = business(directory / "item-report-raw.json")
        selected[arm, station] = report
        ck(f"{label} station table present", "ItemResults" in report and "ItemResultsTotal" in report)
        series = records(report["ItemResults"])
        ck(f"{label} 72 item bins", len(series) == 72)
        expected_stid = "BASE-01" if station == "base" else "DEPOT-01"
        for i, row in enumerate(series):
            ck(f"{label} item interval and identity {i}", row["IID"] == "TEACH-LRU-01"
               and row["STID"] == expected_stid and row["STINT"] == i / 2
               and row["ETINT"] == (i + 1) / 2)
        ck(f"{label} terminal stock one", series[-1]["STSZ"] == series[-1]["STOHA"] == 1
           and series[-1]["NBO"] == 0)
        if station == "base" and arm == "early":
            ck("early base stocked h9 and no BO", series[17]["STOHA"] == 0
               and series[18]["STOHA"] == 1 and all(row["NBO"] == 0 for row in series))
            ck("early base h10 issue then h12 replenish", series[20]["STOHA"] == 0
               and series[24]["STOHA"] == 1)
        if station == "base" and arm == "late":
            ck("late h10–11 base BO", all(series[i]["NBO"] == 1 for i in (20, 21))
               and all(series[i]["NBO"] == 0 for i in range(22, 72)))
            ck("late h11 direct BO fulfillment without on-hand", series[22]["STSZ"] == 1
               and series[22]["STOHA"] == 0 and series[24]["STOHA"] == 1)
        if station == "depot" and arm == "early":
            ck("early depot h9 then h10 issues", series[17]["STOHA"] == 2
               and series[18]["STOHA"] == 1 and series[20]["STOHA"] == 0)
        if station == "depot" and arm == "late":
            ck("late depot h10 then h11 issues", series[19]["STOHA"] == 2
               and series[20]["STOHA"] == 1 and series[22]["STOHA"] == 0)
        for name in ("MissionResults", "SystemResults", "StockTotalResults"):
            ck(f"{label} 72 {name} bins", len(records(report[name])) == 72)

ck("32 raw seals in six closures", seals == 32)
ck("selected mission results equal across arms", selected["early", "base"]["MissionResults"]
   == selected["late", "base"]["MissionResults"])
ck("early/late base and depot item bins differ", all(selected["early", station]["ItemResults"]
   != selected["late", station]["ItemResults"] for station in STATIONS))

result = {
    "schema": "independent-i02-var10-target-backorder-review/v1",
    "passed": not failures,
    "verdict": "GO: bounded h9 stocked target versus h11 target with ordinary backorder" if not failures
               else "NO-GO: independent replay failed",
    "checks_passed": checks - len(failures), "checks_total": checks, "failures": failures,
    "raw_seals_checked": seals,
    "source_sha256": {arm: sha(file) for arm, file in input_files.items()},
    "native_closure_sha256": {arm: sha(directory / "closure.json") for arm, directory in native_dirs.items()},
    "observations": {
        "early": "Physical depot ID0 moves to base h9 and stocks on hand; h10 aircraft repair uses it with no base backorder; ordinary ID1 replenishes h12, system ready h10.5.",
        "late": "h10 aircraft demand opens base BO1; h11 scheduled BETWEEN ID1 reaches base and directly clears BO without adding on-hand; ordinary depot ID0 reaches base h12 and stocks it, system ready h11.3333.",
        "reports": "Four 72-bin station ItemResults ledgers and full System/Stock tables reconcile; mission summaries and outcomes match, both terminal aircraft ready1/base stock1/depot stock1.",
    },
    "limits": ["One IID, two stations, zero-duration one-unit BETWEEN h9/h11 after h4 IN, fixed seed.",
               "This shows one realized target-backorder routing difference, not general queue priority, arbitrary backorders, delays, GUI rendering or cross-engine behavior."],
}
OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                  "checks_total": checks, "failures": failures}, ensure_ascii=False))
sys.exit(0 if not failures else 1)
