"""Independent read-only replay of the sealed E09 v1.0.1 native and item reports."""

from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
NATIVE = CASE / "runs" / "e09-backorder-priority-v101-ssh-20261004-01"
SELECTED = CASE / "runs" / "e09-backorder-priority-v101-item-report-ssh-20261004-01"
ARMS = ("fifo", "priority", "disabled")
STATIONS = ("DEPOT-01", "BASE-01", "BASE-02")
CHECKS: list[tuple[str, bool]] = []


def check(label: str, value: bool) -> None:
    CHECKS.append((label, bool(value)))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def report(path: Path) -> dict:
    source = path.read_text(encoding="utf-8-sig")
    # Native JSON may have a final trailing comma; sanitize syntax only.
    return json.loads(re.sub(r",\s*([}\]])", r"\1", source))


def table_map(document: dict, root: str) -> dict[str, dict]:
    return {table["name"]: table for table in document[root]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def records(table: dict) -> list[dict]:
    columns = [column["name"] for column in table["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in rows(table)]


def close(actual: float, expected: float, tolerance: float = 0.00025) -> bool:
    return abs(actual - expected) <= tolerance


def interval_average(segments: list[tuple[float, float, float]], start: float, end: float) -> float:
    return sum(max(0.0, min(end, b) - max(start, a)) * level for a, b, level in segments) / (end - start)


contract = load(CASE / "contract.json")
native_closure = load(NATIVE / "closure.json")
selected_closure = load(SELECTED / "closure.json")
native_invocation = load(NATIVE / "invocation.json")
selected_invocation = load(SELECTED / "invocation.json")
native_steps = load(NATIVE / "steps.json")
selected_steps = load(SELECTED / "steps.json")
native_outcome = load(NATIVE / "outcome.json")
selected_outcome = load(SELECTED / "outcome.json")

check("contract native run", contract["run_id"] == NATIVE.name)
check("contract selected run", contract["selected_report_run_id"] == SELECTED.name)
for label, directory, closure, invocation, steps in (
    ("native", NATIVE, native_closure, native_invocation, native_steps),
    ("selected", SELECTED, selected_closure, selected_invocation, selected_steps),
):
    check(f"{label} closure run ID", closure["run_id"] == directory.name)
    check(f"{label} closure no error", closure["error"] is None)
    check(f"{label} invocation SHA", sha(directory / "invocation.json") == closure["invocation_sha256"])
    check(f"{label} session zero", invocation["session_id"] == 0)
    check(f"{label} sshd ancestor", "sshd.exe" in invocation["ssh_ancestor_names"])
    check(f"{label} serial mutex", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    check(f"{label} GUI identity", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and bool(invocation["gui"]["start_utc"]))
    for step in steps:
        check(f"{label} step exit {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None)
        check(f"{label} GUI preserved {step['name']}", step["gui_preserved"] is True)
    for key, before in closure["source_hashes_before"].items():
        check(f"{label} source sealed {key}", before == closure["source_hashes_after"][key] == invocation["source_hashes_before"][key])
    for name, seal in closure["raw"].items():
        path = directory / name
        check(f"{label} raw exists {name}", path.is_file())
        check(f"{label} raw length {name}", path.stat().st_size == seal["bytes"])
        check(f"{label} raw SHA {name}", sha(path) == seal["sha256"])
check("12 native steps", [s["name"] for s in native_steps] == [f"{arm}_{stage}" for arm in ARMS for stage in ("import", "export", "calc", "report")])
check("9 selected reports", [s["name"] for s in selected_steps] == [f"{arm}-{station.lower()}" for arm in ARMS for station in STATIONS])
check("32 native raw seals", len(native_closure["raw"]) == 32)
check("20 selected raw seals", len(selected_closure["raw"]) == 20)
check("native outcome clear", native_outcome["error"] is None)
check("selected outcome clear", selected_outcome["error"] is None and selected_outcome["status"] == "completed")
check("selected source run", selected_invocation["source_run_id"] == NATIVE.name)
check("same GUI process in both closures", native_invocation["gui"] == selected_invocation["gui"])

parent = CASES / "E12-var02-two-fault-control-v1.0.0"
sources = {
    "contract": CASE / "contract.json",
    "fifo": CASE / "fifo-input.json",
    "priority": CASE / "priority-input.json",
    "disabled": CASE / "disabled-input.json",
    "diagnostic_closure": CASES / "E09-var01-03-backorder-priority-v1.0.0" / "runs" / "e09-backorder-priority-v100-ssh-20261004-01" / "closure.json",
    "report_builder": CASE / "make_report_settings.py",
    "report_default": Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs"),
    "selector_depot": CASE / "runs" / "report-settings" / "depot-01.sxs",
    "selector_base01": CASE / "runs" / "report-settings" / "base-01.sxs",
    "selector_base02": CASE / "runs" / "report-settings" / "base-02.sxs",
    "parent_input": parent / "native-input.json",
    "parent_closure": parent / "runs" / "e12-var02-two-fault-control-v100-ssh-20261003-01" / "closure.json",
    "parent_signoff": parent / "cli-scope-signoff-2026-10-03.md",
    "e03_signoff": CASES / "E03-two-aircraft-shared-spare-v1.0.0" / "cli-scope-signoff-2026-09-29.md",
    "e07_signoff": CASES / "E07-item-specific-transport-v1.0.1" / "cli-scope-signoff-2026-10-01.md",
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "build.py": CASE / "build.py",
    "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
}
for key, path in sources.items():
    if key in native_closure["source_hashes_before"]:
        check(f"native source hash {key}", sha(path) == native_closure["source_hashes_before"][key])
selected_paths = {
    "contract": CASE / "contract.json",
    "native_closure": NATIVE / "closure.json",
    **{f"{arm}_sxo": NATIVE / f"{arm}.sxo" for arm in ARMS},
    "selector_depot": sources["selector_depot"],
    "selector_base01": sources["selector_base01"],
    "selector_base02": sources["selector_base02"],
    "selector_builder": CASE / "make_report_settings.py",
    "default": sources["report_default"],
    "exe": sources["exe"],
    "report_runner": CASE / "run_item_reports_ssh.ps1",
    "python": sources["python"],
}
for key, path in selected_paths.items():
    check(f"selected source hash {key}", sha(path) == selected_closure["source_hashes_before"][key])
check("contract diagnostic closure", contract["excluded_diagnostic_v100_closure_sha256"] == native_closure["source_hashes_before"]["diagnostic_closure"])
for arm in ARMS:
    check(f"contract input {arm}", contract["inputs_sha256"][arm] == native_closure["source_hashes_before"][arm])
    check(f"selected SXO bound {arm}", selected_closure["source_hashes_before"][f"{arm}_sxo"] == native_closure["raw"][f"{arm}.sxo"]["sha256"])
for key in ("parent_input", "parent_closure", "parent_signoff"):
    check(f"contract parent {key}", contract["dependency"][f"{key}_sha256"] == native_closure["source_hashes_before"][key])
for case_id, key in (("E03", "e03_signoff"), ("E07", "e07_signoff")):
    prerequisite = next(p for p in contract["dependency"]["instructional_prerequisites"] if p["case_id"] == case_id)
    check(f"contract prerequisite {case_id}", prerequisite["signoff_sha256"] == native_closure["source_hashes_before"][key])
check("contract manual", contract["manual"]["sha256"] == native_closure["source_hashes_before"]["manual"])
check("contract default report settings", contract["report_settings"]["installed_default_sha256"] == selected_closure["source_hashes_before"]["default"])
for station, key in (("DEPOT-01", "selector_depot"), ("BASE-01", "selector_base01"), ("BASE-02", "selector_base02")):
    check(f"contract selector {station}", contract["report_settings"]["selectors_sha256"][station] == selected_closure["source_hashes_before"][key])

depot_selector = sources["selector_depot"].read_bytes()
old = b"\x01" + struct.pack("<I", len(b"DEPOT-01\0")) + b"DEPOT-01\0"
check("one depot selector station", depot_selector.count(old) == 1)
for station in ("BASE-01", "BASE-02"):
    new = b"\x01" + struct.pack("<I", len(station) + 1) + station.encode("ascii") + b"\0"
    check(f"selector station substitution {station}", depot_selector.replace(old, new, 1) == (CASE / "runs" / "report-settings" / f"{station.lower()}.sxs").read_bytes())

parent_tables = table_map(load(sources["parent_input"]), "model")
diagnostic = CASES / "E09-var01-03-backorder-priority-v1.0.0"
models = {arm: table_map(load(CASE / f"{arm}-input.json"), "model") for arm in ARMS}
for arm, model in models.items():
    check(f"32 source tables {arm}", len(model) == 32)
    check(f"22 populated source tables {arm}", sum(bool(rows(t)) for t in model.values()) == 22)
    check(f"local input copy {arm}", sha(NATIVE / f"{arm}-input.json") == contract["inputs_sha256"][arm])
    check(f"parent table set {arm}", model.keys() == parent_tables.keys())
    check(f"six parent changed tables {arm}", {name for name in model if model[name] != parent_tables[name]} == {"ProblemDescription", "Control", "Item", "Station", "StockAllocation", "ResultCollection"})
    v100 = table_map(load(diagnostic / f"{arm}-input.json"), "model")
    check(f"v100 data delta {arm}", {name for name in model if model[name] != v100[name]} == {"Item", "ResultCollection"})
    item = records(model["Item"])
    check(f"tracked item {arm}", any(r["IID"] == "TEACH-LRU-01" and r["TRACK"] == "Y" for r in item))
    check(f"item collection {arm}", any(r["RTYPE"] == "ITEM" and r["RCINT"] == 0.5 and r["RCEND"] == 36 for r in records(model["ResultCollection"])))
    control = records(model["Control"])[0]
    station = {r["STID"]: r for r in records(model["Station"])}
    flags = {"fifo": ("Y", "N"), "priority": ("Y", "Y"), "disabled": ("N", "Y")}
    check(f"priority flags {arm}", (control["ENBOP"], station["DEPOT-01"]["BOPRI"]) == flags[arm])
    stock = {r["STID"]: r["STSIZ"] for r in records(model["StockAllocation"])}
    check(f"opening stock geometry {arm}", stock == {"BASE-01": 1, "BASE-02": 0, "DEPOT-01": 0})
    exported = table_map(load(NATIVE / f"{arm}-roundtrip-raw.json"), "model")
    for name, table in model.items():
        original = records(table)
        if not original:
            continue
        check(f"roundtrip table {arm}/{name}", name in exported)
        if name not in exported:
            continue
        returned = records(exported[name])
        check(f"roundtrip row count {arm}/{name}", len(original) == len(returned))
        for index, (before, after) in enumerate(zip(original, returned)):
            for field, value in before.items():
                if value is not None:
                    check(f"roundtrip cell {arm}/{name}/{index}/{field}", after.get(field) == value)
    converter = (NATIVE / f"{arm}-run.log").read_text(encoding="latin-1")
    check(f"converter zero errors {arm}", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter)
    check(f"converter only #108 {arm}", re.findall(r"\(warning #(\d+)\)", converter) == ["108"])
    check(f"usable SXO {arm}", (NATIVE / f"{arm}.sxo").stat().st_size > 300000)
    check(f"completed native arm {arm}", native_outcome[arm] == "completed" and native_outcome["converter_summaries"][arm] == [0, 1, 0])

check("isolated priority/fifo pair", {name for name in models["fifo"] if models["fifo"][name] != models["priority"][name]} == {"ProblemDescription", "Station"})
check("isolated priority/disabled pair", {name for name in models["priority"] if models["priority"][name] != models["disabled"][name]} == {"ProblemDescription", "Control"})
check("FIFO/disabled event byte parity", (NATIVE / "fifo.log").read_bytes() == (NATIVE / "disabled.log").read_bytes())

logs = {arm: (NATIVE / f"{arm}.log").read_text(encoding="latin-1") for arm in ARMS}
for arm, log in logs.items():
    first = log.find("Time: 10.7579 <TEACH-LRU-01,0,DEPOT-01,0> Backorder added")
    second_local = log.find("Time: 11.5 <TEACH-LRU-01,0,BASE-02,0> Backorder added")
    second_depot = log.find("Time: 11.5 <TEACH-LRU-01,0,DEPOT-01,0> Backorder added")
    repair = log.find("Time: 14.9246 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,1>")
    check(f"competing demands precede first repair {arm}", -1 < first < second_local < second_depot < repair)
    check(f"depot two queued BOs {arm}", "Nbr: 2 Backorders:<<TEACH-LRU-01,0,BASE-01,0>,10.7579>,<<TEACH-LRU-01,0,BASE-02,0>,11.5>" in log)
    check(f"BASE-02 local aircraft BO {arm}", "Nbr: 1 Backorders:<<TEACH-AIR-01,BASE-02,0>,11.5>" in log)
    expected = ("BASE-02", "BASE-01") if arm == "priority" else ("BASE-01", "BASE-02")
    for item, depart, arrival, target in ((1, "14.9246", "15.9246", expected[0]), (2, "15.6667", "16.6667", expected[1])):
        origin = "BASE-01" if item == 1 else "BASE-02"
        up_depart = "10.9246" if item == 1 else "11.6667"
        up_arrival = "13.9246" if item == 1 else "14.6667"
        check(f"item upward departure {arm}/{item}", f"Time: {up_depart}  transport request <<TEACH-LRU-01,0,{item}>,<TEACH-LRU-01,0,{origin},0>,<TEACH-LRU-01,0,DEPOT-01,0>> started" in log)
        check(f"item upward arrival {arm}/{item}", f"Time: {up_arrival} <TEACH-LRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,{item}>" in log)
        check(f"item repaired before departure {arm}/{item}", f"Time: {depart} <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,{item}>" in log)
        outward = re.findall(rf"transport request <<TEACH-LRU-01,0,{item}>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,([^,]+),0>> started", log)
        check(f"unique depot dispatch {arm}/{item}", outward == [target])
        check(f"item target arrival {arm}/{item}", f"Time: {arrival} <TEACH-LRU-01,0,{target},0> Replacement item arrives <TEACH-LRU-01,0,{item}>" in log)
        check(f"ordered physical chain {arm}/{item}", float(up_depart) < float(up_arrival) < float(depart) < float(arrival))
    check(f"aircraft receives chosen item {arm}", f"system SURP task 1 on <TEACH-AIR-01,1> subitem received <TEACH-LRU-01,0,{1 if arm == 'priority' else 2}>" in log)
    check(f"six mission attempts {arm}", log.count("mission starting, duration: 3.5") == 6)
    check(f"two mission successes {arm}", len(re.findall(r"mission success:", log)) == 2)
    check(f"four mission aborts {arm}", len(re.findall(r"mission aborted:", log)) == 4)

default_reports = {arm: table_map(report(NATIVE / f"{arm}-report-raw.json"), "report") for arm in ARMS}
selected_reports: dict[tuple[str, str], dict[str, dict]] = {}
for arm in ARMS:
    for station in STATIONS:
        filename = f"{arm}-{station.lower()}-item-report-raw.json"
        current = table_map(report(SELECTED / filename), "report")
        selected_reports[arm, station] = current
        check(f"selected ItemResults table {arm}/{station}", "ItemResults" in current and "ItemResultsTotal" in current)
        item = records(current["ItemResults"])
        check(f"72 selected ItemResults {arm}/{station}", len(item) == 72)
        check(f"selected item/station identity {arm}/{station}", all(row["IID"] == "TEACH-LRU-01" and row["STID"] == station for row in item))
        check(f"one ItemResultsTotal {arm}/{station}", len(records(current["ItemResultsTotal"])) == 1)
        total = records(current["ItemResultsTotal"])[0]
        check(f"ItemResultsTotal identity {arm}/{station}", total["IID"] == "TEACH-LRU-01" and total["STID"] == station)
        for field in ("STOHA", "NBO"):
            check(f"ItemResultsTotal bin average {arm}/{station}/{field}", close(total[field], sum(row[field] for row in item) / len(item), 0.00001))
        expected_stock = 1 if station == "BASE-01" else 0
        for index, row in enumerate(item):
            check(f"selected bin {arm}/{station}/{index}", row["STINT"] == index / 2 and row["ETINT"] == (index + 1) / 2)
            check(f"selected nominal stock {arm}/{station}/{index}", row["STSZ"] == expected_stock)
            check(f"selected nonnegative NBO {arm}/{station}/{index}", row["NBO"] >= 0)
        check(f"selected/default summary parity {arm}/{station}", current["ResultSummary"] == default_reports[arm]["ResultSummary"])
        for name in ("SystemResults", "StockTotalResults"):
            check(f"selected/default {name} columns {arm}/{station}", current[name]["columns"] == default_reports[arm][name]["columns"])
            check(f"selected/default {name} values {arm}/{station}", rows(current[name]) == rows(default_reports[arm][name]))

for arm in ARMS:
    check(f"same summary across stations {arm}", all(selected_reports[arm, station]["ResultSummary"] == selected_reports[arm, "DEPOT-01"]["ResultSummary"] for station in STATIONS))
    depot = records(selected_reports[arm, "DEPOT-01"]["ItemResults"])
    base1 = records(selected_reports[arm, "BASE-01"]["ItemResults"])
    base2 = records(selected_reports[arm, "BASE-02"]["ItemResults"])
    base2_clear = 15.9246 if arm == "priority" else 16.6667
    base1_arrival = 16.6667 if arm == "priority" else 15.9246
    base2_total = records(selected_reports[arm, "BASE-02"]["ItemResultsTotal"])[0]
    check(f"BASE-02 observed wait time {arm}", close(base2_total["WT"], base2_clear - 11.5))
    for index in range(20, 35):  # h10 through h17.5, containing the discriminating events
        start, end = index / 2, (index + 1) / 2
        depot_expected = interval_average([(10.7579, 11.5, 1), (11.5, 14.9246, 2), (14.9246, 15.6667, 1)], start, end)
        base2_expected = interval_average([(11.5, base2_clear, 1)], start, end)
        base1_stock_expected = interval_average([(0, 10.7579, 1), (base1_arrival, 23.4473, 1)], start, end)
        check(f"depot BO ledger {arm}/{index}", close(depot[index]["NBO"], depot_expected))
        check(f"BASE-02 BO ledger {arm}/{index}", close(base2[index]["NBO"], base2_expected))
        check(f"BASE-01 on-hand ledger {arm}/{index}", close(base1[index]["STOHA"], base1_stock_expected))
        check(f"BASE-01 no local BO {arm}/{index}", base1[index]["NBO"] == 0)
        check(f"BASE-02 no stock on hand {arm}/{index}", base2[index]["STOHA"] == 0)
    stock_total = records(default_reports[arm]["StockTotalResults"])
    check(f"72 StockTotal bins {arm}", len(stock_total) == 72)
    for index in range(20, 35):
        check(f"aggregate/local BO reconciliation {arm}/{index}", close(stock_total[index]["NBO"], base2[index]["NBO"]))
    check(f"72 System bins {arm}", len(records(default_reports[arm]["SystemResults"])) == 72)

for station in STATIONS:
    for name in ("ItemResults", "ItemResultsTotal"):
        check(f"FIFO/disabled selected parity {station}/{name}", selected_reports["fifo", station][name] == selected_reports["disabled", station][name])
check("FIFO/disabled native event parity", (NATIVE / "fifo.log").read_bytes() == (NATIVE / "disabled.log").read_bytes())
check("priority clears BASE-02 earlier", records(selected_reports["priority", "BASE-02"]["ItemResults"])[32]["NBO"] < records(selected_reports["fifo", "BASE-02"]["ItemResults"])[32]["NBO"])
check("FIFO replenishes BASE-01 earlier", records(selected_reports["fifo", "BASE-01"]["ItemResults"])[32]["STOHA"] > records(selected_reports["priority", "BASE-01"]["ItemResults"])[32]["STOHA"])
check("all three summaries same", default_reports["fifo"]["ResultSummary"] == default_reports["priority"]["ResultSummary"] == default_reports["disabled"]["ResultSummary"])

failed = [label for label, passed in CHECKS if not passed]
verdict = {
    "schema": "simlox-e09-v101-independent-replay/v1",
    "native_run_id": NATIVE.name,
    "selected_run_id": SELECTED.name,
    "verdict": "GO_BOUNDED" if not failed else "NO_GO",
    "checks": len(CHECKS),
    "passed": len(CHECKS) - len(failed),
    "failed": failed,
    "event_log_sha256": {arm: sha(NATIVE / f"{arm}.log") for arm in ARMS},
    "scope": "One fixed seed, two bases, one depot, first two repaired LRUs and nine station-selected ItemResults exports; no general priority tie-breaker or mission-success effect.",
    "limits": [
        "ItemResults values are half-hour interval averages; nominal stock STSZ is not physical on-hand STOHA.",
        "StockTotalResults.NBO is not the sum of all station-level ItemResults.NBO in this case; only the BASE-02 local backlog reconciles over the tested window.",
    ],
}
(CASE / "review" / "independent-verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(json.dumps(verdict, indent=2))
if failed:
    raise SystemExit(1)
