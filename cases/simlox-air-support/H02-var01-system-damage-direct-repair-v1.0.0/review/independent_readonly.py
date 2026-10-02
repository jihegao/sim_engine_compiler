"""Independent, read-only standard-library replay of H02.var01 native evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
OUT = CASE / "review/independent-readonly-2026-10-02.json"
PARENT = ROOT / "H01-var01-certain-attrition-v1.0.0/certain-input.json"
INSTALL = Path(r"C:\Program Files\Systecon\SIMLOX")
RUNS = {
    "attrition": CASE / "runs/h02-var01-attrition-v100-ssh-20261002-01",
    "system": CASE / "runs/h02-var01-system-v100-ssh-20261002-01",
}
FAILURES: list[str] = []
CHECKS = 0


def ck(label: str, ok: bool) -> None:
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILURES.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path, native: bool = False):
    s = path.read_text(encoding="utf-8-sig", errors="replace")
    if native:
        s = re.sub(r",\s*([}\]])", r"\1", s)
    return json.loads(s)


def tables(obj):
    return {t["name"]: t for t in obj.get("model", obj.get("report"))["tables"]}


def cols(t):
    return [c["name"] for c in t["columns"]]


def rows(t):
    return [r for inst in t["instances"] for r in inst["rows"]]


def records(t):
    return [dict(zip(cols(t), r)) for r in rows(t)]


def near(x, y, tol=1e-4):
    return isinstance(x, (int, float)) and math.isclose(x, y, rel_tol=0, abs_tol=tol)


def frac(a, b, lo, hi):
    return max(0.0, min(b, hi) - max(a, lo)) / (b - a)


contract = read(CASE / "contract.json")
diff = read(CASE / "exact-diff.json")
ck("accepted parent hash", sha(PARENT) == contract["accepted_parent"]["sha256"])
ck("attrition source identical parent", (CASE / "attrition-input.json").read_bytes() == PARENT.read_bytes())
for arm in RUNS:
    ck(f"{arm} source hash", sha(CASE / f"{arm}-input.json") == contract["sources_sha256"][arm])
ck("exact diff hash", sha(CASE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"])
for key, path in {
    "simlox_exe": INSTALL / "Simlox.exe",
    "manual_pdf": INSTALL / "UserDoc/SIMLOX.pdf",
    "table_dictionary": INSTALL / "UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt",
}.items():
    ck(f"installed {key} hash", sha(path) == contract["installed_source_sha256"][key])
source = {arm: tables(read(CASE / f"{arm}-input.json")) for arm in RUNS}
ck("child adds only DamageRepair", set(source["system"]) - set(source["attrition"]) == {"DamageRepair"})
ck("child removes nothing", set(source["attrition"]) <= set(source["system"]))
ck("changed existing tables", {k for k in source["attrition"]
   if source["attrition"][k] != source["system"][k]}
   == {"DamageItem", "ProblemDescription"})
ck("attrition versus system IID", rows(source["attrition"]["DamageItem"])
   == [["BATTLE-LOSS", "TEACH-AIR-01", "<ATTRITION>", 1, None, None, None]]
   and rows(source["system"]["DamageItem"])
   == [["BATTLE-LOSS", "TEACH-AIR-01", "<SYSTEM>", 1, None, None, None]])
ck("direct repair source row", rows(source["system"]["DamageRepair"])
   == [["BATTLE-LOSS", "TEACH-AIR-01", "BASE-01", 1, 0, 1, 1,
        None, None, None, None, None]])
ck("same DAMP and schedules", source["attrition"]["MissionDamage"] == source["system"]["MissionDamage"]
   and source["attrition"]["OperationProfile"] == source["system"]["OperationProfile"])
ck("exact diff lineage", diff["parent_sha256"] == sha(PARENT)
   and diff["attrition_sha256"] == sha(CASE / "attrition-input.json")
   and diff["system_sha256"] == sha(CASE / "system-input.json"))
ck("exact diff objects", diff["added_tables"] == {"DamageRepair": source["system"]["DamageRepair"]}
   and diff["removed_tables"] == []
   and diff["changed_tables"] == {k: {"before": source["attrition"][k],
                                      "after": source["system"][k]}
      for k in ("DamageItem", "ProblemDescription")}
   and diff["unchanged_table_count"] == len(source["attrition"]) - 2)

damage = (8.78145, 21.1446, 32.1965)
returns = (9.28145, 21.6446, 32.393)
repairs_done = (10.2814, 22.6446, 33.393)
observed = {}
for arm, run in RUNS.items():
    inv = read(run / "invocation.json")
    cl = read(run / "closure.json")
    steps = read(run / "steps.json")
    ck(f"{arm} run IDs", inv["run_id"] == cl["run_id"] == run.name)
    ck(f"{arm} invocation seal", cl["invocation_sha256"] == sha(run / "invocation.json"))
    ck(f"{arm} input seal", inv["input_sha256"] == sha(CASE / f"{arm}-input.json")
       == sha(run / "input.json"))
    ck(f"{arm} parent seal", inv["parent_sha256"] == sha(PARENT))
    ck(f"{arm} SSH session zero", inv["execution_mode"] == "ssh_cli_v1"
       and inv["session_id"] == 0 and inv["ssh_connection_present"]
       and "sshd.exe" in [s.lower() for s in inv["ssh_ancestor_names"]])
    ck(f"{arm} mutex and GUI", inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue"
       and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    ck(f"{arm} five steps", [s["name"] for s in steps]
       == ["import", "export", "calc", "jsonreport", "check_import_export"])
    for s in steps:
        ck(f"{arm} {s['name']} step", s["exit_code"] == 0 and not s["error"]
           and s["gui_preserved"] and s["started_utc"] <= s["completed_utc"]
           and s["status"] == ("calc_observed" if s["name"] == "calc" else "completed"))
    ck(f"{arm} command binding", all(s["arguments"] == p["arguments"]
       for s, p in zip(steps[:4], inv["planned_commands"])))
    ck(f"{arm} checker binding", steps[4]["arguments"] == inv["planned_check"]["arguments"])
    ck(f"{arm} source before/after", cl["source_hashes_before"] == cl["source_hashes_after"]
       == inv["source_hashes_before"])
    paths = {"input": CASE / f"{arm}-input.json", "parent": PARENT,
             "contract": CASE / "contract.json",
             "manual": INSTALL / "UserDoc/SIMLOX.pdf",
             "dictionary": INSTALL / "UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt",
             "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
             "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
             "python": Path(inv["planned_check"]["executable"]),
             "runner_script": CASE / "run_native_ssh.ps1", "simlox_exe": INSTALL / "Simlox.exe"}
    for key, path in paths.items():
        ck(f"{arm} source seal {key}", sha(path) == cl["source_hashes_before"][key])
    ck(f"{arm} raw set", set(cl["raw"]) == {
       "input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
       "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
       "roundtrip-validation.json", "steps.json"})
    for name, meta in cl["raw"].items():
        data = (run / name).read_bytes()
        ck(f"{arm} raw seal {name}", len(data) == meta["bytes"]
           and hashlib.sha256(data).hexdigest() == meta["sha256"])
    ck(f"{arm} valid native SXO/report", (run / "model.sxo").stat().st_size > 1000
       and (run / "report-raw.json").stat().st_size > 1000)
    exported = tables(read(run / "roundtrip-raw.json", native=True))
    populated = [k for k, t in source[arm].items() if rows(t)]
    ck(f"{arm} populated tables", len(populated) == (16 if arm == "attrition" else 17))
    for name in populated:
        ck(f"{arm} roundtrip {name}", name in exported
           and cols(source[arm][name]) == cols(exported[name])
           and rows(source[arm][name]) == rows(exported[name]))
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    warnings = {"108", "126"} if arm == "attrition" else {"108", "126", "254"}
    ck(f"{arm} zero converter errors/warnings", f"Input conversion completed. Errors: 0, Warnings: {len(warnings)}, Notes: 0" in calc
       and set(re.findall(r"warning #(\d+)", calc)) == warnings
       and not re.search(r"error #\d+", calc))
    if arm == "system":
        ck("warning 254 wording", "Repair fraction (REPF) is ignored for system damages" in calc)
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    actual_damage = [float(t) for t in re.findall(
        r"Time: ([0-9.]+) <TEACH-AIR-01,0>Damage BATTLE-LOSS occured", log)]
    ck(f"{arm} damage event times", actual_damage == list(damage[:1] if arm == "attrition" else damage))
    ck(f"{arm} first mission abort/return", "Time: 8.78145 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:" in log
       and "Time: 9.28145 <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed:" in log)
    if arm == "attrition":
        ck("control attrition consequence", "Time: 8.78145 <TEACH-AIR-01,0> subject to attrition" in log)
        for i, cancel in ((1, 20.3333), (2, 32.3333)):
            mid = f"<BASIC-MISSION,TEACH-UNIT,0,0,{i}>"
            ck(f"control mission {i} cancelled", f"Time: {cancel:g} {mid} mission cancelled:" in log
               and f"{mid} mission starting" not in log)
        ck("control no repair", "direct repair subtask" not in log)
    else:
        ck("system no attrition", "subject to attrition" not in log)
        ck("system three first-mission/next-mission launches", all(
           f"Time: {t} <BASIC-MISSION,TEACH-UNIT,0,0,{i}> mission starting" in log
           for i, t in enumerate((8, 20, 32))))
        for i, (d, r, e) in enumerate(zip(damage, returns, repairs_done)):
            mid = f"<BASIC-MISSION,TEACH-UNIT,0,0,{i}>"
            ck(f"system mission {i} abort/return", f"Time: {d:g} {mid} mission aborted:" in log
               and f"Time: {r:g} {mid} aborted mission completed:" in log)
            ck(f"system repair {i} starts", f"Time: {r:g}  direct repair subtask {i} seqno 0 within system DIRP task {i} on <TEACH-AIR-01,0> started" in log
               and f"Time: {r:g}  direct repair subtask {i} seqno 0 within system DIRP task {i} on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours" in log)
            ck(f"system repair {i} completes", f"Time: {e:g}  direct repair subtask {i} seqno 0 within system DIRP task {i} on <TEACH-AIR-01,0> completed" in log
               and f"Time: {e:g} <TEACH-AIR-01,BASE-01,0> Maintained system arrives <TEACH-AIR-01,0>" in log)
            ck(f"system repair {i} one hour", near(e - r, 1, 1e-4))
            ck(f"system repair {i} readiness", f"Time: {e:g} <TEACH-AIR-01,0> nbr ready increased at unit:" in log)
        ck("system ready before later allocations", repairs_done[0] < 19 and repairs_done[1] < 31)
    rep = tables(read(run / "report-raw.json", native=True))
    ck(f"{arm} report tables", {"ResultSummary", "SystemResults", "StockTotalResults"} <= set(rep))
    sys = records(rep["SystemResults"])
    stock = records(rep["StockTotalResults"])
    summary = records(rep["ResultSummary"])
    ck(f"{arm} 72+72 report bins", len(sys) == len(stock) == 72 and len(summary) == 1)
    for j, (s, st) in enumerate(zip(sys, stock)):
        a, b = j / 2, (j + 1) / 2
        ck(f"{arm} system bin {j} identity/time", s["UNID"] == "Total over all Units"
           and s["SID"] == "Total over all Systems"
           and near(s["STINT"], a) and near(s["ETINT"], b))
        ck(f"{arm} stock bin {j} time", near(st["STINT"], a) and near(st["ETINT"], b))
        stock_expected = {k: 0 for k in st if k not in ("STINT", "ETINT")}
        stock_expected["PNB"] = 1
        for k in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS"):
            stock_expected[k] = None
        for k, value in stock_expected.items():
            ck(f"{arm} stock {j} {k}", st[k] is None if value is None else near(st[k], value))
        ex = {k: 0 for k in s if k not in ("UNID", "SID", "STINT", "ETINT")}
        if arm == "attrition":
            d = damage[0]
            assigned = frac(a, b, 7, d)
            flight = frac(a, b, 8, d)
            alive = frac(a, b, 0, d)
            ex.update(NSYRY=frac(a, b, 0, 7), NSYMA=assigned,
                      NSYMR=frac(a, b, 7, 8), NSYMO=flight,
                      NSYA=alive, NSYLA=1 - alive, STACC=flight,
                      FTMO=1 if flight else (None if a >= 9 else 0), SYDT=None)
        else:
            assigned = sum(frac(a, b, start - 1, r)
                           for start, r in zip((8, 20, 32), returns))
            preflight = sum(frac(a, b, start - 1, start) for start in (8, 20, 32))
            flight = sum(frac(a, b, start, r) for start, r in zip((8, 20, 32), returns))
            repair = sum(frac(a, b, r, e) for r, e in zip(returns, repairs_done))
            ex.update(NSYRY=1 - assigned - repair, NSYMA=assigned,
                      NSYMR=preflight, NSYMO=flight, NSYUA=repair,
                      NSYA=1 - repair, NSYRP=repair, FTMO=flight,
                      STACC=flight, NDAM=sum(a <= d < b for d in damage),
                      SYDT=1 if any(a <= r < b for r in returns) else None,
                      NSYDT=sum(a <= r < b for r in returns),
                      NREPT=sum(a <= e < b for e in repairs_done))
        for k, value in ex.items():
            ck(f"{arm} system {j} {k}", s[k] is None if value is None else near(s[k], value))
    flight_hours = sum(float(s["NSYMO"] or 0) * .5 for s in sys)
    ck(f"{arm} flight-hour integral", near(flight_hours,
       (damage[0] - 8) if arm == "attrition" else sum(r - start for r, start in zip(returns, (8, 20, 32)))))
    ck(f"{arm} terminal state", near(sys[-1]["NSYRY"] or 0, 0 if arm == "attrition" else 1)
       and near(sys[-1]["NSYLA"] or 0, 1 if arm == "attrition" else 0))
    sm = summary[0]
    ck(f"{arm} summary replication/horizon", sm["NREP"] == 1 and near(sm["RTILW"], 0)
       and near(sm["RTIUP"], 36))
    if arm == "attrition":
        ck("control summary factors", near(sm["MTMF"], .21357427537441254)
           and near(sm["MSTF"], 1/3) and near(sm["MSUF"], 0)
           and near(sm["STMF"], sm["MTMF"]))
    else:
        ck("system summary factors", near(sm["MTMF"], .5531696677207947)
           and near(sm["MSTF"], 1) and near(sm["MSUF"], 0)
           and near(sm["STMF"], sm["MTMF"]))
    ck(f"{arm} summary uncertainty fields zero", all(near(sm[k], 0) for k in
       ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")))
    observed[arm] = {"run_id": run.name, "damage_times": actual_damage,
                     "flight_hours": flight_hours, "summary": sm,
                     "terminal_ready": sys[-1]["NSYRY"], "terminal_lost": sys[-1]["NSYLA"],
                     "system_bins": len(sys), "stock_bins": len(stock)}

result = {
    "schema": "independent-h02-var01-readonly-review/v1",
    "passed": not FAILURES, "verdict": "GO" if not FAILURES else "NO-GO",
    "checks_passed": CHECKS - len(FAILURES), "checks_total": CHECKS, "failures": FAILURES,
    "observed": observed,
    "scope": "One fixed-seed configured contrast: certain <ATTRITION> permanently loses the aircraft after first-mission damage, whereas <SYSTEM> plus a local one-hour DamageRepair yields three damage/abort/return/direct-repair cycles and recovered readiness before later scheduled launches.",
    "limits": [
        "The child changes both consequence IID and adds DamageRepair; it does not isolate general fallback priority among damage replacement, damage repair and ordinary repair.",
        "The warning #254 states DamageItem.REPF is ignored for system damage; this run does not vary that field.",
        "One seed and one airframe do not establish other repair modes, fractions, shortages, damaged LRU behavior, GUI visual behavior or cross-engine parity.",
    ],
}
OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
print(f"{result['verdict']} {result['checks_passed']}/{result['checks_total']} {OUT}")
if FAILURES:
    print("\n".join(FAILURES[:35]))
raise SystemExit(0 if not FAILURES else 1)
