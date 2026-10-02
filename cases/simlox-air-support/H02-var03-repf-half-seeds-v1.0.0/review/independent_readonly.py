"""Independent standard-library replay of eight sealed REPF=0.5 seed runs."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
INSTALL = Path(r"C:\Program Files\Systecon\SIMLOX")
PARENT = ROOT / "H02-var03-repf-zero-v1.0.0/repairable-input.json"
OUT = CASE / "review/independent-readonly-2026-10-02.json"
EXPECTED_ROUTES = {1: "DD", 2: "RRR", 3: "DRD", 4: "RRR", 5: "DRD", 6: "RRR", 7: "RDR", 8: "DRD"}
FAILED = []
N = 0


def ck(label, condition):
    global N
    N += 1
    if not condition:
        FAILED.append(label)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, native=False):
    data = path.read_text(encoding="utf-8-sig", errors="replace")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", data) if native else data)


def tables(obj):
    return {t["name"]: t for t in obj.get("model", obj.get("report"))["tables"]}


def cols(table):
    return [c["name"] for c in table["columns"]]


def rows(table):
    return [r for inst in table["instances"] for r in inst["rows"]]


def records(table):
    return [dict(zip(cols(table), r)) for r in rows(table)]


def near(actual, expected, tol=1e-4):
    return isinstance(actual, (int, float)) and math.isclose(actual, expected, abs_tol=tol, rel_tol=0)


def occupancy(a, b, left, right):
    return max(0.0, min(b, right) - max(a, left)) / (b-a)


def event_list(log, pattern):
    return [(float(x), int(y)) for x, y in re.findall(pattern, log)]


contract = load(CASE / "contract.json")
diff = load(CASE / "exact-diff.json")
parent = tables(load(PARENT))
ck("accepted parent SHA", digest(PARENT) == contract["direct_parent"]["sha256"])
ck("eight frozen seeds", contract["preselected_seeds"] == list(range(1, 9)))
ck("exact diff SHA", digest(CASE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"])
ck("diff parent/seeds", diff["parent_sha256"] == digest(PARENT) and diff["preselected_seeds"] == list(range(1, 9)))
installed = {
    "simlox_exe": INSTALL / "Simlox.exe",
    "manual_pdf": INSTALL / "UserDoc/SIMLOX.pdf",
    "table_dictionary": INSTALL / "UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt",
}
for key, path in installed.items():
    ck("installed " + key, digest(path) == contract["installed_source_sha256"][key])

observed = {}
source_stability = []
for seed in range(1, 9):
    tag = f"seed{seed}"
    input_path = CASE / f"seed-{seed}-input.json"
    run = CASE / f"runs/h02-var03-half-seed{seed}-v100-ssh-20261002-02"
    source = tables(load(input_path))
    ck(tag + " input hash", digest(input_path) == contract["sources_sha256"][str(seed)])
    changed = {k for k in parent if parent[k] != source[k]}
    wanted_changed = {"DamageItem", "ProblemDescription"} | ({"Control"} if seed != 1 else set())
    ck(tag + " exact table delta", set(source) == set(parent) and changed == wanted_changed)
    ck(tag + " REPF source row", rows(source["DamageItem"]) == [["BATTLE-HIT", "TEACH-AIR-01", "TEACH-LRU-01", 1, .5, None, None]])
    parent_control = records(parent["Control"])[0]
    control = records(source["Control"])[0]
    ck(tag + " seed-only Control delta", {k: (parent_control[k], control[k]) for k in control if parent_control[k] != control[k]}
       == ({"RSEED": ("1", str(seed))} if seed != 1 else {}))
    d = diff["arms"][str(seed)]
    ck(tag + " independent diff descriptor", d["input_sha256"] == digest(input_path) and d["added_tables"] == []
       and d["removed_tables"] == [] and set(d["changed_tables"]) == wanted_changed
       and d["unchanged_table_count"] == len(parent)-len(wanted_changed)
       and d["values"] == {"REPF_before": 1.0, "REPF_after": .5, "RSEED_before": "1", "RSEED_after": str(seed)})
    inv, closure, steps = (load(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck(tag + " IDs and invocation seal", inv["run_id"] == closure["run_id"] == run.name
       and closure["invocation_sha256"] == digest(run / "invocation.json"))
    ck(tag + " source/run input seal", inv["input_sha256"] == digest(input_path) == digest(run / "input.json")
       and inv["parent_sha256"] == digest(PARENT))
    ck(tag + " SSH session0/mutex/GUI", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0
       and inv["ssh_connection_present"] and "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]]
       and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340
       and inv["gui"]["session_id"] == 1)
    ck(tag + " five native steps", [s["name"] for s in steps]
       == ["import", "export", "calc", "jsonreport", "check_import_export"])
    for step in steps:
        ck(tag + " step " + step["name"], step["exit_code"] == 0 and not step["error"]
           and step["gui_preserved"] and step["started_utc"] <= step["completed_utc"]
           and step["status"] == ("calc_observed" if step["name"] == "calc" else "completed"))
    ck(tag + " command bindings", all(s["arguments"] == p["arguments"] for s, p in zip(steps[:3], inv["planned_commands"]))
       and steps[3]["arguments"] == inv["planned_report"]["arguments"]
       and steps[4]["arguments"] == inv["planned_check"]["arguments"])
    ck(tag + " before/after source stability", closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
    source_stability.append(closure["source_hashes_before"])
    paths = {"input": input_path, "parent": PARENT, "contract": CASE / "contract.json",
             "manual": installed["manual_pdf"], "dictionary": installed["table_dictionary"],
             "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
             "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
             "python": Path(inv["planned_check"]["executable"]),
             "runner_script": CASE / "run_native_ssh.ps1", "simlox_exe": installed["simlox_exe"]}
    for key, path in paths.items():
        ck(tag + " source seal " + key, digest(path) == closure["source_hashes_before"][key])
    ck(tag + " raw set", set(closure["raw"]) == {"input.json", "model.sxi", "roundtrip-raw.json", "import.log",
       "export.log", "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
       "roundtrip-validation.json", "steps.json"})
    for name, meta in closure["raw"].items():
        payload = (run / name).read_bytes()
        ck(tag + " raw seal " + name, len(payload) == meta["bytes"] and hashlib.sha256(payload).hexdigest() == meta["sha256"])
    ck(tag + " valid native output", (run / "model.sxo").stat().st_size > 1000 and (run / "report-raw.json").stat().st_size > 1000)
    exported = tables(load(run / "roundtrip-raw.json", native=True))
    populated = [name for name, table in source.items() if rows(table)]
    ck(tag + " 24 authored row tables", len(populated) == 24)
    for name in populated:
        ck(tag + " exact roundtrip " + name, name in exported and cols(source[name]) == cols(exported[name])
           and rows(source[name]) == rows(exported[name]))
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck(tag + " converter", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc
       and set(re.findall(r"warning #(\d+)", calc)) == {"108", "2053"}
       and not re.search(r"error #\d+", calc))
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    damage = event_list(log, r"Time: ([\d.]+) <TEACH-AIR-01,0>Damage BATTLE-HIT occured\. Damaged items: <TEACH-LRU-01,0,(\d+)>")
    discard = event_list(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item discarded: <TEACH-LRU-01,0,(\d+)>")
    arrivals = event_list(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)>")
    issues = event_list(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,(\d+)> from stock")
    restock = event_list(log, r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock")
    repair_begin = event_list(log, r"Time: ([\d.]+)  direct repair subtask \d+ seqno 0 within item DIRP task \d+ on <TEACH-LRU-01,0,(\d+)> starts performing, planned to last for 1 hours")
    repair_end = event_list(log, r"Time: ([\d.]+)  direct repair subtask \d+ seqno 0 within item DIRP task \d+ on <TEACH-LRU-01,0,(\d+)> completed")
    back_add = [float(x) for x in re.findall(r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Backorder added", log)]
    back_remove = [(float(x), float(y)) for x,y in re.findall(r"Time: ([\d.]+) <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was ([\d.]+)", log)]
    ready = [float(x) for x in re.findall(r"Time: ([\d.]+) <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>", log)]
    launch = event_list(log, r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission starting, duration: 2 : <TEACH-AIR-01,0>")
    abort = event_list(log, r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission aborted:")
    returned = event_list(log, r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> aborted mission completed:")
    cancelled = event_list(log, r"Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission cancelled:")
    route = "".join("D" if item in {j for _,j in discard} else "R" for _,item in damage)
    ck(tag + " frozen route pattern", route == EXPECTED_ROUTES[seed])
    ck(tag + " damaged physical identity", [j for _,j in damage] == list(range(1,len(damage)+1))
       and [j for _,j in arrivals] == list(range(1,len(damage)+1)))
    ck(tag + " mission count/identity", launch == [(float(8+12*j),j) for j in range(len(damage))]
       and [j for _,j in abort] == [j for _,j in returned] == list(range(len(damage)))
       and (len(cancelled), [j for _,j in cancelled]) == ((1,[2]) if seed == 1 else (0,[]))
       and "mission succeeded" not in log and "subject to attrition" not in log)
    ck(tag + " abort at damage and return", all(near(abort[j][0],damage[j][0])
       and damage[j][0] < returned[j][0] <= 10+12*j for j in range(len(damage))))
    ck(tag + " damaged arrival/order", all(near(arrivals[j][0], returned[j][0]+1/6, .00012)
       and arrivals[j][0] >= returned[j][0] for j in range(len(damage))))
    ck(tag + " exactly one removal outcome", sorted([j for _,j in discard] + [j for _,j in repair_begin])
       == sorted(j for _,j in arrivals))
    ck(tag + " discard at arrival", all(any(j == k and near(t,u) for u,k in arrivals) for t,j in discard))
    ck(tag + " one-hour item repairs", len(repair_begin) == len(repair_end)
       and all(j == k and near(u-t,1,.00012) for (t,j),(u,k) in zip(repair_begin,repair_end)))
    ck(tag + " repair starts at arrival", all(any(j == k and near(t,u) for u,k in arrivals) for t,j in repair_begin))
    ck(tag + " stock issue physical chain", [j for _,j in issues] == list(range(len(issues)))
       and all(any(near(t,u) for u,k in returned) for t,_ in issues))
    ck(tag + " stock-return repaired IDs only", {j for _,j in restock} <= {j for _,j in repair_end}
       and all(any(j==k and near(t,u) for u,k in repair_end) for t,j in restock))
    ck(tag + " backorder time/count", len(back_add) == len(damage)-len(issues)
       and all(any(near(t,u) for u,k in returned) for t in back_add)
       and len(back_remove) <= len(back_add))
    ck(tag + " resolved backorder direct repair", all(any(near(t,u) for u,j in repair_end) for t,_ in back_remove)
       and all(any(near(t-a,w,.00012) for a in back_add) for t,w in back_remove))
    ck(tag + " readiness/repair completion", len(ready) == len(damage)-int(seed in (1,3,5,8))
       and all(any(near(t,r+.5,.00012) for r,j in returned) or any(near(t,u+1/3,.00012) for u,w in back_remove) for t in ready))

    report = tables(load(run / "report-raw.json", native=True))
    ck(tag + " result table set", {"SystemResults", "StockTotalResults", "ResultSummary"} <= set(report))
    sys, stock, sm = (records(report[x]) for x in ("SystemResults", "StockTotalResults", "ResultSummary"))
    ck(tag + " 72 report bins", len(sys) == len(stock) == 72 and len(sm) == 1)
    # Build independent interval ledgers directly from the item and mission events.
    starts = [t for t,j in launch]
    ret = [t for t,j in returned]
    bo_pairs = [(a, next((b for b,w in back_remove if b>a), 36.0)) for a in back_add]
    repair_intervals = []
    wait_intervals = []
    for j,r in enumerate(ret):
        completion = next((t for t in ready if t >= r and (j == len(ret)-1 or t < ret[j+1])), None)
        if any(near(r,a) for a in back_add):
            item_arrival = arrivals[j][0]
            resolution = next((b for a,b in bo_pairs if near(a,r)), 36.0)
            repair_intervals += [(r,item_arrival)]
            wait_intervals += [(item_arrival,resolution)]
            if completion is not None and resolution < 36:
                repair_intervals += [(resolution,completion)]
        elif completion is not None:
            repair_intervals += [(r,completion)]
    for j,(s,st) in enumerate(zip(sys,stock)):
        a,b = j/2,(j+1)/2
        ck(tag+f" System bin {j} coordinates", s["UNID"] == "Total over all Units"
           and s["SID"] == "Total over all Systems" and near(s["STINT"],a) and near(s["ETINT"],b))
        ck(tag+f" Stock bin {j} coordinates", near(st["STINT"],a) and near(st["ETINT"],b))
        backlog = sum(occupancy(a,b,u,v) for u,v in bo_pairs)
        stock_expected = {k:0 for k in st if k not in ("STINT","ETINT")}
        stock_expected.update(NBO=backlog,PNB=1-backlog,
                              NDD=sum(a<=t<b for t in ret),
                              NWT=sum(a<=t<b for t in ret if any(near(t,u) for u,k in issues) or any(near(t,u) and v<36 for u,v in bo_pairs)))
        stock_expected["NBOU"] = None
        stock_expected["WTS"] = next((v-u for u,v in bo_pairs if a<=u<b and v<36),None)
        for k in ("ROS","ROST","WT","WTT"):
            demand = next((t for t in ret if a<=t<b),None)
            if demand is None:
                stock_expected[k] = None
            elif any(near(demand,u) for u,v in bo_pairs):
                stock_expected[k] = 1 if k in ("ROS","ROST") else next((v-u for u,v in bo_pairs if near(u,demand)),None)
                if k in ("WT","WTT") and stock_expected[k] == 36-demand:
                    stock_expected[k] = None
            else:
                stock_expected[k] = 0
        for k,v in stock_expected.items():
            ck(tag+f" Stock {j} {k}", st[k] is None if v is None else near(st[k],v,.0002))
        assigned = sum(occupancy(a,b,start-1,r) for start,r in zip(starts,ret))
        preflight = sum(occupancy(a,b,start-1,start) for start in starts)
        flight = sum(occupancy(a,b,start,r) for start,r in zip(starts,ret))
        rep_occ = sum(occupancy(a,b,u,v) for u,v in repair_intervals)
        waiting = sum(occupancy(a,b,u,v) for u,v in wait_intervals)
        ex = {k:0 for k in s if k not in ("UNID","SID","STINT","ETINT")}
        ex.update(NSYRY=1-assigned-rep_occ-waiting,NSYMA=assigned,NSYMR=preflight,NSYMO=flight,
                  NSYUA=rep_occ+waiting,NSYA=1-rep_occ-waiting,NSYRP=rep_occ,NSYWI=waiting,
                  FTMO=flight,STACC=flight,NDAM=sum(a<=t<b for t,item in damage),
                  SYDT=next((v-u+1/3 for u,v in bo_pairs if a<=u<b and v<36),
                            .5 if any(a<=t<b for t,item in issues) else None),
                  NSYDT=sum(a<=t<b for t,item in issues) + sum(a<=u<b and v<36 for u,v in bo_pairs),
                  NREPT=sum(a<=t<b for t in ready))
        for k,v in ex.items():
            ck(tag+f" System {j} {k}", s[k] is None if v is None else near(s[k],v,.0002))
    flight_hours = sum(float(s["NSYMO"] or 0)*.5 for s in sys)
    ck(tag + " flight integral", near(flight_hours,sum(r-s for s,r in zip(starts,ret)),.0002))
    ck(tag + " summary/horizon", sm[0]["NREP"] == 1 and near(sm[0]["RTILW"],0)
       and near(sm[0]["RTIUP"],36) and near(sm[0]["MSTF"],len(launch)/3)
       and near(sm[0]["MTMF"],flight_hours/6,.0002) and near(sm[0]["STMF"],sm[0]["MTMF"])
       and near(sm[0]["MSUF"],0) and all(near(sm[0][k],0) for k in ("RSMTMF","RSMSTF","RSMSUF","RSSTMF")))
    ck(tag + " terminal", near(sys[-1]["NSYRY"] or 0, int(bool(ready) and ready[-1] > ret[-1]))
       and near(sys[-1]["NSYWI"] or 0, int(bool(bo_pairs) and bo_pairs[-1][1] == 36))
       and near(sys[-1]["NSYLA"] or 0,0)
       and near(stock[-1]["NBO"], int(bool(bo_pairs) and bo_pairs[-1][1] == 36)))
    observed[str(seed)] = {"run_id":run.name,"route":route,"damaged_items":damage,
       "repaired_ids":[item for t,item in repair_end],"discarded_ids":[item for t,item in discard],
       "stock_issue_ids":[item for t,item in issues],"stock_return_ids":[item for t,item in restock],
       "backorders":bo_pairs,"launch_count":len(launch),"cancel_count":len(cancelled),
       "flight_hours":flight_hours,"terminal_ready":sys[-1]["NSYRY"],"terminal_waiting":sys[-1]["NSYWI"]}

ck("stable non-input sources across accepted runs", all({k:v for k,v in source_stability[0].items() if k!="input"}
   == {k:v for k,v in h.items() if k!="input"} for h in source_stability[1:]))
ck("both realized paths across panel", any("R" in x["route"] for x in observed.values())
   and any("D" in x["route"] for x in observed.values()))
diagnostics = {}
for seed in (1,2,3,4):
    tag = f"excluded-seed{seed}"
    run = CASE / f"runs/h02-var03-half-seed{seed}-v100-ssh-20261002-01"
    inv, closure, steps = (load(run / name) for name in ("invocation.json","closure.json","steps.json"))
    ck(tag+" identity and invocation seal", inv["run_id"] == closure["run_id"] == run.name
       and closure["invocation_sha256"] == digest(run / "invocation.json"))
    ck(tag+" old checker/runner fingerprints", inv["checker_sha256"] == closure["source_hashes_before"]["checker"]
       == "94959653600cf886d04d13e2b3dea48cf88c4b07f3669ffc22f94478e51cbbaa"
       and inv["runner_script_sha256"] == closure["source_hashes_before"]["runner_script"]
       == "ef1f27fb69a5351fd519f0e29c32d6caed4501ae7afafe3bf33cb44e0c9ba7b2")
    ck(tag+" source/input stability", closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"]
       and inv["input_sha256"] == digest(CASE / f"seed-{seed}-input.json") == digest(run / "input.json"))
    ck(tag+" native completed/check failed", [x["name"] for x in steps]
       == ["import","export","calc","jsonreport","check_import_export"]
       and all(x["exit_code"] == 0 and x["gui_preserved"] for x in steps[:4])
       and steps[-1]["exit_code"] == 1 and steps[-1]["status"] == "failed"
       and closure["error"] == "roundtrip checker exit=1"
       and not (run / "roundtrip-validation.json").exists())
    ck(tag+" sealed diagnostic raw set", set(closure["raw"]) == {"input.json","model.sxi","roundtrip-raw.json",
       "import.log","export.log","model.sxo","run.log","model.log","report-raw.json","report-export.log","steps.json"})
    for name, meta in closure["raw"].items():
        data = (run / name).read_bytes()
        ck(tag+" raw "+name, len(data) == meta["bytes"] and hashlib.sha256(data).hexdigest() == meta["sha256"])
    diagnostics[str(seed)] = {"run_id":run.name,"closure_sha256":digest(run / "closure.json"),
                              "classification":"excluded checker failure after native report"}
ck("excluded earlier seed1 package", (ROOT / "H02-var03-repf-half-v1.0.0/review/independent-readonly-2026-10-02.json").is_file())
repair_count = sum(x["route"].count("R") for x in observed.values())
discard_count = sum(x["route"].count("D") for x in observed.values())
ck("all 23 observed decisions classified", repair_count == 14 and discard_count == 9)

result = {"schema":"independent-h02-var03-repf-half-seeds-readonly/v1",
          "passed":not FAILED,"verdict":"GO" if not FAILED else "NO-GO",
          "checks_passed":N-len(FAILED),"checks_total":N,"failures":FAILED,"observed":observed,
          "excluded_diagnostics":diagnostics,"realized_repair_count":repair_count,"realized_discard_count":discard_count,
          "scope":"Eight preselected fixed-seed REPF=0.5 guarded runs. Item-identified native logs show repair-only, discard-only, and mixed realizations. Repaired items can directly satisfy a pending backorder without a separate stock-return event. All eight accepted -02 results, including shortage and cancellation, are included.",
          "limits":["This is a small deterministic panel selected after a disclosed separate seed1 diagnostic; the counts do not estimate a 50% population rate, decision independence, or confidence interval.",
                    "Four sealed -01 runs are excluded diagnostics: raw closures show the prior checker fingerprint, checker exit 1 after native report, and absent roundtrip-validation artifact. Package documentation attributes that failure to SyntaxError; the raw closure alone records a checker failure. The separate earlier seed1 run is disclosed and excluded from this panel.",
                    "Only this directly mounted primary LRU, explicit DamageReplacement, BASE-01 stock, installed engine, CLI path and horizon are covered; no fallback, GUI visual or cross-engine claim."]}
OUT.write_bytes((json.dumps(result,indent=2,sort_keys=True)+"\n").encode("utf-8"))
print(f"{result['verdict']} {result['checks_passed']}/{result['checks_total']} {OUT}")
for failure in FAILED[:60]:
    print(failure)
raise SystemExit(0 if not FAILED else 1)
