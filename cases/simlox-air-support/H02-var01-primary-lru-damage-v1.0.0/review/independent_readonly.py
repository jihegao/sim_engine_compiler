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
PARENT = ROOT / "E01-local-spare-explicit-replacement-v1.0.0/native-input.json"
SCHEMA_DONOR = ROOT / "H02-var01-system-damage-direct-repair-v1.0.0/system-input.json"
INSTALL = Path(r"C:\Program Files\Systecon\SIMLOX")
RUNS = {
    "control": CASE / "runs/h02-var01-lru-control-v100-ssh-20261002-01",
    "lru": CASE / "runs/h02-var01-lru-v100-ssh-20261002-01",
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
ck("schema donor hash", sha(SCHEMA_DONOR) == contract["schema_reference"]["sha256"])
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
parent_tables = tables(read(PARENT))
donor = tables(read(SCHEMA_DONOR))
ck("parent-to-control no added/removed tables", set(parent_tables) == set(source["control"]))
ck("parent-to-control changed only FRT tables/description", {k for k in parent_tables
   if parent_tables[k] != source["control"][k]} == {"System", "Item", "ProblemDescription"})
for key in ("System", "Item"):
    before = records(parent_tables[key])
    after = records(source["control"][key])
    ck(f"{key} FRT 300000 to zero", len(before) == len(after) == 1
       and before[0]["FRT"] == 300000 and after[0]["FRT"] == 0
       and {k: v for k, v in before[0].items() if k != "FRT"}
           == {k: v for k, v in after[0].items() if k != "FRT"})
ck("child adds four damage tables", set(source["lru"]) - set(source["control"])
   == {"DamageType", "MissionDamage", "DamageItem", "DamageReplacement"})
ck("child removes nothing", set(source["control"]) <= set(source["lru"]))
ck("control-to-child changes only description", {k for k in source["control"]
   if source["control"][k] != source["lru"][k]} == {"ProblemDescription"})
ck("damage source rows", rows(source["lru"]["MissionDamage"])
   == [["BASIC-MISSION", "TEACH-AIR-01", "BATTLE-HIT", 1, None, None]]
   and rows(source["lru"]["DamageItem"])
   == [["BATTLE-HIT", "TEACH-AIR-01", "TEACH-LRU-01", 1, 1, None, None]]
   and rows(source["lru"]["DamageReplacement"])
   == [["BATTLE-HIT", "BASE-01", "TEACH-AIR-01", "TEACH-LRU-01", .5, 1, "E01-SURP", None, None]])
for name in ("DamageType", "MissionDamage", "DamageItem"):
    ck(f"{name} donor schema", cols(source["lru"][name]) == cols(donor[name]))
ck("same E01 repair/stock topology", all(source["control"][k] == source["lru"][k]
   for k in ("ItemRepair", "StockAllocation", "TaskBreakDown", "Tasks", "OperationProfile")))
ck("exact diff lineage", diff["parent_sha256"] == sha(PARENT)
   and diff["control_sha256"] == sha(CASE / "control-input.json")
   and diff["lru_sha256"] == sha(CASE / "lru-input.json"))
ck("parent-control diff objects", diff["parent_to_control"] == {
    "added_tables": {}, "removed_tables": [],
    "changed_tables": {k: {"before": parent_tables[k], "after": source["control"][k]}
                       for k in ("Item", "ProblemDescription", "System")},
    "unchanged_table_count": len(parent_tables) - 3})
ck("control-lru diff objects", diff["control_to_lru"] == {
    "added_tables": {k: source["lru"][k] for k in
                     ("DamageItem", "DamageReplacement", "DamageType", "MissionDamage")},
    "removed_tables": [],
    "changed_tables": {"ProblemDescription": {
        "before": source["control"]["ProblemDescription"],
        "after": source["lru"]["ProblemDescription"]}},
    "unchanged_table_count": len(source["control"]) - 1})

damage = (8.78145, 20.7434, 32.3406)
returns = (9.28145, 21.2434, 32.6812)
system_ready = (9.78145, 21.7434, 33.1812)
removed = (9.44811, 21.4101, 32.8479)
repaired = (10.4481, 22.4101, 33.8479)
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
    ck(f"{arm} populated tables", len(populated) == (20 if arm == "control" else 24))
    for name in populated:
        ck(f"{arm} roundtrip {name}", name in exported
           and cols(source[arm][name]) == cols(exported[name])
           and rows(source[arm][name]) == rows(exported[name]))
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    warnings = {"108", "2053"}
    ck(f"{arm} zero converter errors/warnings", f"Input conversion completed. Errors: 0, Warnings: {len(warnings)}, Notes: 0" in calc
       and set(re.findall(r"warning #(\d+)", calc)) == warnings
       and not re.search(r"error #\d+", calc))
    ck(f"{arm} zero FRT warning", "FRT is zero for: TEACH-LRU-01" in calc)
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    actual_damage = [(float(t), int(item)) for t, item in re.findall(
        r"Time: ([0-9.]+) <TEACH-AIR-01,0>Damage BATTLE-HIT occured\. Damaged items: <TEACH-LRU-01,0,(\d+)>", log)]
    ck(f"{arm} damage identity/time", actual_damage == ([] if arm == "control" else
       list(zip(damage, (1, 2, 3)))))
    ck(f"{arm} no attrition", "subject to attrition" not in log)
    for i, start in enumerate((8, 20, 32)):
        mid = f"<BASIC-MISSION,TEACH-UNIT,0,0,{i}>"
        ck(f"{arm} mission {i} launch", f"Time: {start} {mid} mission starting, duration: 2" in log)
        if arm == "control":
            ck(f"control mission {i} success", f"Time: {start+2} {mid} mission success:" in log
               and f"Time: {start+2} {mid} mission completed:" in log)
        else:
            d, r = damage[i], returns[i]
            ck(f"lru mission {i} abort/return", f"Time: {d:g} {mid} mission aborted:" in log
               and f"Time: {r:g} {mid} aborted mission completed:" in log)
    if arm == "control":
        ck("control no repair or stock draw", "system SURP task" not in log
           and "Take replacement item" not in log and "item DIRP task" not in log)
    else:
        ck("lru three spare issues", len(re.findall(r"Take replacement item <TEACH-LRU-01,0,\d+> from stock", log)) == 3)
        ck("lru three repaired returns", len(re.findall(r"Put back replacement item <TEACH-LRU-01,0,\d+> to stock", log)) == 3)
        for i, (r, c, rem, e) in enumerate(zip(returns, system_ready, removed, repaired)):
            task = 2*i
            bad, spare = i + 1, i
            remove_sub, fit_sub, repair_sub, item_task = (0, 1, 2, 1) if i == 0 else ((3, 4, 5, 3) if i == 1 else (6, 7, 8, 5))
            ck(f"lru wave {i} stock issue identity", f"Time: {r:g} <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,{spare}> from stock" in log)
            ck(f"lru wave {i} system SURP start/end", f"Time: {r:g}  system SURP task {task} on <TEACH-AIR-01,0> started" in log
               and f"Time: {c:g}  system SURP task {task} on <TEACH-AIR-01,0> completed" in log
               and near(c-r, .5))
            ck(f"lru wave {i} remove subtask", f"Time: {r:g}  remove subitem subtask {remove_sub} seqno 1 within system SURP task {task} on <TEACH-AIR-01,0> starts performing, planned to last for 0.166667 hours" in log
               and f"Time: {rem:g}  remove subitem subtask {remove_sub} seqno 1 within system SURP task {task} on <TEACH-AIR-01,0> completed" in log)
            ck(f"lru wave {i} fit subtask", f"Time: {rem:g}  fit subitem subtask {fit_sub} seqno 2 within system SURP task {task} on <TEACH-AIR-01,0> starts performing, planned to last for 0.333333 hours" in log
               and f"Time: {c:g}  fit subitem subtask {fit_sub} seqno 2 within system SURP task {task} on <TEACH-AIR-01,0> completed" in log)
            ck(f"lru wave {i} removed physical item", f"Time: {rem:g} <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,{bad}>" in log)
            ck(f"lru wave {i} item DIRP one hour", f"Time: {rem:g}  direct repair subtask {repair_sub} seqno 0 within item DIRP task {item_task} on <TEACH-LRU-01,0,{bad}> starts performing, planned to last for 1 hours" in log
               and f"Time: {e:g}  direct repair subtask {repair_sub} seqno 0 within item DIRP task {item_task} on <TEACH-LRU-01,0,{bad}> completed" in log
               and near(e-rem, 1))
            ck(f"lru wave {i} repaired item stock return", f"Time: {e:g} <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,{bad}> to stock" in log)
            ck(f"lru wave {i} system ready", f"Time: {c:g} <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log)
        ck("lru ready before later mission assignments", system_ready[0] < 19 and system_ready[1] < 31)
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
        if arm == "lru":
            stock_expected["NDD"] = sum(a <= t < b for t in removed)
            stock_expected["NWT"] = stock_expected["NDD"]
        for k in ("NBOU", "WTS"):
            stock_expected[k] = None
        for k in ("ROS", "ROST", "WT", "WTT"):
            stock_expected[k] = 0 if arm == "lru" and stock_expected["NDD"] else None
        for k, value in stock_expected.items():
            ck(f"{arm} stock {j} {k}", st[k] is None if value is None else near(st[k], value))
        ex = {k: 0 for k in s if k not in ("UNID", "SID", "STINT", "ETINT")}
        if arm == "control":
            assigned = sum(frac(a, b, start - 1, start + 2) for start in (8, 20, 32))
            preflight = sum(frac(a, b, start - 1, start) for start in (8, 20, 32))
            flight = sum(frac(a, b, start, start + 2) for start in (8, 20, 32))
            ex.update(NSYRY=1 - assigned, NSYMA=assigned, NSYMR=preflight,
                      NSYMO=flight, NSYA=1, FTMO=flight, STACC=flight, SYDT=None)
        else:
            assigned = sum(frac(a, b, start - 1, r)
                           for start, r in zip((8, 20, 32), returns))
            preflight = sum(frac(a, b, start - 1, start) for start in (8, 20, 32))
            flight = sum(frac(a, b, start, r) for start, r in zip((8, 20, 32), returns))
            repair = sum(frac(a, b, r, c) for r, c in zip(returns, system_ready))
            ex.update(NSYRY=1 - assigned - repair, NSYMA=assigned,
                      NSYMR=preflight, NSYMO=flight, NSYUA=repair,
                      NSYA=1 - repair, NSYRP=repair, FTMO=flight,
                      STACC=flight, NDAM=sum(a <= d < b for d in damage),
                      SYDT=.5 if any(a <= r < b for r in returns) else None,
                      NSYDT=sum(a <= r < b for r in returns),
                      NREPT=sum(a <= c < b for c in system_ready))
        for k, value in ex.items():
            ck(f"{arm} system {j} {k}", s[k] is None if value is None else near(s[k], value))
    flight_hours = sum(float(s["NSYMO"] or 0) * .5 for s in sys)
    ck(f"{arm} flight-hour integral", near(flight_hours,
       6 if arm == "control" else sum(r - start for r, start in zip(returns, (8, 20, 32)))))
    ck(f"{arm} terminal state", near(sys[-1]["NSYRY"] or 0, 1)
       and near(sys[-1]["NSYLA"] or 0, 0) and near(stock[-1]["PNB"], 1))
    sm = summary[0]
    ck(f"{arm} summary replication/horizon", sm["NREP"] == 1 and near(sm["RTILW"], 0)
       and near(sm["RTIUP"], 36))
    if arm == "control":
        ck("control summary factors", near(sm["MTMF"], 1)
           and near(sm["MSTF"], 1) and near(sm["MSUF"], 1)
           and near(sm["STMF"], 1))
    else:
        ck("lru summary factors", near(sm["MTMF"], .5343512296676636)
           and near(sm["MSTF"], 1) and near(sm["MSUF"], 0)
           and near(sm["STMF"], sm["MTMF"]))
    ck(f"{arm} summary uncertainty fields zero", all(near(sm[k], 0) for k in
       ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")))
    observed[arm] = {"run_id": run.name, "damage_identity_times": actual_damage,
                     "flight_hours": flight_hours, "summary": sm,
                     "terminal_ready": sys[-1]["NSYRY"], "terminal_lost": sys[-1]["NSYLA"],
                     "system_bins": len(sys), "stock_bins": len(stock)}

result = {
    "schema": "independent-h02-var01-primary-lru-readonly-review/v1",
    "passed": not FAILURES, "verdict": "GO" if not FAILURES else "NO-GO",
    "checks_passed": CHECKS - len(FAILURES), "checks_total": CHECKS, "failures": FAILURES,
    "observed": observed,
    "scope": "One fixed-seed configured primary-LRU damage contrast. The quiet E01 control completes three missions; the damage child logs physical LRU IDs 1/2/3 damaged on successive missions, issues spare IDs 0/1/2, performs three half-hour system SURP exchanges and three one-hour item DIRP repairs, then returns the repaired IDs to BASE-01 stock. The aircraft regains readiness before later launches.",
    "limits": [
        "E01-to-control sets both System.FRT and Item.FRT to zero; the damage contrast is control-to-child, which adds four damage tables plus description.",
        "One seed, one primary LRU, REPF=1 and explicit DamageReplacement do not establish general fallback priority, other repair fractions or shortage behavior.",
        "GUI visual behavior and cross-engine parity are not tested.",
    ],
}
OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
print(f"{result['verdict']} {result['checks_passed']}/{result['checks_total']} {OUT}")
if FAILURES:
    print("\n".join(FAILURES[:35]))
raise SystemExit(0 if not FAILURES else 1)
