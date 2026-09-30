"""Standalone standard-library read-only replay of sealed B04 v1.0.1 pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
PARENT = CASE.parent / "B02-serial-preparation-v1.0.2" / "native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
OUT = Path(__file__).with_name("independent-turnround-2026-09-30.json")
RUNS = {v: CASE / "runs" / f"b04-v101-{v}-20260930-01" for v in ("control", "turnround")}
PARENT_SHA = "fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34"
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
GUI = {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"}
checks = []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, native=False):
    content = path.read_text(encoding="utf-8-sig")
    if native:  # SIMLOX report export has a trailing comma after its final table.
        content = re.sub(r",\s*([}\]])", r"\1", content)
    return json.loads(content)


def check(name, good, detail=None):
    entry = {"name": name, "passed": bool(good)}
    if not good and detail is not None:
        entry["detail"] = detail
    checks.append(entry)


def tables(document, root="model"):
    return {t["name"]: t for t in document[root]["tables"]}


def rows(table):
    return [row for instance in table.get("instances", []) for row in instance.get("rows", [])]


def fields(table, row):
    return dict(zip((c["name"] for c in table["columns"]), row))


def series(table, name):
    j = [c["name"] for c in table["columns"]].index(name)
    return [r[j] for r in rows(table)]


def near(a, b, eps=1e-9):
    return abs(float(a)-float(b)) <= eps


def overlap(start, end, lower, upper):
    return max(0., min(end, upper)-max(start, lower))


def bins(intervals, count=72):
    return [sum(overlap(a,b,i*.5,(i+1)*.5) for a,b in intervals)/.5 for i in range(count)]


def changed_fields(left, right):
    if left["columns"] != right["columns"] or len(rows(left)) != len(rows(right)):
        return {"<shape>"}
    names = [c["name"] for c in left["columns"]]
    return {names[j] for a,b in zip(rows(left),rows(right)) for j in range(len(names)) if a[j] != b[j]}


def log_times(log, pattern):
    return [float(x) for x in re.findall(pattern, log, re.M)]


def main():
    parent = load(PARENT)
    contract = load(CASE / "contract.json")
    inputs = {v: load(CASE / f"{v}-input.json") for v in RUNS}
    pt = tables(parent)
    tabs = {v: tables(inputs[v]) for v in RUNS}
    check("published B02 parent SHA and signoff", sha(PARENT) == PARENT_SHA and (PARENT.parent / "README.md").is_file())
    check("installed manual SHA and cited pages", sha(MANUAL) == MANUAL_SHA and contract["source"]["manual_sha256"] == MANUAL_SHA and contract["source"]["pages"] == [181,182,183,305,306,307])
    check("contract selects B04 v1.0.1 pair and A02 prerequisite", contract["case_id"] == "B04" and contract["version"] == "1.0.1" and contract["requires"] == ["B02","A02"])
    for variant, tab in tabs.items():
        pre = variant + ": "
        check(pre + "parent table set plus intended turnround", set(tab) == set(pt) | ({"MissionTurnround"} if variant == "turnround" else set()))
        check(pre + "changed parent tables only description and profile", {n for n in pt if tab[n] != pt[n]} == {"ProblemDescription","OperationProfile"})
        check(pre + "all other parent tables unchanged", all(tab[n] == pt[n] for n in pt if n not in {"ProblemDescription","OperationProfile"}))
        check(pre + "source row-containing table count", sum(bool(rows(t)) for t in tab.values()) == (17 if variant == "control" else 18))
        check(pre + "description changed only PDESC", changed_fields(pt["ProblemDescription"],tab["ProblemDescription"]) == {"PDESC"})
        profile = tab["OperationProfile"]
        pr = [fields(profile,r) for r in rows(profile)]
        parent_row = fields(pt["OperationProfile"], rows(pt["OperationProfile"])[0])
        check(pre + "two scheduled profile rows with exact times and delay", len(pr) == 2 and all(r["PRID"] == "BASIC-SCHEDULE" and r["SPRID"] == "BASIC-MISSION" and r["ITYPE"] == "SCHEDULED" and r["IQTY"] == 1 for r in pr) and pr[0]["STIM"] == 21.5 and near(pr[0]["DTIM"],1/3) and pr[1]["STIM"] == 24.75 and pr[1]["DTIM"] == 1)
        check(pre + "profile values cloned from B02 except schedule/delay", all(pr[0][k] == parent_row[k] for k in parent_row if k != "STIM") and all(pr[1][k] == pr[0][k] for k in pr[0] if k not in {"STIM","DTIM"}))
    check("variant input differs only in turnround table and label", {n for n in tabs["control"] if tabs["control"][n] != tabs["turnround"][n]} == {"ProblemDescription"} and set(tabs["turnround"]) - set(tabs["control"]) == {"MissionTurnround"})
    mt = tabs["turnround"]["MissionTurnround"]
    tr = fields(mt, rows(mt)[0])
    check("one exact one-hour turnround without resource/subtask reference", len(rows(mt)) == 1 and tuple(tr[k] for k in ("MTID","SID","STID","DURN","TID","DURND","NOTE")) == ("BASIC-MISSION","TEACH-AIR-01","BASE-01",1,None,None,None))
    runner = (CASE / "run_native_ssh.ps1").read_text(errors="replace")
    check("runner contains session0 SSH mutex GUI and source guards", all(s in runner for s in ("$env:SSH_CONNECTION",".SessionId -ne 0","Global\\SimloxIssue18NativeQueue","13340","Assert-Gui","source fingerprint changed during native run")))

    observed = {}
    for variant, run in RUNS.items():
        pre = variant + ": "
        inv, closure, steps = (load(run / filename) for filename in ("invocation.json","closure.json","steps.json"))
        expected = {"input": sha(CASE / f"{variant}-input.json"), "parent": sha(PARENT), "contract": sha(CASE / "contract.json"), "builder": sha(CASE / "build.py"), "checker": sha(CASE / "check_roundtrip.py"), "runner_script": sha(CASE / "run_native_ssh.ps1")}
        check(pre + "source run copy and invocation SHA", sha(run / "input.json") == expected["input"] == inv["input_sha256"])
        check(pre + "invocation bound to closure", inv["run_id"] == closure["run_id"] == run.name and inv["variant"] == variant and closure["invocation_sha256"] == sha(run / "invocation.json"))
        check(pre + "source fingerprints stable through run", all(inv["source_hashes_before"].get(k) == value and closure["source_hashes_before"].get(k) == value and closure["source_hashes_after"].get(k) == value for k,value in expected.items()))
        check(pre + "session0 SSH mutex and GUI identity", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and inv["gui"] == GUI)
        raw = closure["raw"]
        check(pre + "all 12 raw artifact SHA and byte seals", len(raw) == 12 and all((run / name).is_file() and len((run / name).read_bytes()) == meta["bytes"] and sha(run / name) == meta["sha256"] for name,meta in raw.items()))
        check(pre + "five successful steps preserve GUI", [s["name"] for s in steps] == ["import","export","calc","jsonreport","check_import_export"] and all(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] is True for s in steps))
        check(pre + "planned arguments equal executed native commands", [c["name"] for c in inv["planned_commands"]] == ["import","export","calc","jsonreport"] and all(steps[i]["arguments"] == inv["planned_commands"][i]["arguments"] for i in range(4)))
        export = tables(load(run / "roundtrip-raw.json"))
        check(pre + "all source schemas and business rows roundtrip", all(t["columns"] == export[name]["columns"] and (not rows(t) or rows(t) == rows(export[name])) for name,t in tabs[variant].items()))
        check(pre + "checker corroborates roundtrip", load(run / "roundtrip-validation.json")["passed"] is True)
        runlog = (run / "run.log").read_text(errors="replace")
        check(pre + "zero conversion errors, warnings 108/126 only", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog and sorted(map(int,re.findall(r"warning #(\d+)",runlog))) == [108,126] and not re.search(r"error #\d+",runlog))
        log = (run / "model.log").read_text(errors="replace")
        mission = "BASIC-MISSION,TEACH-UNIT,0,0,"
        starts = re.findall(rf"^Time: ([0-9.]+) <{mission}([01])> mission starting, duration: 2 : <(TEACH-AIR-01,0)>",log,re.M)
        ends = re.findall(rf"^Time: ([0-9.]+) <{mission}([01])> mission completed: <(TEACH-AIR-01,0)>",log,re.M)
        successes = re.findall(rf"^Time: ([0-9.]+) <{mission}([01])> mission success:",log,re.M)
        expected_start = 24.75 if variant == "control" else 25
        expected_end = expected_start + 2
        check(pre + "exact two mission IDs, one aircraft, starts and completions", len(starts) == len(ends) == len(successes) == 2 and len(re.findall("mission starting,",log)) == 2 and [int(x[1]) for x in starts] == [0,1] and [float(x[0]) for x in starts] == [21.5,expected_start] and [float(x[0]) for x in ends] == [23.5,expected_end] and [float(x[0]) for x in successes] == [23.5,expected_end] and all(x[2] == "TEACH-AIR-01,0" for x in starts+ends))
        check(pre + "both notice events and midnight day boundary", log_times(log,rf"^Time: ([0-9.]+) <TEACH-UNIT> mission ordered: BASIC-MISSION") == [20.5,23.75] and "Time: 24  Start of day no 1" in log)
        prep_start = log_times(log,rf"^Time: ([0-9.]+) <TEACH-AIR-01,0> preparation started, mission: <{mission}[01]>")
        prep_end = log_times(log,rf"^Time: ([0-9.]+) <TEACH-AIR-01,0> preparation ended, mission: <{mission}[01]>")
        second_prep_start = 23.75 if variant == "control" else 24.5
        second_prep_end = second_prep_start + .5
        check(pre + "serial preparation intervals for both waves", prep_start == [20.5,second_prep_start] and prep_end == [21,second_prep_end])
        turn_start = log_times(log,rf"^Time: ([0-9.]+) <TEACH-AIR-01,0> turnround started, mission: <{mission}[01]>")
        turn_end = log_times(log,rf"^Time: ([0-9.]+) <TEACH-AIR-01,0> turnround ended, mission: <{mission}[01]>")
        expected_turn_end = [23.5,26.75] if variant == "control" else [24.5,28]
        check(pre + "turnround interval and post-work arrival", turn_start == [23.5,expected_end] and turn_end == expected_turn_end and log_times(log,rf"^Time: ([0-9.]+) <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>") == expected_turn_end)
        preassign = log_times(log,rf"^Time: ([0-9.]+) <{mission}1> mission preassigns a system: <TEACH-AIR-01,0>")
        assign = log_times(log,rf"^Time: ([0-9.]+) <{mission}1> mission allocates system: <TEACH-AIR-01,0>")
        check(pre + "second wave preassignment versus assignment", (preassign,assign) == (([],[23.75]) if variant == "control" else ([23.75],[24.5])))
        if variant == "turnround":
            check(pre + "one-hour no-resource task straddles midnight", "Time: 23.5  system turnround task 1 on <TEACH-AIR-01,0> started" in log and "Time: 23.5  subtask 2 seqno 0 within system turnround task 1 on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours" in log and "Time: 24.5  system turnround task 1 on <TEACH-AIR-01,0> completed" in log)
        report = load(run / "report-raw.json",native=True)
        rep = tables(report,"report")
        summ = fields(rep["ResultSummary"], rows(rep["ResultSummary"])[0])
        sys,stock = rep["SystemResults"],rep["StockTotalResults"]
        sr = rows(sys)
        check(pre + "72 contiguous half-hour system and stock bins",len(sr)==len(rows(stock))==72 and all(near(r[2],i*.5) and near(r[3],(i+1)*.5) for i,r in enumerate(sr)) and all(near(r[0],i*.5) and near(r[1],(i+1)*.5) for i,r in enumerate(rows(stock))))
        prep_intervals = [(20.5,21),(second_prep_start,second_prep_end)]
        mission_intervals = [(21.5,23.5),(expected_start,expected_end)]
        turn_intervals = [] if variant == "control" else [(23.5,24.5),(27,28)]
        active_intervals = [(20.5,expected_turn_end[0]),(second_prep_start,expected_turn_end[1])]
        for field,intervals in (("NSYMP",prep_intervals),("NSYMO",mission_intervals),("NSYMT",turn_intervals),("NSYMA",active_intervals),("STACC",mission_intervals)):
            check(pre + field + " matches event-derived occupancy each bin",all(near(actual,expected) for actual,expected in zip(series(sys,field),bins(intervals))))
        check(pre + "ready/available complements assigned occupancy",all(near(r,1-a) for r,a in zip(series(sys,"NSYRY"),bins(active_intervals))) and all(near(a,1) for a in series(sys,"NSYA")))
        check(pre + "summary and four aircraft mission-hours",summ["NREP"]==1 and summ["RTIUP"]==36 and all(summ[k]==1 for k in ("MTMF","MSTF","MSUF","STMF")) and near(sum(x*.5 for x in series(sys,"NSYMO")),4))
        check(pre + "zero faults maintenance and stock demand",max(series(sys,"NFAIL"))==max(series(sys,"NREPT"))==max(series(sys,"NPMT"))==0 and max(series(stock,"NBO"))==max(series(stock,"NDF"))==max(series(stock,"NDD"))==0)
        check(pre + "terminal one aircraft ready",near(series(sys,"NSYRY")[-1],1) and near(series(sys,"NSYMA")[-1],0) and near(series(sys,"NSYMO")[-1],0))
        observed[variant]={"mission_starts":[float(x[0]) for x in starts],"mission_completions":[float(x[0]) for x in ends],"turnround_starts":turn_start,"turnround_ends":turn_end,"preparation_starts":prep_start,"preparation_ends":prep_end,"second_preassigned":preassign,"operating_aircraft_hours":sum(x*.5 for x in series(sys,"NSYMO")),"turnround_aircraft_hours":sum(x*.5 for x in series(sys,"NSYMT")),"terminal_ready":series(sys,"NSYRY")[-1],"report_sha256":sha(run / "report-raw.json")}

    check("turnround shifts second launch by quarter-hour within allowance",near(observed["turnround"]["mission_starts"][1]-observed["control"]["mission_starts"][1],.25) and observed["turnround"]["mission_starts"][1]<=25.75)
    result={"schema":"simlox-b04-v101-independent-turnround-readonly/v1","reviewer":"Standalone standard-library raw replay; no author imports or native invocation","passed":all(x["passed"] for x in checks),"passed_count":sum(x["passed"] for x in checks),"failed_count":sum(not x["passed"] for x in checks),"failed":[x for x in checks if not x["passed"]],"checks":checks,"hashes":{"parent_input":sha(PARENT),"manual_pdf":sha(MANUAL),"contract":sha(CASE / "contract.json"),**{v+"_input":sha(CASE/f"{v}-input.json") for v in RUNS},**{v+"_report":observed[v]["report_sha256"] for v in RUNS}},"observed":observed,"manual_read":"Installed manual pp181-183 and 305-307: preparation follows assignment; post-mission turnround retains system with mission until task completion and DURN is calendar time.","decision":"bounded_pair_accepted" if all(x["passed"] for x in checks) else "review_failed","limits":["One aircraft and one fixed mission type with deterministic no-resource turnround; no repairs, PM or broader schedule generalization.","Native event log identifies preassignment at 23.75 but not the scheduler's internal candidate search; report state bins are time averages rather than instantaneous state at midnight.","The local unpublished v1.0.0 failed-cutoff probe is excluded from this v1.0.1 acceptance.","GUI visual behavior and cross-engine parity were not tested."]}
    OUT.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    print(json.dumps({"passed":result["passed"],"passed_count":result["passed_count"],"failed":result["failed"],"output":str(OUT)}))


if __name__=="__main__":
    main()
