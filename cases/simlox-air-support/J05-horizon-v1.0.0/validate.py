"""Author replay of J05.var05 independent SIMPE/RCEND changes and rejection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUN_IDS = {name: f"j05-horizon-{name}-v100-20261001-01" for name in ("baseline", "rcend9", "simpe9", "simpe48")}
ACCEPTED = ("baseline", "rcend9", "simpe48")
checks: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def ck(name: str, result: bool, detail: object = None) -> None:
    checks.append({"name": name, "pass": bool(result), "detail": detail})


def tables(doc: dict) -> dict[str, list[dict]]:
    out = {}
    for t in doc["report"]["tables"]:
        cols = [c["name"] for c in t["columns"]]
        out[t["name"]] = [dict(zip(cols, row)) for i in t["instances"] for row in i["rows"]]
    return out


contract = load(HERE / "contract.json")
sources = {name: parse_native(HERE / f"{name}-input.json") for name in RUN_IDS}
source_tables = {name: {t["name"]: t for t in doc["model"]["tables"]} for name, doc in sources.items()}
ck("parent_identity", sha(HERE / "baseline-input.json") ==
   sha(HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json") == contract["parent_input_sha256"])
for name in RUN_IDS:
    ck(f"{name}_frozen_input", sha(HERE / f"{name}-input.json") == contract["input_sha256"][name])
    if name != "baseline":
        changed = {key for key in source_tables["baseline"] if source_tables["baseline"][key] != source_tables[name][key]}
        ck(f"{name}_exact_changed_tables", changed ==
           ({"ProblemDescription", "ResultCollection"} if name == "rcend9" else {"ProblemDescription", "Control"}))
ck("rcend9_one_field", source_tables["rcend9"]["ResultCollection"]["instances"][0]["rows"] ==
   [["MISSION", .5, 0, 36, None, None], ["SYSTEM", .5, 0, 9, None, None]])
for name, expected in (("simpe9", 9), ("simpe48", 48)):
    baseline_control = source_tables["baseline"]["Control"]["instances"][0]["rows"][0]
    child_control = source_tables[name]["Control"]["instances"][0]["rows"][0]
    ck(f"{name}_one_field", child_control == [baseline_control[0], expected, *baseline_control[2:]]
       and source_tables[name]["ResultCollection"] == source_tables["baseline"]["ResultCollection"])

native = {}
logs = {}
for name, run_id in RUN_IDS.items():
    run = HERE / "runs" / run_id
    closure, invocation, steps = (load(run / f) for f in ("closure.json", "invocation.json", "steps.json"))
    ck(f"{name}_identity", closure["run_id"] == invocation["run_id"] == run_id)
    ck(f"{name}_source_seal", closure["source_hashes_before"] == closure["source_hashes_after"]
       and closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json")
       and closure["source_hashes_before"]["input"] == contract["input_sha256"][name])
    ck(f"{name}_invocation_seal", closure["invocation_sha256"] == sha(run / "invocation.json"))
    ck(f"{name}_raw_seals", len(closure["raw"]) == (8 if name == "simpe9" else 12)
       and all(sha(run / filename) == meta["sha256"] and (run / filename).stat().st_size == meta["bytes"]
               for filename, meta in closure["raw"].items()))
    ck(f"{name}_guard", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0
       and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"]
       and invocation["gui"]["pid"] == 13340 and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
       and all(step["gui_preserved"] for step in steps))
    ck(f"{name}_import_export", [step["name"] for step in steps[:2]] == ["import", "export"]
       and all(step["status"] == "completed" and step["exit_code"] == 0 for step in steps[:2])
       and sha(run / "input.json") == contract["input_sha256"][name]
       and len(populated(sources[name])) == 13
       and all(populated(parse_native(run / "roundtrip-raw.json")).get(k) == v
               for k, v in populated(sources[name]).items()))
    if name not in ACCEPTED:
        continue
    ck(f"{name}_native_complete", closure["error"] is None
       and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"]
       and all(step["status"] == "completed" and step["exit_code"] == 0 for step in steps)
       and load(run / "roundtrip-validation.json")["passed"])
    ck(f"{name}_zero_converter_errors", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in
       (run / "run.log").read_text(encoding="utf-8-sig", errors="replace"))
    logs[name] = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    native[name] = tables(parse_native(run / "report-raw.json"))
    stock = native[name]["StockTotalResults"]
    ck(f"{name}_stock_ledger", len(stock) == 72 and all(
       row["STINT"] == i * .5 and row["ETINT"] == (i + 1) * .5 and row["PNB"] == 1
       and all(value in (0, None) for field, value in row.items() if field not in ("STINT", "ETINT", "PNB"))
       for i, row in enumerate(stock)))
    summary = native[name]["ResultSummary"]
    ck(f"{name}_summary", len(summary) == 1 and summary[0]["NREP"] == 1
       and (summary[0]["RTILW"], summary[0]["RTIUP"], summary[0]["MTMF"], summary[0]["MSTF"]) ==
       (0, 48 if name == "simpe48" else 36, 1, 1))

ck("baseline_rcend_log_identity", logs["baseline"] == logs["rcend9"]
   and logs["baseline"][:2] == ["SIMLOX LOG FILE", "36"])
ck("simpe48_horizon_and_events", logs["simpe48"][:2] == ["SIMLOX LOG FILE", "48"]
   and logs["simpe48"][2:-1] == logs["baseline"][2:]
   and logs["simpe48"][-1] == "Time: 48  Start of day no 2")
for event in ("Time: 7 <TEACH-UNIT> mission ordered", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting",
              "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success",
              "Time: 10 <TEACH-AIR-01,BASE-01,0> System ready"):
    ck(f"event_{event[:22]}", any(event in line for line in logs["baseline"]))
ck("baseline_system_72_bins", len(native["baseline"]["SystemResults"]) == 72
   and all(row["STINT"] == i * .5 and row["ETINT"] == (i + 1) * .5 for i, row in enumerate(native["baseline"]["SystemResults"])))
short = native["rcend9"]["SystemResults"]
ck("rcend9_system_18_bins", len(short) == 18
   and all(row["STINT"] == i * .5 and row["ETINT"] == (i + 1) * .5 for i, row in enumerate(short))
   and (short[-1]["STINT"], short[-1]["ETINT"], short[-1]["NSYRY"], short[-1]["NSYMA"], short[-1]["NSYMO"]) == (8.5, 9, 0, 1, 1))
ck("rcend9_stock_unchanged", native["baseline"]["StockTotalResults"] == native["rcend9"]["StockTotalResults"])
ck("simpe48_series_end36", native["baseline"]["SystemResults"] == native["simpe48"]["SystemResults"]
   and native["baseline"]["StockTotalResults"] == native["simpe48"]["StockTotalResults"])
ck("collection_end_does_not_stop_mission", any("Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in line for line in logs["rcend9"])
   and native["rcend9"]["ResultSummary"][0]["MTMF"] == 1)

diag = HERE / "runs" / RUN_IDS["simpe9"]
diag_closure, diag_steps = load(diag / "closure.json"), load(diag / "steps.json")
diag_log = (diag / "run.log").read_text(encoding="utf-8-sig", errors="replace")
ck("simpe9_conversion_rejection", "(error #107) Result collection end time must be less than simulation period (SIMPE)" in diag_log
   and "(error #204) Some missions may not return before simulation period ends" in diag_log
   and "Input conversion completed. Errors: 2, Warnings: 2, Notes: 0" in diag_log)
ck("simpe9_no_simulation", diag_closure["error"] == "calc output model.sxo absent/empty"
   and [s["name"] for s in diag_steps] == ["import", "export", "calc"]
   and [s["status"] for s in diag_steps] == ["completed", "completed", "failed"]
   and (diag / "model.sxo").stat().st_size == 4 and not (diag / "report-raw.json").exists()
   and not (diag / "model.log").exists())

result = {"schema": "simlox-j05-horizon-author-validation/v1", "case_id": "J05", "variant_id": "J05.var05",
          "version": "1.0.0", "passed": all(c["pass"] for c in checks), "check_count": len(checks),
          "checks": checks, "accepted": ["rcend9", "simpe48"], "diagnostic_rejected": ["simpe9"],
          "scope": "SYSTEM_RCEND9_vs_SIMPE48_separate_changes_with_SIMPE9_native_rejection",
          "limitations": contract["limitations"]}
out = HERE / "review" / "author-validation-2026-10-01.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{sum(c['pass'] for c in checks)}/{len(checks)} author checks: {'PASS' if result['passed'] else 'FAIL'}")
for item in checks:
    if not item["pass"]:
        print(item["name"], item["detail"])
raise SystemExit(0 if result["passed"] else 1)
