"""Independent, read-only replay of the sealed D12.var01 native pair."""
import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BASE = HERE.parent
RUN = HERE / "runs" / "d12-var02-three-level-v100-ssh-20261004-01"
OUT = HERE / "review" / "independent-verdict.json"
failures = []
checks = 0


def check(ok, label):
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path):
    """Remove native trailing commas in one linear pass outside JSON strings."""
    s = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = escaped = False
    for i, ch in enumerate(s):
        if quoted:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
            continue
        if ch == '"':
            quoted = True
        if ch == ",":
            j = i + 1
            while j < len(s) and s[j].isspace():
                j += 1
            if j < len(s) and s[j] in "]}":
                continue
        out.append(ch)
    return json.loads("".join(out))


def tables(doc, root="model"):
    return {t["name"]: t for t in doc[root]["tables"]}


def instances(table):
    return {i["instance_name"]: i["rows"] for i in table["instances"]}


def records(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for ins in table["instances"] for row in ins["rows"]]


def close(a, b, tol=1e-5):
    return math.isclose(float(a), float(b), abs_tol=tol, rel_tol=0)


contract = native_json(HERE / "contract.json")
closure = native_json(RUN / "closure.json")
inv = native_json(RUN / "invocation.json")
steps = native_json(RUN / "steps.json")
check(sha(HERE / "contract.json") == "d8d0c5f5aefc34041eb0da897c8ed7e0edcc0ff42a4ed81e516336e436b39805", "frozen three-level contract")
check(contract["run_id"] == RUN.name == closure["run_id"] == inv["run_id"], "run identity")
check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
check(closure["error"] is None and closure["publication_state"] == "not_published", "closure status")
check(inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"], "SSH session 0")
check(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "GUI identity")
check(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "mutex")
check(len(steps) == 8, "eight paired native steps")
for arm in ("unlinked", "linked"):
    for action in ("import", "export", "calc", "report"):
        x = next((s for s in steps if s["name"] == f"{arm}_{action}"), None)
        check(x is not None and x["exit_code"] == 0 and x["status"] == "completed" and x["gui_preserved"], f"{arm} {action} guard")
        if x:
            check("-threads 1" in x["arguments"] if action == "calc" else True, f"{arm} serial calc")

pins = {
    "contract": HERE / "contract.json",
    "unlinked": HERE / "unlinked-input.json",
    "linked": HERE / "linked-input.json",
    "parent_input": BASE / "D12-var01-active-small-v1.0.0" / "linked-input.json",
    "parent_closure": BASE / "D12-var01-active-small-v1.0.0" / "runs" / "d12-var01-active-small-v100-ssh-20261004-01" / "closure.json",
    "parent_signoff": BASE / "D12-var01-active-small-v1.0.0" / "cli-scope-signoff-2026-10-04.md",
    "build.py": HERE / "build.py",
    "run_native_ssh.ps1": HERE / "run_native_ssh.ps1",
}
for key, expected in closure["source_hashes_before"].items():
    check(closure["source_hashes_after"].get(key) == expected == inv["source_hashes_before"].get(key), f"{key} stable source seal")
    if key in pins and pins[key].exists():
        check(sha(pins[key]) == expected, f"{key} current bytes")
for name, meta in sorted(closure["raw"].items()):
    p = RUN / name
    check(p.is_file() and p.stat().st_size == meta["bytes"] and sha(p) == meta["sha256"], f"raw {name}")
check(len(closure["raw"]) == 22, "22 sealed raw files")
for arm in ("unlinked", "linked"):
    check(sha(HERE / f"{arm}-input.json") == contract["inputs_sha256"][arm], f"contract {arm} source pin")
    check((RUN / f"{arm}.sxo").stat().st_size > 4, f"{arm} usable SXO")
    runlog = (RUN / f"{arm}-run.log").read_text(errors="replace")
    check("Errors: 0, Warnings: 2, Notes: 0" in runlog, f"{arm} converter summary")
    check("warning #108" in runlog and "warning #126" in runlog, f"{arm} classified warnings")

source = {a: native_json(HERE / f"{a}-input.json") for a in ("unlinked", "linked")}
export = {a: native_json(RUN / f"{a}-roundtrip-raw.json") for a in source}
allowed = {"MaterielPM","PMLocation","ProblemDescription","SubTaskResource","TaskBreakDown","Tasks"}
pt = tables(native_json(pins["parent_input"]))
for arm in source:
    ct = tables(source[arm])
    for name in sorted(pt):
        if name not in allowed:
            check(pt[name] == ct[name], f"{arm} parent unchanged {name}")
    for name in sorted(allowed - {"ProblemDescription"}):
        old,new = pt[name],ct[name]
        check(old["columns"] == new["columns"], f"{arm} {name} columns preserved")
        oldrows,newrows = instances(old)[""],instances(new)[""]
        check(len(newrows) == len(oldrows)+1, f"{arm} {name} one appended row")
        for i,(o,n) in enumerate(zip(oldrows,newrows)):
            for j,col in enumerate(old["columns"]):
                check(o[j] == n[j], f"{arm} {name} row {i} {col['name']} unchanged")
    top = records(ct["MaterielPM"])[-1]
    check((top["PMID"],top["PMINT"],top["OPID"],top["PMRID"]) == ("TOP49",49.0,"CALHOURS",None if arm == "unlinked" else "BIG48P5"), f"{arm} TOP49 definition")
    check(records(ct["PMLocation"])[-1]["PMID"] == "TOP49", f"{arm} PM location ref")
    check(all(records(ct[n])[-1]["TID"] == "PM-TOP49" for n in ("Tasks","TaskBreakDown","SubTaskResource")), f"{arm} top task refs")
for arm in source:
    st, et = tables(source[arm]), tables(export[arm])
    for name, authored in sorted(st.items()):
        ec = et[name]
        columns = [c["name"] for c in authored["columns"]]
        enames = [c["name"] for c in ec["columns"]]
        expected_instances, actual_instances = instances(authored), instances(ec)
        for ins, rows in sorted(expected_instances.items()):
            if not rows or all(all(v is None for v in row) for row in rows):
                continue
            check(ins in actual_instances, f"{arm} {name}/{ins} instance")
            actual = actual_instances.get(ins, [])
            check(len(actual) == len(rows), f"{arm} {name}/{ins} row count")
            for i, row in enumerate(rows):
                for j, col in enumerate(columns):
                    got = actual[i][enames.index(col)] if i < len(actual) and col in enames else object()
                    check(got == row[j], f"{arm} {name}/{ins} row {i} {col}")

# The pair's business delta is confined to the larger PM relation; descriptions differ.
left, right = tables(source["unlinked"]), tables(source["linked"])
for name in sorted(left):
    if name not in ("MaterielPM", "ProblemDescription"):
        check(left[name] == right[name], f"matched table {name}")
lu = records(left["MaterielPM"])
ll = records(right["MaterielPM"])
check(len(lu) == len(ll) == 3, "three PM definitions")
for u, l in zip(lu, ll):
    if u.get("PMID") == "TOP49":
        check({k: v for k, v in u.items() if k != "PMRID"} == {k: v for k, v in l.items() if k != "PMRID"}, "TOP49 other fields equal")
        check(u["PMRID"] is None and l["PMRID"] == "BIG48P5", "only TOP49 relation cell")
    else:
        check(u == l, "small PM definition equal")

event = {}
pm = {}
work = {}
bookings = {}
for arm in source:
    lines = (RUN / f"{arm}.log").read_text(errors="replace").splitlines()
    event[arm] = lines
    ids = {}
    for line in lines:
        m = re.match(r"Time: ([0-9.]+)  system PM task (\d+) on <TEACH-AIR-01,(\d+)> PMID: (\S+)", line)
        if m:
            ids[int(m[2])] = (float(m[1]), int(m[3]), m[4])
    pm[arm] = ids
    work[arm] = [(float(m[1]), int(m[2]), "start" if m[3] == "starts performing" else "end") for line in lines if (m := re.match(r"Time: ([0-9.]+)  subtask (\d+) seqno 1 within system PM task \d+ on <TEACH-AIR-01,\d+> (starts performing|completed|stopped)", line))]
    booking = [(float(m[1]), "on" if m[2] == "allocated" else "off", int(m[3])) for line in lines if (m := re.match(r"Time: ([0-9.]+)  <P-MAINT at <BASE-01,0>> (allocated|deallocated) (?:to|from)\s+maintenance task: 1  available now: (\d+)", line))]
    bookings[arm] = booking
    active = 0
    for t, kind, available in booking:
        active += 1 if kind == "on" else -1
        check(active in (0, 1) and active + available == 1, f"{arm} worker capacity at {t}")
    check(active == 0, f"{arm} worker released")

def before_49(lines):
    return lines[:next(i for i,line in enumerate(lines) if line.startswith("Time: 49 "))]
check(before_49(event["unlinked"]) == before_49(event["linked"]), "identical paired event trace before h49")

expected_pm = {1:(24.0,0,"CAL24"), 2:(24.0,1,"CAL24"), 3:(48.0,1,"CAL24"), 4:(48.0,0,"CAL24"), 5:(48.5,1,"BIG48P5"), 6:(48.5,0,"BIG48P5"), 7:(49.0,0,"TOP49"), 8:(49.0,1,"TOP49")}
for arm in source:
    check(pm[arm] == expected_pm, f"{arm} PM identities")
for arm in source:
    common = {(26.6319,1,"start"),(27.6319,1,"end"),(27.6319,2,"start"),(28.6319,2,"end"),(48,3,"start"),(48.5,3,"end")}
    check(common.issubset(set(work[arm])), f"{arm} common first and active-small work")
    check(any("system DIRP task 0" in line and "started" in line for line in event[arm]), f"{arm} repair occurred")
    check(sum("mission success" in line.lower() for line in event[arm]) >= 1, f"{arm} mission success evidence")
for arm, expected in {
    "unlinked": {(48.5,5,"start"),(49.5,5,"end"),(49.5,6,"start"),(50.5,6,"end"),(50.5,8,"start"),(51.5,8,"end"),(51.5,7,"start"),(52.5,7,"end"),(50.5,4,"end")},
    "linked": {(48.5,5,"start"),(49,5,"end"),(49,6,"start"),(49,6,"end"),(49,7,"start"),(50,7,"end"),(50,8,"start"),(51,8,"end"),(49,4,"end")},
}.items():
    check(expected.issubset(set(work[arm])), f"{arm} post49 work/stop chronology")
check(any(line.startswith("Time: 49 ") and "system PM task 5" in line and "stopped" in line for line in event["linked"]), "linked active BIG48P5 stopped h49")
check(any(line.startswith("Time: 49 ") and "subtask 5" in line and "frees resources" in line for line in event["linked"]), "linked active BIG48P5 releases worker h49")
check(any(line.startswith("Time: 49 ") and "system PM task 6" in line and "stopped" in line for line in event["linked"]), "linked same-time BIG48P5 task6 stopped")
check(any(line.startswith("Time: 49 ") and "system PM task 4" in line and "stopped" in line for line in event["linked"]), "linked CAL24 task4 stopped")
check(not any("subtask 4" in line and "starts performing" in line for line in event["linked"]), "linked CAL24 task4 has zero work")

reports = {a: tables(native_json(RUN / f"{a}-report-raw.json"), "report") for a in source}
summary = {}
for arm, report in reports.items():
    summary[arm] = records(report["ResultSummary"])[0]
    for name in ("SystemResults", "ResourceResults", "StockTotalResults"):
        rows = records(report[name])
        check(len(rows) == 120, f"{arm} {name} 120 bins")
        for i, row in enumerate(rows):
            check(close(row["STINT"], i * .5) and close(row["ETINT"], (i+1)*.5), f"{arm} {name} bin {i} interval")
    rr = records(report["ResourceResults"])
    spans = []
    for (start, kind, _), (end, kind2, _) in zip(bookings[arm][::2], bookings[arm][1::2]):
        check(kind == "on" and kind2 == "off" and end >= start, f"{arm} booking pair")
        spans.append((start, end))
    for i, row in enumerate(rr):
        expected = sum(max(0.0, min((i+1)*.5, b)-max(i*.5, a)) for a,b in spans) / .5
        check(close(row["NRUM"], expected, 3e-4), f"{arm} worker used bin {i}")
        check(float(row["NRUM"]) <= 1.00001, f"{arm} worker capacity bin {i}")
    check(close(sum(float(r["NRUM"])*.5 for r in rr), sum(b-a for a,b in spans), 3e-4), f"{arm} resource hour integral")
    check(close(sum(float(r["NRUM"])*.5 for r in rr), 11.5 if arm == "unlinked" else 10, 3e-4), f"{arm} 11.5/10 booked worker hours")
    stock = records(report["StockTotalResults"])
    for i, row in enumerate(stock):
        check(all(row[k] is None or close(row[k],0) for k in ("NBO","NBOU","NDF","NDD","NDR","NDP")), f"{arm} zero stock/demand bin {i}")
    system = records(report["SystemResults"])
    for i, row in enumerate(system):
        check(close(float(row["NSYA"])+float(row["NSYUA"]),2,3e-4), f"{arm} aircraft conservation bin {i}")
    check(close(system[-1]["NSYRY"],2), f"{arm} terminal ready")
    check(summary[arm]["NREP"] == 1, f"{arm} one replication")

# Event-derived second-cycle work explains the report PM-hour contrast.
for arm, hours in (("unlinked",6.5),("linked",5.0)):
    spans = {}
    for t, task, kind in work[arm]:
        spans.setdefault(task,{})[kind] = t
    check(close(sum(v["end"]-v["start"] for v in spans.values() if "start" in v and "end" in v),hours), f"{arm} PM work hours")
    system = records(reports[arm]["SystemResults"])
    pm_hours = sum(float(r["NSYPM"])*.5 for r in system)
    check(close(pm_hours,hours,1e-3), f"{arm} SystemResults PM hours")
    check(close(sum(float(r["NPMT"]) for r in system), 6 if arm == "unlinked" else 4), f"{arm} completed PM marker count")
    check(close(sum(float(r["NPMS"]) for r in system), 8), f"{arm} PM initiation marker count")
check(summary["unlinked"]["MSTF"] == summary["linked"]["MSTF"], "matched mission success summary")
check(records(reports["unlinked"]["StockTotalResults"]) == records(reports["linked"]["StockTotalResults"]), "all 120 stock bins paired equal")
for field in ("NFAIL","NDAM","STACC","STF"):
    u,l = records(reports["unlinked"]["SystemResults"]),records(reports["linked"]["SystemResults"])
    for i,(ur,lr) in enumerate(zip(u,l)):
        check(ur[field] == lr[field], f"paired SystemResults {field} bin {i}")

result = {
    "case": "D12.var02",
    "run_id": RUN.name,
    "verdict": "GO — bounded TOP49 direct-middle interruption" if not failures else "NO-GO",
    "passed": not failures,
    "checks_passed": checks-len(failures),
    "checks_total": checks,
    "failures": failures,
    "observed": {
        "PM_tasks": {a: [[task,*value] for task,value in sorted(pm[a].items())] for a in pm},
        "PM_work_events": work,
        "PM_work_hours": {"unlinked":6.5,"linked":5.0},
        "linked_BIG48P5_at_49": "aircraft 1 task5 performing h48.5–49 then stopped and worker released; aircraft 0 task6 starts and stops at h49 with zero work",
        "linked_CAL24_at_49": "aircraft 0 task4 also stops at h49, but this does not isolate transitive TOP49 cancellation",
        "worker_capacity": 1,
        "worker_hours": {"unlinked":11.5,"linked":10},
        "report_PM_markers": {"unlinked":{"NPMS":8,"NPMT":6},"linked":{"NPMS":8,"NPMT":4}},
        "report_bins_per_arm": {"SystemResults":120,"ResourceResults":120,"StockTotalResults":120},
        "summary": summary,
    },
    "limits": [
        "One seed, two aircraft, one base, one worker, 60-hour horizon and one three-PM chain; no general PMRID law.",
        "TOP49 directly references BIG48P5. A CAL24 task also stops at h49, but this pair does not isolate transitive cancellation.",
        "The native log shows task stops and resource release, but does not expose PM counter values or behavior at other due-time spacings.",
    ],
}
OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
print(json.dumps({k:result[k] for k in ("verdict","checks_passed","checks_total","failures")},sort_keys=True))
