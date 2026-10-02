"""Independent, read-only raw replay for G11.var09. No author code is imported."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent
PARENT = CASE.parent / "G11-var04-inherit-item-prelife-v1.0.1"
PARENT_INPUT = PARENT / "native-input-inherited.json"
PARENT_CLOSURE = PARENT / "runs/g11-var04-inherited-v101-ssh-20261002-01/closure.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
ARMS = {"age20-then60": "g11-var09-age20-then60-v100-ssh-20261003-01",
        "age60-then20": "g11-var09-age60-then20-v100-ssh-20261003-01"}
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


def near(a, b, tolerance=.0001) -> bool:
    return isinstance(a, (float, int)) and abs(a - b) <= tolerance


def ledger(arm: str, run: Path) -> dict:
    report = tables(run / "report-raw.json", "report")
    ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       f"{arm}: default report tables")
    sy, st = rows(report["SystemResults"]), rows(report["StockTotalResults"])
    ck(len(sy) == len(st) == 192, f"{arm}: 192 report bins")
    ck(rows(report["ResultSummary"]) == [{"NREP": 1, "RTILW": 0, "RTIUP": 96, "MTMF": 0,
        "RSMTMF": 0, "MSTF": 0, "RSMSTF": 0, "MSUF": 0, "RSMSUF": 0, "STMF": 0,
        "RSSTMF": 0}], f"{arm}: no-mission summary")
    zero_sy = ("NSYMA", "NSYMO", "NSYMC", "NSYMP", "NSYMT", "NSYMS", "NSYMR", "NSYAL",
               "FTMO", "NSYRP", "NSYTP", "NSYWR", "NSYWI", "NSYLA", "NSYUH", "NREPT",
               "NFAIL", "NDAM", "NROBT", "NRCFG", "STREQ", "STACC", "STF", "STLOW",
               "SYDTU", "NSYSW", "NPSTA", "NPSUC")
    zero_st = ("NBO", "NDF", "NDD", "NDR", "NLD")
    for i, (s, k) in enumerate(zip(sy, st)):
        t = i / 2
        ck(s["STINT"] == k["STINT"] == t and s["ETINT"] == k["ETINT"] == t+.5,
           f"{arm}: aligned bin {i}")
        pm = int(t in (40, 80))
        tail = int(t in (40.5, 80.5))
        for key, expected in {"NSYRY": 2-pm, "NSYA": 2-pm, "NSYUA": pm,
                              "NSYPM": pm}.items():
            ck(near(s[key], expected, .0001), f"{arm}: SystemResults {key} bin {i}")
        for key, expected in {"NPMS": pm, "NPMT": tail, "NSYDT": pm}.items():
            ck(s[key] == expected, f"{arm}: PM marker {key} bin {i}")
        ck(s["SYDT"] == (.5 if pm else None), f"{arm}: SYDT bin {i}")
        for key in zero_sy:
            ck(s[key] == 0, f"{arm}: zero SystemResults {key} bin {i}")
        ck(k["PNB"] == 1 and k["NDP"] == pm and k["NWT"] == pm,
           f"{arm}: stock demand and replacement bin {i}")
        for key in zero_st:
            ck(k[key] == 0, f"{arm}: zero StockTotalResults {key} bin {i}")
        for key in ("NBOU", "WTS"):
            ck(k[key] is None, f"{arm}: null StockTotalResults {key} bin {i}")
        for key in ("ROS", "ROST", "WT", "WTT"):
            ck(k[key] in (None, 0), f"{arm}: no positive StockTotalResults {key} bin {i}")
    ck(near(sum(x["NSYPM"]*.5 for x in sy), 1) and
       near(sum(x["NSYMO"]*.5 for x in sy), 0), f"{arm}: one system PM hour, no flight")
    ck(near(sy[-1]["NSYRY"], 2) and st[-1]["NBO"] == 0,
       f"{arm}: terminal ready two and no backorder")
    return {"report_sha256": sha(run / "report-raw.json"), "system_bins": len(sy),
            "stock_bins": len(st)}


def main() -> int:
    contract, diff = rd(CASE / "contract.json"), rd(CASE / "exact-diff.json")
    ck(sha(PARENT_INPUT) == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"],
       "accepted G11.var04 parent input")
    ck(sha(PARENT_CLOSURE) == contract["accepted_parent"]["native_closure_sha256"],
       "accepted G11.var04 parent closure")
    ck(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "exact diff seal")
    ck(sha(MANUAL) == contract["source"]["manual_sha256"], "manual seal")
    ck(sha(DICTIONARY) == contract["source"]["dictionary_sha256"], "dictionary seal")
    ck(sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "CLI seal")
    parent = tables(PARENT_INPUT, "model")
    models, evidence = {}, {}
    for arm, run_id in ARMS.items():
        source, run = CASE / f"native-input-{arm}.json", CASE / "runs" / run_id
        model = tables(source, "model")
        models[arm] = model
        ck(sha(source) == contract["inputs"][arm]["sha256"] == diff["arms"][arm]["input_sha256"],
           f"{arm}: input seal")
        delta = {n: {"before": parent[n], "after": model[n]} for n in parent if parent[n] != model[n]}
        delta.update({n: {"before": None, "after": model[n]} for n in set(model)-set(parent)})
        ck(delta == diff["arms"][arm]["changed"], f"{arm}: exact parent delta")
        ck(set(parent).issubset(model), f"{arm}: parent table topology")
        ck([r["IQTY"] for r in rows(model["OperationProfile"])] == [0, 0, 0],
           f"{arm}: no scheduled mission quantities")
        ck(rows(model["SystemDeployment"])[0]["QTYPS"] == 2, f"{arm}: two mother systems")
        pm = rows(model["MaterielPM"])
        ck(any(r["PMID"] == "LRU-CAL100" and r["MID"] == "TEACH-LRU-01" and
               r["OPID"] == "CALHOURS" and r["PMINT"] == 100 and r["MONIT"] == "Y" for r in pm),
           f"{arm}: monitored item CAL100 PM")
        closure, invocation, steps = (rd(run / n) for n in ("closure.json", "invocation.json", "steps.json"))
        ck(closure["run_id"] == invocation["run_id"] == run_id and closure["arm"] == arm,
           f"{arm}: run identity")
        ck(sha(run / "invocation.json") == closure["invocation_sha256"], f"{arm}: invocation seal")
        ck(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"],
           f"{arm}: source before/after stability")
        pins = {"input": source, "parent": PARENT_INPUT, "parent_closure": PARENT_CLOSURE,
                "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
                "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
                "checker": CASE / "check_roundtrip.py", "runner": CASE / "run_native_ssh.ps1",
                "python": PYTHON, "exe": EXE, "manual": MANUAL, "dictionary": DICTIONARY}
        for key, path in pins.items():
            ck(sha(path) == closure["source_hashes_before"][key], f"{arm}: source pin {key}")
        ck(len(closure["raw"]) == 13 and closure["error"] is None, f"{arm}: 13 raw seals")
        for name, seal in closure["raw"].items():
            path = run / name
            ck(path.exists() and path.stat().st_size == seal["bytes"], f"{arm}: raw size {name}")
            ck(sha(path) == seal["sha256"], f"{arm}: raw SHA {name}")
        ck(sha(run / "input.json") == sha(source), f"{arm}: run input equals frozen source")
        ck(invocation["execution_mode"] == "session0_ssh_cli" and invocation["session_id"] == 0 and
           "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]], f"{arm}: SSH session zero")
        ck(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
           invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
           f"{arm}: mutex and GUI")
        ck(invocation["prelife_log_option_before"] == closure["prelife_log_option_after"] == "NO",
           f"{arm}: registry option restoration recorded")
        ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"],
           f"{arm}: five guarded steps")
        for step in steps:
            ck(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"] is True,
               f"{arm}: step {step['name']}")
        exported = tables(run / "roundtrip-raw.json", "model")
        populated = [n for n,t in model.items() if any(i["rows"] for i in t["instances"])]
        ck(len(populated) == 23, f"{arm}: authored row-containing table count")
        for name in populated:
            ck(name in exported and model[name]["columns"] == exported[name]["columns"] and
               model[name]["instances"] == exported[name]["instances"], f"{arm}: roundtrip {name}")
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
           re.findall(r"\(warning #(\d+)\)", runlog) == ["108"] and "(error #" not in runlog,
           f"{arm}: zero errors/notes, only warning 108")
        ck((run / "model.sxo").stat().st_size > 4, f"{arm}: valid SXO")
        ages = re.findall(r"\*\*(TEACH-AIR-01|POS-A|TEACH-LRU-01)\*\*" \
                          r"(SYS-A|SYS-B|POS-INH-A|POS-INH-B|LRU-A|LRU-B)\*\* Age\[CALHOURS\]:([0-9.]+)",
                          (run / "model_Prelife.log").read_text(encoding="utf-8-sig"))
        leaf_ages = (20, 60) if arm == "age20-then60" else (60, 20)
        expected_ages = [("TEACH-AIR-01", "SYS-A", "60.00"), ("POS-A", "POS-INH-A", "60.00"),
                         ("TEACH-LRU-01", "LRU-A", f"{leaf_ages[0]}.00"),
                         ("TEACH-AIR-01", "SYS-B", "60.00"), ("POS-A", "POS-INH-B", "60.00"),
                         ("TEACH-LRU-01", "LRU-B", f"{leaf_ages[1]}.00")]
        ck(ages == expected_ages, f"{arm}: two separate SYS/POS/LRU age paths")
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        expected = ([(40,1,1,2),(80,0,0,1)] if arm == "age20-then60" else
                    [(40,0,0,2),(80,1,1,0)])
        starts = [(float(h),int(sys)) for h,sys in re.findall(
            r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,(\d+)> PMID: LRU-CAL100",log)]
        ck(starts == [(h,sys) for h,sys,_,_ in expected], f"{arm}: PM mother ID and hour")
        demand = [(float(h),int(item)) for h,item in re.findall(
            r"Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos .*?"
            r"item requiring maintenance is <TEACH-LRU-01,0,(\d+)>", log)]
        ck(demand == [(h,item) for h,_,item,_ in expected], f"{arm}: original physical child item demand")
        spare = [(float(h),int(item)) for h,item in re.findall(
            r"Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,(\d+)> from stock", log)]
        ck(spare == [(h,item) for h,_,_,item in expected], f"{arm}: stock spare issue identity")
        item_starts = [(float(h),int(item)) for h,item in re.findall(
            r"Time: ([0-9.]+)  item PM task \d+ on <TEACH-LRU-01,0,(\d+)> started", log)]
        ck(item_starts == [(h+.25,item) for h,_,item,_ in expected], f"{arm}: item PM starts after transport")
        item_ends = [(float(h),int(item)) for h,item in re.findall(
            r"Time: ([0-9.]+)  item PM task \d+ on <TEACH-LRU-01,0,(\d+)> completed", log)]
        ck(item_ends == [(h+1.25,item) for h,_,item,_ in expected], f"{arm}: item PM completes after one hour")
        stock_returns = [(float(h),int(item)) for h,item in re.findall(
            r"Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock",log)]
        ck(stock_returns == item_ends, f"{arm}: repaired original item returns to stock")
        ck("mission starting" not in log and "mission ordered" not in log and "failure occurs" not in log,
           f"{arm}: no missions or random failures")
        ck("books resources" not in log and "requests resources: no resources needed" in log,
           f"{arm}: no resource booking")
        rep = ledger(arm, run)
        evidence[arm] = {"input_sha256": sha(source), "closure_sha256": sha(run / "closure.json"),
                         "model_log_sha256": sha(run / "model.log"),
                         "prelife_log_sha256": sha(run / "model_Prelife.log"), **rep}
    a,b = models["age20-then60"], models["age60-then20"]
    contrast = {n: {"before": a.get(n), "after": b.get(n)} for n in set(a)|set(b) if a.get(n)!=b.get(n)}
    ck(contrast == diff["arm_contrast"] and set(contrast)=={"PrelifeData","ProblemDescription"},
       "pair differs only in PrelifeData and description")
    ar,br = rows(a["PrelifeData"]), rows(b["PrelifeData"])
    ck(len(ar)==len(br)==6 and all({k:v for k,v in x.items() if k!="AGE"}==
       {k:v for k,v in y.items() if k!="AGE"} for x,y in zip(ar,br)) and
       [i for i,(x,y) in enumerate(zip(ar,br)) if x["AGE"]!=y["AGE"]]==[4,5] and
       (ar[4]["AGE"],ar[5]["AGE"],br[4]["AGE"],br[5]["AGE"])==(20,60,60,20),
       "exact two leaf AGE cells swap")
    ck([(r["PLID"],r["MPLID"],r["MPLIND"]) for r in rows(a["PrelifeStructure"])] ==
       [("PL-POS-A","PL-SYS","SYS-A"),("PL-POS-B","PL-SYS","SYS-B"),
        ("PL-LRU-A","PL-POS-A","POS-INH-A"),("PL-LRU-B","PL-POS-B","POS-INH-B")],
       "two separate mother-to-position-to-leaf paths")
    arun,brun=(CASE/"runs"/ARMS[x] for x in ARMS)
    ra,rb=tables(arun/"report-raw.json","report"),tables(brun/"report-raw.json","report")
    ck({k:v for k,v in ra.items() if k!="ProblemDescription"}==
       {k:v for k,v in rb.items() if k!="ProblemDescription"},
       "aggregate report tables equal except description")
    result={"schema":"simlox-independent-g11-var09/v1","passed":not FAILURES,
            "verdict":"GO: bounded two-mother child-age assignment observation" if not FAILURES else "NO-GO: independent replay failed",
            "checks_passed":COUNT-len(FAILURES),"checks_total":COUNT,"failures":FAILURES,
            "evidence":evidence,
            "finding":"Two distinct system PLIND paths map to separate same-type installed LRU children. Swapping only their leaf ages 20/60 to 60/20 reverses which mother and original physical item enters monitored LRU-CAL100 PM at h40 versus h80. Each item PM lasts one hour, each original item returns to stock, aggregate reports match except description, and two systems are ready at horizon.",
            "limits":["Two same-type mothers, one installed position/item each, one spare, one seed, CALHOURS and first monitored PMs only; no general multi-system mapping law.",
                      "The Prelife Log gives ordered SYS/POS/LRU PLIND paths but no numeric system/item IDs; physical ID association uses native PM/demand events.",
                      "Default reports aggregate across systems and stock; individual item conservation comes from native event text.",
                      "No stocked-item prelife, later PM cycles, other OPIDs, GUI visual, or cross-engine parity.",
                      "Registry restoration is supported by guarded invocation/closure records, not an independent live registry read."]}
    output=CASE/"independent-validation.json"
    output.write_bytes((json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+"\n").encode("utf-8"))
    print(json.dumps({"passed":result["passed"],"checks_total":COUNT,"failures":FAILURES,
                      "verdict":result["verdict"],"output":str(output)},ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__=="__main__":
    raise SystemExit(main())
