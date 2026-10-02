"""Independent standard-library read-only H02.var02 nine-run replay."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
PARENT = ROOT / "H02-var01-primary-lru-damage-v1.0.0/lru-input.json"
QUANTITY = ROOT / "G01-var05-qty-two-v1.0.0/native-input.json"
INSTALL = Path(r"C:\Program Files\Systecon\SIMLOX")
OUT = CASE / "review/independent-readonly-2026-10-02.json"
FROZEN_MATRIX = {"control": [0, 0, 0], 1: [2, 2, 1], 2: [1, 2, 0],
                 3: [1, 1, 1], 4: [2, 0, 2], 5: [1, 1, 1],
                 6: [1, 2, 0], 7: [2, 1, 1], 8: [0, 2, 1]}
SOURCE_FAILURES = []
LEDGER_FAILURES = []
SOURCE_CHECKS = 0
LEDGER_CHECKS = 0


def sc(label, condition):
    global SOURCE_CHECKS
    SOURCE_CHECKS += 1
    if not condition:
        SOURCE_FAILURES.append(label)


def lc(label, condition):
    global LEDGER_CHECKS
    LEDGER_CHECKS += 1
    if not condition:
        LEDGER_FAILURES.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, native=False):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text) if native else text)


def tables(obj):
    return {t["name"]: t for t in obj.get("model", obj.get("report"))["tables"]}


def rows(table):
    return [r for inst in table["instances"] for r in inst["rows"]]


def columns(table):
    return [c["name"] for c in table["columns"]]


def records(table):
    return [dict(zip(columns(table), r)) for r in rows(table)]


def near(x, y, tol=.0003):
    return isinstance(x, (int, float)) and abs(x-y) < tol


def occupy(a, b, start, end):
    return max(0, min(b, end)-max(a, start))/(b-a)


contract = load(CASE / "contract.json")
diff = load(CASE / "exact-diff.json")
parent = tables(load(PARENT))
control = tables(load(CASE / "control-input.json"))
sc("parent and quantity reference", sha(PARENT) == contract["direct_parent"]["sha256"]
   == diff["parent_sha256"] and sha(QUANTITY) == contract["quantity_reference"]["sha256"]
   == diff["quantity_reference_sha256"])
sc("control and exact diff", sha(CASE / "control-input.json") == contract["sources_sha256"]["control"]
   == diff["control_sha256"] and sha(CASE / "exact-diff.json")
   == contract["sources_sha256"]["exact_diff"])
sc("parent to control exact table set", {k for k in parent if parent[k] != control[k]}
   == set(diff["parent_to_control_changed_tables"])
   == {"DamageItem", "ItemStructure", "ProblemDescription", "StockAllocation"}
   and rows(control["ItemStructure"])
   == [["TEACH-LRU-01", "TEACH-AIR-01", 2, 1, None, None, None, None, None]]
   and rows(control["StockAllocation"])
   == [["AIR_BASIC", "TEACH-LRU-01", "BASE-01", 2, None, None, None, None, None]]
   and rows(control["DamageItem"])
   == [["BATTLE-HIT", "TEACH-AIR-01", "TEACH-LRU-01", 0, 1, None, None]])
installed = {"simlox_exe": INSTALL / "Simlox.exe",
             "manual_pdf": INSTALL / "UserDoc/SIMLOX.pdf",
             "table_dictionary": INSTALL / "UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"}
for key, path in installed.items():
    sc("installed " + key, sha(path) == contract["installed_source_sha256"][key])

source = {}
source_observed = {}
for arm in ["control"] + list(range(1, 9)):
    key = str(arm)
    tag = f"seed{arm}" if arm != "control" else "control"
    input_path = CASE / (f"seed-{arm}-input.json" if arm != "control" else "control-input.json")
    source[arm] = tables(load(input_path))
    sc(tag + " input and table set", sha(input_path) == contract["sources_sha256"][key]
       and set(source[arm]) == set(parent))
    if arm != "control":
        descriptor = diff["arms"][key]
        changed = {k for k in control if control[k] != source[arm][k]}
        wanted = {"DamageItem", "ProblemDescription"} | ({"Control"} if arm > 1 else set())
        sc(tag + " child delta", sha(input_path) == descriptor["sha256"]
           and changed == set(descriptor["changed_tables"]) == wanted)
        sc(tag + " PROB and RSEED", rows(source[arm]["DamageItem"])[0][3] == .5
           and records(source[arm]["Control"])[0]["RSEED"] == str(arm))
    run = CASE / f"runs/h02-var02-{tag}-v100-ssh-20261002-01"
    invocation, closure, steps = (load(run / name) for name in
                                  ("invocation.json", "closure.json", "steps.json"))
    sc(tag + " session/GUI/mutex", invocation["execution_mode"] == "ssh_cli_v1"
       and invocation["session_id"] == 0
       and invocation["ssh_connection_present"]
       and "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]]
       and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue"
       and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    sc(tag + " IDs and invocation/input seals", invocation["run_id"] == closure["run_id"] == run.name
       and invocation["input_sha256"] == sha(input_path) == sha(run / "input.json")
       and invocation["parent_sha256"] == sha(PARENT)
       and closure["invocation_sha256"] == sha(run / "invocation.json"))
    sc(tag + " stable source hashes", closure["source_hashes_before"]
       == closure["source_hashes_after"] == invocation["source_hashes_before"]
       and closure["source_hashes_before"]["quantity_reference"] == sha(QUANTITY))
    paths = {"input": input_path, "parent": PARENT, "contract": CASE / "contract.json",
             "manual": installed["manual_pdf"], "dictionary": installed["table_dictionary"],
             "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
             "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
             "python": Path(invocation["planned_check"]["executable"]),
             "runner_script": CASE / "run_native_ssh.ps1", "simlox_exe": installed["simlox_exe"]}
    for name, path in paths.items():
        sc(tag + " source seal " + name, sha(path) == closure["source_hashes_before"][name])
    sc(tag + " 12 raw files", len(closure["raw"]) == 12)
    for name, meta in closure["raw"].items():
        sc(tag + " raw seal " + name, sha(run / name) == meta["sha256"]
           and (run / name).stat().st_size == meta["bytes"])
    sc(tag + " five guarded steps", [s["name"] for s in steps]
       == ["import", "export", "calc", "jsonreport", "check_import_export"]
       and all(s["exit_code"] == 0 and s["gui_preserved"] and not s["error"]
               and s["status"] == ("calc_observed" if s["name"] == "calc" else "completed")
               and s["started_utc"] <= s["completed_utc"] for s in steps)
       and all(s["arguments"] == cmd["arguments"]
               for s, cmd in zip(steps[:3], invocation["planned_commands"]))
       and steps[3]["arguments"] == invocation["planned_report"]["arguments"]
       and steps[4]["arguments"] == invocation["planned_check"]["arguments"])
    exported = tables(load(run / "roundtrip-raw.json", native=True))
    populated = [name for name, table in source[arm].items() if rows(table)]
    sc(tag + " 24 populated tables", len(populated) == 24)
    for name in populated:
        sc(tag + " exact native roundtrip " + name, name in exported
           and columns(source[arm][name]) == columns(exported[name])
           and rows(source[arm][name]) == rows(exported[name]))
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    sc(tag + " converter", "Input conversion completed. Errors: 0" in calc
       and set(re.findall(r"warning #(\d+)", calc)) == {"108", "2053"}
       and not re.search(r"error #\d+", calc))
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    hits = re.findall(r"Time: ([\d.]+) <TEACH-AIR-01,0>Damage BATTLE-HIT occured\. Damaged items: ([^\r\n]*)", log)
    counts = [len(re.findall(r"<TEACH-LRU-01,0,\d+>", text)) for t, text in hits]
    damaged_ids = [[int(j) for j in re.findall(r"<TEACH-LRU-01,0,(\d+)>", text)]
                   for t, text in hits]
    physical = [item for ids in damaged_ids for item in ids]
    sc(tag + " damage event counts and identities", len(hits) == 3
       and counts == FROZEN_MATRIX[arm]
       and all(0 <= count <= 2 for count in counts)
       and all(len(set(ids)) == len(ids) for ids in damaged_ids)
       and len(set(physical)) == len(physical))
    def events(pattern):
        return [(float(t), int(i)) for t, i in re.findall(pattern, log)]
    issues = events(r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,(\d+)> from stock")
    arrivals = events(r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)>")
    repair_starts = events(r"Time: ([\d.]+)  direct repair subtask \d+ seqno 0 within item DIRP task \d+ on <TEACH-LRU-01,0,(\d+)> starts performing, planned to last for 1 hours")
    repair_ends = events(r"Time: ([\d.]+)  direct repair subtask \d+ seqno 0 within item DIRP task \d+ on <TEACH-LRU-01,0,(\d+)> completed")
    restocks = events(r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock")
    sc(tag + " physical item issue/repair/return chain",
       len(issues) == len(arrivals) == len(repair_starts) == len(repair_ends) == len(restocks) == len(physical)
       and all(sorted(item for t, item in group) == sorted(physical)
           for group in (arrivals, repair_starts, repair_ends, restocks))
       and all(item == repaired and near(arrived, started)
               for (arrived, item), (started, repaired) in zip(arrivals, repair_starts))
       and all(item == returned and near(ended, stocked)
               for (ended, item), (stocked, returned) in zip(repair_ends, restocks)))
    sc(tag + " local spare physical chain", [item for t, item in issues] == list(range(len(issues))))
    sc(tag + " one-hour item repairs", all(item == repaired and near(end-start, 1)
       for (start, item), (end, repaired) in zip(repair_starts, repair_ends)))
    sc(tag + " no shortage/discard/attrition", "Backorder added" not in log
       and "Item discarded" not in log and "subject to attrition" not in log)
    report = tables(load(run / "report-raw.json", native=True))
    system = records(report["SystemResults"])
    stock = records(report["StockTotalResults"])
    summary = records(report["ResultSummary"])[0]
    sc(tag + " 72 report bins", len(system) == len(stock) == 72)
    sc(tag + " summary status", summary["NREP"] == 1 and near(summary["RTIUP"], 36)
       and near(summary["MSTF"], 1) and near(summary["MSUF"], counts.count(0)/3))
    sc(tag + " terminal readiness and stock", near(system[-1]["NSYRY"], 1)
       and near(system[-1]["NSYLA"], 0) and near(stock[-1]["PNB"], 1)
       and near(stock[-1]["NBO"], 0))
    source_observed[tag] = {"counts": counts, "damaged_ids": damaged_ids,
                            "spare_ids": [i for t, i in issues],
                            "closure_sha256": sha(run / "closure.json"),
                            "report_sha256": sha(run / "report-raw.json")}

# Independently derive the System and Stock half-hour ledgers from mission and
# system-replacement events, including zero-consequence BATTLE-HIT events.
ledger_observed = {}
for arm, expected_counts in FROZEN_MATRIX.items():
    tag = f"seed{arm}" if arm != "control" else "control"
    run = CASE / f"runs/h02-var02-{tag}-v100-ssh-20261002-01"
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    launch = [(float(t), int(i)) for t, i in re.findall(
        r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission starting, duration: 2", log)]
    abort = [(float(t), int(i)) for t, i in re.findall(
        r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission aborted:", log)]
    abort_complete = [(float(t), int(i)) for t, i in re.findall(
        r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> aborted mission completed:", log)]
    success = [(float(t), int(i)) for t, i in re.findall(
        r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission success:", log)]
    damages = [float(t) for t in re.findall(
        r"Time: ([\d.]+) <TEACH-AIR-01,0>Damage BATTLE-HIT occured", log)]
    ready = [float(t) for t in re.findall(
        r"Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> System ready", log)]
    task_starts = [(float(t), int(i)) for t, i in re.findall(
        r"Time: ([\d.]+)  system SURP task (\d+) on <TEACH-AIR-01,0> started", log)]
    task_ends = [(float(t), int(i)) for t, i in re.findall(
        r"Time: ([\d.]+)  system SURP task (\d+) on <TEACH-AIR-01,0> completed", log)]
    lc(tag + " three launches", launch == [(8., 0), (20., 1), (32., 2)])
    lc(tag + " three damage opportunities", len(damages) == 3)
    lc(tag + " mission outcome identities", [i for t, i in abort]
       == [i for i, count in enumerate(expected_counts) if count]
       and [i for t, i in success] == [i for i, count in enumerate(expected_counts) if not count])
    lc(tag + " system task count", len(task_starts) == len(task_ends) == sum(expected_counts))
    lc(tag + " no cancellation/attrition", "mission cancelled" not in log
       and "subject to attrition" not in log)
    report = tables(load(run / "report-raw.json", native=True))
    system = records(report["SystemResults"])
    stock = records(report["StockTotalResults"])
    summary = records(report["ResultSummary"])[0]
    returns = {i: t for t, i in abort_complete}
    returns.update({i: t for t, i in success})
    ready_by_wave = {}
    for i, count in enumerate(expected_counts):
        ready_by_wave[i] = (next(t for t in ready if returns[i] <= t < returns[i]+2)
                            if count else returns[i])
    lc(tag + " return and readiness", len(returns) == 3 and all(
       near(ready_by_wave[i]-returns[i], .5 if count else 0)
       for i, count in enumerate(expected_counts)))
    lc(tag + " 72 System and Stock bins", len(system) == len(stock) == 72)
    for index, (s, st) in enumerate(zip(system, stock)):
        a, b = index/2, (index+1)/2
        lc(f"{tag} bin {index} coordinates", near(s["STINT"], a) and near(s["ETINT"], b)
           and near(st["STINT"], a) and near(st["ETINT"], b))
        assigned = sum(occupy(a, b, start-1, returns[i]) for start, i in launch)
        flight = sum(occupy(a, b, start, returns[i]) for start, i in launch)
        preflight = sum(occupy(a, b, start-1, start) for start, i in launch)
        repair = sum(occupy(a, b, returns[i], ready_by_wave[i])
                     for i, count in enumerate(expected_counts) if count)
        expected_system = {key: 0 for key in s if key not in ("UNID", "SID", "STINT", "ETINT")}
        expected_system.update(NSYRY=1-assigned-repair, NSYMA=assigned,
            NSYMO=flight, NSYMR=preflight, NSYUA=repair, NSYA=1-repair,
            NSYRP=repair, FTMO=flight, STACC=flight,
            NDAM=sum(a <= t < b for t in damages),
            SYDT=.5 if any(count and a <= returns[i] < b
                           for i, count in enumerate(expected_counts)) else None,
            NSYDT=sum(bool(count) and a <= returns[i] < b
                       for i, count in enumerate(expected_counts)),
            NREPT=sum(count for i, count in enumerate(expected_counts)
                      if a <= ready_by_wave[i] < b))
        for key, expected in expected_system.items():
            lc(f"{tag} System {index} {key}", s[key] is None if expected is None
               else near(s[key], expected))
        expected_stock = {key: 0 for key in st if key not in ("STINT", "ETINT")}
        demand = sum(count for i, count in enumerate(expected_counts)
                     if a <= returns[i] < b)
        expected_stock.update(PNB=1, NDD=demand, NWT=demand)
        for key in ("NBOU", "WTS"):
            expected_stock[key] = None
        for key in ("ROS", "ROST", "WT", "WTT"):
            expected_stock[key] = 0 if demand else None
        for key, expected in expected_stock.items():
            lc(f"{tag} Stock {index} {key}", st[key] is None if expected is None
               else near(st[key], expected))
    lc(tag + " summary", near(summary["MTMF"],
       sum(returns[i]-launch[i][0] for i in range(3))/6)
       and near(summary["STMF"], summary["MTMF"])
       and near(summary["MSTF"], 1)
       and near(summary["MSUF"], expected_counts.count(0)/3))
    lc(tag + " terminal", near(system[-1]["NSYRY"], 1)
       and near(stock[-1]["PNB"], 1) and near(stock[-1]["NBO"], 0))
    ledger_observed[tag] = {"counts": expected_counts,
                            "summary": summary,
                            "terminal_ready": system[-1]["NSYRY"]}

result = {"schema": "independent-h02-var02-two-lru-prob-half-readonly/v1",
          "passed": not SOURCE_FAILURES and not LEDGER_FAILURES,
          "verdict": "GO" if not SOURCE_FAILURES and not LEDGER_FAILURES else "NO-GO",
          "source_checks_passed": SOURCE_CHECKS-len(SOURCE_FAILURES),
          "source_checks_total": SOURCE_CHECKS,
          "ledger_checks_passed": LEDGER_CHECKS-len(LEDGER_FAILURES),
          "ledger_checks_total": LEDGER_CHECKS,
          "checks_passed": SOURCE_CHECKS+LEDGER_CHECKS-len(SOURCE_FAILURES)-len(LEDGER_FAILURES),
          "checks_total": SOURCE_CHECKS+LEDGER_CHECKS,
          "failures": SOURCE_FAILURES+LEDGER_FAILURES,
          "observed_source_and_identity": source_observed,
          "observed_ledgers": ledger_observed,
          "count_matrix": {str(k): v for k, v in FROZEN_MATRIX.items()},
          "cohort_count_frequencies": {str(k): sum(v.count(k) for arm, v in FROZEN_MATRIX.items()
                                               if arm != "control") for k in (0, 1, 2)},
          "scope": "One PROB=0 control and eight fixed-seed PROB=0.5 native runs with two identical directly mounted LRU copies and two local spares. The logs and report bins show zero, one, or two item consequences per BATTLE-HIT event, followed by item-identified replacement and one-hour repair for each damaged LRU.",
          "limits": ["The eight deterministic preselected seeds do not estimate a 50% population probability, establish independence, or test distinct item types.",
                     "No shortage, nested structure, other station, GUI visual behavior, or cross-engine parity is tested."]}
OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True)+"\n").encode("utf-8"))
print(f"{result['verdict']} provenance={result['source_checks_passed']}/{SOURCE_CHECKS} ledger={result['ledger_checks_passed']}/{LEDGER_CHECKS} {OUT}")
for failure in result["failures"][:50]:
    print(failure)
raise SystemExit(0 if result["passed"] else 1)
