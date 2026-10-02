"""Independent read-only replay for the E08.var03 DLAYL Y/N diagnostic."""
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
PARENT = ROOT / "E08-var01-immediate-lateral-v1.0.2/on-input.json"
DONOR = ROOT / "I02-var04-between-delay-v1.0.0/native-input.json"
ARMS = ("off", "on")
STATIONS = ("base-01", "base-02", "depot")
failures: list[str] = []
checks = 0


def ck(name: str, condition: bool) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(name)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", raw))


def tbl(doc, key="model") -> dict:
    return {table["name"]: table for table in doc[key]["tables"]}


def rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, raw)) for instance in table["instances"] for raw in instance["rows"]]


def semantic(path: Path) -> dict:
    return {k: v for k, v in tbl(parse(path), "report").items() if k != "ProblemDescription"}


def provenance(inv: dict, label: str) -> None:
    ck(f"{label} session0 SSH", inv.get("execution_mode") == "ssh_cli_v1"
       and inv.get("session_id") == 0 and "sshd.exe" in inv.get("ssh_ancestor_names", []))
    ck(f"{label} native mutex", inv.get("queue_mutex") == r"Global\SimloxIssue18NativeQueue")
    ck(f"{label} GUI identity", inv.get("gui", {}).get("pid") == 13340
       and inv.get("gui", {}).get("session_id") == 1)


def verify_raw(directory: Path, closure: dict, label: str) -> int:
    for name, seal in closure["raw"].items():
        file = directory / name
        ck(f"{label} raw {name} present", file.is_file())
        if file.is_file():
            ck(f"{label} raw {name} bytes", file.stat().st_size == seal["bytes"])
            ck(f"{label} raw {name} hash", sha(file) == seal["sha256"])
    return len(closure["raw"])


contract, difference = parse(CASE / "contract.json"), parse(CASE / "exact-diff.json")
inputs = {arm: CASE / f"{arm}-input.json" for arm in ARMS}
source = {arm: tbl(parse(path)) for arm, path in inputs.items()}
parent = tbl(parse(PARENT))
donor = tbl(parse(DONOR))
ck("accepted E08 parent hash", sha(PARENT) == contract["direct_parent"]["source_sha256"] == difference["parent_sha256"])
ck("accepted I02 schema donor hash", sha(DONOR) == contract["transfer_schema_donor"]["source_sha256"]
   == difference["transfer_schema_donor_sha256"])
ck("exact diff hash", sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
installed = {
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
}
for key, field in (("manual", "manual_pdf"), ("dictionary", "table_dictionary"),
                   ("simlox_exe", "simlox_exe")):
    ck(f"installed {key} pin", sha(installed[key]) == contract["installed_source_sha256"][field])

for arm in ARMS:
    ck(f"{arm} input SHA", sha(inputs[arm]) == contract[f"{arm}_input_sha256"] == difference[f"{arm}_sha256"])
off_delta = {name for name in set(parent) | set(source["off"]) if parent.get(name) != source["off"].get(name)}
ck("OFF exact parent table delta", off_delta == {"ItemTransfer", "StockAllocation", "ProblemDescription"})
ck("OFF one added transfer table", "ItemTransfer" not in parent and difference["off_from_parent"]["added_tables"] == ["ItemTransfer"])
ck("donor-native transfer columns", source["off"]["ItemTransfer"]["columns"] == donor["ItemTransfer"]["columns"])
ck("h9 transfer row", rows(source["off"]["ItemTransfer"]) == [{
    "STFID": "DEPOT-01", "STTID": "BASE-02", "IID": "TEACH-LRU-01", "TFTIME": 9,
    "TFQTY": 1, "TFDT": 2, "NOTE": None,
}])
parent_stock, off_stock = rows(parent["StockAllocation"]), rows(source["off"]["StockAllocation"])
ck("peer stock size only", len(parent_stock) == len(off_stock) == 3 and all(
    (a == b if a["STID"] != "BASE-02" else a["STSIZ"] == 1 and b["STSIZ"] == 0
     and {k: v for k, v in a.items() if k != "STSIZ"} == {k: v for k, v in b.items() if k != "STSIZ"})
    for a, b in zip(parent_stock, off_stock)))
on_delta = {name for name in set(source["off"]) | set(source["on"])
            if source["off"].get(name) != source["on"].get(name)}
ck("matched ON delta only DLAYL and description", on_delta == {"LateralSupport", "ProblemDescription"})
off_lateral, on_lateral = rows(source["off"]["LateralSupport"]), rows(source["on"]["LateralSupport"])
ck("DLAYL-only business row", len(off_lateral) == len(on_lateral) == 1
   and off_lateral[0]["DLAYL"] == "N" and on_lateral[0]["DLAYL"] == "Y"
   and {k: v for k, v in off_lateral[0].items() if k != "DLAYL"}
   == {k: v for k, v in on_lateral[0].items() if k != "DLAYL"}
   and on_lateral[0]["LSRUL"] == "IMMEDIATE")
ck("both child topology and seed equal", all(source["off"][name] == source["on"][name]
   for name in source["off"] if name not in on_delta))

common_pins = {
    "parent": PARENT, "donor": DONOR, "contract": CASE / "contract.json",
    "manual": installed["manual"], "dictionary": installed["dictionary"],
    "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
    "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
    "python": installed["python"], "runner_script": CASE / "run_native_ssh.ps1",
    "simlox_exe": installed["simlox_exe"],
}
native = {arm: RUNS / f"e08-dlayl-{arm}-v100-ssh-20261002-01" for arm in ARMS}
closures, default_reports, logs = {}, {}, {}
seal_count = 0
for arm, directory in native.items():
    inv, closure = parse(directory / "invocation.json"), parse(directory / "closure.json")
    closures[arm] = closure
    ck(f"{arm} invocation seal", sha(directory / "invocation.json") == closure["invocation_sha256"])
    ck(f"{arm} source hash stability", inv["source_hashes_before"]
       == closure["source_hashes_before"] == closure["source_hashes_after"])
    provenance(inv, arm)
    for key, path in {"input": inputs[arm], **common_pins}.items():
        ck(f"{arm} source seal {key}", closure["source_hashes_before"][key] == sha(path))
    ck(f"{arm} raw input copy", sha(directory / "input.json") == sha(inputs[arm]))
    seal_count += verify_raw(directory, closure, arm)
    steps = parse(directory / "steps.json")
    ck(f"{arm} five guarded steps", [step["name"] for step in steps]
       == ["import", "export", "calc", "jsonreport", "check_import_export"])
    for step in steps:
        ck(f"{arm} {step['name']} completion", step["exit_code"] == 0
           and step["error"] is None and step["gui_preserved"] is True)
    ck(f"{arm} valid SXO", (directory / "model.sxo").stat().st_size > 4)
    run_log = (directory / "run.log").read_text(encoding="cp1252")
    ck(f"{arm} converter zero errors", "Input conversion completed. Errors: 0, Warnings: 1" in run_log
       and "(warning #108)" in run_log and "(error #" not in run_log)
    exported = tbl(parse(directory / "roundtrip-raw.json"))
    populated = {name: table for name, table in source[arm].items() if rows(table)}
    ck(f"{arm} 25 row-containing source tables", len(populated) == 25)
    for name, table in populated.items():
        ck(f"{arm} exact native row roundtrip {name}", exported.get(name) == table)
    default_reports[arm] = semantic(directory / "report-raw.json")
    ck(f"{arm} default report tables", set(default_reports[arm])
       == {"ResultSummary", "SystemResults", "StockTotalResults"})
    for table_name in ("SystemResults", "StockTotalResults"):
        report_rows = rows(default_reports[arm][table_name])
        ck(f"{arm} 72 {table_name} bins", len(report_rows) == 72)
        for i, row in enumerate(report_rows):
            ck(f"{arm} {table_name} interval {i}", row["STINT"] == i / 2
               and row["ETINT"] == (i + 1) / 2)
    summary = rows(default_reports[arm]["ResultSummary"])[0]
    ck(f"{arm} 2/3 mission success", summary["NREP"] == 1 and abs(summary["MSUF"] - 2 / 3) < 1e-6)
    sys_rows = rows(default_reports[arm]["SystemResults"])
    ck(f"{arm} delayed readiness and terminal one", sys_rows[30]["NSYRY"] == 0
       and sys_rows[31]["NSYRY"] == 1 and sys_rows[-1]["NSYRY"] == 1)
    logs[arm] = (directory / "model.log").read_bytes()

ck("OFF/ON model.log byte-identical", logs["off"] == logs["on"])
ck("OFF/ON all default business reports equal", default_reports["off"] == default_reports["on"])
accepted_log_path = ROOT / "E08-var01-immediate-lateral-v1.0.2/runs/e08-immediate-on-v102-ssh-20261002-01/model.log"
accepted_log = accepted_log_path.read_text(encoding="cp1252")
ck("accepted IMMEDIATE control lateral dispatch", "Time: 10  transport task 0 created from <BASE-02,0> to <BASE-01,0>" in accepted_log
   and "Time: 10.5 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,1>" in accepted_log
   and "Time: 10.8333 <TEACH-AIR-01,BASE-01,0> System ready" in accepted_log)
accepted_summary = semantic(ROOT / "E08-var01-immediate-lateral-v1.0.2/runs/e08-immediate-on-v102-ssh-20261002-01/report-raw.json")
ck("delayed children differ from immediate parent system ledger", default_reports["off"]["SystemResults"]
   != accepted_summary["SystemResults"] and default_reports["on"]["SystemResults"] != accepted_summary["SystemResults"])
log = logs["off"].decode("cp1252")
event_phrases = [
    "Time: 9  item transfer task 0 (BETWEEN)  created: starting from <TEACH-LRU-01,0,DEPOT-01,0> aiming for <TEACH-LRU-01,0,BASE-02,0>",
    "Time: 9 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
    "Time: 9  item transfer task 0 (BETWEEN)  starts with 1 items, transfer time: 2",
    "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Lateral support check, ordinary remaining time: 2",
    "Candidates: <<TEACH-LRU-01,0,BASE-02,0>,0.5,0>",
    "Time: 11  item transfer task 0 (BETWEEN)  arrives with 1 items",
    "Time: 11 <TEACH-LRU-01,0,BASE-02,0> Replacement item arrives <TEACH-LRU-01,0,0>",
    "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,1>",
    "Time: 14.1667 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,1>",
    "Time: 14.1667  transport task 2 created from <DEPOT-01,0> to <BASE-01,0>",
    "Time: 14.1667  transport task 2 starts with 1 items/systems, transport time: 1",
    "Time: 15.1667 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,1>",
    "Time: 15.5 <TEACH-AIR-01,BASE-01,0> System ready",
]
positions = [log.find(phrase) for phrase in event_phrases]
for phrase, position in zip(event_phrases, positions):
    ck(f"event {phrase[:66]}", position >= 0)
ck("physical event order", positions == sorted(positions))
ck("no observed peer-to-demand lateral transport", not re.search(
    r"transport task \d+ created from <BASE-02,0> to <BASE-01,0>", log))
ck("no peer item issue", "Take replacement item <TEACH-LRU-01,0,0> from stock" not in
   "\n".join(line for line in log.splitlines() if "BASE-02" in line))
for n, launch, completion, outcome in ((0, 8, 10, "aborted mission completed"),
                                       (1, 20, 22, "mission completed"),
                                       (2, 32, 34, "mission completed")):
    identity = f"<BASIC-MISSION,TEACH-UNIT,0,0,{n}>"
    ck(f"mission {n} launch", f"Time: {launch} {identity} mission starting" in log)
    ck(f"mission {n} finish", f"Time: {completion} {identity} {outcome}" in log)
ck("first mission failure time", "Time: 9.8829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted" in log)

selected = {}
for arm, native_dir in native.items():
    for station in STATIONS:
        label = f"{arm}/{station}"
        directory = RUNS / f"e08-dlayl-{arm}-{station}-report-v100-ssh-20261002-01"
        inv, closure = parse(directory / "invocation.json"), parse(directory / "closure.json")
        ck(f"{label} invocation seal", closure["invocation_sha256"] == sha(directory / "invocation.json"))
        ck(f"{label} native closure binding", inv["source_closure_sha256"] == sha(native_dir / "closure.json"))
        ck(f"{label} stable source seals", inv["source_hashes_before"]
           == closure["source_hashes_before"] == closure["source_hashes_after"])
        provenance(inv, label)
        pins = {
            "sxo": native_dir / "model.sxo",
            "settings": RUNS / "report-settings" / f"{station}-item.sxs",
            "exe": installed["simlox_exe"], "runner": CASE / "report_native_ssh.ps1",
        }
        for key, path in pins.items():
            ck(f"{label} source {key}", closure["source_hashes_before"][key] == sha(path))
        ck(f"{label} selected report command", "-rpts" in inv["arguments"]
           and "-rjexport" in inv["arguments"] and str(pins["settings"]) in inv["arguments"])
        ck(f"{label} report exit", closure["exit_code"] == 0 and closure["error"] is None)
        seal_count += verify_raw(directory, closure, label)
        report = semantic(directory / "item-report-raw.json")
        selected[arm, station] = report
        ck(f"{label} selected tables", {"ItemResults", "ItemResultsTotal", "MissionResults",
           "SystemResults", "StockTotalResults"}.issubset(report))
        item = rows(report["ItemResults"])
        ck(f"{label} 72 item bins", len(item) == 72)
        station_id = "DEPOT-01" if station == "depot" else station.upper()
        ck(f"{label} IID and position", all(r["IID"] == "TEACH-LRU-01" and r["STID"] == station_id for r in item))
        for i, row in enumerate(item):
            ck(f"{label} item interval {i}", row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2)
        if station == "base-01":
            ck(f"{label} ordinary BO until fractional 15–15.5 bin", all(item[i]["NBO"] == 1 for i in range(20, 30))
               and abs(item[30]["NBO"] - 1 / 3) < 1e-5 and all(item[i]["NBO"] == 0 for i in range(31, 72)))
            ck(f"{label} no base spare", all(row["STSZ"] == row["STOHA"] == 0 for row in item))
        elif station == "base-02":
            ck(f"{label} future item arrives only at h11", all(item[i]["STOHA"] == 0 for i in range(22))
               and all(item[i]["STOHA"] == 1 for i in range(22, 72)))
        else:
            ck(f"{label} h9 depot issue", all(item[i]["STOHA"] == 1 for i in range(18))
               and all(item[i]["STOHA"] == 0 for i in range(18, 72)))
            ck(f"{label} ordinary depot BO h10–14.1667", all(item[i]["NBO"] == 1 for i in range(20, 28))
               and abs(item[28]["NBO"] - 1 / 3) < 1e-5 and all(item[i]["NBO"] == 0 for i in range(29, 72)))
        for table_name in ("MissionResults", "SystemResults", "StockTotalResults"):
            ck(f"{label} 72 {table_name}", len(rows(report[table_name])) == 72)
            if table_name == "MissionResults":
                ck(f"{label} mission interval endpoints", all(r["STINT"] == i / 2
                   and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(rows(report[table_name]))))
            else:
                selected_rows = rows(report[table_name])
                default_rows = rows(default_reports[arm][table_name])
                shared = set(selected_rows[0]) & set(default_rows[0])
                ck(f"{label} selected {table_name} shared fields match default", all(
                    {key: row[key] for key in shared} == {key: default_rows[i][key] for key in shared}
                    for i, row in enumerate(selected_rows)))

for station in STATIONS:
    ck(f"OFF/ON full {station} reports equal", selected["off", station] == selected["on", station])
ck("36 raw seals across eight closures", seal_count == 36)

result = {
    "schema": "independent-e08-var03-delayed-lateral-review/v1",
    "passed": not failures,
    "verdict": ("RESTRICTED GO for reproducible unchanged OFF/ON diagnostic; NO-GO for positive DLAYL distinction"
                if not failures else "NO-GO: independent replay failures"),
    "checks_passed": checks - len(failures), "checks_total": checks, "failures": failures,
    "raw_seals_checked": seal_count,
    "source_sha256": {arm: sha(path) for arm, path in inputs.items()},
    "native_closure_sha256": {arm: sha(directory / "closure.json") for arm, directory in native.items()},
    "native_model_log_sha256": {arm: sha(directory / "model.log") for arm, directory in native.items()},
    "observations": {
        "scheduled_transfer": "DEPOT physical ID0 departs for BASE-02 at h9, remains in transit at h10, arrives h11.",
        "lateral": "Both logs show the same candidate check at h10; neither ships the h11 peer item to BASE-01.",
        "ordinary_supply": "Failed mounted ID1 repairs at depot h13.1667–14.1667, then transports to BASE-01 h14.1667–15.1667; aircraft ready h15.5.",
        "outcome": "OFF and ON logs are byte-identical, all default and selected business report tables match; first mission aborts, later two succeed, terminal aircraft ready1/peer stock1/depot stock0.",
    },
    "limits": [
        "The positive DLAYL effect predeclared in the contract is not observed in this fixed geometry and seed.",
        "The h10 candidate line does not prove why no lateral shipment occurred, nor does this rule out DLAYL effects with other future-supply sources or timings.",
        "No general DLAYL ineffectiveness, GUI visual behavior, or cross-engine claim.",
    ],
}
OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                  "checks_total": checks, "failures": failures}, ensure_ascii=False))
sys.exit(0 if not failures else 1)
