"""Independent, read-only replay of the sealed D12.var01 native pair."""
import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BASE = HERE.parent
RUN = HERE / "runs" / "d12-var01-pm-relation-v101-ssh-20261004-01"
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
check(sha(HERE / "contract.json") == "eb79896fac43418539580ba674d4b028fd4792f3839c792a694e0d813f31afce", "frozen v1.0.1 contract")
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
    "parent_input": BASE / "D05-maintenance-competition-v1.0.0" / "native-input.json",
    "parent_closure": BASE / "D05-maintenance-competition-v1.0.0" / "runs" / "d05-pilot-v100-ssh-20260930-03" / "closure.json",
    "parent_signoff": BASE / "D05-maintenance-competition-v1.0.0" / "cli-scope-signoff-2026-09-30.md",
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
parent = native_json(pins["parent_input"])
pt, ut = tables(parent), tables(source["unlinked"])
allowed = {"Control","MaterielPM","PMLocation","ProblemDescription","ResultCollection","SubTaskResource","TaskBreakDown","Tasks"}
for name in sorted(pt):
    if name not in allowed:
        check(pt[name] == ut[name], f"parent unchanged {name}")
for name in ("Control","MaterielPM","ResultCollection"):
    pcol = [c["name"] for c in pt[name]["columns"]]
    old, new = instances(pt[name])[""], instances(ut[name])[""]
    check(len(new) == len(old)+(1 if name == "MaterielPM" else 0), f"parent {name} row count")
    permitted = {"Control":{"SIMPE","RCEND"},"MaterielPM":{"ENREG"},"ResultCollection":{"RCEND"}}[name]
    for i, prow in enumerate(old):
        for j, col in enumerate(pcol):
            if col not in permitted:
                check(prow[j] == new[i][j], f"parent {name} row {i} {col} unchanged")
    if name == "Control":
        check(all(old[0][pcol.index(k)] == 36 and new[0][pcol.index(k)] == 60 for k in ("SIMPE","RCEND")), "60-hour control delta")
    elif name == "MaterielPM":
        check(old[0][pcol.index("ENREG")] is None and new[0][pcol.index("ENREG")] == "Y", "CAL24 regular interval delta")
    else:
        check(all(o[pcol.index("RCEND")] == 36 and n[pcol.index("RCEND")] == 60 for o,n in zip(old,new)), "60-hour collection delta")
for name in ("MaterielPM","PMLocation","SubTaskResource","TaskBreakDown","Tasks"):
    old,new = instances(pt[name])[""],instances(ut[name])[""]
    check(new[:len(old)] == old if name != "MaterielPM" else True, f"parent {name} prefix")
    check(len(new) == len(old)+1, f"parent {name} appended one row")
check(records(ut["MaterielPM"])[-1]["PMID"] == "BIG47", "BIG47 added")
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
check(len(lu) == len(ll) == 2, "two PM definitions")
for u, l in zip(lu, ll):
    if u.get("PMID") == "BIG47":
        check({k: v for k, v in u.items() if k != "PMRID"} == {k: v for k, v in l.items() if k != "PMRID"}, "BIG47 other fields equal")
        check(u["PMRID"] is None and l["PMRID"] == "CAL24", "only relation cell")
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
    work[arm] = [(float(m[1]), int(m[2]), "start" if m[3] == "starts performing" else "end") for line in lines if (m := re.match(r"Time: ([0-9.]+)  subtask (\d+) seqno 1 within system PM task \d+ on <TEACH-AIR-01,\d+> (starts performing|completed)", line))]
    booking = [(float(m[1]), "on" if m[2] == "allocated" else "off", int(m[3])) for line in lines if (m := re.match(r"Time: ([0-9.]+)  <P-MAINT at <BASE-01,0>> (allocated|deallocated) (?:to|from)\s+maintenance task: 1  available now: (\d+)", line))]
    bookings[arm] = booking
    active = 0
    for t, kind, available in booking:
        active += 1 if kind == "on" else -1
        check(active in (0, 1) and active + available == 1, f"{arm} worker capacity at {t}")
    check(active == 0, f"{arm} worker released")

def before_47(lines):
    return lines[:next(i for i,line in enumerate(lines) if line.startswith("Time: 47 "))]
check(before_47(event["unlinked"]) == before_47(event["linked"]), "identical paired event trace before h47")

check(pm["unlinked"] == {1:(24.0,0,"CAL24"), 2:(24.0,1,"CAL24"), 3:(47.0,1,"BIG47"), 4:(47.0,0,"BIG47"), 5:(48.0,1,"CAL24"), 6:(48.0,0,"CAL24")}, "unlinked PM identities")
check(pm["linked"] == {1:(24.0,0,"CAL24"), 2:(24.0,1,"CAL24"), 3:(47.0,1,"BIG47"), 4:(47.0,0,"BIG47"), 5:(48.0,0,"CAL24")}, "linked PM identities")
for arm, expected in {
    "unlinked": [(26.4799,1,"start"),(27.4799,1,"end"),(27.4799,2,"start"),(28.4799,2,"end"),(47,3,"start"),(48,3,"end"),(48,4,"start"),(49,4,"end"),(49,5,"start"),(50,5,"end"),(50,6,"start"),(51,6,"end")],
    "linked": [(26.4799,1,"start"),(27.4799,1,"end"),(27.4799,2,"start"),(28.4799,2,"end"),(47,3,"start"),(48,3,"end"),(48,4,"start"),(49,4,"end")],
}.items():
    check(work[arm] == expected, f"{arm} PM work chronology")
    check(any("system DIRP task 0" in line and "started" in line for line in event[arm]), f"{arm} repair occurred")
    check(sum("mission success" in line.lower() for line in event[arm]) >= 1, f"{arm} mission success evidence")
check(any("system PM task 5" in line and "stopped" in line for line in event["linked"]), "linked h48 CAL24 stopped")
check(not any("subtask 5" in line and "starts performing" in line for line in event["linked"]), "linked h48 CAL24 has zero work")

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
    check(close(sum(float(r["NRUM"])*.5 for r in rr), 11 if arm == "unlinked" else 9, 3e-4), f"{arm} 11/9 booked worker hours")
    stock = records(report["StockTotalResults"])
    for i, row in enumerate(stock):
        check(all(row[k] is None or close(row[k],0) for k in ("NBO","NBOU","NDF","NDD","NDR","NDP")), f"{arm} zero stock/demand bin {i}")
    system = records(report["SystemResults"])
    for i, row in enumerate(system):
        check(close(float(row["NSYA"])+float(row["NSYUA"]),2,3e-4), f"{arm} aircraft conservation bin {i}")
    check(close(system[-1]["NSYRY"],2), f"{arm} terminal ready")
    check(summary[arm]["NREP"] == 1, f"{arm} one replication")

# Event-derived second-cycle work explains the report PM-hour contrast.
for arm, hours in (("unlinked",6.0),("linked",4.0)):
    spans = {}
    for t, task, kind in work[arm]:
        spans.setdefault(task,{})[kind] = t
    check(close(sum(v["end"]-v["start"] for v in spans.values()),hours), f"{arm} PM work hours")
    system = records(reports[arm]["SystemResults"])
    pm_hours = sum(float(r["NSYPM"])*.5 for r in system)
    check(close(pm_hours,hours,1e-3), f"{arm} SystemResults PM hours")
check(summary["unlinked"]["MSTF"] == summary["linked"]["MSTF"], "matched mission success summary")
check(records(reports["unlinked"]["StockTotalResults"]) == records(reports["linked"]["StockTotalResults"]), "all 120 stock bins paired equal")
for field in ("NFAIL","NDAM","STACC","STF"):
    u,l = records(reports["unlinked"]["SystemResults"]),records(reports["linked"]["SystemResults"])
    for i,(ur,lr) in enumerate(zip(u,l)):
        check(ur[field] == lr[field], f"paired SystemResults {field} bin {i}")

result = {
    "case": "D12.var01",
    "run_id": RUN.name,
    "verdict": "GO — bounded observed PMRID work-cancellation contrast" if not failures else "NO-GO",
    "passed": not failures,
    "checks_passed": checks-len(failures),
    "checks_total": checks,
    "failures": failures,
    "observed": {
        "PM_tasks": {a: [[task,*value] for task,value in sorted(pm[a].items())] for a in pm},
        "PM_work_hours": {"unlinked":6,"linked":4},
        "linked_CAL24_at_48": "aircraft 0 task created at h48, explicitly stopped at h49 without worker time; aircraft 1 no task",
        "unlinked_CAL24_at_48": "two tasks work serially h49–51",
        "worker_capacity": 1,
        "report_bins_per_arm": {"SystemResults":120,"ResourceResults":120,"StockTotalResults":120},
        "summary": summary,
    },
    "limits": [
        "One seed, two aircraft, one base, one P-MAINT worker, 60-hour horizon; no general PMRID scheduling law.",
        "The linked arm still creates a CAL24 task at h48. Evidence supports cancellation of work, not absence of task creation.",
        "The native log does not expose counter values; reset is inferred only from task and work behavior.",
        "The smaller PM had not begun work when BIG47 initiated, so started-small-PM interruption remains untested.",
    ],
}
OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
print(json.dumps({k:result[k] for k in ("verdict","checks_passed","checks_total","failures")},sort_keys=True))
