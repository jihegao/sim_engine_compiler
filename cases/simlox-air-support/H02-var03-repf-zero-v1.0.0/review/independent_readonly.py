"""Independent, read-only standard-library replay of H02.var03 REPF endpoints."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
OUT = CASE / "review/independent-readonly-2026-10-02.json"
PARENT = ROOT / "H02-var01-primary-lru-damage-v1.0.0/lru-input.json"
INSTALL = Path(r"C:\Program Files\Systecon\SIMLOX")
RUNS = {
    "repairable": CASE / "runs/h02-var03-repairable-v100-ssh-20261002-01",
    "discard": CASE / "runs/h02-var03-discard-v100-ssh-20261002-01",
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
ck("accepted parent hash", sha(PARENT) == contract["direct_parent"]["sha256"])
ck("repairable byte-identical parent", (CASE / "repairable-input.json").read_bytes() == PARENT.read_bytes())
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
ck("same business table set", set(source["repairable"]) == set(source["discard"]))
ck("only DamageItem and description changed", {k for k in source["repairable"]
   if source["repairable"][k] != source["discard"][k]}
   == {"DamageItem", "ProblemDescription"})
ck("exact REPF-only business field", rows(source["repairable"]["DamageItem"])
   == [["BATTLE-HIT", "TEACH-AIR-01", "TEACH-LRU-01", 1, 1, None, None]]
   and rows(source["discard"]["DamageItem"])
   == [["BATTLE-HIT", "TEACH-AIR-01", "TEACH-LRU-01", 1, 0, None, None]])
ck("same replacement/repair/stock/schedule topology", all(
   source["repairable"][k] == source["discard"][k]
   for k in ("DamageReplacement", "ItemRepair", "StockAllocation",
             "TaskBreakDown", "Tasks", "OperationProfile", "MissionDamage")))
ck("exact diff lineage", diff["parent_sha256"] == sha(PARENT)
   and diff["repairable_sha256"] == sha(CASE / "repairable-input.json")
   and diff["discard_sha256"] == sha(CASE / "discard-input.json"))
ck("exact diff objects", diff["added_tables"] == []
   and diff["removed_tables"] == []
   and diff["changed_tables"] == {k: {"before": source["repairable"][k],
                                   "after": source["discard"][k]}
      for k in ("DamageItem", "ProblemDescription")}
   and diff["unchanged_table_count"] == len(parent_tables) - 2)

damage = (8.78145, 20.7434, 32.3406)
returns = (9.28145, 21.2434, 32.6812)
system_ready = (9.78145, 21.7434, 33.1812)
removed = (9.44811, 21.4101, 32.8479)
repaired = (10.4481, 22.4101, 33.8479)
discard_damage = (8.78145, 20.1965)
discard_returns = (9.28145, 20.393)
discard_removed = (9.44811, 20.5596)
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
    ck(f"{arm} populated tables", len(populated) == 24)
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
    ck(f"{arm} damage identity/time", actual_damage ==
       (list(zip(damage, (1, 2, 3))) if arm == "repairable" else
        list(zip(discard_damage, (1, 2)))))
    ck(f"{arm} no attrition", "subject to attrition" not in log)
    for i, start in enumerate((8, 20) if arm == "discard" else (8, 20, 32)):
        mid = f"<BASIC-MISSION,TEACH-UNIT,0,0,{i}>"
        ck(f"{arm} mission {i} launch", f"Time: {start} {mid} mission starting, duration: 2" in log)
        d = damage[i] if arm == "repairable" else discard_damage[i]
        r = returns[i] if arm == "repairable" else discard_returns[i]
        ck(f"{arm} mission {i} abort/return", f"Time: {d:g} {mid} mission aborted:" in log
           and f"Time: {r:g} {mid} aborted mission completed:" in log)
    if arm == "repairable":
        ck("repairable three spare issues", len(re.findall(r"Take replacement item <TEACH-LRU-01,0,\d+> from stock", log)) == 3)
        ck("repairable three repaired returns", len(re.findall(r"Put back replacement item <TEACH-LRU-01,0,\d+> to stock", log)) == 3)
        for i, (r, c, rem, e) in enumerate(zip(returns, system_ready, removed, repaired)):
            task = 2*i
            bad, spare = i + 1, i
            remove_sub, fit_sub, repair_sub, item_task = (0, 1, 2, 1) if i == 0 else ((3, 4, 5, 3) if i == 1 else (6, 7, 8, 5))
            ck(f"repairable wave {i} stock issue identity", f"Time: {r:g} <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,{spare}> from stock" in log)
            ck(f"repairable wave {i} system SURP start/end", f"Time: {r:g}  system SURP task {task} on <TEACH-AIR-01,0> started" in log
               and f"Time: {c:g}  system SURP task {task} on <TEACH-AIR-01,0> completed" in log
               and near(c-r, .5))
            ck(f"repairable wave {i} remove subtask", f"Time: {r:g}  remove subitem subtask {remove_sub} seqno 1 within system SURP task {task} on <TEACH-AIR-01,0> starts performing, planned to last for 0.166667 hours" in log
               and f"Time: {rem:g}  remove subitem subtask {remove_sub} seqno 1 within system SURP task {task} on <TEACH-AIR-01,0> completed" in log)
            ck(f"repairable wave {i} fit subtask", f"Time: {rem:g}  fit subitem subtask {fit_sub} seqno 2 within system SURP task {task} on <TEACH-AIR-01,0> starts performing, planned to last for 0.333333 hours" in log
               and f"Time: {c:g}  fit subitem subtask {fit_sub} seqno 2 within system SURP task {task} on <TEACH-AIR-01,0> completed" in log)
            ck(f"repairable wave {i} removed physical item", f"Time: {rem:g} <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,{bad}>" in log)
            ck(f"repairable wave {i} item DIRP one hour", f"Time: {rem:g}  direct repair subtask {repair_sub} seqno 0 within item DIRP task {item_task} on <TEACH-LRU-01,0,{bad}> starts performing, planned to last for 1 hours" in log
               and f"Time: {e:g}  direct repair subtask {repair_sub} seqno 0 within item DIRP task {item_task} on <TEACH-LRU-01,0,{bad}> completed" in log
               and near(e-rem, 1))
            ck(f"repairable wave {i} repaired item stock return", f"Time: {e:g} <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,{bad}> to stock" in log)
            ck(f"repairable wave {i} system ready", f"Time: {c:g} <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log)
        ck("repairable ready before later mission assignments", system_ready[0] < 19 and system_ready[1] < 31)
    else:
        ck("discard first spare issue ID0", "Time: 9.28145 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in log)
        ck("discard first system SURP/ready", "Time: 9.28145  system SURP task 0 on <TEACH-AIR-01,0> started" in log
           and "Time: 9.78145  system SURP task 0 on <TEACH-AIR-01,0> completed" in log
           and "Time: 9.78145 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log)
        for i, t in ((1, discard_removed[0]), (2, discard_removed[1])):
            ck(f"discard damaged physical item {i}", f"Time: {t:g} <TEACH-LRU-01,0,BASE-01,0> Item discarded: <TEACH-LRU-01,0,{i}>" in log)
        ck("discard no item DIRP/stock return", "item DIRP task" not in log
           and "Put back replacement item" not in log and "Finished repair of item" not in log)
        ck("discard second backorder at return", "Time: 20.393 <TEACH-LRU-01,0,BASE-01,0> Backorder added" in log)
        ck("discard no second spare issue", len(re.findall(r"Take replacement item <TEACH-LRU-01,0,\d+> from stock", log)) == 1)
        ck("discard third mission cancelled", "Time: 32.3333 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission cancelled:" in log
           and "<BASIC-MISSION,TEACH-UNIT,0,0,2> mission starting" not in log)
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
        if arm == "repairable":
            stock_expected["PNB"] = 1
            stock_expected["NDD"] = sum(a <= t < b for t in removed)
            stock_expected["NWT"] = stock_expected["NDD"]
        else:
            backorder = frac(a, b, 20.393, 36)
            stock_expected.update(NBO=backorder, PNB=1-backorder,
                                  NDD=sum(a <= t < b for t in (discard_removed[0], discard_returns[1])),
                                  NWT=sum(a <= discard_removed[0] < b for _ in (0,)))
        for k in ("NBOU", "WTS"):
            stock_expected[k] = None
        for k in ("ROS", "ROST", "WT", "WTT"):
            if arm == "repairable" and stock_expected["NDD"]:
                stock_expected[k] = 0
            elif arm == "discard" and a <= discard_removed[0] < b:
                stock_expected[k] = 0
            elif arm == "discard" and a <= discard_returns[1] < b and k in ("ROS", "ROST"):
                stock_expected[k] = 1
            else:
                stock_expected[k] = None
        for k, value in stock_expected.items():
            ck(f"{arm} stock {j} {k}", st[k] is None if value is None else near(st[k], value))
        ex = {k: 0 for k in s if k not in ("UNID", "SID", "STINT", "ETINT")}
        if arm == "repairable":
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
        else:
            assigned = sum(frac(a, b, start - 1, r)
                           for start, r in zip((8, 20), discard_returns))
            preflight = sum(frac(a, b, start - 1, start) for start in (8, 20))
            flight = sum(frac(a, b, start, r) for start, r in zip((8, 20), discard_returns))
            repair = frac(a, b, discard_returns[0], system_ready[0]) + frac(a, b, discard_returns[1], discard_removed[1])
            wait = frac(a, b, discard_removed[1], 36)
            ex.update(NSYRY=1-assigned-repair-wait, NSYMA=assigned,
                      NSYMR=preflight, NSYMO=flight, NSYUA=repair+wait,
                      NSYA=1-repair-wait, NSYRP=repair, NSYWI=wait,
                      FTMO=flight, STACC=flight,
                      NDAM=sum(a <= d < b for d in discard_damage),
                      SYDT=.5 if a <= discard_returns[0] < b else None,
                      NSYDT=sum(a <= discard_returns[0] < b for _ in (0,)),
                      NREPT=sum(a <= system_ready[0] < b for _ in (0,)))
        for k, value in ex.items():
            ck(f"{arm} system {j} {k}", s[k] is None if value is None else near(s[k], value))
    flight_hours = sum(float(s["NSYMO"] or 0) * .5 for s in sys)
    ck(f"{arm} flight-hour integral", near(flight_hours,
       sum(r - start for r, start in zip(returns, (8, 20, 32))) if arm == "repairable"
       else sum(r - start for r, start in zip(discard_returns, (8, 20)))))
    ck(f"{arm} terminal state", near(sys[-1]["NSYRY"] or 0, 1 if arm == "repairable" else 0)
       and near(sys[-1]["NSYWI"] or 0, 0 if arm == "repairable" else 1)
       and near(sys[-1]["NSYLA"] or 0, 0)
       and near(stock[-1]["PNB"], 1 if arm == "repairable" else 0)
       and near(stock[-1]["NBO"], 0 if arm == "repairable" else 1))
    sm = summary[0]
    ck(f"{arm} summary replication/horizon", sm["NREP"] == 1 and near(sm["RTILW"], 0)
       and near(sm["RTIUP"], 36))
    if arm == "repairable":
        ck("repairable summary factors", near(sm["MTMF"], .5343512296676636)
           and near(sm["MSTF"], 1) and near(sm["MSUF"], 0)
           and near(sm["STMF"], sm["MTMF"]))
    else:
        ck("discard summary factors", near(sm["MTMF"], .2790661156177521)
           and near(sm["MSTF"], 2/3) and near(sm["MSUF"], 0)
           and near(sm["STMF"], sm["MTMF"]))
    ck(f"{arm} summary uncertainty fields zero", all(near(sm[k], 0) for k in
       ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")))
    observed[arm] = {"run_id": run.name, "damage_identity_times": actual_damage,
                     "flight_hours": flight_hours, "summary": sm,
                     "terminal_ready": sys[-1]["NSYRY"], "terminal_lost": sys[-1]["NSYLA"],
                     "system_bins": len(sys), "stock_bins": len(stock)}

result = {
    "schema": "independent-h02-var03-repf-endpoints-readonly-review/v1",
    "passed": not FAILURES, "verdict": "GO" if not FAILURES else "NO-GO",
    "checks_passed": CHECKS - len(FAILURES), "checks_total": CHECKS, "failures": FAILURES,
    "observed": observed,
    "scope": "One fixed-seed REPF endpoint contrast on the same damage/replacement/ItemRepair configuration. REPF=1 repairs and returns damaged LRU IDs 1/2/3 to BASE-01 stock, supporting three launches. REPF=0 discards damaged IDs 1/2 without item DIRP; the first local spare is issued, the second return creates a persistent backorder, and the third mission cancels.",
    "limits": [
        "This pair tests REPF endpoints 1 and 0 on one seed, one primary LRU and an explicit DamageReplacement; intermediate probabilities and population frequencies remain untested.",
        "The stock report PNB remains 1 after the first physical spare issue and becomes 0 at the second backorder; physical stock loss is established by item-level log events as well as the later stock-bin transition.",
        "The pair does not establish general repair-data fallback priority or alternative stations.",
        "GUI visual behavior and cross-engine parity are not tested.",
    ],
}
OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
print(f"{result['verdict']} {result['checks_passed']}/{result['checks_total']} {OUT}")
if FAILURES:
    print("\n".join(FAILURES[:35]))
raise SystemExit(0 if not FAILURES else 1)
