"""Read-only replay of the excluded E09 v1.0.0 three-arm diagnostic."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "e09-backorder-priority-v100-ssh-20261004-01"
ARMS = ("fifo", "priority", "disabled")
CHECKS: list[tuple[str, bool]] = []


def check(label: str, passed: bool) -> None:
    CHECKS.append((label, bool(passed)))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_report(path: Path) -> dict:
    source = path.read_text(encoding="utf-8-sig")
    check(f"native trailing-comma syntax {path.name}", bool(re.search(r",\s*]\s*}\s*}$", source)))
    return json.loads(re.sub(r",\s*([}\]])", r"\1", source))


def table_map(doc: dict, root: str) -> dict[str, dict]:
    return {t["name"]: t for t in doc[root]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def mapped(table: dict) -> list[dict]:
    names = [col["name"] for col in table["columns"]]
    return [dict(zip(names, row, strict=True)) for row in rows(table)]


contract = load(CASE / "contract.json")
closure = load(RUN / "closure.json")
invocation = load(RUN / "invocation.json")
steps = load(RUN / "steps.json")
outcome = load(RUN / "outcome.json")

check("contract run ID", contract["run_id"] == RUN.name)
check("closure run ID", closure["run_id"] == RUN.name)
check("closure clean", closure["error"] is None)
check("outcome clean", outcome["error"] is None)
check("invocation hash", digest(RUN / "invocation.json") == closure["invocation_sha256"])
check("session zero", invocation["session_id"] == 0)
check("SSH ancestor", "sshd.exe" in invocation["ssh_ancestor_names"])
check("serial mutex", invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
check("GUI identity", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and bool(invocation["gui"]["start_utc"]))
check("12 serial steps", [s["name"] for s in steps] == [f"{arm}_{stage}" for arm in ARMS for stage in ("import", "export", "calc", "report")])
for step in steps:
    check(f"step succeeded {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None)
    check(f"GUI preserved {step['name']}", step["gui_preserved"] is True)

parent = CASES / "E12-var02-two-fault-control-v1.0.0"
sources = {
    "contract": CASE / "contract.json",
    "fifo": CASE / "fifo-input.json",
    "priority": CASE / "priority-input.json",
    "disabled": CASE / "disabled-input.json",
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
for key, before in closure["source_hashes_before"].items():
    check(f"source unchanged {key}", before == closure["source_hashes_after"][key] == invocation["source_hashes_before"][key])
    if key in sources:
        check(f"source hash {key}", digest(sources[key]) == before)
for arm in ARMS:
    check(f"contract input hash {arm}", contract["inputs_sha256"][arm] == closure["source_hashes_before"][arm])
for key in ("parent_input", "parent_closure", "parent_signoff"):
    check(f"contract parent seal {key}", contract["dependency"][f"{key}_sha256"] == closure["source_hashes_before"][key])
for prerequisite, key in (("E03", "e03_signoff"), ("E07", "e07_signoff")):
    item = next(p for p in contract["dependency"]["instructional_prerequisites"] if p["case_id"] == prerequisite)
    check(f"prerequisite {prerequisite}", item["signoff_sha256"] == closure["source_hashes_before"][key])
check("manual seal", contract["manual"]["sha256"] == closure["source_hashes_before"]["manual"])

check("32 sealed raw files", len(closure["raw"]) == 32)
for name, seal in closure["raw"].items():
    path = RUN / name
    check(f"raw exists {name}", path.is_file())
    check(f"raw size {name}", path.stat().st_size == seal["bytes"])
    check(f"raw SHA {name}", digest(path) == seal["sha256"])

parent_tables = table_map(load(sources["parent_input"]), "model")
models = {arm: table_map(load(CASE / f"{arm}-input.json"), "model") for arm in ARMS}
for arm, model in models.items():
    check(f"run-local source copy {arm}", digest(RUN / f"{arm}-input.json") == contract["inputs_sha256"][arm])
    check(f"32 authored tables {arm}", len(model) == 32)
    check(f"same table set {arm}", model.keys() == parent_tables.keys())
    changed = {name for name in model if model[name] != parent_tables[name]}
    check(f"four changed parent tables {arm}", changed == {"ProblemDescription", "Control", "Station", "StockAllocation"})
    exported = table_map(load(RUN / f"{arm}-roundtrip-raw.json"), "model")
    for name, table in model.items():
        original = mapped(table)
        if not original:
            continue
        check(f"roundtrip table {arm}/{name}", name in exported)
        if name not in exported:
            continue
        returned = mapped(exported[name])
        check(f"roundtrip count {arm}/{name}", len(original) == len(returned))
        for index, (a, b) in enumerate(zip(original, returned)):
            for field, value in a.items():
                if value is not None:
                    check(f"roundtrip cell {arm}/{name}/{index}/{field}", b.get(field) == value)
    converter = (RUN / f"{arm}-run.log").read_text(encoding="latin-1")
    check(f"converter zero errors {arm}", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter)
    check(f"converter only #108 {arm}", re.findall(r"\(warning #(\d+)\)", converter) == ["108"])
    check(f"usable SXO {arm}", (RUN / f"{arm}.sxo").stat().st_size > 100000)
    check(f"completed arm {arm}", outcome[arm] == "completed" and outcome["converter_summaries"][arm] == [0, 1, 0])

def values(arm: str, name: str) -> list[dict]:
    return mapped(models[arm][name])

for arm, enbop, bopri in (("fifo", "Y", "N"), ("priority", "Y", "Y"), ("disabled", "N", "Y")):
    check(f"Control.ENBOP {arm}", values(arm, "Control")[0]["ENBOP"] == enbop)
    station = {r["STID"]: r for r in values(arm, "Station")}
    check(f"depot BOPRI {arm}", station["DEPOT-01"]["BOPRI"] == bopri)
    check(f"non-depot stations unchanged {arm}", [r for r in values(arm, "Station") if r["STID"] != "DEPOT-01"] == [r for r in mapped(parent_tables["Station"]) if r["STID"] != "DEPOT-01"])
    stock = {r["STID"]: r["STSIZ"] for r in values(arm, "StockAllocation")}
    check(f"opening stock geometry {arm}", stock == {"BASE-01": 1, "BASE-02": 0, "DEPOT-01": 0})
for left, right, expected in (("fifo", "priority", {"ProblemDescription", "Station"}), ("priority", "disabled", {"ProblemDescription", "Control"})):
    check(f"isolated pair {left}/{right}", {name for name in models[left] if models[left][name] != models[right][name]} == expected)

logs = {arm: (RUN / f"{arm}.log").read_text(encoding="latin-1") for arm in ARMS}
check("FIFO and disabled logs identical", (RUN / "fifo.log").read_bytes() == (RUN / "disabled.log").read_bytes())
for arm, log in logs.items():
    first = log.find("Time: 10.7579 <TEACH-LRU-01,0,DEPOT-01,0> Backorder added")
    second = log.find("Time: 11.5 <TEACH-LRU-01,0,BASE-02,0> Backorder added")
    depot_second = log.find("Time: 11.5 <TEACH-LRU-01,0,DEPOT-01,0> Backorder added")
    repair = log.find("Time: 14.9246 <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,1>")
    check(f"ordered simultaneous backorders {arm}", -1 < first < second < depot_second < repair)
    check(f"depot BO count two {arm}", "Backorders at: <TEACH-LRU-01,0,DEPOT-01,0> Nbr: 2 Backorders:<<TEACH-LRU-01,0,BASE-01,0>,10.7579>,<<TEACH-LRU-01,0,BASE-02,0>,11.5>" in log)
    check(f"BASE-02 aircraft-blocking BO {arm}", "Backorders at: <TEACH-LRU-01,0,BASE-02,0> Nbr: 1 Backorders:<<TEACH-AIR-01,BASE-02,0>,11.5>" in log)
    check(f"BASE-01 local spare consumed {arm}", "Time: 10.7579 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in log)
    check(f"same two depot repairs {arm}", all(f"Time: {time} <TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,{item}>" in log for item, time in ((1, "14.9246"), (2, "15.6667"))))
    expected = ("BASE-02", "BASE-01") if arm == "priority" else ("BASE-01", "BASE-02")
    for item, depart, arrive, target in ((1, "14.9246", "15.9246", expected[0]), (2, "15.6667", "16.6667", expected[1])):
        origin = "BASE-01" if item == 1 else "BASE-02"
        up_start = "10.9246" if item == 1 else "11.6667"
        up_arrival = "13.9246" if item == 1 else "14.6667"
        check(f"failed item leaves origin {arm}/item{item}", f"Time: {up_start}  transport request <<TEACH-LRU-01,0,{item}>,<TEACH-LRU-01,0,{origin},0>,<TEACH-LRU-01,0,DEPOT-01,0>> started" in log)
        check(f"failed item arrives at depot {arm}/item{item}", f"Time: {up_arrival} <TEACH-LRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,{item}>" in log)
        started = re.findall(rf"Time: {depart}\s+transport request <<TEACH-LRU-01,0,{item}>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,([^,]+),0>> started", log)
        arrival = re.findall(rf"Time: {arrive} <TEACH-LRU-01,0,([^,]+),0> Replacement item arrives <TEACH-LRU-01,0,{item}>", log)
        check(f"unique outbound transfer {arm}/item{item}", started == [target])
        check(f"unique physical arrival {arm}/item{item}", arrival == [target])
        check(f"ordered item repair/transport chain {arm}/item{item}", float(up_start) < float(up_arrival) < float(depart) < float(arrive))
        all_depot_out = re.findall(rf"transport request <<TEACH-LRU-01,0,{item}>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,([^,]+),0>> started", log)
        check(f"no duplicated depot dispatch {arm}/item{item}", all_depot_out == [target])
    check(f"priority target uses replacement in aircraft {arm}", f"system SURP task 1 on <TEACH-AIR-01,1> subitem received <TEACH-LRU-01,0,{1 if arm == 'priority' else 2}>" in log)
    check(f"three mission starts each base {arm}", log.count("mission starting, duration: 3.5") == 6)
    check(f"two mission successes {arm}", len(re.findall(r"mission success:", log)) == 2)
    check(f"four mission aborts {arm}", len(re.findall(r"mission aborted:", log)) == 4)

reports = {arm: table_map(native_report(RUN / f"{arm}-report-raw.json"), "report") for arm in ARMS}
for arm, report in reports.items():
    check(f"aggregate report table set {arm}", set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    for table_name in ("SystemResults", "StockTotalResults"):
        bins = mapped(report[table_name])
        check(f"72 half-hour rows {arm}/{table_name}", len(bins) == 72)
        for index, row in enumerate(bins):
            check(f"report bin {arm}/{table_name}/{index}", row["STINT"] == index * 0.5 and row["ETINT"] == (index + 1) * 0.5)
    check(f"one ResultSummary {arm}", len(rows(report["ResultSummary"])) == 1)
for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
    check(f"FIFO/disabled report parity {name}", reports["fifo"][name] == reports["disabled"][name])
check("same mission ResultSummary with priority", reports["fifo"]["ResultSummary"] == reports["priority"]["ResultSummary"])
check("priority changes SystemResults", reports["fifo"]["SystemResults"] != reports["priority"]["SystemResults"])
check("priority changes StockTotalResults", reports["fifo"]["StockTotalResults"] != reports["priority"]["StockTotalResults"])
for arm in ARMS:
    system = mapped(reports[arm]["SystemResults"])
    stock = mapped(reports[arm]["StockTotalResults"])
    check(f"bounded stock NBO {arm}", all(row["NBO"] >= 0 for row in stock))
    check(f"bounded ready count {arm}", all(0 <= row["NSYRY"] <= 2 for row in system))
check("earlier BASE-02 readiness under priority", mapped(reports["priority"]["SystemResults"])[32]["NSYRY"] > mapped(reports["fifo"]["SystemResults"])[32]["NSYRY"])
check("earlier aggregate BO clearance under priority", mapped(reports["priority"]["StockTotalResults"])[32]["NBO"] < mapped(reports["fifo"]["StockTotalResults"])[32]["NBO"])

failures = [name for name, passed in CHECKS if not passed]
verdict = {
    "schema": "simlox-e09-v100-independent-diagnostic-replay/v1",
    "run_id": RUN.name,
    "verdict": "NO_GO_FULL_CONTRACT" if not failures else "NO_GO_REPLAY",
    "event_contrast": "GO_BOUNDED" if not failures else "NO_GO",
    "checks": len(CHECKS),
    "passed": len(CHECKS) - len(failures),
    "failed": failures,
    "reason": "Default JSON has no per-station ItemResults; contract requires per-station stock/backorder report rows. Event logs establish the arm contrast, but v1.0.0 remains an excluded diagnostic.",
    "log_sha256": {arm: digest(RUN / f"{arm}.log") for arm in ARMS},
    "scope": "One fixed seed and first two repaired LRUs at one depot; no general priority tie-breaker claim.",
}
(CASE / "review" / "independent-verdict.json").write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(json.dumps(verdict, indent=2))
if failures:
    raise SystemExit(1)
