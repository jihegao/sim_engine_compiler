"""Read-only author replay of seeded multi-OPID RANDOM age and override pair."""
import hashlib
import json
import math
import re
from pathlib import Path
from check_roundtrip import SHA,native_json,populated

HERE=Path(__file__).resolve().parent
RUNS={arm:f"g11-var12-{arm}-v100-ssh-20261003-02" for arm in SHA}
PARENT=HERE.parent/"G11-var03-random-system-prelife-v1.0.0"
PARENT_SHA="6984ce91a40a1a0c491ff7eeda4b808c314d50577ec008d1d9f65780acfac512"
PARENT_CLOSURE="56cd0216ea0bec079059c4d0bc09da9914570a7b3c4f10f7ea708a6ed33c76fc"
CONTRACT="8a93e0ea1753003cdc9f84933a4c89a7bb4fc415cc232784a75d35441618c9f2"
DIFF="9068f02c24300775960b4a7ed5a624a30736b7f2ad6e0f109ff8127b5408ea73"
PARENT_RUN=PARENT/"runs/g11-var03-random-seed1-v100-ssh-20261002-01"
EXCLUDED_CLOSURE="01b7600d1af57d167b5392610ae2aee5cbc1f7b6d67e5d32aae2b7e8d5a14802"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def vals(t,name):
    i=[c["name"] for c in t["columns"]].index(name)
    return [row[i] for inst in t["instances"] for row in inst["rows"]]
class Audit:
    def __init__(self):self.checks,self.errors=0,[]
    def need(self,ok,label):
        self.checks+=1
        if not ok:self.errors.append(label)

def arm_replay(arm,a):
    run=HERE/"runs"/RUNS[arm]
    closure,invocation,steps=(read(run/n) for n in ("closure.json","invocation.json","steps.json"))
    a.need(closure["arm"]==arm and closure["run_id"]==RUNS[arm] and closure["error"] is None,f"{arm} closure identity")
    a.need(sha(run/"invocation.json")==closure["invocation_sha256"],f"{arm} invocation seal")
    a.need(invocation["session_id"]==0 and "sshd.exe" in invocation["ssh_ancestor_names"],f"{arm} SSH0")
    a.need(invocation["gui"]["pid"]==13340 and invocation["gui"]["session_id"]==1,f"{arm} GUI")
    a.need(invocation["queue_mutex"]=="Global\\SimloxIssue18NativeQueue",f"{arm} mutex")
    a.need(invocation["prelife_log_option_before"]=="NO" and closure["prelife_log_option_after"]=="NO",f"{arm} registry restore")
    a.need([s["name"] for s in steps]==["import","export","calc","jsonreport","check_import_export"],f"{arm} five steps")
    for s in steps:a.need(s["status"]=="completed" and s["exit_code"]==0 and s["gui_preserved"],f"{arm} step {s['name']}")
    for key,digest in {"input":SHA[arm],"parent":PARENT_SHA,"parent_closure":PARENT_CLOSURE,"contract":CONTRACT,"exact_diff":DIFF}.items():a.need(closure["source_hashes_before"].get(key)==digest,f"{arm} pinned {key}")
    for key,digest in closure["source_hashes_before"].items():a.need(closure["source_hashes_after"].get(key)==digest,f"{arm} unchanged {key}")
    a.need(len(closure["raw"])==13,f"{arm} raw count")
    for name,seal in closure["raw"].items():
        p=run/name;a.need(p.is_file() and p.stat().st_size==seal["bytes"] and sha(p)==seal["sha256"],f"{arm} raw {name}")
    roundtrip=read(run/"roundtrip-validation.json")
    before,after=populated(native_json(run/"input.json")),populated(native_json(run/"roundtrip-raw.json"))
    a.need(roundtrip["passed"] and not roundtrip["differences"] and len(before)==21 and roundtrip["populated_tables"]==sorted(before),f"{arm} roundtrip verdict")
    for name,body in before.items():a.need(after.get(name)==body,f"{arm} roundtrip {name}")
    runlog=(run/"run.log").read_text(encoding="utf-8-sig",errors="replace")
    warning_ids=re.findall(r"\(warning #(\d+)\)",runlog)
    expected=["108","126"] if arm=="added-ophours" else ["108","126","2058"]
    a.need(warning_ids==expected and f"Input conversion completed. Errors: 0, Warnings: {len(expected)}, Notes: 0" in runlog and "(error #" not in runlog and "(notice #" not in runlog,f"{arm} classified converter warnings")
    a.need(("Data overrides previous data: PL-SYS/RND-0-120/CALHOURS" in runlog)==(arm=="calendar-override"),f"{arm} override warning text")
    prelife=(run/"model_Prelife.log").read_text(encoding="utf-8-sig",errors="replace")
    ages=[(float(c),float(o)) for c,o in re.findall(r"\*\*TEACH-AIR-01\*\*RND-0-120\*\* Age\[CALHOURS\]:([0-9.]+) Age\[OPHOURS\]:([0-9.]+)",prelife)]
    expected_ages=([(68.21,34.11),(46.89,23.44),(8.20,4.10)] if arm=="added-ophours" else [(51.16,34.11),(35.17,23.44),(6.15,4.10)])
    a.need(ages==expected_ages,f"{arm} native ages")
    ratio=2 if arm=="added-ophours" else 1.5
    for i,(cal,oph) in enumerate(ages):a.need(abs(cal-ratio*oph)<=.02,f"{arm} common random draw {i}")
    event=(run/"model.log").read_text(encoding="utf-8-sig",errors="replace")
    pm=[(float(t),int(i)) for t,i in re.findall(r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,(\d+)> started",event)]
    expected_pm=([(31.7879,0),(53.1133,1),(91.8013,2)] if arm=="added-ophours" else [(48.8409,0),(64.835,1),(93.851,2)])
    a.need(pm==expected_pm,f"{arm} first PM identities/times")
    for t,i in pm:a.need(abs(t-(100-ages[i][0]))<.02,f"{arm} PM arithmetic ID{i}")
    a.need(not re.search(r"mission (started|success:|cancelled)",event,re.I) and "backorder" not in event.lower() and "(error #" not in event,f"{arm} no missions/backorders/errors")
    report={t["name"]:t for t in native_json(run/"report-raw.json")["report"]["tables"]}
    a.need(set(report)=={"ProblemDescription","ResultSummary","SystemResults","StockTotalResults"},f"{arm} report tables")
    for field,target in {"NREP":1,"RTIUP":104,"MSTF":0,"MSUF":0}.items():a.need(vals(report["ResultSummary"],field)==[target],f"{arm} summary {field}")
    for name in ("SystemResults","StockTotalResults"):
        st,en=vals(report[name],"STINT"),vals(report[name],"ETINT")
        a.need(len(st)==208 and st[0]==0 and en[-1]==104 and all(x==y for x,y in zip(en,st[1:])),f"{arm} {name} bins")
    for field,target in (("NPMT",3),("NPMS",3),("NSYPM",6)):
        a.need(math.isclose(sum(x or 0 for x in vals(report["SystemResults"],field)),target,abs_tol=1e-6),f"{arm} system {field}")
    a.need(sum(x or 0 for x in vals(report["StockTotalResults"],"NBO"))==0 and sum(x or 0 for x in vals(report["SystemResults"],"NFAIL"))==0,f"{arm} no failure/backorder")
    a.need(vals(report["SystemResults"],"NSYRY")[-1]==3,f"{arm} terminal ready3")
    if arm=="added-ophours":
        a.need((run/"model.log").read_bytes()==(PARENT_RUN/"model.log").read_bytes(),"added OPHOURS parent event equality")
        prior={t["name"]:t for t in native_json(PARENT_RUN/"report-raw.json")["report"]["tables"]}
        for name in ("ResultSummary","SystemResults","StockTotalResults"):a.need(report[name]==prior[name],f"added OPHOURS parent report {name}")
    return {"arm":arm,"run_id":RUNS[arm],"closure_sha256":sha(run/"closure.json"),"prelife_log_sha256":sha(run/"model_Prelife.log"),"event_log_sha256":sha(run/"model.log"),"report_sha256":sha(run/"report-raw.json"),"ages_calhours_ophours":ages,"system_pm":pm,"warnings":warning_ids}

def main():
    a=Audit()
    for label,path,digest in (("parent",PARENT/"native-input-random-seed1.json",PARENT_SHA),("parent closure",PARENT_RUN/"closure.json",PARENT_CLOSURE),("contract",HERE/"contract.json",CONTRACT),("diff",HERE/"exact-diff.json",DIFF),("excluded diagnostic closure",HERE/"runs/g11-var12-calendar-override-v100-ssh-20261003-01/closure.json",EXCLUDED_CLOSURE)):a.need(sha(path)==digest,f"{label} SHA")
    excluded=read(HERE/"runs/g11-var12-calendar-override-v100-ssh-20261003-01/closure.json")
    a.need(excluded["error"]=="unexpected warnings" and excluded["run_id"] not in RUNS.values(),"failed diagnostic excluded")
    docs=[]
    for arm in RUNS:
        p=HERE/f"native-input-{arm}.json";a.need(sha(p)==SHA[arm],f"{arm} input SHA");docs.append(native_json(p))
    tables=[{t["name"]:t for t in doc["model"]["tables"]} for doc in docs]
    a.need({n for n in tables[0] if tables[0][n]!=tables[1][n]}=={"PrelifeDataAge","ProblemDescription"},"pair changed tables")
    arows=[t["PrelifeDataAge"]["instances"][0]["rows"] for t in tables]
    a.need(arows[0]==[["PL-SYS","RND-0-120","OPHOURS",60.,0.,None]] and arows[1]==arows[0]+[["PL-SYS","RND-0-120","CALHOURS",90.,0.,None]],"only calendar override added")
    arms=[arm_replay(arm,a) for arm in RUNS]
    a.need([x[1] for x in arms[0]["ages_calhours_ophours"]]==[x[1] for x in arms[1]["ages_calhours_ophours"]],"OPHOURS realizations unchanged by override")
    result={"schema":"simlox-g11-var12-multi-opid-random-author-replay/v1","case_id":"G11","variant_id":"G11.var12","version":"1.0.0","checks":a.checks,"passed_checks":a.checks-len(a.errors),"passed":not a.errors,"differences":a.errors,"arms":arms,"excluded_diagnostic_closure_sha256":EXCLUDED_CLOSURE,"scope":"one seeded top-level three-system RANDOM draw across two OPIDs and same-OPID calendar override","publication_state":"not_published"}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result["passed"] else 1
if __name__=="__main__":raise SystemExit(main())
