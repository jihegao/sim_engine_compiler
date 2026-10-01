"""Independent, read-only replay of the two H01.var01 native runs.

Uses only Python's standard library and original model/source/run artifacts. It
does not import or execute the package builder, runner, or author validator.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parent
OUT = HERE / "independent-readonly-2026-10-02.json"
RUNS = {
    "zero": CASE / "runs/h01-zero-v100-ssh-20261002-01",
    "certain": CASE / "runs/h01-certain-v100-ssh-20261002-01",
}
INSTALL = Path(r"C:\Program Files\Systecon\SIMLOX")
SOURCE_PATHS = {
    "input": None,
    "parent": ROOT / "A02-single-aircraft-repeated-missions/native-input.json",
    "table_dictionary": INSTALL / "UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt",
    "manual": INSTALL / "UserDoc/SIMLOX.pdf",
    "contract": CASE / "contract.json",
    "builder": CASE / "build.py",
    "exact_diff": CASE / "exact-diff.json",
    "diff_checker": CASE / "describe_diff.py",
    "checker": CASE / "check_roundtrip.py",
    "runner_script": CASE / "run_native_ssh.ps1",
    "simlox_exe": INSTALL / "Simlox.exe",
}
failures: list[str] = []
checks = 0


def ck(label: str, condition: bool) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, native: bool = False):
    s = path.read_text(encoding="utf-8-sig")
    if native:
        s = re.sub(r",\s*([}\]])", r"\1", s)
    return json.loads(s)


def table_map(obj):
    base = obj.get("model", obj.get("report"))
    return {t["name"]: t for t in base["tables"]}


def row_map(obj):
    return {name: [row for inst in table["instances"] for row in inst["rows"]]
            for name, table in table_map(obj).items()}


def cols(table):
    return [c["name"] for c in table["columns"]]


def records(table):
    names = cols(table)
    return [dict(zip(names, r)) for inst in table["instances"] for r in inst["rows"]]


def near(x, y, tol=2e-5):
    return isinstance(x, (int, float)) and math.isclose(x, y, abs_tol=tol, rel_tol=0)


def occupancy(a, b, start, end):
    return max(0.0, min(b, end) - max(a, start)) / (b - a)


contract = load(CASE / "contract.json")
diff = load(CASE / "exact-diff.json")
parent_path = SOURCE_PATHS["parent"]
ck("accepted parent hash", digest(parent_path) == contract["accepted_parent"]["sha256"])
ck("exact diff hash", digest(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
for key, path in (("simlox_exe", SOURCE_PATHS["simlox_exe"]),
                  ("manual_pdf", SOURCE_PATHS["manual"]),
                  ("table_dictionary", SOURCE_PATHS["table_dictionary"])):
    ck(f"installed {key} fingerprint", digest(path) == contract["installed_source_sha256"][key])

parent = table_map(load(parent_path))
inputs = {arm: load(CASE / f"{arm}-input.json") for arm in RUNS}
src_tables = {arm: table_map(obj) for arm, obj in inputs.items()}
for arm in RUNS:
    ck(f"{arm} source hash", digest(CASE / f"{arm}-input.json") == contract["source_sha256"][arm])
ck("parent to zero changed only description", all(src_tables["zero"][k] == v
   for k, v in parent.items() if k != "ProblemDescription"))
ck("parent to zero adds exactly three tables", set(src_tables["zero"]) - set(parent)
   == {"DamageType", "MissionDamage", "DamageItem"})
ck("parent to zero does not remove tables", not (set(parent) - set(src_tables["zero"])))
ck("zero to certain changes exactly two tables", {k for k in src_tables["zero"]
   if src_tables["zero"][k] != src_tables["certain"][k]}
   == {"MissionDamage", "ProblemDescription"})
ck("damage zero row", row_map(inputs["zero"])["MissionDamage"]
   == [["BASIC-MISSION", "TEACH-AIR-01", "BATTLE-LOSS", 0, None, None]])
ck("damage certain row", row_map(inputs["certain"])["MissionDamage"]
   == [["BASIC-MISSION", "TEACH-AIR-01", "BATTLE-LOSS", 1, None, None]])
ck("attrition row identical", row_map(inputs["zero"])["DamageItem"]
   == row_map(inputs["certain"])["DamageItem"]
   == [["BATTLE-LOSS", "TEACH-AIR-01", "<ATTRITION>", 1, None, None, None]])
ck("damage type identical", row_map(inputs["zero"])["DamageType"]
   == row_map(inputs["certain"])["DamageType"])
ck("exact diff source hashes", diff["parent_sha256"] == contract["accepted_parent"]["sha256"]
   and diff["zero_sha256"] == contract["source_sha256"]["zero"]
   and diff["certain_sha256"] == contract["source_sha256"]["certain"])
ck("exact diff parent delta", diff["parent_to_zero"] == {
    "added_tables": ["DamageItem", "DamageType", "MissionDamage"],
    "changed_tables": ["ProblemDescription"]})
ck("exact diff pair rows", diff["zero_to_certain"] == {
    "MissionDamage": {"before": row_map(inputs["zero"])["MissionDamage"],
                      "after": row_map(inputs["certain"])["MissionDamage"]},
    "ProblemDescription": {"before": row_map(inputs["zero"])["ProblemDescription"],
                           "after": row_map(inputs["certain"])["ProblemDescription"]}})

observed: dict[str, object] = {}
for arm, run in RUNS.items():
    inv = load(run / "invocation.json")
    closure = load(run / "closure.json")
    steps = load(run / "steps.json")
    ck(f"{arm} run IDs", inv["run_id"] == closure["run_id"] == run.name)
    ck(f"{arm} sealed invocation", closure["invocation_sha256"] == digest(run / "invocation.json"))
    ck(f"{arm} input source seal", inv["input_sha256"] == digest(CASE / f"{arm}-input.json")
       == digest(run / "input.json"))
    ck(f"{arm} parent seal", inv["parent_sha256"] == digest(parent_path))
    ck(f"{arm} SSH session", inv["session_id"] == 0
       and inv["execution_mode"] == "ssh_cli_v1"
       and inv["ssh_connection_present"]
       and "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]])
    ck(f"{arm} GUI and queue", inv["gui"]["pid"] == 13340
       and inv["gui"]["session_id"] == 1
       and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
    ck(f"{arm} five ordered native/check steps", [s["name"] for s in steps]
       == ["import", "export", "calc", "jsonreport", "check_import_export"])
    for step in steps:
        ck(f"{arm} {step['name']} completed", step["exit_code"] == 0
           and step["status"] == "completed" and step["gui_preserved"]
           and not step["error"] and step["started_utc"] <= step["completed_utc"])
    ck(f"{arm} command binding", all(s["arguments"] == p["arguments"]
       for s, p in zip(steps[:4], inv["planned_commands"])))
    ck(f"{arm} check binding", steps[4]["arguments"] == inv["planned_check"]["arguments"])
    ck(f"{arm} source before-after stable", closure["source_hashes_before"]
       == closure["source_hashes_after"] == inv["source_hashes_before"])
    source_paths = dict(SOURCE_PATHS)
    source_paths["input"] = CASE / f"{arm}-input.json"
    source_paths["python"] = Path(inv["planned_check"]["executable"])
    for key, path in source_paths.items():
        ck(f"{arm} source seal {key}", digest(path) == closure["source_hashes_before"][key])
    ck(f"{arm} closure raw set", set(closure["raw"]) == {
       "input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
       "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
       "roundtrip-validation.json", "steps.json"})
    for name, meta in closure["raw"].items():
        data = (run / name).read_bytes()
        ck(f"{arm} raw seal {name}", len(data) == meta["bytes"]
           and hashlib.sha256(data).hexdigest() == meta["sha256"])
    ck(f"{arm} valid native output", (run / "model.sxi").stat().st_size > 1000
       and (run / "model.sxo").stat().st_size > 1000)
    runlog = (run / "run.log").read_text(encoding="utf-8-sig")
    ck(f"{arm} converter outcomes", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog
       and "warning #108" in runlog and "warning #126" in runlog
       and not re.search(r"\berror\s*#", runlog, re.I))
    raw_export = table_map(load(run / "roundtrip-raw.json", native=True))
    source = src_tables[arm]
    populated = [k for k, t in source.items() if any(inst["rows"] for inst in t["instances"])]
    ck(f"{arm} 16 populated tables", len(populated) == 16)
    for name in populated:
        ck(f"{arm} roundtrip {name}", name in raw_export
           and cols(source[name]) == cols(raw_export[name])
           and records(source[name]) == records(raw_export[name]))
    report = table_map(load(run / "report-raw.json", native=True))
    ck(f"{arm} report tables", {"ResultSummary", "SystemResults", "StockTotalResults"} <= set(report))
    sr = records(report["SystemResults"])
    st = records(report["StockTotalResults"])
    summary = records(report["ResultSummary"])
    ck(f"{arm} 72 system and stock bins", len(sr) == len(st) == 72 and len(summary) == 1)
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    ck(f"{arm} no ordinary failure or repair", not re.search(r"Time: [0-9.]+ .* failure (occured|occurred)|Time: [0-9.]+ .* repair (started|completed)", log, re.I))
    ck(f"{arm} no repair/PM events", not re.search(r"repair (started|completed)|PMTask (started|completed)", log, re.I))

    if arm == "zero":
        ck("zero no damage/attrition", "Damage BATTLE-LOSS" not in log
           and "subject to attrition" not in log)
        for idx, t in enumerate((8, 20, 32)):
            mid = f"<BASIC-MISSION,TEACH-UNIT,0,0,{idx}>"
            for hour, marker in ((t - 1, "mission ordered"), (t, "mission starting"),
                                 (t + 2, "mission success"), (t + 2, "mission completed")):
                ck(f"zero mission {idx} {marker}", f"Time: {hour} " in log
                   and any(f"Time: {hour} {mid} {marker}" in line
                           for line in log.splitlines()) if marker != "mission ordered"
                   else f"Time: {hour} <TEACH-UNIT> mission ordered: BASIC-MISSION" in log)
            ck(f"zero mission {idx} aircraft", f"{mid} mission allocates system: <TEACH-AIR-01,0>" in log)
        ck("zero no mission abort/cancel", "mission aborted:" not in log and "mission cancelled:" not in log)
    else:
        m = re.search(r"Time: ([0-9.]+) <TEACH-AIR-01,0>Damage BATTLE-LOSS occured", log)
        damage_time = float(m.group(1)) if m else -1
        ck("certain damage during first mission", m is not None and 8 < damage_time < 10)
        ck("certain explicit attrition", f"Time: {damage_time:g} <TEACH-AIR-01,0> subject to attrition" in log)
        ck("certain first abort and completion", f"Time: {damage_time:g} <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:" in log
           and "Time: 9.28145 <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed:" in log)
        ck("certain no first success", "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" not in log)
        for idx, order, cancel in ((1, 19, 20.3333), (2, 31, 32.3333)):
            mid = f"<BASIC-MISSION,TEACH-UNIT,0,0,{idx}>"
            ck(f"certain mission {idx} ordered/activated", f"Time: {order} <TEACH-UNIT> mission ordered: BASIC-MISSION" in log
               and f"Time: {order} {mid} mission activated, systems requested: 1" in log)
            ck(f"certain mission {idx} waits/cancels", f"Time: {order} {mid} mission waiting:" in log
               and f"Time: {cancel:g} {mid} mission cancelled:" in log)
            ck(f"certain mission {idx} never launches", f"{mid} mission starting" not in log
               and f"{mid} mission success" not in log and f"{mid} mission allocates system" not in log)

    for i, (s, stock) in enumerate(zip(sr, st)):
        a, b = i / 2, (i + 1) / 2
        ck(f"{arm} system time bin {i}", near(s["STINT"], a, 1e-8)
           and near(s["ETINT"], b, 1e-8) and s["UNID"] == "Total over all Units"
           and s["SID"] == "Total over all Systems")
        ck(f"{arm} stock time bin {i}", near(stock["STINT"], a, 1e-8)
           and near(stock["ETINT"], b, 1e-8))
        expected_stock = {name: 0 for name in stock if name not in ("STINT", "ETINT")}
        expected_stock["PNB"] = 1
        for name in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS"):
            expected_stock[name] = None
        for name, val in expected_stock.items():
            ck(f"{arm} stock {i} {name}", stock[name] is None if val is None
               else near(stock[name], val, 2e-5))
        expected = {name: 0.0 for name in s if name not in ("UNID", "SID", "STINT", "ETINT")}
        expected["SYDT"] = None
        if arm == "zero":
            missions = ((7, 8, 10), (19, 20, 22), (31, 32, 34))
            assigned = sum(occupancy(a, b, x, z) for x, y, z in missions)
            preflight = sum(occupancy(a, b, x, y) for x, y, z in missions)
            operating = sum(occupancy(a, b, y, z) for x, y, z in missions)
            expected.update(NSYRY=1 - assigned, NSYMA=assigned, NSYMR=preflight,
                            NSYMO=operating, NSYA=1, FTMO=operating, STACC=operating)
        else:
            # The log rounds the damage time to 5 decimals. The report retains
            # finer precision, hence tolerance on the fractional damage bin.
            d = damage_time
            assigned = occupancy(a, b, 7, d)
            operating = occupancy(a, b, 8, d)
            alive = occupancy(a, b, 0, d)
            expected.update(NSYRY=occupancy(a, b, 0, 7), NSYMA=assigned,
                            NSYMR=occupancy(a, b, 7, 8), NSYMO=operating,
                            NSYA=alive, NSYLA=1 - alive, STACC=operating)
            # FTMO is a per-bin flight marker, not fractional aircraft hours.
            expected["FTMO"] = 1 if operating > 0 else (None if a >= 9 else 0)
        for name, val in expected.items():
            ck(f"{arm} system {i} {name}", s[name] is None if val is None
               else near(s[name], val, 2e-5))
    flight = sum(float(s["NSYMO"] or 0) * 0.5 for s in sr)
    ck(f"{arm} flight hour integral", near(flight, 6 if arm == "zero" else damage_time - 8, 2e-5))
    ck(f"{arm} terminal ready/lost", near(sr[-1]["NSYRY"] or 0, 1 if arm == "zero" else 0)
       and near(sr[-1]["NSYLA"] or 0, 0 if arm == "zero" else 1))
    sm = summary[0]
    ck(f"{arm} summary replication/horizon", sm["NREP"] == 1
       and near(sm["RTILW"], 0) and near(sm["RTIUP"], 36))
    if arm == "zero":
        ck("zero summary factors", all(near(sm[k], 1) for k in ("MTMF", "MSTF", "MSUF", "STMF"))
           and all(near(sm[k], 0) for k in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")))
    else:
        ck("certain summary factors", near(sm["MTMF"], 0.21357427537441254, 1e-7)
           and near(sm["MSTF"], 1 / 3, 1e-7) and near(sm["MSUF"], 0)
           and near(sm["STMF"], sm["MTMF"], 1e-7)
           and all(near(sm[k], 0) for k in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")))
    observed[arm] = {"source_sha256": digest(CASE / f"{arm}-input.json"),
                     "run_id": run.name, "damage_time_logged": damage_time if arm == "certain" else None,
                     "flight_hours_from_bins": flight, "summary": sm,
                     "system_bins": len(sr), "stock_bins": len(st)}

result = {
    "schema": "independent-h01-var01-readonly-review/v1",
    "verdict": "GO" if not failures else "NO-GO",
    "passed": not failures,
    "checks_passed": checks - len(failures), "checks_total": checks,
    "failures": failures,
    "observed": observed,
    "scope": "One installed SIMLOX version, one seed, one aircraft, DAMP endpoints 0 and 1, one BATTLE-LOSS damage type with certain <ATTRITION> consequence. The certain arm loses the aircraft at the first-mission damage event, aborts that mission and cancels the two later missions; the zero arm completes all three.",
    "limits": [
        "The exact damage time is a fixed-seed observation; neither its distribution nor any intermediate DAMP probability is established.",
        "The report stock PNB remains 1 in both arms; aircraft loss is established by the event log and SystemResults.NSYLA/NSYRY, not by a stock decrease.",
        "No item damage, repair, repeated DAMRT, continuous mission, multiple aircraft, GUI-only run, or cross-engine behavior is tested.",
    ],
}
OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
print(f"{result['verdict']} {result['checks_passed']}/{result['checks_total']} {OUT}")
if failures:
    print("\n".join(failures[:30]))
raise SystemExit(0 if not failures else 1)
