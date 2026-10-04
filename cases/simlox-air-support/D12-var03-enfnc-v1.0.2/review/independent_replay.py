"""Independent standard-library replay of sealed D12.var03 ENFNC evidence."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
RUN = CASE / "runs" / "d12-var03-enfnc-v102-ssh-20261004-01"
OUT = CASE / "review" / "independent-verdict.json"
checks, failures = 0, []


def ck(value, label):
    global checks
    checks += 1
    if not value:
        failures.append(label)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    data = path.read_text(encoding="utf-8-sig")
    out, quoted, escaped = [], False, False
    for i, char in enumerate(data):
        if quoted:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        if char == ",":
            j = i+1
            while j < len(data) and data[j].isspace():
                j += 1
            if j < len(data) and data[j] in "]}":
                continue
        out.append(char)
    return json.loads("".join(out))


def tbl(doc, root="model"):
    return {t["name"]:t for t in doc[root]["tables"]}


def rows(table):
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols,r)) for ins in table["instances"] for r in ins["rows"]]


def inst(table):
    return {i["instance_name"]:i["rows"] for i in table["instances"]}


def approx(a,b,tol=2e-4):
    return math.isclose(float(a),float(b),abs_tol=tol,rel_tol=0)


contract, closure = read(CASE/"contract.json"), read(RUN/"closure.json")
inv, steps = read(RUN/"invocation.json"), read(RUN/"steps.json")
ck(contract["run_id"] == RUN.name == inv["run_id"] == closure["run_id"], "run identity")
ck(digest(RUN/"invocation.json") == closure["invocation_sha256"], "invocation seal")
ck(closure["error"] is None and closure["publication_state"] == "not_published", "closure status")
ck(inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"], "session-0 SSH ancestry")
ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "queue mutex")
ck(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "GUI identity")
ck(len(steps) == 8, "eight native steps")
for arm in ("n","y"):
    for action in ("import","export","calc","report"):
        step = next((x for x in steps if x["name"] == f"{arm}_{action}"),None)
        ck(step is not None and step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"{arm} {action} completed and GUI preserved")
        if step and action == "calc":
            ck("-threads 1" in step["arguments"], f"{arm} serial calculation")

paths = {
    "contract": CASE/"contract.json",
    "n": CASE/"n-input.json",
    "y": CASE/"y-input.json",
    "parent_input": ROOT/"D08-var03-criticality-v1.0.0"/"native-input-failure-mode.json",
    "parent_closure": ROOT/"D08-var03-criticality-v1.0.0"/"runs"/"d08-var03-failure-mode-v100-ssh-20261002-01"/"closure.json",
    "parent_signoff": ROOT/"D08-var03-criticality-v1.0.0"/"cli-scope-signoff-2026-10-02.md",
    "pattern_input": ROOT/"D05-maintenance-competition-v1.0.0"/"native-input.json",
    "pattern_signoff": ROOT/"D05-maintenance-competition-v1.0.0"/"cli-scope-signoff-2026-09-30.md",
    "diagnostic_closure": ROOT/"D12-var03-enfnc-v1.0.0"/"runs"/"d12-var03-enfnc-v100-ssh-20261004-01"/"closure.json",
    "no_exposure_closure": ROOT/"D12-var03-enfnc-v1.0.1"/"runs"/"d12-var03-enfnc-v101-ssh-20261004-01"/"closure.json",
    "build.py": CASE/"build.py",
    "run_native_ssh.ps1": CASE/"run_native_ssh.ps1",
}
for key,sha in sorted(closure["source_hashes_before"].items()):
    ck(closure["source_hashes_after"].get(key) == sha == inv["source_hashes_before"].get(key), f"stable {key} seal")
    if key in paths:
        ck(paths[key].is_file() and digest(paths[key]) == sha, f"current {key} bytes")
ck(digest(paths["contract"]) == closure["source_hashes_before"]["contract"], "frozen contract byte pin")
for name,metadata in sorted(closure["raw"].items()):
    path=RUN/name
    ck(path.is_file() and path.stat().st_size == metadata["bytes"] and digest(path) == metadata["sha256"], f"raw seal {name}")
ck(len(closure["raw"]) == 22, "22 raw seals")

src = {a:read(CASE/f"{a}-input.json") for a in ("n","y")}
parent = tbl(read(paths["parent_input"]))
st = {a:tbl(src[a]) for a in src}
for arm in src:
    ck(digest(CASE/f"{arm}-input.json") == contract["inputs_sha256"][arm], f"{arm} contract input pin")
    ck((RUN/f"{arm}.sxo").stat().st_size > 4, f"{arm} usable SXO")
    runlog=(RUN/f"{arm}-run.log").read_text(errors="replace")
    ck("Errors: 0" in runlog and "Notes: 0" in runlog, f"{arm} converter zero errors/notes")
    ck("warning #108" in runlog and "Warnings: 1" in runlog, f"{arm} classified warning")
    changed={k for k in parent if parent[k] != st[arm][k]}
    ck(changed == {"CMLocation","Control","FailureMode","MaterielPM","OperationProfile","PMLocation","ProblemDescription","Resource","ResourceAllocation","ResultCollection","SubTaskResource","SubTaskType","TaskBreakDown","Tasks"}, f"{arm} parent changed-table set")
    ck(rows(st[arm]["Control"])[0]["SIMPE"] == 14 and rows(st[arm]["Control"])[0]["RCEND"] == 14, f"{arm} 14h simulation")
    ck(len(rows(st[arm]["OperationProfile"])) == 1, f"{arm} one mission profile")
    ck(rows(st[arm]["FailureMode"])[0]["FRQ"] == 3000000, f"{arm} failure frequency")
    pm=rows(st[arm]["MaterielPM"])[0]
    ck((pm["PMID"],pm["PMINT"],pm["OPID"],pm["DTIM"],pm["MNOCC"],pm["ENFNC"]) == ("PM9P9",9.9,"CALHOURS",.5,1,arm.upper()), f"{arm} PM definition")
    authored,native=st[arm],tbl(read(RUN/f"{arm}-roundtrip-raw.json"))
    for name,table in sorted(authored.items()):
        actual=native[name]
        cols=[c["name"] for c in table["columns"]]
        native_cols=[c["name"] for c in actual["columns"]]
        for label,rr in sorted(inst(table).items()):
            if not rr or all(all(v is None for v in row) for row in rr):
                continue
            got=inst(actual).get(label,[])
            ck(len(got)==len(rr),f"{arm} {name}/{label} row count")
            for i,row in enumerate(rr):
                for j,column in enumerate(cols):
                    ck(i<len(got) and column in native_cols and got[i][native_cols.index(column)]==row[j],f"{arm} {name}/{label} row{i} {column}")
for name in sorted(st["n"]):
    if name not in ("ProblemDescription","MaterielPM"):
        ck(st["n"][name] == st["y"][name],f"matched pair table {name}")
npm,ypm=rows(st["n"]["MaterielPM"])[0],rows(st["y"]["MaterielPM"])[0]
ck({k:v for k,v in npm.items() if k!="ENFNC"} == {k:v for k,v in ypm.items() if k!="ENFNC"}, "PM differs only ENFNC")
ck(npm["ENFNC"]=="N" and ypm["ENFNC"]=="Y", "N/Y sole business discriminator")

events={a:(RUN/f"{a}.log").read_text(errors="replace").splitlines() for a in src}
def time_event(arm,time,fragment):
    return any(line.startswith(f"Time: {time} ") and fragment in line for line in events[arm])
def time_both(arm,time,first,second):
    return any(line.startswith(f"Time: {time} ") and first in line and second in line for line in events[arm])
for arm in src:
    ck(time_event(arm,"8.31325","noncritical CM failure mode added"),f"{arm} observed noncritical failure")
    ck(time_event(arm,"10","mission success"),f"{arm} mission success h10")
    ck(any(".PM9P9 Non-Critical" in line for line in events[arm]),f"{arm} PM pending at return")
    ck(time_event(arm,"10","system PM task 0") and time_event(arm,"10","system CM task 1"),f"{arm} PM and CM task starts at return")
    ck(time_event(arm,"11.5","system PM task 0") or time_event(arm,"11","system PM task 0"),f"{arm} PM completes")
    ck(time_event(arm,"11.5","system CM task 1") or time_event(arm,"10.5","system CM task 1"),f"{arm} CM completes")

expected={"n":{"pm":(10,11),"cm":(11,11.5)},"y":{"pm":(10.5,11.5),"cm":(10,10.5)}}
bookings={}
for arm in src:
    pmstart,pmend=expected[arm]["pm"]
    cmstart,cmend=expected[arm]["cm"]
    for kind,low,high in (("PM",pmstart,pmend),("CM",cmstart,cmend)):
        fragment=("subtask 0 seqno 1 within system PM task 0" if kind=="PM" else "direct repair subtask 1 seqno 1 within system CM task 1")
        ck(time_both(arm,str(low),fragment,"starts performing"),f"{arm} {kind} work starts")
        ck(time_both(arm,str(high),fragment,"completed"),f"{arm} {kind} work ends")
    entries=[]
    for line in events[arm]:
        m=re.match(r"Time: ([0-9.]+)  <P-MAINT at <BASE-01,0>> (allocated|deallocated) (?:to|from)\s+maintenance task: 1  available now: (\d+)",line)
        if m:
            entries.append((float(m[1]),1 if m[2]=="allocated" else -1,int(m[3])))
    bookings[arm]=entries
    ck([e[0] for e in entries]==[10,10.5,10.5,11.5] if arm=="y" else [e[0] for e in entries]==[10,11,11,11.5],f"{arm} worker booking order")
    active=0
    for t,delta,available in entries:
        active+=delta
        ck(active in (0,1) and active+available==1,f"{arm} single-worker capacity {t}")
    ck(active==0,f"{arm} worker released by horizon")

report={a:tbl(read(RUN/f"{a}-report-raw.json"),"report") for a in src}
summaries={a:rows(report[a]["ResultSummary"])[0] for a in src}
for arm in src:
    for name in ("SystemResults","ResourceResults","StockTotalResults"):
        rr=rows(report[arm][name])
        ck(len(rr)==28,f"{arm} {name} 28 half-hour bins")
        for i,row in enumerate(rr):
            ck(approx(row["STINT"],i*.5) and approx(row["ETINT"],(i+1)*.5),f"{arm} {name} bin{i} bounds")
    sys,resource,stock=(rows(report[arm][n]) for n in ("SystemResults","ResourceResults","StockTotalResults"))
    spans=[(entries[0][0],entries[1][0]),(entries[2][0],entries[3][0])] if (entries:=bookings[arm]) else []
    for i,row in enumerate(resource):
        occupancy=sum(max(0,min((i+1)*.5,b)-max(i*.5,a))/.5 for a,b in spans)
        ck(approx(row["NRUM"],occupancy),f"{arm} ResourceResults NRUM bin{i}")
        ck(float(row["NRUM"])<=1.00001,f"{arm} worker capacity bin{i}")
    ck(approx(sum(float(r["NRUM"])*.5 for r in resource),1.5),f"{arm} worker hour integral")
    for i,row in enumerate(sys):
        pm_a,pm_b=expected[arm]["pm"]
        cm_a,cm_b=expected[arm]["cm"]
        pm_fraction=max(0,min((i+1)*.5,pm_b)-max(i*.5,pm_a))/.5
        cm_fraction=max(0,min((i+1)*.5,cm_b)-max(i*.5,cm_a))/.5
        ck(approx(row["NSYPM"],pm_fraction),f"{arm} SystemResults PM bin{i}")
        ck(approx(row["NSYRP"],cm_fraction),f"{arm} SystemResults repair bin{i}")
        ck(approx(float(row["NSYA"])+float(row["NSYUA"]),1),f"{arm} aircraft conservation bin{i}")
    ck(approx(sum(float(r["NSYPM"])*.5 for r in sys),1),f"{arm} PM-hour integral")
    ck(approx(sum(float(r["NSYRP"])*.5 for r in sys),.5),f"{arm} CM-hour integral")
    ck(approx(sum(float(r["NPMS"]) for r in sys),1) and approx(sum(float(r["NPMT"]) for r in sys),1),f"{arm} PM markers")
    ck(approx(sum(float(r["NFAIL"]) for r in sys),1),f"{arm} one failure marker")
    for i,row in enumerate(stock):
        ck(all(row[k] is None or approx(row[k],0) for k in ("NBO","NBOU","NDF","NDD","NDR","NDP")),f"{arm} zero stock activity bin{i}")
    ck(approx(sys[-1]["NSYRY"],1),f"{arm} terminal aircraft ready")
    ck(summaries[arm]["NREP"]==1 and approx(summaries[arm]["MSTF"],1),f"{arm} summary one successful mission")
ck(summaries["n"]==summaries["y"],"paired summary equality")
ck(rows(report["n"]["StockTotalResults"])==rows(report["y"]["StockTotalResults"]),"paired stock report equality")

result={
    "case":"D12.var03",
    "run_id":RUN.name,
    "verdict":"GO — bounded ENFNC N/Y noncritical CM-before-PM ordering" if not failures else "NO-GO",
    "passed":not failures,
    "checks_passed":checks-len(failures),
    "checks_total":checks,
    "failures":failures,
    "observed":{"failure_hour":8.31325,"mission":"one success at h10","N":{"PM_work":[10,11],"CM_work":[11,11.5]},"Y":{"CM_work":[10,10.5],"PM_work":[10.5,11.5]},"worker_hours_each":1.5,"report_bins_each":28,"summary":summaries},
    "limits":["One fixed seed, one aircraft/base/worker, one explicit noncritical failure mode and one PM; no general priority law.","PM9P9 is pending at h10 return; its internal due/counter state at h9.9 is not directly logged.","v1.0.0 converter #204 and v1.0.1 no-exposure runs are excluded diagnostics; neither supports the behavior claim.","No PMRID, critical-PM, remote-base, GUI or cross-engine inference."],
}
OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
print(json.dumps({k:result[k] for k in ("verdict","checks_passed","checks_total","failures")},sort_keys=True))
