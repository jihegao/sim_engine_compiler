"""Independent read-only replay of A08.var02 aggregate and explicit-seed evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
PARENT = CASE.parent / "A08-var01-fixed-count-random-time-v1.0.0" / "native-input.json"
SOURCE = CASE / "native-input.json"
AGG_ID = "a08-var02-random-count-eq-v100-ssh-20260930-01"
MATRIX_ID = "a08-var02-seed-matrix-v100-ssh-20260930-01"
AGG = CASE / "runs" / AGG_ID
MATRIX = CASE / "runs" / MATRIX_ID
OUT = CASE / "review" / "independent-random-count-2026-09-30.json"
PARENT_SHA = "df7ecf0549fc8b1a506095194b97dac810afc395a76b4c478cfe43eec1838920"
SOURCE_SHA = "54e1fab467ede59829b0c8994aa4d72f1e08878cf7a39532c6fe61364ca87c84"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
START_RE = re.compile(r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission starting, duration: 2 : <TEACH-AIR-01,(\d+)>")
SUCCESS_RE = re.compile(r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission success:")
FINISH_RE = re.compile(r"^Time: ([\d.]+) <BASIC-MISSION,TEACH-UNIT,0,0,(\d+)> mission completed: <TEACH-AIR-01,(\d+)>")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, native: bool = False) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    if native:
        # Native output can include trailing commas. Strip only outside strings.
        out, quoted, escaped = [], False, False
        for i, c in enumerate(raw):
            if quoted:
                out.append(c)
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == '"':
                    quoted = False
            elif c == '"':
                quoted = True
                out.append(c)
            elif c == "," and re.match(r"\s*[}\]]", raw[i + 1:]):
                continue
            else:
                out.append(c)
        raw = "".join(out)
    return json.loads(raw)


def table(doc: dict, root: str, name: str) -> dict:
    found = [x for x in doc[root]["tables"] if x["name"] == name]
    if len(found) != 1:
        raise ValueError((name, len(found)))
    return found[0]


def rows(doc: dict, root: str, name: str) -> list[dict]:
    t = table(doc, root, name)
    keys = [x["name"] for x in t["columns"]]
    return [dict(zip(keys, r)) for inst in t["instances"] for r in inst["rows"]]


def near(a: float, b: float, tolerance: float = 1e-4) -> bool:
    return math.isclose(a, b, abs_tol=tolerance, rel_tol=0)


def event_map(text: str, pattern: re.Pattern) -> dict[int, tuple[float, int | None]]:
    result = {}
    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            ident = int(match.group(2))
            if ident in result:
                raise ValueError((pattern.pattern, ident, "duplicate"))
            result[ident] = (float(match.group(1)),
                int(match.group(3)) if match.lastindex == 3 else None)
    return result


def t_critical_975(df: int) -> float:
    coefficient = math.exp(math.lgamma((df+1)/2) - math.lgamma(df/2))/math.sqrt(df*math.pi)
    def cdf(x: float) -> float:
        n, width = 2048, x/2048
        def density(v: float) -> float:
            return coefficient*(1+v*v/df)**(-(df+1)/2)
        integral = density(0)+density(x)
        integral += 4*sum(density(k*width) for k in range(1,n,2))
        integral += 2*sum(density(k*width) for k in range(2,n,2))
        return .5+integral*width/3
    lo, hi = 0., 4.
    for _ in range(42):
        mid=(lo+hi)/2
        if cdf(mid)<.975: lo=mid
        else: hi=mid
    return (lo+hi)/2


def main() -> None:
    checks = []
    def ck(name: str, actual: object, expected: object) -> None:
        passed=actual==expected
        checks.append({"name":name,"passed":passed,**({} if passed else
            {"actual":repr(actual)[:650],"expected":repr(expected)[:650]})})

    contract=load(CASE/"contract.json")
    matrix_contract=load(CASE/"contract-seed-matrix-v1.json")
    manifest=load(CASE/"seed-matrix-v1.json")
    diff=load(CASE/"exact-diff.json")
    parent,child=load(PARENT),load(SOURCE)
    ck("accepted A08.var01 parent hash",sha(PARENT),PARENT_SHA)
    ck("frozen A08.var02 input hash",sha(SOURCE),SOURCE_SHA)
    ck("installed manual hash",sha(MANUAL),MANUAL_SHA)
    parent_case=CASE.parent/"A08-var01-fixed-count-random-time-v1.0.0"
    ck("accepted parent signoff exists",(parent_case/
       "cli-scope-signoff-2026-09-30.md").is_file(),True)
    ck("parent independent review passed",load(parent_case/"review"/
       "independent-random-time-2026-09-30.json")["passed"],True)
    ck("contract and matrix contract source bindings",(
       contract["parent"]["input_sha256"],contract["native_input_sha256"],
       contract["source"]["manual_pdf_sha256"],matrix_contract["parent_contract_sha256"],
       matrix_contract["aggregate_input_sha256"],matrix_contract["seed_manifest_sha256"],
       matrix_contract["seed_generator_sha256"]),
       (PARENT_SHA,SOURCE_SHA,MANUAL_SHA,sha(CASE/"contract.json"),SOURCE_SHA,
        sha(CASE/"seed-matrix-v1.json"),sha(CASE/"build_seed_matrix.py")))
    ck("matrix acceptance frozen as predeclared candidate",matrix_contract["status"],
       "predeclared_candidate")
    pt={t["name"]:t for t in parent["model"]["tables"]}
    ct={t["name"]:t for t in child["model"]["tables"]}
    changed={n for n in pt if pt[n]!=ct[n]}
    ck("same 31 model table names",(set(pt),len(pt)),(set(ct),31))
    ck("exact three changed tables",changed,{"OperationProfile","ProblemDescription","Unit"})
    ck("28 unchanged tables and schemas",(len(set(pt)-changed),
       all(pt[n]["columns"]==ct[n]["columns"] for n in pt)),(28,True))
    ck("frozen exact-diff matches source",(
       diff["parent_sha256"],diff["child_sha256"],set(diff["changed_tables_only"]),
       diff["unchanged_table_count"],all(diff["changed_tables"][n]==
       {"before":pt[n],"after":ct[n]} for n in changed)),
       (PARENT_SHA,SOURCE_SHA,changed,28,True))
    old_profile,new_profile=rows(parent,"model","OperationProfile"),rows(child,"model","OperationProfile")
    ck("profile only IQTYD and IDISP changed",{k:(v,new_profile[0][k]) for k,v in
       old_profile[0].items() if v!=new_profile[0][k]},
       {"IQTYD":(None,"<POISSON>"),"IDISP":("RANDOM","EQUIDIST")})
    ck("fixed random-count profile fields",(
       len(new_profile),new_profile[0]["STIM"],new_profile[0]["ITYPE"],
       new_profile[0]["IQTY"],new_profile[0]["IPER"],new_profile[0]["DTIM"]),
       (1,8,"RANDOM",3,12,1/3))
    ck("unit/problem label changes only",(
       {k for k,v in rows(parent,"model","Unit")[0].items()
        if v!=rows(child,"model","Unit")[0][k]},
       {k for k,v in rows(parent,"model","ProblemDescription")[0].items()
        if v!=rows(child,"model","ProblemDescription")[0][k]}),
       ({"DESCR"},{"PDESC"}))
    ctl=rows(child,"model","Control")[0]
    ck("32 reps, horizon36, half-hour bins, seed1",(
       ctl["NREPS"],ctl["SIMPE"],ctl["RCEND"],ctl["RCINT"],ctl["RSEED"]),
       (32,36,36,.5,"1"))
    ck("three aircraft and zero failure preserved",(
       rows(child,"model","SystemDeployment")[0]["QTYPS"],
       rows(child,"model","System")[0]["FRT"]),(3,0))

    def guard(inv: dict) -> tuple:
        return (inv["execution_mode"],inv["session_id"],inv["ssh_connection_present"],
           "sshd.exe" in [x.lower() for x in inv["ssh_ancestor_names"]],
           inv["queue_mutex"],inv["gui"]["pid"],inv["gui"]["session_id"],
           bool(inv["gui"]["start_utc"]))
    guard_tail=(0,True,True,"Global\\SimloxIssue18NativeQueue",13340,1,True)
    def conversion(path: Path) -> tuple:
        text=path.read_text(encoding="utf-8-sig",errors="replace")
        return (re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",text),
            sorted(re.findall(r"warning #(\d+)",text)))
    def check_runner(path: Path) -> bool:
        text=path.read_text(encoding="utf-8-sig")
        return all(s in text for s in ("SSH_CONNECTION","sshd.exe","WaitOne(0)",
           "Global\\SimloxIssue18NativeQueue","13340","Assert-Gui"))
    agg_inv,agg_cl,agg_steps=(load(AGG/n) for n in ("invocation.json","closure.json","steps.json"))
    ck("aggregate guard",guard(agg_inv),("ssh_cli_v1",*guard_tail))
    ck("aggregate runner guard text",check_runner(CASE/"run_native_ssh.ps1"),True)
    ck("aggregate invocation/input identity",(
       agg_inv["run_id"],agg_inv["input_sha256"],agg_inv["parent_sha256"],
       sha(AGG/"input.json")),(AGG_ID,SOURCE_SHA,PARENT_SHA,SOURCE_SHA))
    ck("aggregate closure clean/source stable",(
       agg_cl["error"],agg_cl["run_id"],agg_cl["invocation_sha256"],
       agg_cl["source_hashes_before"]==agg_cl["source_hashes_after"],
       agg_inv["source_hashes_before"]==agg_cl["source_hashes_before"]),
       (None,AGG_ID,sha(AGG/"invocation.json"),True,True))
    agg_sources={"input":SOURCE,"parent":PARENT,"contract":CASE/"contract.json",
       "builder":CASE/"build.py","checker":CASE/"check_roundtrip.py",
       "runner_script":CASE/"run_native_ssh.ps1"}
    for name,path in agg_sources.items():
        ck("aggregate source seal "+name,agg_cl["source_hashes_before"][name],sha(path))
    ck("aggregate 12-file raw inventory",(len(agg_cl["raw"]),set(agg_cl["raw"])),
       (12,{p.name for p in AGG.iterdir() if p.is_file()}-{"invocation.json","closure.json"}))
    for name,seal in agg_cl["raw"].items():
        path=AGG/name
        ck("aggregate raw seal "+name,(seal["bytes"],seal["sha256"]),
           (path.stat().st_size,sha(path)))
    ck("aggregate five completed steps",[(x["name"],x["status"],x["exit_code"],
       x["gui_preserved"]) for x in agg_steps],[(n,"completed",0,True) for n in
       ("import","export","calc","jsonreport","check_import_export")])
    ck("aggregate CLI arguments planned",[x["arguments"] for x in agg_steps[:4]],
       [x["arguments"] for x in agg_inv["planned_commands"]])
    aggregate_export=load(AGG/"roundtrip-raw.json",native=True)
    source_tables=[t for t in child["model"]["tables"] if any(i["rows"] for i in t["instances"])]
    ck("13 source row-containing tables",len(source_tables),13)
    ck("aggregate independent source roundtrip",all(
       table(aggregate_export,"model",t["name"])["columns"]==t["columns"] and
       table(aggregate_export,"model",t["name"])["instances"]==t["instances"]
       for t in source_tables),True)
    aggregate_rt=load(AGG/"roundtrip-validation.json")
    ck("aggregate checker artifact agrees",(
       aggregate_rt["passed"],aggregate_rt["differences"],
       aggregate_rt["source_sha256"],aggregate_rt["roundtrip_sha256"]),
       (True,[],SOURCE_SHA,sha(AGG/"roundtrip-raw.json")))
    ck("aggregate conversion/warnings",conversion(AGG/"run.log"),
       ([("0","2","0")],["108","126"]))
    agg_log=(AGG/"model.log").read_text(encoding="utf-8-sig",errors="replace")
    ck("aggregate log exposes one group",(agg_log.count("SIMLOX LOG FILE"),
       len(event_map(agg_log,START_RE))),(1,2))
    aggregate_report=load(AGG/"report-raw.json",native=True)
    agg_sum=rows(aggregate_report,"report","ResultSummary")[0]
    agg_system,agg_stock=(rows(aggregate_report,"report",n) for n in
       ("SystemResults","StockTotalResults"))
    ck("aggregate 32-replication summary",(
       agg_sum["NREP"],agg_sum["RTIUP"],agg_sum["MTMF"],
       agg_sum["MSTF"],agg_sum["MSUF"],agg_sum["STMF"]),
       (32,36,1,1,1,1))
    ck("aggregate 72 half-hour bins",(len(agg_system),len(agg_stock),
       all(r["STINT"]==i/2 and r["ETINT"]==(i+1)/2 for i,r in enumerate(agg_system)),
       all(r["STINT"]==i/2 and r["ETINT"]==(i+1)/2 for i,r in enumerate(agg_stock))),
       (72,72,True,True))
    agg_hours=sum((r["NSYMO"] or 0)*.5 for r in agg_system)
    ck("aggregate mean operation exposure 7 hours",near(agg_hours,7),True)
    ck("aggregate zero fault/stock and terminal ready3",(
       all((r[k] or 0)==0 for r in agg_system for k in ("NFAIL","NREPT","NSYRP")),
       all((r[k] or 0)==0 for r in agg_stock for k in ("NBO","NDF","NDD","NDR","NDP","NWT")),
       agg_system[-1]["NSYRY"],agg_system[-1]["NSYA"]),(True,True,3,3))

    matrix_inv,matrix_cl,matrix_steps=(load(MATRIX/n) for n in
       ("invocation.json","closure.json","steps.json"))
    ck("manifest seed range/input names/source",(
       manifest["parent_input_sha256"],[x["seed"] for x in manifest["seeds"]],
       [x["input_name"] for x in manifest["seeds"]]),
       (SOURCE_SHA,list(range(1,33)),[f"seed-{s:02d}.json" for s in range(1,33)]))
    ck("matrix guard and run identity",(guard(matrix_inv),matrix_inv["run_id"]),
       (("ssh_cli_seed_matrix_v1",*guard_tail),MATRIX_ID))
    ck("matrix runner guard text",check_runner(CASE/"run_native_seed_matrix_ssh.ps1"),True)
    ck("matrix invocation seed list matches manifest",matrix_inv["seeds"],manifest["seeds"])
    ck("matrix closure clean/source stable/160 steps",(
       matrix_cl["error"],matrix_cl["run_id"],matrix_cl["completed_steps"],
       matrix_cl["expected_steps"],matrix_cl["invocation_sha256"],
       matrix_cl["source_hashes_before"]==matrix_cl["source_hashes_after"],
       matrix_inv["source_hashes_before"]==matrix_cl["source_hashes_before"]),
       (None,MATRIX_ID,160,160,sha(MATRIX/"invocation.json"),True,True))
    matrix_sources={"aggregate_input":SOURCE,"seed_manifest":CASE/"seed-matrix-v1.json",
       "initial_contract":CASE/"contract.json",
       "matrix_contract":CASE/"contract-seed-matrix-v1.json",
       "builder":CASE/"build.py","seed_builder":CASE/"build_seed_matrix.py",
       "checker":CASE/"check_roundtrip.py",
       "seed_checker":CASE/"check_seed_roundtrip.py",
       "runner_script":CASE/"run_native_seed_matrix_ssh.ps1"}
    for name,path in matrix_sources.items():
        ck("matrix source seal "+name,matrix_cl["source_hashes_before"][name],sha(path))
    ck("matrix 353-file raw inventory",(len(matrix_cl["raw"]),set(matrix_cl["raw"])),
       (353,{p.relative_to(MATRIX).as_posix() for p in MATRIX.rglob("*") if p.is_file()}
        -{"invocation.json","closure.json"}))
    for name,seal in matrix_cl["raw"].items():
        path=MATRIX/name
        ck("matrix raw seal "+name,(seal["bytes"],seal["sha256"]),
           (path.stat().st_size,sha(path)))
    ck("160 ordered successful steps, GUI preserved",[(x["seed"],x["name"],
       x["status"],x["exit_code"],x["gui_preserved"]) for x in matrix_steps],
       [(s,n,"completed",0,True) for s in range(1,33) for n in
        ("import","export","calc","jsonreport","check_import_export")])

    observations=[]
    max_spacing_error=0.
    max_bin_error=0.
    for entry in manifest["seeds"]:
        seed=entry["seed"]
        input_path=CASE/"seed-inputs"/entry["input_name"]
        run=MATRIX/f"seed-{seed:02d}"
        seed_doc=load(input_path)
        ck(f"seed {seed:02d} frozen source and copied input",(
           sha(input_path),sha(run/"input.json"),
           (run/"input.json").read_bytes()==input_path.read_bytes()),
           (entry["input_sha256"],entry["input_sha256"],True))
        st={t["name"]:t for t in seed_doc["model"]["tables"]}
        ck(f"seed {seed:02d} exact table delta",{n for n in ct if ct[n]!=st[n]},
           {"Control","ProblemDescription"})
        seed_ctl=rows(seed_doc,"model","Control")[0]
        ck(f"seed {seed:02d} exact Control delta",{k:(v,seed_ctl[k]) for k,v in
           ctl.items() if v!=seed_ctl[k]},
           {"NREPS":(32,1),**({} if seed==1 else {"RSEED":("1",str(seed))})})
        ck(f"seed {seed:02d} PDESC label only",{k for k,v in
           rows(child,"model","ProblemDescription")[0].items() if v!=
           rows(seed_doc,"model","ProblemDescription")[0][k]},{"PDESC"})
        native_export=load(run/"roundtrip-raw.json",native=True)
        ck(f"seed {seed:02d} independent 13-table roundtrip",all(
           table(native_export,"model",t["name"])["columns"]==t["columns"] and
           table(native_export,"model",t["name"])["instances"]==t["instances"]
           for t in seed_doc["model"]["tables"] if any(i["rows"] for i in t["instances"])),True)
        rt=load(run/"roundtrip-validation.json")
        ck(f"seed {seed:02d} checker/conversion",(
           rt["passed"],rt["differences"],rt["input_sha256"],rt["roundtrip_sha256"],
           conversion(run/"run.log")),
           (True,[],entry["input_sha256"],sha(run/"roundtrip-raw.json"),
            ([("0","2","0")],["108","126"])))
        log=(run/"model.log").read_text(encoding="utf-8-sig",errors="replace")
        started,success,finished=(event_map(log,p) for p in
           (START_RE,SUCCESS_RE,FINISH_RE))
        count=len(started)
        ordered=sorted((t,ident,aircraft) for ident,(t,aircraft) in started.items())
        times=[x[0] for x in ordered]
        ck(f"seed {seed:02d} event IDs/count consistent",(
           set(started)==set(success)==set(finished),len(success),len(finished)),
           (True,count,count))
        spacing=[8+12*k/count for k in range(count)] if count else []
        errors=[abs(actual-predicted) for actual,predicted in zip(times,spacing)]
        max_spacing_error=max(max_spacing_error,*(errors or [0]))
        ck(f"seed {seed:02d} exact positive-count equidistant layout",
           len(times)==count and all(near(a,b,.001) for a,b in zip(times,spacing)) and
           all(8<=t<20 for t in times),True)
        ck(f"seed {seed:02d} success/completion 2h after starts",all(
           ident in success and ident in finished and
           near(success[ident][0]-t,2,.001) and
           near(finished[ident][0]-t,2,.001) and
           finished[ident][1]==aircraft for t,ident,aircraft in ordered),True)
        ck(f"seed {seed:02d} no shortage/cancellation/failure/repair/backorder",all(
           word not in log.lower() for word in
           ("mission waiting","mission cancelled","mission aborted",
            "critical random failure added","direct repair subtask","backorder")),True)
        report=load(run/"report-raw.json",native=True)
        summary=rows(report,"report","ResultSummary")[0]
        system,stock=(rows(report,"report",n) for n in
           ("SystemResults","StockTotalResults"))
        ck(f"seed {seed:02d} NREP1 and 72 aligned bins",(
           summary["NREP"],summary["RTIUP"],len(system),len(stock),
           all(r["STINT"]==i/2 and r["ETINT"]==(i+1)/2 for i,r in enumerate(system)),
           all(r["STINT"]==i/2 and r["ETINT"]==(i+1)/2 for i,r in enumerate(stock))),
           (1,36,72,72,True,True))
        if count:
            ck(f"seed {seed:02d} successful positive-count summary",(
               summary["MTMF"],summary["MSTF"],summary["MSUF"],summary["STMF"]),
               (1,1,1,1))
        hours=sum((r["NSYMO"] or 0)*.5 for r in system)
        ck(f"seed {seed:02d} operation exposure equals 2h times count",near(hours,2*count,.001),True)
        ck(f"seed {seed:02d} terminal three ready",(
           system[-1]["NSYRY"],system[-1]["NSYA"],system[-1]["NSYMO"]),(3,3,0))
        ck(f"seed {seed:02d} zero fault/stock report ledger",(
           all((r[k] or 0)==0 for r in system for k in ("NFAIL","NREPT","NSYRP")),
           all((r[k] or 0)==0 for r in stock for k in
               ("NBO","NDF","NDD","NDR","NDP","NWT"))),(True,True))
        errors=[]
        for row in system:
            lo,hi=row["STINT"],row["ETINT"]
            predicted=sum(max(0.,min(hi,t+2)-max(lo,t))/.5 for t in times)
            errors.append(abs((row["NSYMO"] or 0)-predicted))
        max_bin_error=max(max_bin_error,*(errors or [0]))
        ck(f"seed {seed:02d} every operating bin matches events",max(errors or [0])<.001,True)
        observations.append({"seed":seed,"count":count,"start_hours":times,
            "operating_aircraft_hours":hours,"model_log_sha256":sha(run/"model.log"),
            "report_raw_sha256":sha(run/"report-raw.json")})

    ck("aggregate exposed log equals seed-1 log",(AGG/"model.log").read_bytes(),
       (MATRIX/"seed-01"/"model.log").read_bytes())
    counts=[x["count"] for x in observations]
    ck("32 observed counts and at least two distinct",(len(counts),len(set(counts))>1),
       (32,True))
    mean,variance=statistics.mean(counts),statistics.variance(counts)
    tcrit=t_critical_975(31)
    half=tcrit*math.sqrt(variance/32)
    ck("Student-t df31 critical independently calculated",near(tcrit,2.039513446,.00001),True)
    ck("nominal count-mean half-width at most one",half<=1,True)

    passed=all(c["passed"] for c in checks)
    result={"schema":"simlox-a08-var02-independent-readonly/v1",
       "reviewer":"Standalone standard-library read-only replay; no author validator import or native invocation",
       "passed":passed,"passed_count":sum(c["passed"] for c in checks),
       "failed_count":sum(not c["passed"] for c in checks),
       "failed":[c for c in checks if not c["passed"]],"checks":checks,
       "hashes":{"parent_input":sha(PARENT),"child_input":sha(SOURCE),
          "aggregate_invocation":sha(AGG/"invocation.json"),
          "aggregate_closure":sha(AGG/"closure.json"),
          "aggregate_model_log":sha(AGG/"model.log"),
          "aggregate_report_raw":sha(AGG/"report-raw.json"),
          "matrix_manifest":sha(CASE/"seed-matrix-v1.json"),
          "matrix_invocation":sha(MATRIX/"invocation.json"),
          "matrix_closure":sha(MATRIX/"closure.json"),
          "matrix_steps":sha(MATRIX/"steps.json")},
       "observed":{"aggregate_NREP":agg_sum["NREP"],
          "aggregate_event_groups_exposed":agg_log.count("SIMLOX LOG FILE"),
          "aggregate_average_operating_aircraft_hours":agg_hours,
          "matrix_completed_steps_including_checkers":len(matrix_steps),
          "counts_by_seed":observations,"count_mean":mean,
          "count_sample_variance":variance,"student_t_critical_df31":tcrit,
          "nominal_95_percent_count_mean_half_width":half,
          "minimum_count":min(counts),"maximum_count":max(counts),
          "zero_count_seeds":sum(x==0 for x in counts),
          "maximum_printed_spacing_error_hours":max_spacing_error,
          "maximum_event_to_bin_count_error":max_bin_error},
       "decision":"bounded_random_count_equidistant_accepted" if passed else
          "review_rejected_pending_resolution",
       "limits":[
          "The 32-replication aggregate log exposes one replication. The 32 explicit seeds give separately observed runs, not the aggregate run's hidden replication counts.",
          "The explicit-seed mean count differs from the aggregate's implied mean; they are different random-stream experiments and are not forced to agree.",
          "No zero-count seed occurred (minimum one), so the native zero-count branch is unobserved even though the frozen acceptance specified how to evaluate it.",
          "The nominal Student-t interval describes this fixed convenience matrix conditional on assumptions; it does not establish a Poisson law or independent streams.",
          "Report-bin checks use event-log times at printed precision; other distributions, periods, GUI visual behavior and cross-engine equivalence remain untested."],
       "publication_state":"independent_review_only"}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))
    print(json.dumps({"passed":passed,"passed_count":result["passed_count"],
       "failed":result["failed"],"output":str(OUT)}))


if __name__=="__main__":
    main()
