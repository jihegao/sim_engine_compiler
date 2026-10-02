"""Independent read-only replay of E08.var01 v1.0.2 native lateral pair."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / "review/independent-readonly-2026-10-02.json"
PARENT = HERE.parent / "E07-item-specific-transport-v1.0.1/native-input.json"
SOURCES = {"on": HERE / "on-input.json", "off": HERE / "off-input.json"}
NATIVE = {arm: HERE / f"runs/e08-immediate-{arm}-v102-ssh-20261002-01" for arm in SOURCES}
SELECTED = {(arm, pos): HERE / f"runs/e08-{arm}-{pos}-report-v102-ssh-20261002-01" for arm in SOURCES for pos in ("base01", "base02", "depot")}
failures: list[str] = []
checks = 0


def ck(label: str, value: bool) -> None:
    global checks
    checks += 1
    if not value:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def js(path: Path, native: bool = False):
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text) if native else text)


def tables(doc, report: bool = False):
    return {t["name"]: t for t in doc["report" if report else "model"]["tables"]}


def rows(table):
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, r)) for instance in table["instances"] for r in instance["rows"]]


contract, exact = js(HERE / "contract.json"), js(HERE / "exact-diff.json")
parent_doc = js(PARENT)
models = {arm: js(path) for arm, path in SOURCES.items()}
parent_tables = tables(parent_doc)
model_tables = {arm: tables(doc) for arm, doc in models.items()}
ck("accepted parent SHA", sha(PARENT) == contract["parent_sha256"] == exact["parent_sha256"])
for arm in SOURCES:
    ck(f"{arm} source SHA", sha(SOURCES[arm]) == contract[f"{arm}_input_sha256"] == exact[f"{arm}_sha256"])
    segment = exact[f"{arm}_from_parent"]
    actual_added = set(model_tables[arm]) - set(parent_tables)
    actual_removed = set(parent_tables) - set(model_tables[arm])
    actual_changed = {n for n in set(model_tables[arm]) & set(parent_tables) if model_tables[arm][n] != parent_tables[n]}
    ck(f"{arm} parent delta keys", set(segment["added"]) == actual_added and set(segment["removed"]) == actual_removed and set(segment["changed"]) == actual_changed)
    for name in actual_added:
        ck(f"{arm} added {name}", segment["added"][name] == model_tables[arm][name])
    for name in actual_changed:
        ck(f"{arm} changed {name} before", segment["changed"][name]["before"] == parent_tables[name])
        ck(f"{arm} changed {name} after", segment["changed"][name]["after"] == model_tables[arm][name])
ck("exact on/off changed tables", {name for name in model_tables["on"] if model_tables["on"][name] != model_tables["off"][name]} == {"Control", "ProblemDescription"})
on_control, off_control = rows(model_tables["on"]["Control"])[0], rows(model_tables["off"]["Control"])[0]
ck("ENLAT isolated Y/N", on_control["ENLAT"] == "Y" and off_control["ENLAT"] == "N" and {k: v for k, v in on_control.items() if k != "ENLAT"} == {k: v for k, v in off_control.items() if k != "ENLAT"})
ck("diff on/off isolated keys", exact["on_from_off"]["added"] == exact["on_from_off"]["removed"] == {} and set(exact["on_from_off"]["changed"]) == {"Control", "ProblemDescription"})
for name in ("Control", "ProblemDescription"):
    ck(f"diff on/off {name} before", exact["on_from_off"]["changed"][name]["before"] == model_tables["off"][name])
    ck(f"diff on/off {name} after", exact["on_from_off"]["changed"][name]["after"] == model_tables["on"][name])
ck("shared lateral geometry", rows(model_tables["on"]["LateralSupport"]) == [{"LGID": "LAT-01", "TLAT": .5, "DLAYL": "N", "LSRUL": "IMMEDIATE", "NOTE": None}] and rows(model_tables["on"]["StationLateralSupport"]) == [{"LGID": "LAT-01", "STID": "BASE-01", "LSTID": "BASE-02", "TFRLS": .5, "TTOLS": .5, "NOTE": None}])
ck("tracked LRU and item report", rows(model_tables["on"]["Item"])[0]["TRACK"] == rows(model_tables["off"]["Item"])[0]["TRACK"] == "Y" and any(r["RTYPE"] == "ITEM" and r["RCINT"] == .5 for r in rows(model_tables["on"]["ResultCollection"])))

installed = {
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
}
for key, path in installed.items():
    field = {"manual": "manual_pdf_sha256", "dictionary": "dictionary_sha256", "simlox_exe": None}[key]
    if field:
        ck(f"installed {key} SHA", sha(path) == contract[field])
ck("installed EXE SHA", sha(installed["simlox_exe"]) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0")

native_closures = {}
for arm, directory in NATIVE.items():
    invocation, closure = js(directory / "invocation.json"), js(directory / "closure.json")
    native_closures[arm] = closure
    ck(f"{arm} invocation seal", closure["invocation_sha256"] == sha(directory / "invocation.json"))
    ck(f"{arm} stable source", invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"])
    ck(f"{arm} session0 SSH guard", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"])
    ck(f"{arm} mutex and GUI", invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    source_paths = {
        "input": SOURCES[arm], "parent": PARENT, "contract": HERE / "contract.json",
        "manual": installed["manual"], "dictionary": installed["dictionary"], "builder": HERE / "build.py",
        "exact_diff": HERE / "exact-diff.json", "diff_checker": HERE / "describe_diff.py",
        "checker": HERE / "check_roundtrip.py",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        "runner_script": HERE / "run_native_ssh.ps1", "simlox_exe": installed["simlox_exe"],
    }
    for key, path in source_paths.items():
        ck(f"{arm} source {key} pin", closure["source_hashes_before"][key] == sha(path))
    ck(f"{arm} original input copy", sha(directory / "input.json") == sha(SOURCES[arm]))
    for filename, seal in closure["raw"].items():
        path = directory / filename
        ck(f"{arm}/{filename} bytes", path.stat().st_size == seal["bytes"])
        ck(f"{arm}/{filename} SHA", sha(path) == seal["sha256"])
    steps = js(directory / "steps.json")
    ck(f"{arm} five ordered steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"])
    for step in steps:
        ck(f"{arm} {step['name']} successful and GUI preserved", step["exit_code"] == 0 and step["error"] is None and step["gui_preserved"] is True)
    runlog = (directory / "run.log").read_text(encoding="cp1252")
    ck(f"{arm} zero conversion errors", "Input conversion completed. Errors: 0" in runlog and "(error #" not in runlog)
    ck(f"{arm} valid SXO", (directory / "model.sxo").stat().st_size > 4)
    exported = tables(js(directory / "roundtrip-raw.json", True))
    substantive = {n for n, t in model_tables[arm].items() if rows(t)}
    ck(f"{arm} 24 populated authored tables", len(substantive) == 24)
    for name in sorted(substantive):
        ck(f"{arm} exact roundtrip {name}", exported.get(name) == model_tables[arm][name])

selected_reports = {}
for (arm, pos), directory in SELECTED.items():
    invocation, closure = js(directory / "invocation.json"), js(directory / "closure.json")
    native_dir = NATIVE[arm]
    ck(f"{arm}/{pos} invocation seal", closure["invocation_sha256"] == sha(directory / "invocation.json"))
    ck(f"{arm}/{pos} stable report sources", closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"])
    ck(f"{arm}/{pos} source closure", invocation["source_run_id"] == native_dir.name and invocation["source_closure_sha256"] == sha(native_dir / "closure.json"))
    ck(f"{arm}/{pos} session/queue/GUI", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    settings = HERE / f"runs/report-settings/{'base-01' if pos == 'base01' else 'base-02' if pos == 'base02' else 'depot'}-item.sxs"
    report_paths = {"sxo": native_dir / "model.sxo", "settings": settings, "exe": installed["simlox_exe"], "runner": HERE / "report_native_ssh.ps1"}
    for key, path in report_paths.items():
        ck(f"{arm}/{pos} {key} pin", closure["source_hashes_before"][key] == sha(path))
    ck(f"{arm}/{pos} report command and exit", str(settings) in invocation["arguments"] and str(report_paths["sxo"]) in invocation["arguments"] and "-report -rpts" in invocation["arguments"] and "-rjexport" in invocation["arguments"] and closure["exit_code"] == 0 and closure["error"] is None)
    for filename, seal in closure["raw"].items():
        path = directory / filename
        ck(f"{arm}/{pos}/{filename} bytes", path.stat().st_size == seal["bytes"])
        ck(f"{arm}/{pos}/{filename} SHA", sha(path) == seal["sha256"])
    selected_reports[arm, pos] = tables(js(directory / "item-report-raw.json", True), True)
    ordinary = tables(js(native_dir / "report-raw.json", True), True)
    for name in ordinary.keys() & selected_reports[arm, pos].keys():
        ck(f"{arm}/{pos} shared report rows {name}", rows(ordinary[name]) == rows(selected_reports[arm, pos][name]))

for arm in SOURCES:
    inventory = {pos: rows(selected_reports[arm, pos]["ItemResults"]) for pos in ("base01", "base02", "depot")}
    system = rows(selected_reports[arm, "base01"]["SystemResults"])
    stock = rows(selected_reports[arm, "base01"]["StockTotalResults"])
    ck(f"{arm} three item, system, stock 72-bin ledgers", all(len(v) == 72 for v in inventory.values()) and len(system) == len(stock) == 72)
    for i in range(72):
        h = i / 2
        for pos, station in (("base01", "BASE-01"), ("base02", "BASE-02"), ("depot", "DEPOT-01")):
            r = inventory[pos][i]
            ck(f"{arm}/{pos} bin {i} identity/grid", r["IID"] == "TEACH-LRU-01" and r["STID"] == station and r["STINT"] == h and r["ETINT"] == h+.5)
        ck(f"{arm} system/stock bin {i} grid", system[i]["STINT"] == stock[i]["STINT"] == h and system[i]["ETINT"] == stock[i]["ETINT"] == h+.5)
        base01, base02, depot = (inventory[pos][i] for pos in ("base01", "base02", "depot"))
        ck(f"{arm} bin {i} base01 nominal/on-hand", base01["STSZ"] == base01["STOHA"] == 0)
        ck(f"{arm} bin {i} base01 backorder", base01["NBO"] == (1 if 10 <= h < (10.5 if arm == "on" else 11) else 0))
        ck(f"{arm} bin {i} base02 nominal", base02["STSZ"] == 1)
        ck(f"{arm} bin {i} base02 on-hand", base02["STOHA"] == (1 if arm == "off" or h < 10 or h >= 11 else 0))
        ck(f"{arm} bin {i} depot nominal/on-hand", depot["STSZ"] == 1 and abs(depot["STOHA"] - (1 if h < 10 or h >= 14.5 else 0 if h < 14 else .6666666865348816)) < 1e-6)
        ck(f"{arm} bin {i} no base02/depot backorders", base02["NBO"] == depot["NBO"] == 0)
        ck(f"{arm} bin {i} aggregate backorder", stock[i]["NBO"] == base01["NBO"])
    for pos, item_rows in inventory.items():
        total = rows(selected_reports[arm, pos]["ItemResultsTotal"])[0]
        ck(f"{arm}/{pos} total stock means", abs(total["STSZ"] - sum(r["STSZ"] for r in item_rows)/72) < 1e-6 and abs(total["STOHA"] - sum(r["STOHA"] for r in item_rows)/72) < 1e-6)
    ck(f"{arm} summary success fraction", abs(rows(selected_reports[arm, "base01"]["ResultSummary"])[0]["MSUF"] - 2/3) < 1e-6)
    ck(f"{arm} terminal ready and station stock", system[-1]["NSYRY"] == 1 and inventory["base01"][-1]["STOHA"] == 0 and inventory["base02"][-1]["STOHA"] == 1 and inventory["depot"][-1]["STOHA"] == 1)
ck("mission outcome reports same", all(rows(selected_reports["on", "base01"][n]) == rows(selected_reports["off", "base01"][n]) for n in ("ResultSummary", "MissionResults", "MissionResultsTotal", "FixedMissionResults", "FixedMissionResultsTotal")))
on_sys = rows(selected_reports["on", "base01"]["SystemResults"])
off_sys = rows(selected_reports["off", "base01"]["SystemResults"])
ck("half-hour faster system ready response", on_sys[21]["NSYRY"] > off_sys[21]["NSYRY"] and on_sys[22]["NSYRY"] > off_sys[22]["NSYRY"] and on_sys[23]["NSYRY"] == off_sys[23]["NSYRY"] == 1)
ck("shorter base01 backorder integral", sum(r["NBO"]*.5 for r in rows(selected_reports["on", "base01"]["ItemResults"])) == .5 and sum(r["NBO"]*.5 for r in rows(selected_reports["off", "base01"]["ItemResults"])) == 1)
for i in range(72):
    for table_name in ("SystemResults", "StockTotalResults"):
        a = rows(selected_reports["on", "base01"][table_name])[i]
        b = rows(selected_reports["off", "base01"][table_name])[i]
        if i not in ((20, 21, 22) if table_name == "SystemResults" else (20, 21)):
            ck(f"{table_name} bin {i} equal outside route effect", a == b)

logs = {arm: (directory / "model.log").read_text(encoding="cp1252") for arm, directory in NATIVE.items()}
phrases = {
    "on": [
        "Time: 10 <TEACH-LRU-01,0,BASE-02,0> Take replacement item <TEACH-LRU-01,0,1> from stock",
        "Time: 10  transport task 0 created from <BASE-02,0> to <BASE-01,0>",
        "Time: 10  transport task 0 starts with 1 items/systems, transport time: 0.5",
        "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
        "Time: 10  transport task 1 created from <DEPOT-01,0> to <BASE-02,0>",
        "Time: 11  transport task 1 arrives with 1 items/systems",
        "Time: 11 <TEACH-LRU-01,0,BASE-02,0> Replacement item arrives <TEACH-LRU-01,0,0>",
        "Time: 10.5 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,1>",
        "Time: 10.5 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 0.5",
        "Time: 10.8333 <TEACH-AIR-01,BASE-01,0> System ready",
        "Time: 14.1667 <TEACH-LRU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-LRU-01,0,2>",
    ],
    "off": [
        "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
        "Time: 10  transport task 0 created from <DEPOT-01,0> to <BASE-01,0>",
        "Time: 10  transport task 0 starts with 1 items/systems, transport time: 1",
        "Time: 11 <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>",
        "Time: 11 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 1",
        "Time: 11.3333 <TEACH-AIR-01,BASE-01,0> System ready",
        "Time: 14.1667 <TEACH-LRU-01,0,DEPOT-01,0> Replacement item arrives <TEACH-LRU-01,0,1>",
    ],
}
for arm, log in logs.items():
    for phrase in phrases[arm]:
        ck(f"{arm} physical event {phrase[:62]}", phrase in log)
    ck(f"{arm} first mission abort and later successes", "Time: 9.8829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted" in log and all(f"Time: {h} <BASIC-MISSION,TEACH-UNIT,0,0,{n}> mission success" in log for n, h in ((1, 22), (2, 34))))
ck("off arm no active lateral transport", "transport task 0 created from <BASE-02,0> to <BASE-01,0>" not in logs["off"])

result = {
    "schema": "independent-e08-var01-lateral-review/v1", "case": HERE.name,
    "passed": not failures, "verdict": "GO: bounded immediate lateral source distinction" if not failures else "NO-GO: independent replay failed",
    "checks_passed": checks - len(failures), "checks_total": checks, "failures": failures,
    "source_sha256": {arm: sha(path) for arm, path in SOURCES.items()},
    "native_closure_sha256": {arm: sha(directory / "closure.json") for arm, directory in NATIVE.items()},
    "selected_closure_sha256": {f"{arm}_{pos}": sha(directory / "closure.json") for (arm, pos), directory in SELECTED.items()},
    "selected_report_sha256": {f"{arm}_{pos}": sha(directory / "item-report-raw.json") for (arm, pos), directory in SELECTED.items()},
    "observations": {
        "on": "ENLAT Y takes physical peer item ID1 BASE-02→BASE-01 h10–10.5, then depot item ID0 replenishes BASE-02 h11; damaged ID2 is repaired/restocked at DEPOT-01 h14.1667.",
        "off": "ENLAT N takes depot item ID0 DEPOT-01→BASE-01 h10–11; BASE-02 stock1 remains unused; damaged ID1 returns repaired to depot h14.1667.",
        "backorder_and_readiness": "BASE-01 backorder lasts 0.5h ON versus1h OFF; aircraft ready h10.8333 versus h11.3333. Both arms later succeed missions at h22/h34 and end ready.",
    },
    "limits": [
        "This is one IID, two peers in one LAT-01 group, IMMEDIATE/DLAYL=N, one seed, and this installed CLI. No EXTENDED, ADJACENT, delayed lateral, competing peers, GUI-visual, or cross-engine result.",
        "ItemResults is selected per IID/STID stock position. BASE-01 nominal and on-hand stock remain zero because arrivals immediately satisfy backorders; source route is established by physical item identity and task log, with corroborating peer/depot item bins.",
        "A one-seed route choice does not prove a general priority rule under all in-transit ordinary supplies.",
    ],
}
OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(json.dumps({"verdict": result["verdict"], "checks_passed": result["checks_passed"], "checks_total": checks, "failures": failures}, indent=2))
sys.exit(0 if result["passed"] else 1)
