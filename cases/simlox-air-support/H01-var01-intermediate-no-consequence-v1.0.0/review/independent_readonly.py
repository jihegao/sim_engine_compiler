"""Independent standard-library, read-only replay of H01.var01 DAMP=0.5 evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
OUT = CASE / "review/independent-readonly-2026-10-02.json"
PARENT = ROOT / "A02-single-aircraft-repeated-missions/native-input.json"
INSTALL = Path(r"C:\Program Files\Systecon\SIMLOX")
RUNS = {
    "control": CASE / "runs/h01-var01-intermediate-control-v100-ssh-20261002-01",
    "intermediate": CASE / "runs/h01-var01-intermediate-child-v100-ssh-20261002-01",
}
failures: list[str] = []
checks = 0


def ck(name, ok):
    global checks
    checks += 1
    if not ok:
        failures.append(name)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p, native=False):
    s = p.read_text(encoding="utf-8-sig")
    if native:
        s = re.sub(r",\s*([}\]])", r"\1", s)
    return json.loads(s)


def tables(obj):
    return {t["name"]: t for t in obj.get("model", obj.get("report"))["tables"]}


def cols(t):
    return [c["name"] for c in t["columns"]]


def rows(t):
    return [r for inst in t["instances"] for r in inst["rows"]]


def recs(t):
    return [dict(zip(cols(t), r)) for r in rows(t)]


def near(x, y):
    return isinstance(x, (int, float)) and math.isclose(x, y, abs_tol=1e-7, rel_tol=0)


contract = read(CASE / "contract.json")
diff = read(CASE / "exact-diff.json")
ck("accepted A02 parent", sha(PARENT) == contract["accepted_parent"]["sha256"])
ck("control identical to A02", (CASE / "control-input.json").read_bytes() == PARENT.read_bytes())
for arm in RUNS:
    ck(f"{arm} source hash", sha(CASE / f"{arm}-input.json") == contract["sources_sha256"][arm])
ck("exact diff hash", sha(CASE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"])
for key, p in {
    "manual_pdf": INSTALL / "UserDoc/SIMLOX.pdf",
    "table_dictionary": INSTALL / "UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt",
    "simlox_exe": INSTALL / "Simlox.exe",
}.items():
    ck(f"installed {key}", sha(p) == contract["installed_source_sha256"][key])
source = {arm: tables(read(CASE / f"{arm}-input.json")) for arm in RUNS}
ck("intermediate adds exactly three tables", set(source["intermediate"]) - set(source["control"])
   == {"DamageType", "MissionDamage", "DamageItem"})
ck("intermediate removes no table", set(source["control"]) <= set(source["intermediate"]))
ck("intermediate existing delta only PDESC", {k for k in source["control"]
   if source["control"][k] != source["intermediate"][k]} == {"ProblemDescription"})
ck("intermediate configuration", rows(source["intermediate"]["MissionDamage"])
   == [["BASIC-MISSION", "TEACH-AIR-01", "BATTLE-HIT", .5, None, None]])
ck("zero consequence", rows(source["intermediate"]["DamageItem"])
   == [["BATTLE-HIT", "TEACH-AIR-01", "<ATTRITION>", 0, None, None, None]])
ck("exact diff lineage", diff["parent_sha256"] == sha(PARENT)
   and diff["control_sha256"] == sha(CASE / "control-input.json")
   and diff["intermediate_sha256"] == sha(CASE / "intermediate-input.json"))
ck("exact diff tables", diff["added_tables"] == {k: source["intermediate"][k]
   for k in ("DamageItem", "DamageType", "MissionDamage")}
   and diff["removed_tables"] == []
   and diff["changed_tables"] == {"ProblemDescription": {
       "before": source["control"]["ProblemDescription"],
       "after": source["intermediate"]["ProblemDescription"]}}
   and diff["unchanged_table_count"] == len(source["control"]) - 1)

reports = {}
observed = {}
expected_times = (20.1366, 33.1446)
for arm, run in RUNS.items():
    inv = read(run / "invocation.json")
    cl = read(run / "closure.json")
    steps = read(run / "steps.json")
    ck(f"{arm} run identity", inv["run_id"] == cl["run_id"] == run.name)
    ck(f"{arm} invocation seal", cl["invocation_sha256"] == sha(run / "invocation.json"))
    ck(f"{arm} input binding", inv["input_sha256"] == sha(CASE / f"{arm}-input.json")
       == sha(run / "input.json"))
    ck(f"{arm} parent binding", inv["parent_sha256"] == sha(PARENT))
    ck(f"{arm} SSH session zero", inv["execution_mode"] == "ssh_cli_v1"
       and inv["session_id"] == 0 and inv["ssh_connection_present"]
       and "sshd.exe" in [s.lower() for s in inv["ssh_ancestor_names"]])
    ck(f"{arm} GUI and queue", inv["gui"]["pid"] == 13340
       and inv["gui"]["session_id"] == 1
       and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
    ck(f"{arm} five steps", [s["name"] for s in steps]
       == ["import", "export", "calc", "jsonreport", "check_import_export"])
    for s in steps:
        ck(f"{arm} step {s['name']}", s["exit_code"] == 0 and not s["error"]
           and s["status"] == ("calc_observed" if s["name"] == "calc" else "completed")
           and s["gui_preserved"] and s["started_utc"] <= s["completed_utc"])
    ck(f"{arm} command binding", all(s["arguments"] == p["arguments"]
       for s, p in zip(steps[:4], inv["planned_commands"])))
    ck(f"{arm} check binding", steps[4]["arguments"] == inv["planned_check"]["arguments"])
    ck(f"{arm} frozen source stability", cl["source_hashes_before"]
       == cl["source_hashes_after"] == inv["source_hashes_before"])
    paths = {"input": CASE / f"{arm}-input.json", "parent": PARENT,
             "contract": CASE / "contract.json",
             "manual": INSTALL / "UserDoc/SIMLOX.pdf",
             "dictionary": INSTALL / "UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt",
             "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
             "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
             "python": Path(inv["planned_check"]["executable"]),
             "runner_script": CASE / "run_native_ssh.ps1", "simlox_exe": INSTALL / "Simlox.exe"}
    for name, p in paths.items():
        ck(f"{arm} source seal {name}", sha(p) == cl["source_hashes_before"][name])
    ck(f"{arm} raw set", set(cl["raw"]) == {
        "input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
        "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
        "roundtrip-validation.json", "steps.json"})
    for name, meta in cl["raw"].items():
        data = (run / name).read_bytes()
        ck(f"{arm} raw seal {name}", len(data) == meta["bytes"]
           and hashlib.sha256(data).hexdigest() == meta["sha256"])
    exported = tables(read(run / "roundtrip-raw.json", native=True))
    populated = [k for k, t in source[arm].items() if rows(t)]
    ck(f"{arm} populated source table count", len(populated) == (13 if arm == "control" else 16))
    for name in populated:
        ck(f"{arm} exact roundtrip {name}", name in exported
           and cols(source[arm][name]) == cols(exported[name])
           and rows(source[arm][name]) == rows(exported[name]))
    runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck(f"{arm} zero converter errors", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog
       and set(re.findall(r"warning #(\d+)", runlog)) == {"108", "126"}
       and not re.search(r"error #\d+", runlog))
    ck(f"{arm} valid SXO/report", (run / "model.sxo").stat().st_size > 1000
       and (run / "report-raw.json").stat().st_size > 1000)
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    ck(f"{arm} no attrition/abort", "subject to attrition" not in log
       and "mission aborted" not in log and "mission cancelled" not in log)
    ck(f"{arm} no repair/failure", not re.search(r"Time: [0-9.]+ .*repair (started|completed)|Time: [0-9.]+ .*failure (occurred|occured)", log, re.I))
    for idx, t in enumerate((8, 20, 32)):
        mid = f"<BASIC-MISSION,TEACH-UNIT,0,0,{idx}>"
        for hour, phrase in ((t - 1, "mission activated, systems requested: 1"),
                             (t, "mission starting, duration: 2"),
                             (t + 2, "mission success:"), (t + 2, "mission completed:")):
            ck(f"{arm} mission {idx} {phrase}", f"Time: {hour} {mid} {phrase}" in log)
        ck(f"{arm} mission {idx} allocated aircraft", f"{mid} mission allocates system: <TEACH-AIR-01,0>" in log)
        ck(f"{arm} mission {idx} ready again", f"Time: {t+2} <TEACH-AIR-01,0> nbr ready increased at unit:" in log)
    hits = [float(x) for x in re.findall(r"Time: ([0-9.]+) <TEACH-AIR-01,0>Damage BATTLE-HIT occured", log)]
    if arm == "control":
        ck("control no damage", not hits and "Damage " not in log)
    else:
        ck("intermediate exact two hit times", hits == list(expected_times))
        ck("intermediate no prelaunch/intermission hits", all(any(start < t < start + 2
           for start in (8, 20, 32)) for t in hits))
        ck("first mission no hit", not any(8 < t < 10 for t in hits))
        ck("second and third mission each one hit", sum(20 < t < 22 for t in hits) == 1
           and sum(32 < t < 34 for t in hits) == 1)
        ck("at most one same-type hit per mission", all(sum(start < t < start + 2 for t in hits) <= 1
           for start in (8, 20, 32)))
    rep = tables(read(run / "report-raw.json", native=True))
    ck(f"{arm} report tables", {"ResultSummary", "SystemResults", "StockTotalResults"} <= set(rep))
    sys = recs(rep["SystemResults"])
    stock = recs(rep["StockTotalResults"])
    summary = recs(rep["ResultSummary"])
    ck(f"{arm} 72+72 bins", len(sys) == len(stock) == 72 and len(summary) == 1)
    for i, (s, st) in enumerate(zip(sys, stock)):
        a, b = i / 2, (i + 1) / 2
        ck(f"{arm} system bin {i} identity/time", s["UNID"] == "Total over all Units"
           and s["SID"] == "Total over all Systems" and near(s["STINT"], a) and near(s["ETINT"], b))
        ck(f"{arm} stock bin {i} time", near(st["STINT"], a) and near(st["ETINT"], b))
        active = any(start <= a < start + 3 for start in (7, 19, 31))
        flight = any(start <= a < start + 2 for start in (8, 20, 32))
        preflight = a in (7, 7.5, 19, 19.5, 31, 31.5)
        exp = {k: 0 for k in s if k not in ("UNID", "SID", "STINT", "ETINT")}
        exp.update(NSYRY=0 if active else 1, NSYMA=1 if active else 0,
                   NSYMR=1 if preflight else 0, NSYMO=1 if flight else 0,
                   NSYA=1, FTMO=1 if flight else 0, STACC=1 if flight else 0,
                   NDAM=sum(a <= t < b for t in hits), SYDT=None)
        for k, value in exp.items():
            ck(f"{arm} system {i} {k}", s[k] is None if value is None else near(s[k], value))
        sexp = {k: 0 for k in st if k not in ("STINT", "ETINT")}
        sexp["PNB"] = 1
        for k in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS"):
            sexp[k] = None
        for k, value in sexp.items():
            ck(f"{arm} stock {i} {k}", st[k] is None if value is None else near(st[k], value))
    ck(f"{arm} six aircraft flight hours", near(sum(s["NSYMO"] * .5 for s in sys), 6))
    ck(f"{arm} damage bin sum", sum(s["NDAM"] for s in sys) == len(hits))
    ck(f"{arm} terminal ready/stock", near(sys[-1]["NSYRY"], 1)
       and near(sys[-1]["NSYA"], 1) and near(sys[-1]["NSYLA"], 0)
       and near(stock[-1]["PNB"], 1))
    ck(f"{arm} summary", summary[0] == {"NREP": 1, "RTILW": 0, "RTIUP": 36,
       "MTMF": 1, "RSMTMF": 0, "MSTF": 1, "RSMSTF": 0,
       "MSUF": 1, "RSMSUF": 0, "STMF": 1, "RSSTMF": 0})
    reports[arm] = {"summary": summary[0], "system": sys, "stock": stock}
    observed[arm] = {"run_id": run.name, "hit_times": hits,
                     "hits_by_mission": [sum(start < t < start + 2 for t in hits)
                                         for start in (8, 20, 32)],
                     "flight_hours": sum(s["NSYMO"] * .5 for s in sys),
                     "system_bins": len(sys), "stock_bins": len(stock)}

ck("paired result summary equal", reports["control"]["summary"] == reports["intermediate"]["summary"])
ck("paired stock tables equal", reports["control"]["stock"] == reports["intermediate"]["stock"])
for i, (a, b) in enumerate(zip(reports["control"]["system"], reports["intermediate"]["system"])):
    ck(f"paired system {i} equal except NDAM", {k: v for k, v in a.items() if k != "NDAM"}
       == {k: v for k, v in b.items() if k != "NDAM"})

result = {
    "schema": "independent-h01-var01-intermediate-readonly-review/v1",
    "passed": not failures, "verdict": "GO" if not failures else "NO-GO",
    "checks_passed": checks - len(failures), "checks_total": checks, "failures": failures,
    "observed": observed,
    "scope": "One fixed seed, DAMP=0.5, three two-hour fixed missions, and a zero-probability attrition consequence. The first mission has no BATTLE-HIT; the second and third each have one in-flight hit, with all three sorties successful and SystemResults.NDAM matching the two events.",
    "limits": [
        "Three fixed-seed opportunities do not calibrate the 0.5 probability, prove independence, or establish a population timing law.",
        "PROB=0 prevents the modeled attrition consequence, so no positive damage consequence, item damage, repair or attrition behavior is proved.",
        "Other DAMP values, DAMRT settings, continuous missions, multiple aircraft, GUI visual behavior and cross-engine parity remain untested.",
    ],
}
OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
print(f"{result['verdict']} {result['checks_passed']}/{result['checks_total']} {OUT}")
if failures:
    print("\n".join(failures[:30]))
raise SystemExit(0 if not failures else 1)
