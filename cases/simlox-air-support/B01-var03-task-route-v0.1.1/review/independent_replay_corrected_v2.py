"""Independent, read-only replay of sealed B01.var03 v0.1.1 evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / "runs/b01-var03-task-route-v011-ssh-20261006-01"
PARENT = ROOT / "B03-explicit-cold-hot-v1.0.2"
PARENT_RUN = Path(r"C:\Users\user\dev\sim_engine_compiler-b03-v102\cases\simlox-air-support\B03-explicit-cold-hot-v1.0.2\runs\b03-v102-ssh-20260929-02")
OLD = ROOT / "B01-var03-task-route-v0.1.0"
OUT = CASE / "review/independent-verdict-corrected-v2.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_bytes())


def native_json(path: Path):
    """Remove native trailing commas outside quoted strings, in one pass."""
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
        elif ch == '"':
            quoted = True
            out.append(ch)
        elif ch == ",":
            j = i + 1
            while j < len(s) and s[j].isspace():
                j += 1
            if j == len(s) or s[j] not in "]}":
                out.append(ch)
        else:
            out.append(ch)
    return json.loads("".join(out))


def tables(obj, root):
    return {t["name"]: t for t in obj[root]["tables"]}


def cells(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def equal(a, b):
    if isinstance(a, (int, float)) and not isinstance(a, bool) and isinstance(b, (int, float)) and not isinstance(b, bool):
        return abs(a-b) <= 2e-5
    return a == b


def main():
    checks = 0
    failures = []
    def check(condition, label):
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(label)

    contract = load(CASE / "contract.json")
    cc = load(RUN / "closure.json")
    pc = load(PARENT_RUN / "closure.json")
    inv = load(RUN / "invocation.json")
    steps = load(RUN / "steps.json")
    check(sha(CASE / "contract.json") == "c06ef07a090403ca77f04189f49251bffec3c79cff5e77d5ae19cad10df426bc", "contract pin")
    check(sha(CASE / "native-input.json") == contract["source_delta"]["child_input_sha256"], "child source pin")
    check(sha(PARENT / "native-input.json") == contract["accepted_parent"]["input_sha256"], "parent source pin")
    check(sha(PARENT_RUN / "closure.json") == contract["accepted_parent"]["closure_sha256"], "parent closure pin")
    check(sha(RUN / "closure.json") == "d06ece9686a3d088e456885fe1d8e17aa11e099d3f0636520f2b9c1f04d15c75", "child closure pin")
    check(sha(OLD / "contract.json") == cc["source_hashes_before"]["previous_contract"], "excluded contract pin")
    check(sha(OLD / "review/independent-contract-nogo-2026-10-06.md") == cc["source_hashes_before"]["previous_nogo_review"], "excluded NO_GO pin")
    check(not (OLD / "runs").exists() or not any((OLD / "runs").iterdir()), "excluded arm has no native run")
    check(cc["source_hashes_before"] == cc["source_hashes_after"] == inv["source_hashes_before"], "source before/after and invocation equality")
    source_paths = {
        "child_input": CASE / "native-input.json", "child_contract": CASE / "contract.json",
        "contract_review": CASE / "review/independent-contract-go-2026-10-06.md",
        "builder": CASE / "build.py", "parent_diff_checker": CASE / "check_parent_diff.py",
        "roundtrip_checker": CASE / "check_roundtrip.py", "shared_parser": ROOT / "tools/validate_native.py",
        "behavior_validator": CASE / "validate_native_cli.py", "runner_script": CASE / "run_native_ssh.ps1",
        "accepted_input": PARENT / "native-input.json", "accepted_contract": PARENT / "contract.json",
        "accepted_diff": PARENT / "parent-diff.json", "accepted_evidence": PARENT / "evidence-2026-09-29.md",
        "accepted_verdict": PARENT / "review/independent-readonly-2026-09-29.json",
        "accepted_closure": PARENT_RUN / "closure.json",
        "prereq_scope": ROOT / "A02-single-aircraft-repeated-missions/cli-scope-signoff-2026-09-29.md",
        "previous_contract": OLD / "contract.json", "previous_nogo_review": OLD / "review/independent-contract-nogo-2026-10-06.md",
        "prelaunch_approval": CASE / "review/independent-prelaunch-go.json",
        "installed_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "installed_manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "installed_dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    }
    for key, target in sorted(source_paths.items()):
        check(target.is_file() and sha(target) == cc["source_hashes_before"].get(key), "source seal " + key)
    check(sha(RUN / "invocation.json") == cc["invocation_sha256"], "invocation seal")
    for label, folder, closure, expected in (("child", RUN, cc, 12), ("parent", PARENT_RUN, pc, 11)):
        check(len(closure["raw"]) == expected, label + " raw count")
        for name, rec in sorted(closure["raw"].items()):
            path = folder / name
            check(path.is_file() and len(path.read_bytes()) == rec["bytes"] and sha(path) == rec["sha256"], label + " raw " + name)
    check(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"], "SSH0 provenance")
    check(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "mutex provenance")
    check(inv["gui"] == {"pid":13340,"session_id":1,"start_utc":"2026-09-28T10:09:56.8261381Z","start_unix_ms":1790590196826}, "GUI identity")
    check([x["name"] for x in steps] == ["import","export","check_import_export","calc","jsonreport"], "ordered five stages")
    for x in steps:
        check(x["status"] == "completed" and x["exit_code"] == 0 and x["gui_preserved"], "stage " + x["name"])
    check((RUN / "model.sxo").stat().st_size > 4, "usable SXO")
    runlog = (RUN / "run.log").read_text(errors="replace")
    check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog, "converter summary")
    check(set(re.findall(r"warning #(\d+)",runlog)) == {"108","126"}, "converter warning set")
    check("error #" not in runlog.lower(), "no conversion error")
    a, b = (load(PARENT / "native-input.json"), load(CASE / "native-input.json"))
    at, bt = tables(a,"model"), tables(b,"model")
    check(set(at) == set(bt) and len(bt) == 31, "31 source tables")
    changes=[]
    for name in sorted(set(at)&set(bt)):
        x,y=at[name],bt[name]
        check(x["columns"] == y["columns"] and len(x["instances"]) == len(y["instances"]), "source table structure " + name)
        for ii,(xi,yi) in enumerate(zip(x["instances"],y["instances"])):
            check(xi["instance_name"] == yi["instance_name"] and len(xi["rows"]) == len(yi["rows"]), "source instance " + name)
            for ri,(xr,yr) in enumerate(zip(xi["rows"],yi["rows"])):
                for ci,(v,w) in enumerate(zip(xr,yr)):
                    if v != w:
                        changes.append((name,ii,ri,x["columns"][ci]["name"],v,w))
    check(changes == [("OperationProfile",0,0,"SPRID","COLD-FIRST","HOT-SORTIE")], "exact one-cell source delta")
    source = load(RUN / "input.json")
    check(source == b, "run input exact source")
    export=native_json(RUN / "roundtrip-raw.json")
    et=tables(export,"model")
    authored=0
    for name, src in sorted(bt.items()):
        if not any(i["rows"] for i in src["instances"]):
            continue
        authored+=1
        check(name in et and src["columns"] == et[name]["columns"], "roundtrip columns " + name)
        if name not in et:
            continue
        dest=et[name]
        check(len(src["instances"]) == len(dest["instances"]), "roundtrip instances " + name)
        for i,(x,y) in enumerate(zip(src["instances"],dest["instances"])):
            check(x["instance_name"] == y["instance_name"] and x["rows"] == y["rows"], f"roundtrip rows {name}/{i}")
    check(authored == 17, "17 authored row-containing tables")
    log=(RUN / "model.log").read_text(errors="replace")
    plog=(PARENT_RUN / "model.log").read_text(errors="replace")
    check("COLD-FIRST" not in log and "PREP-FIXED" not in log, "no cold route event")
    check("mission ordered: COLD-FIRST" in plog, "parent cold first route")
    for i,(notice,start,finish) in enumerate(((7,8,10),(11,12,14),(15,16,18))):
        ident=f"<HOT-SORTIE,TEACH-UNIT,0,0,{i}>"
        for when,phrase in ((notice,"mission created:"),(notice,"mission allocates system: <TEACH-AIR-01,0>"),(start,"mission starting, duration: 2"),(finish,"mission success:"),(finish,"mission completed: <TEACH-AIR-01,0>")):
            check(f"Time: {when} {ident} {phrase}" in log, f"mission {i} {when} {phrase}")
        check(f"Time: {notice} <TEACH-UNIT> mission ordered: HOT-SORTIE" in log, f"mission {i} order")
        check(f"Time: {notice} <TEACH-AIR-01,0> preparation started, mission: {ident}" in log, f"mission {i} preparation start")
        check(f"Time: {notice}  subtask {i} seqno 1 within system preparation task {i} on <TEACH-AIR-01,0> starts performing, planned to last for 0.166667 hours" in log, f"mission {i} hot subtask")
        check(re.search(rf"Time: {notice}\.166\d+  system preparation task {i} on <TEACH-AIR-01,0> completed",log) is not None, f"mission {i} prep completion")
    check(len(re.findall(r"mission success:",log))==3 and "mission aborted:" not in log and "mission cancelled:" not in log, "three successes no cancellation")
    cr=native_json(RUN / "report-raw.json")
    pr=native_json(PARENT_RUN / "report-raw.json")
    ct,pt=tables(cr,"report"),tables(pr,"report")
    check(set(ct)==set(pt), "report table set")
    check(len(cells(ct["SystemResults"]))==len(cells(pt["SystemResults"]))==72, "72 System rows")
    check(len(cells(ct["SystemResults"]))>0 and len(ct["SystemResults"]["columns"])==40, "40 System fields")
    check(len(cells(ct["StockTotalResults"]))==len(cells(pt["StockTotalResults"]))==72, "72 Stock rows")
    check(len(ct["StockTotalResults"]["columns"])==16, "16 Stock fields")
    intended={(14,"NSYMP"):(1,1/3),(14,"NSYMR"):(0,2/3),(14,"NPSUC"):(0,1),(15,"NPSUC"):(1,0)}
    actual=[]
    for table in sorted(set(ct)&set(pt)):
        x,y=ct[table],pt[table]
        if table=="ProblemDescription":
            check(x==y,"ProblemDescription parity")
            continue
        check([c["name"] for c in x["columns"]]==[c["name"] for c in y["columns"]], "report columns "+table)
        xr,yr=cells(x),cells(y)
        check(len(xr)==len(yr), "report row count "+table)
        for i,(row,oldrow) in enumerate(zip(xr,yr)):
            for j,(v,w) in enumerate(zip(row,oldrow)):
                field=x["columns"][j]["name"]
                if table=="SystemResults" and (i,field) in intended:
                    ov,nv=intended[i,field]
                    check(equal(w,ov) and equal(v,nv), f"declared System {i}/{field}")
                    if not equal(v,w): actual.append((i,field))
                else:
                    check(equal(v,w), f"parity {table}/{i}/{field}")
    check(sorted(actual)==sorted(intended), "exact four System changes")
    sysrows=cells(ct["SystemResults"])
    cols={c["name"]:i for i,c in enumerate(ct["SystemResults"]["columns"])}
    check(all(equal(row[cols["STINT"]],i/2) and equal(row[cols["ETINT"]],(i+1)/2) for i,row in enumerate(sysrows)), "half-hour 36h bins")
    prep=sum((r[cols["NSYMP"]] or 0)*0.5 for r in sysrows)
    flight=sum((r[cols["NSYMO"]] or 0)*0.5 for r in sysrows)
    check(equal(prep,0.5), "event-derived three times 1/6 preparation hours")
    check(equal(flight,6), "three 2h flights")
    check(len(cells(ct["ResultSummary"]))==1 and len(ct["ResultSummary"]["columns"])==11,"11 summary fields")
    result={"schema":"independent-b01-var03-task-route-replay/v1","decision":"GO_BOUNDED" if not failures else "NO_GO","passed":checks-len(failures),"total":checks,"failures":failures,"run_id":RUN.name,"child_closure_sha256":sha(RUN/"closure.json"),"parent_closure_sha256":sha(PARENT_RUN/"closure.json"),"source_delta":changes,"system_changed_cells":actual,"preparation_aircraft_hours":prep,"flight_aircraft_hours":flight,"limits":["One explicit source-selected HOT-SORTIE route on one aircraft, site and seed; no history-driven switching claim.","v0.1.0 was a contract-only NO_GO; no native run was used.","No aircraft-type or station mapping, GUI visual, resource, failure, inventory or general engine claim."]}
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8",newline="\n")
    print(result["decision"],result["passed"],"/",result["total"])
    if failures: print("\n".join(failures[:40]))


if __name__=="__main__":
    main()
