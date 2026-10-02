"""Independent read-only replay of G11.var10, using frozen source and native raw bytes."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent
PARENT = CASE.parent / "G11-var04-inherit-item-prelife-v1.0.1"
PARENT_INPUT = PARENT / "native-input-explicit-control.json"
PARENT_RUN = PARENT / "runs/g11-var04-explicit-control-v101-ssh-20261002-01"
RUN = CASE / "runs/g11-var10-assy-inherit-v100-ssh-20261003-01"
SOURCE = CASE / "native-input-assy-inherit.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
COUNT = 0
FAILURES: list[str] = []


def ck(ok: bool, label: str) -> None:
    global COUNT
    COUNT += 1
    if not ok:
        FAILURES.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rd(path: Path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(path: Path, root: str) -> dict:
    return {t["name"]: t for t in rd(path)[root]["tables"]}


def rows(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, r)) for i in table["instances"] for r in i["rows"]]


def near(a, b, tol=.0001) -> bool:
    return isinstance(a, (float, int)) and abs(a-b) <= tol


def report_ledger() -> None:
    report = tables(RUN / "report-raw.json", "report")
    parent = tables(PARENT_RUN / "report-raw.json", "report")
    ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       "four default report tables")
    ck({n:t for n,t in report.items() if n!="ProblemDescription"} ==
       {n:t for n,t in parent.items() if n!="ProblemDescription"},
       "candidate report equals accepted parent except description")
    sy, st = rows(report["SystemResults"]), rows(report["StockTotalResults"])
    ck(len(sy)==len(st)==192, "192 System/Stock bins")
    ck(rows(report["ResultSummary"])==[{"NREP":1,"RTILW":0,"RTIUP":96,"MTMF":0,
        "RSMTMF":0,"MSTF":0,"RSMSTF":0,"MSUF":0,"RSMSUF":0,"STMF":0,"RSSTMF":0}],
       "no-mission result summary")
    zero_sy=("NSYMA","NSYMO","NSYMC","NSYMP","NSYMT","NSYMS","NSYMR","NSYAL","FTMO",
             "NSYRP","NSYTP","NSYWR","NSYWI","NSYLA","NSYUH","NREPT","NFAIL","NDAM",
             "NROBT","NRCFG","STREQ","STACC","STF","STLOW","SYDTU","NSYSW","NPSTA","NPSUC")
    for i,(s,k) in enumerate(zip(sy,st)):
        t=i/2
        ck(s["STINT"]==k["STINT"]==t and s["ETINT"]==k["ETINT"]==t+.5,
           f"aligned report interval {i}")
        active=int(t==80)
        for key,value in {"NSYRY":1-active,"NSYA":1-active,"NSYUA":active,"NSYPM":active}.items():
            ck(near(s[key],value),f"SystemResults {key} bin {i}")
        for key,value in {"NPMS":active,"NPMT":int(t==80.5),"NSYDT":active}.items():
            ck(s[key]==value,f"SystemResults {key} marker bin {i}")
        ck(s["SYDT"]==(.5 if active else None),f"SYDT bin {i}")
        for key in zero_sy:
            ck(s[key]==0,f"zero SystemResults {key} bin {i}")
        ck(k["PNB"]==1 and k["NDP"]==active and k["NWT"]==active,
           f"stock demand and replacement bin {i}")
        for key in ("NBO","NDF","NDD","NDR","NLD"):
            ck(k[key]==0,f"zero StockTotalResults {key} bin {i}")
        for key in ("NBOU","WTS"):
            ck(k[key] is None,f"null StockTotalResults {key} bin {i}")
        for key in ("ROS","ROST","WT","WTT"):
            ck(k[key] in (None,0),f"no positive {key} bin {i}")
    ck(near(sum(s["NSYPM"]*.5 for s in sy),.5) and
       near(sum(s["NSYMO"]*.5 for s in sy),0),"half-hour system PM, no flight")
    ck(near(sy[-1]["NSYRY"],1) and st[-1]["NBO"]==0,"terminal ready one, no BO")


def main() -> int:
    contract,diff=rd(CASE/"contract.json"),rd(CASE/"exact-diff.json")
    ck(sha(PARENT_INPUT)==contract["accepted_parent"]["input_sha256"]==diff["parent_sha256"],
       "accepted G11.var04 parent input")
    ck(sha(PARENT_RUN/"closure.json")==contract["accepted_parent"]["native_closure_sha256"],
       "accepted G11.var04 parent closure")
    ck(sha(SOURCE)==contract["input"]["sha256"]==diff["input_sha256"],"child source seal")
    ck(sha(CASE/"exact-diff.json")==contract["exact_diff_sha256"],"exact diff seal")
    ck(sha(MANUAL)==contract["source"]["manual_sha256"],"manual seal")
    ck(sha(DICTIONARY)==contract["source"]["dictionary_sha256"],"dictionary seal")
    ck(sha(EXE)=="fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0","CLI seal")
    parent,model=tables(PARENT_INPUT,"model"),tables(SOURCE,"model")
    delta={n:{"before":parent[n],"after":model[n]} for n in parent if parent[n]!=model[n]}
    delta.update({n:{"before":None,"after":model[n]} for n in set(model)-set(parent)})
    ck(delta==diff["changed"] and set(delta)=={"Item","MaterielStructure","Prelife",
       "PrelifeData","PrelifeStructure","ProblemDescription"},"exact six-table parent delta")
    ck(rows(model["Item"])[-1]["IID"]=="TEACH-ASSY-01" and
       rows(model["Item"])[-1]["TYPE"]=="ASSY","ASSY physical item source")
    ck([(r["MID"],r["MMID"]) for r in rows(model["MaterielStructure"])]==
       [("TEACH-ASSY-01","TEACH-AIR-01"),("POS-A","TEACH-ASSY-01"),
        ("TEACH-LRU-01","POS-A")],"four-node physical tree")
    ck([(r["PLID"],r["MPLID"],r["MPLIND"]) for r in rows(model["PrelifeStructure"])]==
       [("PL-ASSY","PL-SYS","SYS-60"),("PL-POS","PL-ASSY","ASSY-INH"),
        ("PL-LRU","PL-POS","POS-INH")],"four-node prelife tree")
    ck([(r["PLID"],r["PLIND"],r["AGE"],r["TYPE"]) for r in rows(model["PrelifeData"])]==
       [("PL-SYS","SYS-60",60,"FIXED"),("PL-ASSY","ASSY-INH",0,"INHERIT"),
        ("PL-POS","POS-INH",0,"INHERIT"),("PL-LRU","LRU-20",20,"FIXED")],
       "explicit system/leaf and inherited intermediate ages")
    ck([r["IQTY"] for r in rows(model["OperationProfile"])]==[0,0,0],"no mission quantity")
    closure,invocation,steps=(rd(RUN/n) for n in ("closure.json","invocation.json","steps.json"))
    ck(closure["run_id"]==invocation["run_id"]==RUN.name,"native run identity")
    ck(sha(RUN/"invocation.json")==closure["invocation_sha256"],"invocation seal")
    ck(invocation["source_hashes_before"]==closure["source_hashes_before"]==
       closure["source_hashes_after"],"source before/after stability")
    pins={"input":SOURCE,"parent":PARENT_INPUT,"parent_closure":PARENT_RUN/"closure.json",
          "contract":CASE/"contract.json","exact_diff":CASE/"exact-diff.json",
          "builder":CASE/"build.py","diff_builder":CASE/"describe_diff.py",
          "checker":CASE/"check_roundtrip.py","runner":CASE/"run_native_ssh.ps1",
          "python":PYTHON,"exe":EXE,"manual":MANUAL,"dictionary":DICTIONARY}
    for key,path in pins.items():
        ck(sha(path)==closure["source_hashes_before"][key],f"source SHA {key}")
    ck(len(closure["raw"])==13 and closure["error"] is None,"13 raw seals, no runner error")
    for name,seal in closure["raw"].items():
        path=RUN/name
        ck(path.exists() and path.stat().st_size==seal["bytes"],f"raw size {name}")
        ck(sha(path)==seal["sha256"],f"raw SHA {name}")
    ck(sha(RUN/"input.json")==sha(SOURCE),"run source byte identity")
    ck(invocation["execution_mode"]=="session0_ssh_cli" and invocation["session_id"]==0 and
       "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]],"session0 SSH")
    ck(invocation["queue_mutex"]=="Global\\SimloxIssue18NativeQueue" and
       invocation["gui"]["pid"]==13340 and invocation["gui"]["session_id"]==1,
       "native mutex and GUI preserved")
    ck(invocation["prelife_log_option_before"]==closure["prelife_log_option_after"]=="NO",
       "Prelife Log registry option restored")
    ck([s["name"] for s in steps]==["import","export","calc","jsonreport","check_import_export"],
       "five guarded steps")
    for step in steps:
        ck(step["exit_code"]==0 and step["status"]=="completed" and step["gui_preserved"] is True,
           f"step {step['name']} successful")
    exported=tables(RUN/"roundtrip-raw.json","model")
    populated=[n for n,t in model.items() if any(i["rows"] for i in t["instances"])]
    ck(len(populated)==23,"23 authored populated tables")
    for name in populated:
        ck(name in exported and model[name]["columns"]==exported[name]["columns"] and
           model[name]["instances"]==exported[name]["instances"],f"exact roundtrip {name}")
    runlog=(RUN/"run.log").read_text(encoding="utf-8-sig",errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
       re.findall(r"\(warning #(\d+)\)",runlog)==["108"] and "(error #" not in runlog,
       "zero errors/notes, inherited warning108 only")
    ck((RUN/"model.sxo").stat().st_size>4,"valid SXO")
    prelife=(RUN/"model_Prelife.log").read_text(encoding="utf-8-sig")
    ages=re.findall(r"\*\*(TEACH-AIR-01|TEACH-ASSY-01|POS-A|TEACH-LRU-01)\*\*"
                    r"(SYS-60|ASSY-INH|POS-INH|LRU-20)\*\* Age\[CALHOURS\]:([0-9.]+)",prelife)
    ck(ages==[("TEACH-AIR-01","SYS-60","60.00"),("TEACH-ASSY-01","ASSY-INH","60.00"),
              ("POS-A","POS-INH","60.00"),("TEACH-LRU-01","LRU-20","20.00")],
       "four-node observed Prelife ages")
    log=(RUN/"model.log").read_text(encoding="utf-8-sig")
    ck(re.findall(r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,0> PMID: LRU-CAL100",log)==["80"],
       "single original-item PM begins h80")
    for time,fragment in ((80,"Item demand arrives from pos"),(80,"item requiring maintenance is <TEACH-LRU-01,0,0>"),
                          (80,"Take replacement item <TEACH-LRU-01,0,2> from stock"),
                          (80.25,"item PM task 1 on <TEACH-LRU-01,0,0> started"),
                          (80.5,"system PM task 0 on <TEACH-AIR-01,0> completed"),
                          (81.25,"item PM task 1 on <TEACH-LRU-01,0,0> completed"),
                          (81.25,"Put back replacement item <TEACH-LRU-01,0,0> to stock")):
        ck(any(line.startswith(f"Time: {time:g} ") and fragment in line for line in log.splitlines()),
           f"native event {fragment[:32]} at {time:g}")
    ck("Stock initiated" in log and "Level: 1 Items:<TEACH-LRU-01,0,2>" in log and
       "Level: 0 Items:" in log and "Level: 1 Items:<TEACH-LRU-01,0,0>" in log,
       "stock initial ID2, issue, repaired ID0 return")
    ck("TEACH-ASSY-01" not in log and "books resources" not in log and
       "mission starting" not in log and "failure occurs" not in log,
       "no logged ASSY demand, resource booking, mission or random failure")
    parentlog=(PARENT_RUN/"model.log").read_text(encoding="utf-8-sig")
    ck("Take replacement item <TEACH-LRU-01,0,1> from stock" in parentlog and
       "Take replacement item <TEACH-LRU-01,0,2> from stock" in log,
       "ASSY adds a physical node and shifts spare ID from parent 1 to child 2")
    report_ledger()
    result={"schema":"simlox-independent-g11-var10/v1","passed":not FAILURES,
            "verdict":"GO: bounded ASSY/MPID prelife inheritance observation" if not FAILURES else
                      "NO-GO: independent replay failed",
            "checks_passed":COUNT-len(FAILURES),"checks_total":COUNT,"failures":FAILURES,
            "evidence":{"input_sha256":sha(SOURCE),"closure_sha256":sha(RUN/"closure.json"),
                        "prelife_log_sha256":sha(RUN/"model_Prelife.log"),
                        "model_log_sha256":sha(RUN/"model.log"),
                        "report_sha256":sha(RUN/"report-raw.json")},
            "finding":"An added physical ASSY and matching inherited Prelife node create the four-node system→ASSY→MPID→LRU path. The native Prelife Log shows ages60/60/60/20; the original LRU ID0 enters monitored PM at h80, spare LRU ID2 is issued, and ID0 returns to stock at h81.25. Non-description aggregate report tables match the accepted parent.",
            "limits":["The child spare is physical ID2 while the accepted parent spare is ID1, consistent with the added ASSY node changing physical ID enumeration. Internal ID allocation is not directly exposed; native model logs are not byte-identical.",
                      "No ASSY logistics demand is observed in this one first-PM, one-ASSY/MPID/LRU, one-seed run; this does not prove absence for all hierarchies or operations.",
                      "The default report is aggregate System/Stock, so physical item identity and stock conservation rely on native event text.",
                      "No missions, later PM cycles, other hierarchies, GUI visual behavior, or cross-engine parity.",
                      "Registry restoration is supported by sealed guarded records, not an independent live registry read."]}
    out=CASE/"independent-validation.json"
    out.write_bytes((json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+"\n").encode("utf-8"))
    print(json.dumps({"passed":result["passed"],"checks_total":COUNT,"failures":FAILURES,
                      "verdict":result["verdict"],"output":str(out)},ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__=="__main__":
    raise SystemExit(main())
