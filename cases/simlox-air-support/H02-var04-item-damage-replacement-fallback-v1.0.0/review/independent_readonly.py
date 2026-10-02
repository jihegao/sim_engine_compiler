"""Independent, read-only H02.var04 item replacement fallback replay."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
PARENT = ROOT / "H02-var01-primary-lru-damage-v1.0.0/lru-input.json"
INSTALL = Path(r"C:\Program Files\Systecon\SIMLOX")
OUT = CASE / "review/independent-readonly-2026-10-02.json"
FAILURES = []
CHECKS = 0
EVENT_CHECKS = 0
IN_EVENT = False


def ck(label, condition):
    global CHECKS, EVENT_CHECKS
    CHECKS += 1
    if IN_EVENT:
        EVENT_CHECKS += 1
    if not condition:
        FAILURES.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, native=False):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text) if native else text)


def tables(obj):
    return {t["name"]: t for t in obj.get("model", obj.get("report"))["tables"]}


def columns(table):
    return [c["name"] for c in table["columns"]]


def rows(table):
    return [r for inst in table["instances"] for r in inst["rows"]]


def records(table):
    return [dict(zip(columns(table), r)) for r in rows(table)]


def near(actual, expected, tol=.0002):
    return isinstance(actual, (int, float)) and abs(actual-expected) < tol


def occupy(a, b, start, end):
    return max(0, min(b, end)-max(a, start))/(b-a)


contract = load(CASE / "contract.json")
diff = load(CASE / "exact-diff.json")
parent = tables(load(PARENT))
ck("accepted parent SHA", sha(PARENT) == contract["direct_parent"]["sha256"] == diff["parent_sha256"])
ck("exact diff SHA", sha(CASE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"])
installed = {"simlox_exe": INSTALL / "Simlox.exe",
             "manual_pdf": INSTALL / "UserDoc/SIMLOX.pdf",
             "table_dictionary": INSTALL / "UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"}
for name, path in installed.items():
    ck("installed " + name, sha(path) == contract["installed_source_sha256"][name])

source = {}
for arm in ("explicit", "fallback"):
    path = CASE / f"{arm}-input.json"
    source[arm] = tables(load(path))
    ck(arm + " input SHA", sha(path) == contract["sources_sha256"][arm]
       == diff[f"{arm}_sha256"])
    ck(arm + " table set", set(source[arm]) == set(parent))
    ck(arm + " row-containing tables", sum(bool(rows(t)) for t in source[arm].values())
       == (25 if arm == "explicit" else 24))
ck("parent-to-explicit tables", {k for k in parent if parent[k] != source["explicit"][k]}
   == {"ItemReplacement", "ProblemDescription"})
ck("parent-to-explicit diff objects", diff["parent_to_explicit"]["changed_tables"]
   == {k: {"before": parent[k], "after": source["explicit"][k]}
       for k in ("ItemReplacement", "ProblemDescription")}
   and diff["parent_to_explicit"]["added_tables"] == []
   and diff["parent_to_explicit"]["removed_tables"] == []
   and diff["parent_to_explicit"]["unchanged_table_count"] == len(parent)-2)
ck("explicit-to-fallback tables", {k for k in parent
   if source["explicit"][k] != source["fallback"][k]}
   == {"DamageReplacement", "ProblemDescription"})
ck("explicit-to-fallback diff objects", diff["explicit_to_fallback"]["changed_tables"]
   == {k: {"before": source["explicit"][k], "after": source["fallback"][k]}
       for k in ("DamageReplacement", "ProblemDescription")}
   and diff["explicit_to_fallback"]["added_tables"] == []
   and diff["explicit_to_fallback"]["removed_tables"] == []
   and diff["explicit_to_fallback"]["unchanged_table_count"] == len(parent)-2)
ck("ordinary item replacement SURPT1 unchanged", source["explicit"]["ItemReplacement"]
   == source["fallback"]["ItemReplacement"]
   and rows(source["explicit"]["ItemReplacement"]) ==
   [["TEACH-AIR-01", "TEACH-LRU-01", "BASE-01", 1, 1, None, None, None, None, None]])
ck("damage-specific SURPT0.5 removed", rows(source["explicit"]["DamageReplacement"])
   == [["BATTLE-HIT", "BASE-01", "TEACH-AIR-01", "TEACH-LRU-01", .5, 1, "E01-SURP", None, None]]
   and rows(source["fallback"]["DamageReplacement"]) == [])

closure_sha = {}
report_sha = {}
observed = {}
summary_by_arm = {}
for arm, duration in (("explicit", .5), ("fallback", 1)):
    run = CASE / f"runs/h02-var04-item-{arm}-v100-ssh-20261002-01"
    inv, closure, steps = (load(run / name) for name in
                           ("invocation.json", "closure.json", "steps.json"))
    ck(arm + " identity/invocation seal", inv["run_id"] == closure["run_id"] == run.name
       and closure["invocation_sha256"] == sha(run / "invocation.json"))
    ck(arm + " source/run input seal", inv["input_sha256"] == sha(CASE / f"{arm}-input.json")
       == sha(run / "input.json") and inv["parent_sha256"] == sha(PARENT))
    ck(arm + " SSH/session/mutex/GUI", inv["execution_mode"] == "ssh_cli_v1"
       and inv["session_id"] == 0 and inv["ssh_connection_present"]
       and "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]]
       and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue"
       and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    ck(arm + " source before/after", closure["source_hashes_before"]
       == closure["source_hashes_after"] == inv["source_hashes_before"])
    paths = {"input": CASE / f"{arm}-input.json", "parent": PARENT,
             "contract": CASE / "contract.json", "manual": installed["manual_pdf"],
             "dictionary": installed["table_dictionary"], "builder": CASE / "build.py",
             "exact_diff": CASE / "exact-diff.json", "diff_checker": CASE / "describe_diff.py",
             "checker": CASE / "check_roundtrip.py",
             "python": Path(inv["planned_check"]["executable"]),
             "runner_script": CASE / "run_native_ssh.ps1", "simlox_exe": installed["simlox_exe"]}
    for name, path in paths.items():
        ck(arm + " source seal " + name, sha(path) == closure["source_hashes_before"][name])
    ck(arm + " twelve raw files", set(closure["raw"]) == {"input.json", "model.sxi",
       "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log",
       "model.log", "report-raw.json", "report-export.log", "roundtrip-validation.json", "steps.json"})
    for name, meta in closure["raw"].items():
        payload = (run / name).read_bytes()
        ck(arm + " raw seal " + name, len(payload) == meta["bytes"]
           and hashlib.sha256(payload).hexdigest() == meta["sha256"])
    ck(arm + " five steps", [s["name"] for s in steps]
       == ["import", "export", "calc", "jsonreport", "check_import_export"])
    for step in steps:
        ck(arm + " step " + step["name"], step["exit_code"] == 0
           and step["gui_preserved"] and not step["error"]
           and step["status"] == ("calc_observed" if step["name"] == "calc" else "completed"))
    ck(arm + " command binding", all(s["arguments"] == p["arguments"]
       for s, p in zip(steps[:3], inv["planned_commands"]))
       and steps[3]["arguments"] == inv["planned_report"]["arguments"]
       and steps[4]["arguments"] == inv["planned_check"]["arguments"])
    ck(arm + " valid SXO/report", (run / "model.sxo").stat().st_size > 1000
       and (run / "report-raw.json").stat().st_size > 1000)
    exported = tables(load(run / "roundtrip-raw.json", native=True))
    for name, table in source[arm].items():
        if rows(table):
            ck(arm + " exact native roundtrip " + name, name in exported
               and columns(table) == columns(exported[name]) and rows(table) == rows(exported[name]))
    closure_sha[arm] = sha(run / "closure.json")
    report_sha[arm] = sha(run / "report-raw.json")

    IN_EVENT = True
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    def events(pattern):
        return [(float(t), int(i)) for t, i in re.findall(pattern, log)]
    damage = events(r"Time: ([\d.]+) <TEACH-AIR-01,0>Damage BATTLE-HIT occured\. Damaged items: <TEACH-LRU-01,0,(\d+)>")
    issues = events(r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,(\d+)> from stock")
    arrivals = events(r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)>")
    restocks = events(r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock")
    repair_starts = events(r"Time: ([\d.]+)  direct repair subtask \d+ seqno 0 within item DIRP task \d+ on <TEACH-LRU-01,0,(\d+)> starts performing, planned to last for 1 hours")
    repair_ends = events(r"Time: ([\d.]+)  direct repair subtask \d+ seqno 0 within item DIRP task \d+ on <TEACH-LRU-01,0,(\d+)> completed")
    returns = [float(t) for t in re.findall(
        r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,\d+> aborted mission completed", log)]
    ready = [float(t) for t in re.findall(
        r"Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> System ready", log)]
    ck(arm + " physical item chain", [i for t, i in damage] == [1, 2, 3]
       and [i for t, i in issues] == [0, 1, 2]
       and [i for t, i in arrivals] == [i for t, i in restocks] == [1, 2, 3])
    ck(arm + " SURP/arrival timing", len(returns) == len(ready) == 3
       and all(near(ready[i]-returns[i], duration)
       and near(arrivals[i][0]-returns[i], duration/3 if arm == "explicit" else .5)
       for i in range(3)))
    ck(arm + " one-hour item DIRP/stock return", len(repair_starts) == len(repair_ends) == 3
       and all(bad == repaired == i+1 and near(start, arrivals[i][0])
       and near(end-start, 1) and near(restocks[i][0], end)
       for i, ((start, bad), (end, repaired)) in enumerate(zip(repair_starts, repair_ends))))
    ck(arm + " no shortage/discard/cancel", "Backorder added" not in log
       and "Item discarded" not in log and "mission cancelled" not in log)
    IN_EVENT = False
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck(arm + " converter", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc
       and set(re.findall(r"warning #(\d+)", calc)) == {"108", "2053"})
    IN_EVENT = True
    report = tables(load(run / "report-raw.json", native=True))
    system = records(report["SystemResults"])
    stock = records(report["StockTotalResults"])
    summary = records(report["ResultSummary"])[0]
    summary_by_arm[arm] = summary
    ck(arm + " 72 report bins", len(system) == len(stock) == 72)
    for index, (s, st) in enumerate(zip(system, stock)):
        a, b = index/2, (index+1)/2
        ck(f"{arm} bin {index} coordinates", near(s["STINT"], a)
           and near(s["ETINT"], b) and near(st["STINT"], a) and near(st["ETINT"], b))
        flight = sum(occupy(a, b, start, end) for start, end in zip((8, 20, 32), returns))
        assigned = sum(occupy(a, b, start-1, end) for start, end in zip((8, 20, 32), returns))
        preflight = sum(occupy(a, b, start-1, start) for start in (8, 20, 32))
        repair = sum(occupy(a, b, start, end) for start, end in zip(returns, ready))
        expected_system = {key: 0 for key in s if key not in ("UNID", "SID", "STINT", "ETINT")}
        expected_system.update(NSYRY=1-assigned-repair, NSYMA=assigned,
            NSYMO=flight, NSYMR=preflight, NSYUA=repair, NSYA=1-repair,
            NSYRP=repair, FTMO=flight, STACC=flight,
            NDAM=sum(a <= t < b for t, item in damage),
            SYDT=duration if any(a <= t < b for t in returns) else None,
            NSYDT=sum(a <= t < b for t in returns),
            NREPT=sum(a <= t < b for t in ready))
        for key, expected in expected_system.items():
            ck(f"{arm} System {index} {key}", s[key] is None if expected is None
               else near(s[key], expected))
        expected_stock = {key: 0 for key in st if key not in ("STINT", "ETINT")}
        expected_stock.update(PNB=1, NDD=sum(a <= t < b for t in returns),
                              NWT=sum(a <= t < b for t in returns))
        for key in ("NBOU", "WTS"):
            expected_stock[key] = None
        for key in ("ROS", "ROST", "WT", "WTT"):
            expected_stock[key] = 0 if any(a <= t < b for t in returns) else None
        for key, expected in expected_stock.items():
            ck(f"{arm} Stock {index} {key}", st[key] is None if expected is None
               else near(st[key], expected))
    ck(arm + " summary", summary["NREP"] == 1
       and near(summary["MTMF"], .5343512296676636)
       and near(summary["MSTF"], 1) and near(summary["MSUF"], 0)
       and near(summary["STMF"], summary["MTMF"]))
    ck(arm + " terminal", near(system[-1]["NSYRY"], 1)
       and near(system[-1]["NSYWI"], 0) and near(stock[-1]["PNB"], 1)
       and near(stock[-1]["NBO"], 0))
    observed[arm] = {"damage_identity_times": damage, "stock_issue_identity_times": issues,
                     "damaged_item_arrival_times": arrivals,
                     "repair_start_identity_times": repair_starts,
                     "repair_end_identity_times": repair_ends,
                     "stock_return_identity_times": restocks,
                     "aborted_mission_return_times": returns,
                     "system_ready_times": ready,
                     "summary": summary}
    IN_EVENT = False

ck("pair summary equality", summary_by_arm["explicit"] == summary_by_arm["fallback"])
result = {"schema": "independent-h02-var04-item-replacement-fallback-readonly/v1",
          "passed": not FAILURES, "verdict": "GO" if not FAILURES else "NO-GO",
          "checks_passed": CHECKS-len(FAILURES), "checks_total": CHECKS,
          "event_report_checks": EVENT_CHECKS, "pairwise_summary_checks": 1,
          "failures": FAILURES, "closure_sha256": closure_sha,
          "report_sha256": report_sha, "observed": observed,
          "scope": "One fixed-seed, directly mounted primary-LRU contrast at BASE-01. The explicit DamageReplacement row yields three half-hour system SURP tasks; with that row absent, ordinary ItemReplacement yields three one-hour SURP tasks. Damaged LRUs receive inherited one-hour item repair and return to stock in both arms.",
          "limits": ["No shortage path is observed; the pair does not test alternative stations, multi-item structures, DamageRepair-to-SystemRepair fallback, GUI visual behavior, or cross-engine parity."]}
OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True)+"\n").encode("utf-8"))
print(f"{result['verdict']} {result['checks_passed']}/{result['checks_total']} event/report={EVENT_CHECKS} {OUT}")
for failure in FAILURES[:50]:
    print(failure)
raise SystemExit(0 if not FAILURES else 1)
