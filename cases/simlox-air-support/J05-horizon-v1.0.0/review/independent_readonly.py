"""Independent read-only replay of four sealed J05.var05 native attempts.

Standard library only. No author imports and no SIMLOX invocation. The script
reads frozen sources and ignored raw files, then writes only its JSON result.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUNS = CASE / "runs"
REPORT = Path(__file__).with_name("independent-readonly-2026-10-01.json")
VARIANTS = ("baseline", "rcend9", "simpe9", "simpe48")
SHA = {
    "baseline": "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7",
    "rcend9": "820245982879328592a23d2189bb0bf480136f4365b53a002db9161c08687f0b",
    "simpe9": "fd8e2b5750afdc2495d30cd0d8ea30044a9f9a77732851ea99a6eeaae8846d49",
    "simpe48": "81fcd338490eb7e5abb143e8fc5914cf674f687f87dffee6900fc67d009a5e7e",
}
checks: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ck(name: str, ok: bool, detail: object = None) -> None:
    checks.append({"name": name, "pass": bool(ok), "detail": detail})


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    """Parse native JSON, ignoring only trailing commas outside strings."""
    raw = path.read_text(encoding="utf-8-sig")
    output: list[str] = []
    quote = escape = False
    for i, ch in enumerate(raw):
        if quote:
            output.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                quote = False
        elif ch == '"':
            quote = True
            output.append(ch)
        elif ch == "," and raw[i + 1:].lstrip().startswith(("]", "}")):
            continue
        else:
            output.append(ch)
    return json.loads("".join(output))


def tables(doc: dict) -> dict:
    output = {}
    for table in doc["model"]["tables"]:
        name = table["name"]
        assert name not in output
        output[name] = table
    return output


def rows(doc: dict) -> dict:
    output = {}
    for name, table in tables(doc).items():
        values = [row for instance in table["instances"] for row in instance["rows"]]
        if values:
            assert all(len(row) == len(table["columns"]) for row in values)
            output[name] = ([c["name"] for c in table["columns"]], values)
    return output


def results(doc: dict) -> dict:
    output = {}
    for table in doc["report"]["tables"]:
        name = table["name"]
        assert name not in output
        columns = [c["name"] for c in table["columns"]]
        output[name] = [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]
    return output


def sealed(run: Path, closure: dict) -> bool:
    return (closure["invocation_sha256"] == sha(run / "invocation.json") and
            all((run / file).is_file() and (run / file).stat().st_size == meta["bytes"] and
                sha(run / file) == meta["sha256"] for file, meta in closure["raw"].items()))


contract = load(CASE / "contract.json")
source = {v: native(CASE / f"{v}-input.json") for v in VARIANTS}
source_tables = {v: tables(source[v]) for v in VARIANTS}
source_rows = {v: rows(source[v]) for v in VARIANTS}
manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
ck("manual_dictionary_bytes", sha(manual) == contract["source_manual_sha256"] and
   sha(dictionary) == contract["source_dictionary_sha256"])
ck("accepted_parent_bytes", sha(CASE / "baseline-input.json") ==
   sha(ROOT / "A01-single-aircraft-single-mission" / "native-input.json") == SHA["baseline"])
for v in VARIANTS:
    ck(f"{v}_frozen_input", sha(CASE / f"{v}-input.json") == SHA[v] == contract["input_sha256"][v])
    ck(f"{v}_source_31_tables", len(source_tables[v]) == 31 and len(source_rows[v]) == 13)
for v, behavior in (("rcend9", "ResultCollection"), ("simpe9", "Control"), ("simpe48", "Control")):
    ck(f"{v}_two_table_delta", set(source_tables[v]) == set(source_tables["baseline"]) and
       {name for name in source_tables["baseline"] if source_tables[v][name] != source_tables["baseline"][name]} ==
       {"ProblemDescription", behavior})
ck("rcend9_exact_field", source_rows["rcend9"]["ResultCollection"][1] ==
   [["MISSION", .5, 0, 36, None, None], ["SYSTEM", .5, 0, 9, None, None]] and
   source_tables["rcend9"]["Control"] == source_tables["baseline"]["Control"])
base_control = source_rows["baseline"]["Control"][1][0]
for v, period in (("simpe9", 9), ("simpe48", 48)):
    ck(f"{v}_exact_field", source_rows[v]["Control"][1][0] ==
       [base_control[0], period, *base_control[2:]] and
       source_tables[v]["ResultCollection"] == source_tables["baseline"]["ResultCollection"])

raw: dict[str, dict] = {}
logs: dict[str, list[str]] = {}
reports: dict[str, dict] = {}
gui: dict[str, tuple] = {}
for v in VARIANTS:
    run = RUNS / f"j05-horizon-{v}-v100-20261001-01"
    invocation, closure, steps = (load(run / f) for f in ("invocation.json", "closure.json", "steps.json"))
    raw[v] = {"closure_sha256": sha(run / "closure.json"), "file_sha256":
              {file: meta["sha256"] for file, meta in closure["raw"].items()}}
    gui[v] = (invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["gui"]["start_utc"])
    ck(f"{v}_run_identity", invocation["run_id"] == closure["run_id"] == run.name and
       invocation["variant"] == v and invocation["input_sha256"] == SHA[v])
    ck(f"{v}_closure_seals", sealed(run, closure) and len(closure["raw"]) == (8 if v == "simpe9" else 12))
    before = closure["source_hashes_before"]
    ck(f"{v}_source_seals", before == closure["source_hashes_after"] and
       before["input"] == SHA[v] == sha(run / "input.json") and
       before["parent"] == SHA["baseline"] and
       before["contract"] == sha(CASE / "contract.json") and
       before["builder"] == sha(CASE / "build.py") and
       before["checker"] == sha(CASE / "check_roundtrip.py") and
       before["runner_script"] == sha(CASE / "run_native_ssh.ps1"))
    ck(f"{v}_ssh_gui_queue", invocation["execution_mode"] == "ssh_cli_v1" and
       invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
       "sshd.exe" in invocation["ssh_ancestor_names"] and
       invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and
       invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
       all(step["gui_preserved"] for step in steps))
    ck(f"{v}_import_export", [step["name"] for step in steps[:2]] == ["import", "export"] and
       all(step["status"] == "completed" and step["exit_code"] == 0 for step in steps[:2]) and
       "Import completed!" in (run / "import.log").read_text(encoding="utf-8-sig", errors="replace") and
       "Export completed!" in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"))
    exported = rows(native(run / "roundtrip-raw.json"))
    ck(f"{v}_exact_source_roundtrip", all(exported.get(name) == value for name, value in source_rows[v].items()))
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    if v == "simpe9":
        ck("simpe9_converter_diagnostics", "(error #107) Result collection end time must be less than simulation period (SIMPE)" in conversion and
           "(error #204) Some missions may not return before simulation period ends" in conversion and
           "Errors: 2, Warnings: 2, Notes: 0" in conversion and
           "warning #108" in conversion and "warning #126" in conversion)
        ck("simpe9_sealed_rejection", closure["error"] == "calc output model.sxo absent/empty" and
           [s["name"] for s in steps] == ["import", "export", "calc"] and
           [s["status"] for s in steps] == ["completed", "completed", "failed"] and
           [s["exit_code"] for s in steps] == [0, 0, 0] and
           (run / "model.sxo").stat().st_size == 4 and
           not (run / "report-raw.json").exists() and not (run / "model.log").exists())
        continue
    ck(f"{v}_native_complete", closure["error"] is None and
       [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and
       all(s["status"] == "completed" and s["exit_code"] == 0 for s in steps))
    ck(f"{v}_zero_conversion_errors", "Errors: 0, Warnings: 2, Notes: 0" in conversion and
       "warning #108" in conversion and "warning #126" in conversion and "Saving results" in conversion)
    logs[v] = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    reports[v] = results(native(run / "report-raw.json"))
    summary = reports[v]["ResultSummary"]
    ck(f"{v}_summary", len(summary) == 1 and all(summary[0][key] == expected for key, expected in
       {"NREP": 1, "RTILW": 0, "RTIUP": 48 if v == "simpe48" else 36,
        "MTMF": 1, "MSTF": 1, "MSUF": 1, "STMF": 1}.items()))
    stock = reports[v]["StockTotalResults"]
    ck(f"{v}_stock_72", len(stock) == 72 and all(
       row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 and row["PNB"] == 1 and
       all(value in (0, None) for field, value in row.items() if field not in ("STINT", "ETINT", "PNB"))
       for i, row in enumerate(stock)))

ck("same_gui_identity", len(set(gui.values())) == 1)
ck("baseline_rcend9_events_identical", logs["baseline"] == logs["rcend9"] and logs["baseline"][1] == "36")
ck("simpe48_event_prefix_and_day2", logs["simpe48"][1] == "48" and
   logs["simpe48"][2:-1] == logs["baseline"][2:] and
   logs["simpe48"][-1] == "Time: 48  Start of day no 2")
trace = "\n".join(logs["baseline"])
for name, part in {
    "ordered7": "Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION",
    "allocated7": "Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>",
    "launched8": "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2",
    "task8_5": "Time: 8.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> task starting",
    "task9_5": "Time: 9.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> task completed",
    "success10": "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success",
    "ready10": "Time: 10 <TEACH-AIR-01,BASE-01,0> System ready",
}.items():
    ck(f"event_{name}", part in trace)
ck("one_mission_no_fault", trace.count("mission starting, duration") == 1 and
   "mission cancelled" not in trace and "failure occurred" not in trace)

base_system = reports["baseline"]["SystemResults"]
ck("baseline_system_72_occupancy", len(base_system) == 72 and all(
   row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 and
   row["NSYRY"] == (1 if i < 14 or i >= 20 else 0) and
   row["NSYMA"] == (1 if 14 <= i < 20 else 0) and
   row["NSYMO"] == (1 if 16 <= i < 20 else 0) and
   row["STACC"] == (1 if 16 <= i < 20 else 0)
   for i, row in enumerate(base_system)))
short = reports["rcend9"]["SystemResults"]
ck("rcend9_system_18_prefix", len(short) == 18 and short == base_system[:18] and
   short[-1]["STINT"] == 8.5 and short[-1]["ETINT"] == 9 and
   (short[-1]["NSYRY"], short[-1]["NSYMA"], short[-1]["NSYMO"]) == (0, 1, 1))
ck("rcend9_stock_summary_full", reports["rcend9"]["StockTotalResults"] ==
   reports["baseline"]["StockTotalResults"] and
   reports["rcend9"]["ResultSummary"] == reports["baseline"]["ResultSummary"])
ck("simpe48_system_stock_still_end36", reports["simpe48"]["SystemResults"] == base_system and
   reports["simpe48"]["StockTotalResults"] == reports["baseline"]["StockTotalResults"])

result = {
    "schema": "simlox-j05-horizon-independent-readonly/v1", "case_id": "J05", "variant_id": "J05.var05",
    "reviewer": "independent standard-library raw replay; no author imports or native calls",
    "decision": "bounded_go_with_simpe9_diagnostic" if all(x["pass"] for x in checks) else "no_go",
    "passed": sum(x["pass"] for x in checks), "total": len(checks), "checks": checks,
    "raw": raw,
    "accepted": ["rcend9", "simpe48"], "control": "baseline", "rejected_diagnostic": ["simpe9"],
    "limitations": [
        "One seed and one deterministic mission without failures or inventory movement.",
        "SIMPE9 with all explicit collection ends at36 is converter-rejected; this does not demonstrate a live hour9 simulation cutoff or terminal in-flight state.",
        "Only SYSTEM RCEND is shortened; MISSION time-dependent output and other result types are unverified.",
        "SIMPE48 extends simulation to48 while explicit collection still ends36; report summary RTIUP follows the simulation horizon.",
        "Native JSON trailing commas are normalized only for parsing; closure hashes bind original raw bytes.",
    ],
}
REPORT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print(f"{result['passed']}/{result['total']} {result['decision']}")
for item in checks:
    if not item["pass"]:
        print("FAIL", item["name"], item["detail"])
raise SystemExit(0 if result["decision"].startswith("bounded_go") else 1)
