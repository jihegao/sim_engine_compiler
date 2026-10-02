"""Independent, read-only H02.var04 source and native evidence replay."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
PARENT = ROOT / "H02-var01-system-damage-direct-repair-v1.0.0/system-input.json"
INSTALL = Path(r"C:\Program Files\Systecon\SIMLOX")
OUT = CASE / "review/independent-readonly-2026-10-02.json"
FAILURES = []
CHECKS = 0
EVENT_CHECKS = 0
IN_EVENT_REPLAY = False


def ck(label, condition):
    global CHECKS, EVENT_CHECKS
    CHECKS += 1
    if IN_EVENT_REPLAY:
        EVENT_CHECKS += 1
    if not condition:
        FAILURES.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path, native=False):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text) if native else text)


def tables(obj):
    return {t["name"]: t for t in obj.get("model", obj.get("report"))["tables"]}


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def columns(table):
    return [column["name"] for column in table["columns"]]


def records(table):
    return [dict(zip(columns(table), row)) for row in rows(table)]


def near(actual, expected, tol=.0002):
    return isinstance(actual, (int, float)) and abs(actual-expected) < tol


def occupancy(a, b, start, end):
    return max(0, min(b, end)-max(a, start))/(b-a)


contract = read(CASE / "contract.json")
diff = read(CASE / "exact-diff.json")
parent = tables(read(PARENT))
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
    source[arm] = tables(read(path))
    ck(arm + " source SHA", sha(path) == contract["sources_sha256"][arm] == diff[f"{arm}_sha256"])
    ck(arm + " table set", set(source[arm]) == set(parent))
    changed = {name for name in parent if parent[name] != source[arm][name]}
    wanted = ({"SystemRepair", "ProblemDescription"} if arm == "explicit"
              else {"SystemRepair", "DamageRepair", "ProblemDescription"})
    ck(arm + " parent table delta", changed == wanted)
    if arm == "explicit":
        ck("parent-to-explicit exact diff objects", diff["parent_to_explicit"]["changed_tables"]
           == {name: {"before": parent[name], "after": source[arm][name]} for name in changed})
    ck(arm + " authored row table count", sum(bool(rows(t)) for t in source[arm].values())
       == (18 if arm == "explicit" else 17))
ck("pairwise only DamageRepair and description", {name for name in source["explicit"]
   if source["explicit"][name] != source["fallback"][name]}
   == {"DamageRepair", "ProblemDescription"})
ck("pairwise exact diff objects", diff["explicit_to_fallback"]["changed_tables"]
   == {name: {"before": source["explicit"][name], "after": source["fallback"][name]}
       for name in ("DamageRepair", "ProblemDescription")})
ck("ordinary SystemRepair DIRPT2 unchanged", source["explicit"]["SystemRepair"]
   == source["fallback"]["SystemRepair"]
   and rows(source["explicit"]["SystemRepair"])[0][2] == 2)
ck("DamageRepair DIRPT1 absent only in fallback", rows(source["explicit"]["DamageRepair"])[0][3] == 1
   and rows(source["fallback"]["DamageRepair"]) == [])

closure_sha = {}
report_sha = {}
summary_by_arm = {}
observed = {}
source_checks = CHECKS
for arm, duration in (("explicit", 1), ("fallback", 2)):
    run = CASE / f"runs/h02-var04-{arm}-v100-ssh-20261002-01"
    invocation = read(run / "invocation.json")
    closure = read(run / "closure.json")
    steps = read(run / "steps.json")
    ck(arm + " run ID/invocation SHA", invocation["run_id"] == closure["run_id"] == run.name
       and closure["invocation_sha256"] == sha(run / "invocation.json"))
    ck(arm + " source/run SHA", invocation["input_sha256"] == sha(CASE / f"{arm}-input.json")
       == sha(run / "input.json") and invocation["parent_sha256"] == sha(PARENT))
    ck(arm + " SSH/session/mutex/GUI", invocation["execution_mode"] == "ssh_cli_v1"
       and invocation["session_id"] == 0 and invocation["ssh_connection_present"]
       and "sshd.exe" in [name.lower() for name in invocation["ssh_ancestor_names"]]
       and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue"
       and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    ck(arm + " before/after source seal", closure["source_hashes_before"]
       == closure["source_hashes_after"] == invocation["source_hashes_before"])
    paths = {"input": CASE / f"{arm}-input.json", "parent": PARENT,
             "contract": CASE / "contract.json", "manual": installed["manual_pdf"],
             "dictionary": installed["table_dictionary"], "builder": CASE / "build.py",
             "exact_diff": CASE / "exact-diff.json", "diff_checker": CASE / "describe_diff.py",
             "checker": CASE / "check_roundtrip.py",
             "python": Path(invocation["planned_check"]["executable"]),
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
        ck(arm + " native step " + step["name"], step["exit_code"] == 0
           and step["gui_preserved"] and not step["error"]
           and step["status"] == ("calc_observed" if step["name"] == "calc" else "completed"))
    ck(arm + " command binding", all(step["arguments"] == planned["arguments"]
       for step, planned in zip(steps[:3], invocation["planned_commands"]))
       and steps[3]["arguments"] == invocation["planned_report"]["arguments"]
       and steps[4]["arguments"] == invocation["planned_check"]["arguments"])
    ck(arm + " valid SXO/report", (run / "model.sxo").stat().st_size > 1000
       and (run / "report-raw.json").stat().st_size > 1000)
    exported = tables(read(run / "roundtrip-raw.json", native=True))
    for name, table in source[arm].items():
        if rows(table):
            ck(arm + " exact native roundtrip " + name, name in exported
               and columns(table) == columns(exported[name]) and rows(table) == rows(exported[name]))
    closure_sha[arm] = sha(run / "closure.json")
    report_sha[arm] = sha(run / "report-raw.json")

    # The event and report checks below reproduce the separate 7,362-check replay.
    IN_EVENT_REPLAY = True
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    starts = [float(t) for t in re.findall(
        r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission starting", log)]
    damage = [float(t) for t in re.findall(
        r"Time: ([\d.]+) <TEACH-AIR-01,0>Damage BATTLE-LOSS occured", log)]
    returns = [float(t) for t in re.findall(
        r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,\d+> aborted mission completed", log)]
    work = [(float(t), int(i), int(hours)) for t, i, hours in re.findall(
        r"Time: ([\d.]+)  direct repair subtask (\d+) seqno 0 within system DIRP task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for (\d+) hours", log)]
    ends = [(float(t), int(i)) for t, i in re.findall(
        r"Time: ([\d.]+)  direct repair subtask (\d+) seqno 0 within system DIRP task \d+ on <TEACH-AIR-01,0> completed", log)]
    ready = [float(t) for t in re.findall(
        r"Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> System ready", log)]
    ck(arm + " scheduled starts", starts == [8, 20, 32])
    ck(arm + " matched damage", len(damage) == 3 and all(near(x, y)
       for x, y in zip(damage, [8.78145, 21.1446, 32.1965])))
    ck(arm + " matched aborted returns", len(returns) == 3 and all(near(x, y)
       for x, y in zip(returns, [9.28145, 21.6446, 32.393])))
    ck(arm + " work duration and readiness", len(work) == len(ends) == len(ready) == 3
       and all(near(start, returns[i]) and sub == end_sub == i and hours == duration
       and near(end-start, duration) and near(ready[i], end)
       for i, ((start, sub, hours), (end, end_sub)) in enumerate(zip(work, ends))))
    ck(arm + " aborts/no attrition", len(re.findall("mission aborted:", log)) == 3
       and "mission succeeded" not in log and "mission cancelled" not in log
       and "subject to attrition" not in log)
    calc = (run / "run.log").read_text(encoding="utf-8-sig")
    ck(arm + " converter diagnostics", "Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in calc
       and set(re.findall(r"warning #(\d+)", calc)) == {"108", "126", "254"})
    report = tables(read(run / "report-raw.json", native=True))
    system = records(report["SystemResults"])
    stock = records(report["StockTotalResults"])
    summary = records(report["ResultSummary"])[0]
    summary_by_arm[arm] = summary
    ck(arm + " 72 report bins", len(system) == len(stock) == 72)
    for index, (s, st) in enumerate(zip(system, stock)):
        a, b = index/2, (index+1)/2
        ck(f"{arm} bin {index} coordinates", near(s["STINT"], a) and near(s["ETINT"], b)
           and near(st["STINT"], a) and near(st["ETINT"], b))
        expected_system = {key: 0 for key in s if key not in ("UNID", "SID", "STINT", "ETINT")}
        assigned = sum(occupancy(a, b, start-1, end) for start, end in zip(starts, returns))
        flight = sum(occupancy(a, b, start, end) for start, end in zip(starts, returns))
        preflight = sum(occupancy(a, b, start-1, start) for start in starts)
        repair = sum(occupancy(a, b, start, end) for start, end in zip(returns, ready))
        expected_system.update(NSYRY=1-assigned-repair, NSYMA=assigned,
            NSYMR=preflight, NSYMO=flight, NSYUA=repair, NSYA=1-repair,
            NSYRP=repair, FTMO=flight, STACC=flight,
            NDAM=sum(a <= t < b for t in damage),
            SYDT=duration if any(a <= t < b for t in returns) else None,
            NSYDT=sum(a <= t < b for t in returns),
            NREPT=sum(a <= t < b for t in ready))
        for key, expected in expected_system.items():
            ck(f"{arm} System {index} {key}", s[key] is None if expected is None
               else near(s[key], expected))
        expected_stock = {key: 0 for key in st if key not in ("STINT", "ETINT")}
        expected_stock["PNB"] = 1
        for key in ("NBOU", "ROS", "ROST", "WT", "WTT", "WTS"):
            expected_stock[key] = None
        for key, expected in expected_stock.items():
            ck(f"{arm} Stock {index} {key}", st[key] is None if expected is None
               else near(st[key], expected))
    ck(arm + " summary", summary["NREP"] == 1 and near(summary["RTIUP"], 36)
       and near(summary["MTMF"], .5531696677207947)
       and near(summary["MSTF"], 1) and near(summary["MSUF"], 0)
       and near(summary["STMF"], summary["MTMF"]))
    ck(arm + " terminal", near(system[-1]["NSYRY"], 1)
       and near(system[-1]["NSYLA"], 0) and near(stock[-1]["PNB"], 1)
       and near(stock[-1]["NBO"], 0))
    observed[arm] = {"damage_times": damage, "return_times": returns,
                     "repair_start_times": [t for t, i, h in work],
                     "repair_end_times": [t for t, i in ends],
                     "ready_times": ready,
                     "total_repair_hours": sum(end-start for (start, i, h), (end, j) in zip(work, ends)),
                     "summary": summary}
    IN_EVENT_REPLAY = False

ck("summary pair equality", summary_by_arm["explicit"] == summary_by_arm["fallback"])
result = {"schema": "independent-h02-var04-system-damage-fallback-readonly/v1",
          "passed": not FAILURES, "verdict": "GO" if not FAILURES else "NO-GO",
          "checks_passed": CHECKS-len(FAILURES), "checks_total": CHECKS,
          "event_report_checks": EVENT_CHECKS,
          "pairwise_summary_checks": 1,
          "failures": FAILURES, "closure_sha256": closure_sha,
          "report_sha256": report_sha, "observed": observed,
          "scope": "One fixed-seed, one-system <SYSTEM> damage contrast: a DamageRepair DIRPT1 row is selected in the explicit arm; with that row absent, the unchanged ordinary SystemRepair DIRPT2 row supplies direct repair. Three matched damage and repair cycles and all 72 System and Stock bins per arm reconcile.",
          "limits": ["Warning #254 says REPF is ignored for system damage; this is a direct-repair fallback observation, not a repairability-fraction test.",
                     "No item replacement fallback, other damage mechanisms, stations, tasks, GUI visual behavior, or cross-engine parity is established."]}
OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True)+"\n").encode("utf-8"))
print(f"{result['verdict']} {result['checks_passed']}/{result['checks_total']} {OUT}")
for failure in FAILURES[:50]:
    print(failure)
raise SystemExit(0 if not FAILURES else 1)
