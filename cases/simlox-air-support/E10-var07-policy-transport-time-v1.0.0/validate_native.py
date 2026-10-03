"""Author replay of the bounded E10.var07 transport-time native evidence."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E10-var01-fixed-ondem-v1.0.1"
RUN_IDS = {arm: f"e10-var07-{arm}-v100-ssh-20261003-01" for arm in ("det3", "exp3")}
CLOSURE_SHA = {
    "det3": "eb881599bb4c4697d6d08e122dfc44100faf709adcd30a626096e04f73966cd9",
    "exp3": "9c86d9dcff9ca38d6abce74a7b808567945fd5c1e2926a0c3aae18b47a7fc133",
}
RAW_NAMES = {
    "input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
    "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
    "steps.json", "roundtrip-validation.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(table: dict) -> list[dict]:
    cols = [col["name"] for col in table["columns"]]
    return [dict(zip(cols, row)) for inst in table["instances"] for row in inst["rows"]]


def first(log: str, pattern: str) -> float:
    matches = re.findall(pattern, log)
    if len(matches) != 1:
        raise ValueError(f"expected one event for {pattern!r}, found {len(matches)}")
    return float(matches[0])


def close(a: float, b: float, tol: float = 0.00012) -> bool:
    return math.isfinite(a) and math.isfinite(b) and abs(a - b) <= tol


def main() -> int:
    failures: list[str] = []
    checks = 0

    def ck(label: str, passed: bool) -> None:
        nonlocal checks
        checks += 1
        if not passed:
            failures.append(label)

    contract = read(HERE / "contract.json")
    diff = read(HERE / "exact-diff.json")
    cp = contract["accepted_parent"]
    ck("contract identity", (contract["case_id"], contract["variant_id"], contract["case_version"]) == ("E10", "E10.var07", "1.0.0-candidate"))
    ck("exact diff seal", sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"])
    ck("accepted parent seals", sha(PARENT / "native-input-ondem.json") == cp["input_sha256"] and sha(PARENT / "runs" / cp["run_id"] / "closure.json") == cp["native_closure_sha256"] and sha(PARENT / "evidence-index.json") == cp["evidence_index_sha256"])
    data: dict[str, dict] = {}
    for arm, run_id in RUN_IDS.items():
        run = HERE / "runs" / run_id
        ck(f"{arm} source input", sha(HERE / f"native-input-{arm}.json") == contract["native_inputs_sha256"][arm])
        ck(f"{arm} frozen native closure", sha(run / "closure.json") == CLOSURE_SHA[arm])
        inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{arm} run identity", inv["case_id"] == "E10" and inv["variant_id"] == "E10.var07" and inv["arm"] == arm and inv["run_id"] == closure["run_id"] == run_id)
        ck(f"{arm} guarded SSH/GUI", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
        ck(f"{arm} source stable", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
        pins = inv["source_hashes_before"]
        ck(f"{arm} source pins", all(pins[key] == sha(HERE / filename) for key, filename in (("input", f"native-input-{arm}.json"), ("contract", "contract.json"), ("exact_diff", "exact-diff.json"), ("builder", "build.py"), ("diff_builder", "describe_diff.py"), ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1"))))
        ck(f"{arm} parent pins", pins["parent"] == cp["input_sha256"] and pins["parent_closure"] == cp["native_closure_sha256"] and pins["parent_index"] == cp["evidence_index_sha256"])
        ck(f"{arm} installed source pins", pins["simlox_exe"] == contract["source"]["simlox_exe_sha256"] and pins["manual"] == contract["source"]["manual_pdf_sha256"] and pins["dictionary"] == contract["source"]["dictionary_sha256"])
        ck(f"{arm} five completed steps", [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True for step in steps))
        ck(f"{arm} raw set", set(closure["raw"]) == RAW_NAMES)
        for name, meta in closure["raw"].items():
            path = run / name
            ck(f"{arm} raw {name}", path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"])
        ck(f"{arm} copied input", sha(run / "input.json") == contract["native_inputs_sha256"][arm])
        source = populated(parse_native(run / "input.json"))
        exported = populated(parse_native(run / "roundtrip-raw.json"))
        rt = read(run / "roundtrip-validation.json")
        ck(f"{arm} 22 authored tables roundtrip", len(source) == 22 and rt["passed"] is True and rt["differences"] == [] and all(exported.get(name) == table for name, table in source.items()))
        ck(f"{arm} no authored resources", all(name not in source for name in ("Resource", "ResourceAllocation", "TaskResource", "SubTaskResource")))
        conv = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} converter", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conv and Counter(re.findall(r"\(warning #(\d+)\)", conv)) == Counter({"108": 1}))
        ck(f"{arm} native outputs", all((run / filename).stat().st_size > 1000 for filename in ("model.sxo", "model.log", "report-raw.json")))
        report = {table["name"]: table for table in parse_native(run / "report-raw.json")["report"]["tables"]}
        ck(f"{arm} report table scope", {"ResultSummary", "SystemResults", "StockTotalResults"}.issubset(report) and "ResourceResults" not in report)
        system, stock = rows(report["SystemResults"]), rows(report["StockTotalResults"])
        ck(f"{arm} 72 aligned half-hour bins", len(system) == len(stock) == 72 and all(system[i]["STINT"] == stock[i]["STINT"] == i / 2 and system[i]["ETINT"] == stock[i]["ETINT"] == (i + 1) / 2 for i in range(72)))
        ck(f"{arm} one failure repair demand", sum(r["NFAIL"] or 0 for r in system) == sum(r["NREPT"] or 0 for r in system) == sum(r["NDF"] or 0 for r in stock) == 1)
        ck(f"{arm} terminal report", system[-1]["NSYRY"] == system[-1]["NSYA"] == 1 and stock[-1]["NBO"] == 0 and stock[-1]["PNB"] == 1 and all((system[-1][key] or 0) == 0 for key in ("NSYWI", "NSYRP", "NSYTP")))
        ck(f"{arm} mission metric", close(rows(report["ResultSummary"])[0]["MSUF"], 2 / 3, 1e-5))
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} one physical item cycle", all(log.count(token) == 1 for token in ("critical random failure added", "Backorder added", "Backorder removed", "Take replacement item", "Put back replacement item", "transport task 1 starts with 1 items/systems", "transport task 1 arrives with 1 items/systems")))
        ck(f"{arm} item identity", "subitem failed: <TEACH-LRU-01,0,1>" in log and "Take replacement item <TEACH-LRU-01,0,0>" in log and "Replacement item arrives <TEACH-LRU-01,0,0>" in log and "Put back replacement item <TEACH-LRU-01,0,1> to stock" in log)
        ck(f"{arm} unchanged upstream cycle", "Time: 10.1667  transport task 2 starts with 1 items/systems, transport time: 2" in log and "Time: 12.1667  transport task 2 arrives with 1 items/systems" in log and "Time: 13.1667 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item" in log)
        ck(f"{arm} mission outcomes", log.count("mission aborted:") == 1 and log.count("mission success:") == 2 and "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in log)
        ck(f"{arm} no resource allocation", "requests resources: no resources needed" in log and "allocated to maintenance task" not in log)
        try:
            travel = first(log, r"Time: 10  transport task 1 starts with 1 items/systems, transport time: ([0-9.]+)")
            arrival = first(log, r"Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>")
            wait = first(log, r"Backorder removed, waiting time was ([0-9.]+)")
            ready = first(log, r"Time: ([0-9.]+) <TEACH-AIR-01,BASE-01,0> Maintained system arrives")
            ck(f"{arm} travel/arrival/wait/fit", close(arrival - 10, travel) and close(wait, travel) and close(ready - arrival, 1 / 3))
            ck(f"{arm} stock report wait", close(sum((r["NBO"] or 0) * .5 for r in stock), travel, 2e-5))
            # Native event timestamps are printed to four decimals; half-hour
            # report fractions retain more precision than the displayed log.
            ck(f"{arm} readiness report timing", close(system[26]["NSYRY"], max(0, min(1, (13.5 - ready) / .5)), 1e-4) and close(system[27]["NSYRY"], max(0, min(1, (14 - ready) / .5)), 1e-4))
            ck(f"{arm} report repair bin", sum(r["NREPT"] or 0 for r in system) == 1 and system[int(ready * 2)]["NREPT"] == 1)
            data[arm] = {"travel": travel, "arrival": arrival, "wait": wait, "ready": ready, "log": log, "system": system, "stock": stock}
        except ValueError as error:
            ck(f"{arm} unique transport timeline: {error}", False)
    if set(data) == set(RUN_IDS):
        det, exp = data["det3"], data["exp3"]
        ck("det3 frozen timeline", det["travel"] == 3 and det["arrival"] == 13 and det["wait"] == 3 and close(det["ready"], 13 + 1 / 3))
        ck("exp3 observed draw", exp["travel"] > 0 and math.isfinite(exp["travel"]) and not close(exp["travel"], 3) and close(exp["travel"], 3.37148) and close(exp["arrival"], 13.37148) and close(exp["ready"], 13.7048133))
        ck("same pre-demand boundary", all(token in det["log"] and token in exp["log"] for token in ("Time: 9.8829 <TEACH-AIR-01,0> critical random failure added", "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Item demand arrives", "Time: 10 <TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives")))
        ck("random clocks after draw disclosed", "Time: 20 <TEACH-AIR-01,0> Next random failure will occur 23.7461" in det["log"] and "Time: 20 <TEACH-AIR-01,0> Next random failure will occur 23.2987" in exp["log"])
    result = {"schema": "simlox-e10-var07-policy-transport-time-v100-author-validation/v1", "passed": not failures, "checks": checks, "differences": failures, "scope": "bounded_two_arm_native_cli_replay", "observed": {arm: {key: value for key, value in data[arm].items() if key in ("travel", "arrival", "wait", "ready")} for arm in data}, "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
