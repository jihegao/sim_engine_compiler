"""Independent I03.var08 prospective reader. PURE fixtures never signify native acceptance."""
import argparse
import copy
import datetime
import hashlib
import json
import math
import os
import re
import struct
import subprocess
from pathlib import Path

def repo_root():
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "AGENTS.md").is_file() and (candidate / "cases/simlox-air-support/publication-index-v1.json").is_file():
            return candidate
    raise AssertionError("repository root with AGENTS and catalog not found")


ROOT = repo_root()
PKG = ROOT / "cases/simlox-air-support/I03-var08-idle-at-maxut-out-v1.0.0"
PARENT = ROOT / "cases/simlox-air-support/C08-exact-limit-v1.0.0"
ACCEPTED = PARENT / "runs/c08-exact-limit-20260930-02"
CONTRACT = PKG / "contract.json"
CONTRACT_SHA = "f23c6284afdaf25c7115f293907411ab941c0603b11d8bbf45d7fd8a5e671b41"
GIT = r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe"
RUN_ID = "i03-var08-idle-maxut-out-v100-ssh-20261008-01"


def sha(b): return hashlib.sha256(b).hexdigest()


def unique_pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out: raise AssertionError(f"duplicate JSON key: {k}")
        out[k] = v
    return out


def parse_json(b, native=False):
    s = b.decode("utf-8-sig")
    assert "\r" not in s.replace("\r\n", ""), "bare CR"
    s=s.replace("\r\n", "\n")
    def bad_constant(v): raise AssertionError(f"nonfinite literal {v}")
    try:
        out = json.loads(s, object_pairs_hook=unique_pairs, parse_constant=bad_constant)
    except json.JSONDecodeError:
        # Accepted SIMLOX report exporter has exactly one final table-array
        # trailing comma. No general JSON5/trailing-comma normalization.
        marker=",\n      ]"
        assert native and s.count(marker)==1 and s.endswith("         },\n      ]\n   }\n}\n")
        out=json.loads(s.replace(marker,"\n      ]",1),object_pairs_hook=unique_pairs,parse_constant=bad_constant)
    def finite(x):
        if isinstance(x, float): assert math.isfinite(x), "nonfinite overflow"
        elif isinstance(x, dict):
            for y in x.values(): finite(y)
        elif isinstance(x, list):
            for y in x: finite(y)
    finite(out)
    return out


def typed(a, b):
    if type(a) is not type(b): return False
    if isinstance(a, dict): return a.keys() == b.keys() and all(typed(a[k], b[k]) for k in a)
    if isinstance(a, list): return len(a) == len(b) and all(typed(x, y) for x, y in zip(a, b))
    return a == b


def number(a, b):
    return type(a) in (int, float) and type(b) in (int, float) and math.isfinite(a) and math.isfinite(b) and a == b


def f32(x): return struct.unpack("<f", struct.pack("<f", x))[0]


def pinned(path, spec):
    b = Path(path).read_bytes()
    assert len(b) == spec["bytes"] and sha(b) == spec["sha256"], path
    return b


def validate_catalog_prefix(old, live):
    assert old.keys()==live.keys()=={"schema","as_of","catalog_snapshot","entry_publication_state","meaning","entries"}
    for k in old:
        if k!="entries":assert typed(old[k],live[k]),k
    assert len(old["entries"])==495 and len(live["entries"])>=495
    assert typed(live["entries"][:495],old["entries"])
    ids=[e["publication_id"] for e in live["entries"]]
    assert all(type(x) is str and x for x in ids) and len(ids)==len(set(ids))
    return 495


def custody(c):
    l = c["lineage"]
    assert len(l["accepted_81_local_and_base_git_refs"]) == 81
    assert len(l["mandatory_108_original_raw"]) == 108
    tree_raw=subprocess.run([GIT,"ls-tree","-rz",l["base_commit"]],cwd=ROOT,capture_output=True,check=True).stdout
    tree={}
    for record in tree_raw.split(b"\0"):
        if not record:continue
        head,path=record.split(b"\t",1)
        mode,kind,oid=head.decode("ascii").split(" ")
        assert kind=="blob" and mode in ("100644","100755","120000")
        key=path.decode("utf-8")
        assert key not in tree
        tree[key]=oid
    for r in l["accepted_81_local_and_base_git_refs"]:
        assert tree[r["path"]]==r["oid"]
        a = pinned(ROOT / r["path"], r["disk"])
        p = subprocess.run([GIT, "cat-file", "blob", r["oid"]], cwd=ROOT, capture_output=True, check=True)
        b = p.stdout
        assert len(b) == r["git"]["bytes"] and sha(b) == r["git"]["sha256"]
        assert (a == b) is r["byte_equal"]
    for r in l["mandatory_108_original_raw"]: pinned(r["path"], r)
    for k, r in l["required_docs_8"].items(): pinned(ROOT / k, r)
    for r in l["installed_exe_manual_dictionary_3"].values(): pinned(r["path"], r)
    pinned(l["selection_v2"]["path"], l["selection_v2"])
    pinned(l["parent"]["source"]["path"], l["parent"]["source"])
    pinned(l["parent"]["report_raw"]["path"], l["parent"]["report_raw"])
    pinned(l["parent"]["evidence_index"]["path"], l["parent"]["evidence_index"])
    context=parse_json((PKG/"context-custody.json").read_bytes())
    assert context.keys()=={"schema","records","accepted_original_raw_are_not_replaced_by_copies"}
    assert context["schema"]=="i03-var08-context-custody/v1"
    assert context["accepted_original_raw_are_not_replaced_by_copies"] is True
    assert len(context["records"])==19
    for j,r in enumerate(context["records"]):
        assert r.keys()=={"original_path","owned_copy","bytes","sha256","original_if_present_must_match"}
        assert r["owned_copy"]==f"preserved-context/context-{j:02d}.bytes"
        pinned(PKG/r["owned_copy"],r)
        if r["original_if_present_must_match"]:
            original=ROOT/r["original_path"]
            if original.exists():pinned(original,r)
    local_archive=pinned(PKG/"preserved-context/context-17.bytes",l["catalog_local_495"])
    git_archive=pinned(PKG/"preserved-context/context-18.bytes",l["catalog_git_495"])
    g=subprocess.run([GIT,"cat-file","blob",l["catalog_git_495"]["oid"]],cwd=ROOT,capture_output=True,check=True)
    assert git_archive==g.stdout
    old=parse_json(local_archive)
    live=parse_json((ROOT/"cases/simlox-air-support/publication-index-v1.json").read_bytes())
    validate_catalog_prefix(old,live)
    pure_map=parse_json((PKG/"pure-proof-custody.json").read_bytes())
    assert set(pure_map)=={"schema","records","original_receipt_sha256"}
    assert pure_map["schema"]=="i03-var08-local-pure-proof-custody/v1"
    assert len(pure_map["records"])==13
    assert pure_map["original_receipt_sha256"]==pure_map["records"][-1]["sha256"]
    for j,r in enumerate(pure_map["records"]):
        assert set(r)=={"original_path","owned_copy","bytes","sha256",
                       "original_if_present_must_match"}
        assert r["owned_copy"]==f"preserved-pure-proof/pure-{j:02d}.bytes"
        assert type(r["original_if_present_must_match"]) is bool and r["original_if_present_must_match"]
        pinned(PKG/r["owned_copy"],r)
        original=Path(r["original_path"])
        if original.exists():pinned(original,r)
    return 81 + 108 + 8 + 3 + 19 + 13


def expected_source(c):
    parent = parse_json((PARENT / "exact-limit-input.json").read_bytes())
    assert list(parent) == ["model"] and len(parent["model"]["tables"]) == 35
    x = copy.deepcopy(parent)
    tables = x["model"]["tables"]
    assert [t["name"] for t in tables][22:24] == ["ResourceAllocation", "MaterielPM"]
    pd = tables[0]
    assert pd["name"] == "ProblemDescription" and pd["instances"][0]["rows"] == [[c["source_delta"]["old_pdesc"]]]
    pd["instances"][0]["rows"] = [[c["source_delta"]["new_pdesc"]]]
    rt = c["source_delta"]
    assert rt["insert_at_zero_based_index"] == 23 and rt["insert_table"] == "ResourceTransfer"
    new = {"name": "ResourceTransfer", "columns": rt["columns"], "instances": [{"instance_name": "", "rows": [rt["one_row"]]}]}
    tables.insert(23, new)
    assert len(tables) == 36 and len({t["name"] for t in tables}) == 36
    rows = sum(len(i["rows"]) for t in tables for i in t["instances"])
    cells = sum(len(r) for t in tables for i in t["instances"] for r in i["rows"])
    assert (rows, cells) == (28, 242)
    return x


def verify_source(c, actual):
    expected = expected_source(c)
    assert typed(actual, expected), "child source, table order, metadata or two-cell delta"
    return 242


def verify_export(source, export):
    assert source.keys() == export.keys() == {"model"}
    a, b = source["model"], export["model"]
    assert a.keys() == b.keys() == {"database_version", "tables"}
    assert typed(a["database_version"], b["database_version"])
    at, bt = a["tables"], b["tables"]
    assert len(at) == len(bt) == 36
    placeholders = 0; rows = 0; cells = 0
    for t, e in zip(at, bt):
        assert t.keys() == e.keys() == {"name", "columns", "instances"}
        assert typed(t["name"], e["name"]) and typed(t["columns"], e["columns"])
        assert len(t["instances"]) == len(e["instances"]) == 1
        ti, ei = t["instances"][0], e["instances"][0]
        assert ti.keys() == ei.keys() == {"instance_name", "rows"}
        assert typed(ti["instance_name"], ei["instance_name"])
        original, exported = ti["rows"], ei["rows"]
        if not original:
            placeholders += 1
            assert exported == [[None] * len(t["columns"])]
        else:
            assert len(original) == len(exported)
            for sr, er in zip(original, exported):
                assert len(sr) == len(er) == len(t["columns"])
                for sv, ev, col in zip(sr, er, t["columns"]):
                    if col["datatype"] == "double" and sv is not None:
                        assert number(sv, ev)
                    else:
                        assert typed(sv, ev)
        rows += len(exported)
        cells += sum(len(r) for r in exported)
    assert (placeholders, rows, cells) == (11, 39, 383)
    return cells


def transfer_lines(task_id):
    assert type(task_id) is int and task_id >= 0
    return [
        f"Time: 24.75  resource transfer task {task_id} (OUT)  created: starting from  <P-CREW at <BASE-01,0>>",
        "Time: 24.75  <P-CREW at <BASE-01,0>> Resource transfer demand arrives from OUT-transfer ",
        f"Time: 24.75  resource transfer task {task_id} (OUT)  starts with 1 resources, transfer time: 0",
        f"Time: 24.75  resource transfer task {task_id} (OUT)  arrives with 1 resources",
    ]


TRANSFER_LINES = transfer_lines(0)  # PURE fixture only; actual task ID is bound below.


def expected_log(task_id=0):
    parent = (ACCEPTED / "model.log").read_text(encoding="utf-8-sig").splitlines()
    assert len(parent) == 171 and parent[:2] == ["SIMLOX LOG FILE", "36"]
    assert not any("resource transfer task" in s for s in parent)
    loc = next(i for i, s in enumerate(parent) if s.startswith("Time: 25  resource shift 2 created"))
    child = parent[:loc] + transfer_lines(task_id) + parent[loc:]
    before = "  Free resources at: <BASE-01,0> P-CREW 2"
    after = "  Free resources at: <BASE-01,0> P-CREW 1"
    shift = next(i for i, s in enumerate(child) if s.startswith("Time: 26  resource shift 3 starting"))
    assert child[shift + 1] == before
    child[shift + 1] = after
    return child


def verify_log(actual):
    # Whole ordered typed/untimed ledger: every diagnostic is source-bound to the
    # accepted parent, and the one transfer uses the accepted I03 OUT grammar.
    got = actual.decode("utf-8-sig").splitlines()
    matches=[re.fullmatch(r"Time: 24\.75  resource transfer task (0|[1-9][0-9]*) \(OUT\)  created: starting from  <P-CREW at <BASE-01,0>>",s) for s in got]
    ids=[int(m.group(1)) for m in matches if m]
    assert len(ids)==1, ids
    task_id=ids[0]
    want = expected_log(task_id)
    assert len(got) == len(want) == 175
    assert got == want, next(((i, a, b) for i, (a, b) in enumerate(zip(got, want)) if a != b), None)
    assert not any("backorder" in s.lower() for s in got)
    events=[]
    for s in got[2:]:
        if s.startswith("Time: "):
            m=re.match(r"^Time: (\d+(?:\.\d+)?)\b",s)
            assert m, s
            events.append((float(m.group(1)),s))
    assert events == sorted(events,key=lambda x:x[0])
    assert [t for t,s in events if "resource transfer task" in s] == [24.75,24.75,24.75]
    assert [t for t,s in events if "Resource transfer demand arrives" in s] == [24.75]
    # Task-linked conservation: two preparation allocations/releases, then
    # scheduled nominal decrement, one departure, completion marker without a
    # second local decrement. Shift presentation is a separate clock.
    nominal = 2; local = 2; booked = 0; reserved = 0; departed = 0
    requested = 0; started = 0; arrived = 0; backorder = 0; ready = 0
    for t,s in events:
        if "nbr ready increased at unit:" in s:
            assert t in (0,29)
            ready += 1
            assert ready <= 2
        elif "nbr ready decreased at unit:" in s:
            assert t == 23.5 and ready > 0
            ready -= 1
        elif "allocated to maintenance task: 1  available now:" in s:
            assert t == 23.5 and booked < 2
            booked += 1
            assert int(s.rsplit("available now:", 1)[1].strip()) == local-booked
        elif "deallocated from  maintenance task: 1  available now:" in s:
            assert t == 24.5 and booked > 0
            booked -= 1
            assert int(s.rsplit("available now:", 1)[1].strip()) == local-booked
        elif f"resource transfer task {task_id} (OUT)  created" in s:
            assert (t,nominal,local,booked,reserved)==(24.75,2,2,0,0)
            nominal-=1
        elif "Resource transfer demand arrives from OUT-transfer" in s:
            assert (t,local,booked,reserved)==(24.75,2,0,0)
            requested += 1; reserved=1
        elif f"resource transfer task {task_id} (OUT)  starts with 1 resources" in s:
            assert (t,local,reserved)==(24.75,2,1)
            local-=1;reserved=0;departed+=1;started+=1
        elif f"resource transfer task {task_id} (OUT)  arrives with 1 resources" in s:
            assert (t,local,departed,requested-arrived)==(24.75,1,1,1)
            arrived+=1
    assert (nominal,local,booked,reserved,departed,requested,started,arrived,backorder,ready)==(1,1,0,0,1,1,1,1,0,2)
    assert requested-arrived == 0
    shifts=[]
    for i,s in enumerate(got[:-1]):
        if "resource shift " in s and " starting at <P-CREW" in s:
            m=re.match(r"^Time: (\d+(?:\.\d+)?)",s);assert m
            q=re.fullmatch(r"  Free resources at: <BASE-01,0> P-CREW (\d+)",got[i+1]);assert q
            shifts.append((float(m.group(1)),int(q.group(1))))
    assert shifts==[(0.0,0),(23.0,2),(25.0,0),(26.0,1),(28.0,0)]
    return len(events)


def expected_report(c, child=True):
    spec=c["report"]
    parent=parse_json((ACCEPTED/"report-raw.json").read_bytes(), native=True)["report"]
    tables=parent["tables"]
    assert [t["name"] for t in tables]==spec["table_order"]
    out=copy.deepcopy(parent)
    checks=0; diffs=0
    for t in out["tables"]:
        name=t["name"]
        meta=spec["metadata"][name]
        assert typed(t["columns"],meta["columns"])
        assert [i["instance_name"] for i in t["instances"]]==meta["instances"]
        assert len(t["instances"])==1
        rows=t["instances"][0]["rows"]
        assert len(rows)==meta["rows"]
        cols=[x["name"] for x in t["columns"]]
        newrows=[]
        for j,row in enumerate(rows):
            st=j/2;en=(j+1)/2
            if name=="ProblemDescription":
                old={"PDESC":c["source_delta"]["old_pdesc"]}; new={"PDESC":c["source_delta"]["new_pdesc"]}
            elif name=="ResultSummary":
                old=spec["summary"];new=old.copy()
            elif name=="SystemResults":
                old={k:0 for k in cols};old.update({"UNID":"Total over all Units","SID":"Total over all Systems","STINT":st,"ETINT":en,"SYDT":None})
                old.update({"NSYRY":0 if 23.5<=st<29 else 2,"NSYMA":2 if 23.5<=st<29 else 0,
                            "NSYMO":2 if 28<=st<29 else 0,"NSYMP":2 if 23.5<=st<24.5 else 0,
                            "NSYMR":2 if 24.5<=st<28 else 0,"NSYA":2,"FTMO":1 if 28<=st<29 else 0,
                            "STACC":2 if 28<=st<29 else 0,"NPSTA":2 if st==23.5 else 0,
                            "NPSUC":2 if st==24.5 else 0})
                new=old.copy()
            elif name=="StockTotalResults":
                old={k:0 for k in cols};old.update({"STINT":st,"ETINT":en,"PNB":1})
                for k in spec["stock"]["undefined_null"]:old[k]=None
                new=old.copy()
            elif name=="ResourceResults":
                old={k:0 for k in cols};old.update({"RID":"Total over all Resources","STID":"Total over all Stations","STINT":st,"ETINT":en,"NR":2,"NRN":2,
                     "NRA":2 if (23<=st<25 or 26<=st<28) else 0,"NRUM":2 if 23.5<=st<24.5 else 0})
                new=old.copy()
                new["NR"]=new["NRN"]=(2 if en<=24.5 else 1.5 if st==24.5 else 1)
                new["NRA"]=(2 if 23<=st<24.5 else 1.5 if st==24.5 else 1 if 26<=st<28 else 0)
            elif name=="ResourceResultsTotal":
                old={k:0 for k in cols};old.update({"RID":"Total over all Resources","STID":"Total over all Stations","NR":2,"NRN":2,"NRA":f32(8/36),"NRUM":f32(2/36)})
                new=old.copy();new.update({"NR":f32(60.75/36),"NRN":f32(60.75/36),"NRA":f32(5.75/36)})
            else: raise AssertionError(name)
            assert set(cols)==set(old)==set(new)
            assert len(row)==len(cols)
            for k,v in zip(cols,row):
                if type(old[k]) in (int,float):assert number(v,old[k]),(name,j,k,v,old[k])
                else: assert typed(v,old[k]),(name,j,k,v,old[k])
            checks+=len(row)
            diffs+=sum(old[k]!=new[k] for k in cols)
            newrows.append([new[k] if child else old[k] for k in cols])
        t["instances"][0]["rows"]=newrows
    assert checks==5210 and diffs==55
    by_name={t["name"]:t for t in out["tables"]}
    interval=by_name["ResourceResults"]
    total=by_name["ResourceResultsTotal"]
    icols=[z["name"] for z in interval["columns"]]
    tcols=[z["name"] for z in total["columns"]]
    ir=interval["instances"][0]["rows"]
    tr=total["instances"][0]["rows"][0]
    for field in ("NR", "NRA", "NRN", "NRUM", "NRW"):
        integral=sum(row[icols.index(field)]*0.5 for row in ir)
        contract_integral=spec["resource"]["child_integrals" if child else "parent_integrals"][field]
        assert integral==contract_integral,(field,integral,contract_integral)
        assert f32(integral/36)==tr[tcols.index(field)]
    return out


def verify_report(c, actual):
    expect=expected_report(c,True)
    assert actual.keys() == {"report"} and actual["report"].keys() == {"tables"}
    a,b=actual["report"]["tables"],expect["tables"]
    assert len(a)==len(b)==6
    checks=0
    for t,e in zip(a,b):
        assert t.keys() == e.keys() == {"name", "columns", "instances"}
        assert typed(t["name"],e["name"]) and typed(t["columns"],e["columns"])
        assert len(t["instances"])==len(e["instances"])==1
        ti,ei=t["instances"][0],e["instances"][0]
        assert ti.keys() == ei.keys() == {"instance_name", "rows"}
        assert typed(ti["instance_name"],ei["instance_name"])
        assert len(ti["rows"])==len(ei["rows"])
        for row,er in zip(ti["rows"],ei["rows"]):
            assert len(row)==len(er)==len(t["columns"])
            for val,ex,col in zip(row,er,t["columns"]):
                if col["datatype"]=="double" and ex is not None:
                    assert number(val,ex),(t["name"],col["name"],val,ex)
                else: assert typed(val,ex),(t["name"],col["name"],val,ex)
                checks+=1
    assert checks==5210
    return checks


def pure(c):
    src=expected_source(c)
    assert verify_source(c,src)==242
    rt=copy.deepcopy(src)
    for t in rt["model"]["tables"]:
        if not t["instances"][0]["rows"]:
            t["instances"][0]["rows"]=[[None]*len(t["columns"])]
        for row in t["instances"][0]["rows"]:
            for j,col in enumerate(t["columns"]):
                if col["datatype"]=="double" and type(row[j]) is float and row[j].is_integer():row[j]=int(row[j])
    assert verify_export(src,rt)==383
    log=("\n".join(expected_log())+"\n").encode()
    events=verify_log(log)
    report=expected_report(c,True)
    cells=verify_report(c,{"report":report})
    return {"mode":"PURE_SYNTHETIC_NOT_NATIVE","source_cells":242,"export_cells":383,"timed_events":events,"report_cells":cells}


RUN_FILES = {
    "input.json", "model.sxi", "import.log", "roundtrip-raw.json",
    "export.log", "roundtrip-validation.json", "model.sxo", "model.log",
    "model-run.log", "report-raw.json", "report-export.log",
    "author-validation.json", "steps.json", "invocation.json", "closure.json",
} | {f"{n}-stderr.txt" for n in (
    "import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"
)} | {f"{n}-stdout.txt" for n in ("import", "export", "calc", "jsonreport")}
PYTHON = r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
EXE = r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"
WORKSPACE = r"C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace"
CATALOG = ROOT / "cases/simlox-air-support/publication-index-v1.json"
PROOF_TOOLS = ("build.py", "copy_context.py", "source_gate.py",
               "self_check.py", "make_prelaunch_manifest.py")
CORE_OWNED = {
    ".gitattributes",".gitignore","contract.json","DEVELOPMENT-CONTRACT.md",
    "execution-contract.json","README.md","REPRODUCTION.md","build.py",
    "native-input.json","exact-diff.json","check_roundtrip.py","event_ledger.py",
    "report_oracle.py","validate_native_cli.py","source_gate.py","self_check.py",
    "copy_context.py","context-custody.json","copy_pure_proof.py",
    "pure-proof-custody.json","captured_process.ps1",
    "checker_receipt.ps1","preflight_receipt.ps1","run_native_ssh.ps1",
    "ssh_transport.py","pure_proof.py","make_source_inventory.py","make_prelaunch_manifest.py",
    "review/independent_replay.py","review/independent_self_check.py",
} | {f"preserved-context/context-{i:02d}.bytes" for i in range(19)} | {
    f"preserved-pure-proof/pure-{i:02d}.bytes" for i in range(13)} | {
    "preserved-development/checker_receipt.ps1.var05-template.bytes",
    "preserved-development/copy-context-v1-original-required-draft.py.bytes",
    "preserved-development/event-ledger-v1-incomplete-terminal.py.bytes",
    "preserved-development/event-ledger-v1-terminal-gap.md",
    "preserved-development/preflight_receipt.ps1.var05-template.bytes",
    "preserved-development/report-oracle-v1-parse-failure.md",
    "preserved-development/report-oracle-v1-trailing-comma-draft.py.bytes",
    "preserved-development/report-oracle-v2-suffix-draft.py.bytes",
    "preserved-development/report-oracle-v2-suffix-failure.md",
    "preserved-development/report-oracle-v3-total-constant-draft.py.bytes",
    "preserved-development/report-oracle-v3-total-constant-gap.md",
    "preserved-development/run_native_ssh.ps1.var05-template.bytes",
    "preserved-development/run-native-v1-pure-proof-not-durable.ps1.bytes",
    "preserved-development/run-native-v1-pure-proof-gap.md",
    "preserved-development/ssh_transport.py.var05-template.bytes",
    "review/preserved-reviewer-v1-fixedid.py.bytes",
    "review/preserved-reviewer-v2-broad-comma.py.bytes",
    "review/preserved-reviewer-v3-gittree-mode.py.bytes",
    "review/preserved-reviewer-v4-preprovenance.py.bytes",
    "review/preserved-reviewer-v5-first-provenance.py.bytes",
    "review/preserved-reviewer-v6-subset-owned.py.bytes",
    "review/preserved-reviewer-custody-map-shape-failure.md",
    "review/independent-method-static-go-2026-10-08.md",
}


def require_core_owned(relative_paths):
    assert type(relative_paths) is set and relative_paths==CORE_OWNED,(
        "missing",CORE_OWNED-relative_paths,"unexpected",relative_paths-CORE_OWNED)


def verify_gui(actual):
    assert typed(actual,{"pid":13340,"session_id":1,
                         "start_unix_ms":1790590196826,"responding":True})


def file_record(path):
    b = Path(path).read_bytes()
    return {"bytes":len(b),"sha256":sha(b)}


def utc(value):
    assert type(value) is str and value
    value = value.replace("Z","+00:00")
    result = datetime.datetime.fromisoformat(value)
    assert result.tzinfo is not None and result.utcoffset()==datetime.timedelta(0)
    return result


def assert_int(value, expected=None):
    assert type(value) is int and (expected is None or value==expected),(value,expected)


def source_map_sha(source_map):
    return sha(json.dumps(source_map,ensure_ascii=False,separators=(",",":")).encode("utf-8"))


def verify_manifest():
    path=PKG/"prelaunch-manifest.json"
    raw=path.read_bytes();d=parse_json(raw)
    assert set(d)=={
        "schema","run_id","contract_sha256","execution_binding_sha256",
        "source_count","source_files","live_catalog_prelaunch_pin",
        "historical_catalog_prefix_always_checked","accepted_raw_records",
        "accepted_nonclosure_raw","accepted_closure_records",
        "accepted_invocation_records","accepted_source_git_pairs",
        "new_native_runs_authorized_by_manifest","independent_method_state"}
    assert d["schema"]=="i03-var08-idle-maxut-prelaunch-manifest/v1"
    assert d["run_id"]==RUN_ID and d["contract_sha256"]==CONTRACT_SHA
    assert_int(d["historical_catalog_prefix_always_checked"],495)
    assert_int(d["accepted_raw_records"],108)
    assert_int(d["accepted_nonclosure_raw"],93)
    assert_int(d["accepted_closure_records"],8)
    assert_int(d["accepted_invocation_records"],7)
    assert_int(d["accepted_source_git_pairs"],81)
    assert_int(d["new_native_runs_authorized_by_manifest"],0)
    assert d["independent_method_state"]=="exact methods pinned; fresh approval required"
    rows=d["source_files"];assert type(rows) is list
    assert_int(d["source_count"],len(rows))
    keys=[r["key"] for r in rows];paths=[r["path"] for r in rows]
    assert len(keys)==len(set(keys)) and len(paths)==len(set(paths))
    assert len({p.casefold() for p in paths})==len(paths)
    by_key={};source_map={}
    for r in rows:
        assert set(r)=={"key","path","bytes","sha256"}
        assert type(r["key"]) is str and type(r["path"]) is str
        assert type(r["bytes"]) is int and r["bytes"]>=0
        assert type(r["sha256"]) is str and re.fullmatch("[0-9a-f]{64}",r["sha256"])
        p=Path(r["path"]);assert p.is_absolute()
        assert file_record(p)=={"bytes":r["bytes"],"sha256":r["sha256"]}
        by_key[r["key"]]=r;source_map[r["key"]]=r["sha256"]
    required={
        "child_contract":PKG/"contract.json",
        "execution_binding":PKG/"execution-contract.json",
        "child_input":PKG/"native-input.json",
        "behavior_validator":PKG/"validate_native_cli.py",
        "runner_script":PKG/"run_native_ssh.ps1",
        "independent_replay":PKG/"review/independent_replay.py",
        "independent_self_check":PKG/"review/independent_self_check.py",
        "owned_source_inventory":PKG/"source-inventory.json"}
    assert set(required)<=set(by_key)
    for key,path in required.items():assert Path(by_key[key]["path"])==path
    assert source_map["child_contract"]==CONTRACT_SHA
    assert source_map["execution_binding"]==d["execution_binding_sha256"]
    assert CATALOG not in map(Path,paths)
    live=d["live_catalog_prelaunch_pin"]
    assert set(live)=={"path","bytes","sha256"} and Path(live["path"])==CATALOG
    contract=parse_json(CONTRACT.read_bytes())
    historical=contract["lineage"]["catalog_local_495"]
    assert {k:live[k] for k in ("bytes","sha256")}=={
        k:historical[k] for k in ("bytes","sha256")}
    # Current publication may append. Its typed prefix was checked in custody().
    inv=parse_json((PKG/"source-inventory.json").read_bytes())
    assert set(inv)=={"schema","source_count","source_files",
                     "provisional_independent_methods_absent","excluded_future"}
    assert inv["schema"]=="i03-var08-idle-maxut-owned-source-inventory/v1"
    assert type(inv["source_files"]) is list
    assert_int(inv["source_count"],len(inv["source_files"]))
    assert type(inv["provisional_independent_methods_absent"]) is bool
    assert not inv["provisional_independent_methods_absent"]
    assert inv["excluded_future"]==["source-inventory.json","prelaunch-manifest.json",
        "runs/","transport-evidence/","test-output/","review/independent-prelaunch-",
        "review/independent-postrun-","review/independent-content-"]
    owned_paths={r["relative_path"] for r in inv["source_files"]}
    assert len(owned_paths)==len(inv["source_files"])
    require_core_owned(owned_paths)
    role_for={
        "contract.json":"child_contract",
        "execution-contract.json":"execution_binding",
        "native-input.json":"child_input",
        "validate_native_cli.py":"behavior_validator",
        "run_native_ssh.ps1":"runner_script",
        "review/independent_replay.py":"independent_replay",
        "review/independent_self_check.py":"independent_self_check"}
    expected={}
    def add_expected(key,path,record=None):
        path=Path(path)
        assert key not in expected
        pin=record or file_record(path)
        expected[key]={"path":str(path),"bytes":pin["bytes"],"sha256":pin["sha256"]}
    for r in inv["source_files"]:
        assert set(r)=={"relative_path","path","bytes","sha256"}
        assert Path(r["path"])==PKG/r["relative_path"]
        assert r["path"] in paths
        assert file_record(r["path"])=={"bytes":r["bytes"],"sha256":r["sha256"]}
        add_expected(role_for.get(r["relative_path"],"owned:"+r["relative_path"]),
                     r["path"],r)
    add_expected("owned_source_inventory",PKG/"source-inventory.json")
    lineage=contract["lineage"]
    for i,r in enumerate(lineage["accepted_81_local_and_base_git_refs"]):
        add_expected(f"accepted_source:{i}",ROOT/r["path"],r["disk"])
    for i,r in enumerate(lineage["mandatory_108_original_raw"]):
        add_expected(f"accepted_raw:{i}",r["path"],r)
    already={v["path"].casefold():v for v in expected.values()}
    for i,(relative,r) in enumerate(lineage["required_docs_8"].items()):
        path=str(ROOT/relative)
        if path.casefold() in already:
            assert {k:already[path.casefold()][k] for k in ("bytes","sha256")}=={
                k:r[k] for k in ("bytes","sha256")}
        else:
            add_expected(f"required_doc:{i}",path,r);already[path.casefold()]=expected[f"required_doc:{i}"]
    for field,r in lineage["installed_exe_manual_dictionary_3"].items():
        add_expected("installed:"+field,r["path"],r)
    helper=ROOT/"cases/simlox-air-support/I03-var05-in-zero-delay-v1.0.0/captured_process.ps1"
    helper_pin=file_record(PKG/"captured_process.ps1")
    assert helper_pin["sha256"]=="17285b90093c2d80c6241e1345b9926a2e4dd0f0b2b24f831c84c1cfa885b794"
    # The accepted helper is a distinct pinned source, byte-equal to the owned copy.
    add_expected("accepted_capture_helper_ancestry",helper,helper_pin)
    assert file_record(helper)==helper_pin
    assert set(by_key)==set(expected) and len(by_key)==len(expected)
    for key,want in expected.items():
        assert {field:by_key[key][field] for field in ("path","bytes","sha256")}==want,key
    return raw,d,source_map,source_map_sha(source_map)


def verify_pure_proof(proof_path, mode, manifest_raw, source_map, expected_sha=None):
    proof_path=Path(proof_path)
    raw=proof_path.read_bytes()
    if expected_sha is not None:assert sha(raw)==expected_sha
    d=parse_json(raw)
    assert set(d)=={"schema","mode","run_id","manifest_sha256","source_map_sha256",
                     "started_utc","completed_utc","status","error","checks",
                     "source_hashes_after"}
    assert d["schema"]=="i03-var08-idle-maxut-pure-proof/v1"
    assert d["mode"]==mode and d["run_id"]==RUN_ID
    assert d["manifest_sha256"]==sha(manifest_raw)
    assert d["source_map_sha256"]==source_map_sha(source_map)
    assert d["status"]=="passed" and d["error"] is None
    assert typed(d["source_hashes_after"],source_map)
    checks=d["checks"];assert type(checks) is list and len(checks)==5
    previous=utc(d["started_utc"])
    for tool,step in zip(PROOF_TOOLS,checks):
        assert set(step)=={"tool","program","arguments","started_utc","completed_utc",
                          "status","error","child_pid","child_session_id","exit_code",
                          "capture_error","stdout_path","stderr_path","stdout_bytes",
                          "stderr_bytes","stdout_sha256","stderr_sha256"}
        assert step["tool"]==tool and step["program"]==PYTHON
        assert step["arguments"]==f'-X utf8 -B "{PKG/tool}"'
        assert step["status"]=="completed" and step["error"] is None and step["capture_error"] is None
        start,end=utc(step["started_utc"]),utc(step["completed_utc"])
        assert previous<=start<=end;previous=end
        assert_int(step["child_pid"]);assert step["child_pid"]>0
        assert_int(step["child_session_id"],0);assert_int(step["exit_code"],0)
        for stream in ("stdout","stderr"):
            path=proof_path.parent/f"{Path(tool).stem}-{stream}.bin"
            assert Path(step[f"{stream}_path"])==path
            assert_int(step[f"{stream}_bytes"],path.stat().st_size)
            assert step[f"{stream}_sha256"]==sha(path.read_bytes())
        assert_int(step["stderr_bytes"],0)
    assert previous<=utc(d["completed_utc"])
    return d


def verify_preflight(manifest_raw, source_map, map_sha):
    approval_raw=(PKG/"review/independent-prelaunch-go.json").read_bytes()
    approval=parse_json(approval_raw)
    assert set(approval)=={"schema","decision","run_id","manifest_sha256","runner_sha256",
        "validator_sha256","contract_sha256","execution_binding_sha256","input_sha256",
        "source_map_sha256","independent_replay_sha256","preflight_relative_path",
        "preflight_sha256"}
    assert approval["schema"]=="i03-var08-idle-maxut-independent-prelaunch-go/v1"
    assert approval["decision"]=="GO_PRELAUNCH" and approval["run_id"]==RUN_ID
    for key,want in {
        "manifest_sha256":sha(manifest_raw),"runner_sha256":source_map["runner_script"],
        "validator_sha256":source_map["behavior_validator"],
        "contract_sha256":CONTRACT_SHA,
        "execution_binding_sha256":source_map["execution_binding"],
        "input_sha256":source_map["child_input"],
        "source_map_sha256":map_sha,
        "independent_replay_sha256":source_map["independent_replay"]}.items():
        assert approval[key]==want,key
    rel=approval["preflight_relative_path"]
    assert type(rel) is str and re.fullmatch(r"review[\\/]preflight-ssh0-[0-9]{8}T[0-9]{9}Z\.json",rel)
    path=PKG/rel
    assert path.resolve().parent==(PKG/"review").resolve() and not path.is_symlink()
    raw=path.read_bytes();assert sha(raw)==approval["preflight_sha256"]
    d=parse_json(raw)
    assert set(d)=={"schema","run_id","run_dirs_absent","ssh_session","ps_major",
        "ssh_ancestors","mutex_free","wts_active_gui_count","gui","accepted_raw_seals",
        "accepted_nonclosure_raw","accepted_closures","accepted_invocations",
        "excluded_failed_witness_raw","total_original_raw","manifest_sha256",
        "source_map_sha256","source_hashes","source_hashes_after_pure",
        "pure_proof_directory","pure_proof_path","pure_proof_sha256","pure_checks",
        "native_process_started"}
    assert d["schema"]=="i03-var08-idle-maxut-ssh-preflight/v1"
    assert d["run_id"]==RUN_ID and d["manifest_sha256"]==sha(manifest_raw)
    assert d["source_map_sha256"]==map_sha
    assert typed(d["source_hashes"],source_map) and typed(d["source_hashes_after_pure"],source_map)
    for key,want in (("ssh_session",0),("ps_major",5),("wts_active_gui_count",1),
        ("accepted_raw_seals",108),("accepted_nonclosure_raw",93),
        ("accepted_closures",8),("accepted_invocations",7),
        ("excluded_failed_witness_raw",0),("total_original_raw",108)):
        assert_int(d[key],want)
    assert type(d["run_dirs_absent"]) is bool and d["run_dirs_absent"]
    assert type(d["mutex_free"]) is bool and d["mutex_free"]
    assert type(d["native_process_started"]) is bool and not d["native_process_started"]
    assert type(d["ssh_ancestors"]) is list and "sshd.exe" in d["ssh_ancestors"]
    verify_gui(d["gui"])
    proof=Path(d["pure_proof_path"])
    assert Path(d["pure_proof_directory"])==proof.parent
    assert proof.name=="pure-proof.json"
    assert proof.parent.parent==PKG/"test-output" and proof.parent.name.startswith("preflight-pure-")
    p=verify_pure_proof(proof,"preflight",manifest_raw,source_map,d["pure_proof_sha256"])
    assert typed(d["pure_checks"],p["checks"])
    return approval_raw,approval,raw,d,path


def planned_steps(run):
    def q(name):return f'"{run/name}"'
    def cq(name):return f'"{PKG/name}"'
    rq=f'"{run}"'
    return [
        {"name":"import","program":EXE,"arguments":f'-silent -jimport {q("input.json")} -save {q("model.sxi")} -log {q("import.log")} -close'},
        {"name":"export","program":EXE,"arguments":f'{q("model.sxi")} -silent -jexport {q("roundtrip-raw.json")} -log {q("export.log")} -close'},
        {"name":"check_import_export","program":PYTHON,"arguments":f'-X utf8 -B {cq("check_roundtrip.py")} {rq}'},
        {"name":"calc","program":EXE,"arguments":f'{q("model.sxi")} -silent -threads 1 -calc -log {q("model-run.log")} -close'},
        {"name":"jsonreport","program":EXE,"arguments":f'{q("model.sxo")} -silent -jsonreport {q("report-raw.json")} -log {q("report-export.log")} -close'},
        {"name":"check_behavior","program":PYTHON,"arguments":f'-X utf8 -B {cq("validate_native_cli.py")} {rq}'},
    ]


def verify_converter(run):
    raw=(run/"model-run.log").read_bytes()
    s=raw.decode("utf-8-sig")
    for label,name in (("Input file","model.sxi"),("Output file","model.sxo"),("File","model.sxi")):
        matches=re.findall(rf"(?m)^{re.escape(label)}: ([^\r\n]+)\r?$",s)
        assert len(matches)==1 and matches[0].replace("\\","/")==str(run/name).replace("\\","/")
    assert len(re.findall(r"(?m)^Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0\r?$",s))==1
    warnings=re.findall(r"(?m)^Form: ([^\r\n]+)\r?\n(rec [^\r\n]+)\r?$",s)
    assert warnings==[
        ("Control","rec 1: (warning #108) Enabling simulation log may generate extensive data in log file"),
        ("System","rec 1: (warning #126) This system contains no items: TEACH-AIR-01")]
    assert len(re.findall(r"(?m)^Form: ",s))==len(re.findall(r"(?m)^rec ",s))==2
    codes=[(kind.lower(),num) for kind,num in
           re.findall(r"\b(warning|error|notice|note)\s*#(\d+)",s,re.I)]
    assert codes==[("warning","108"),("warning","126")]
    assert s.count("Input conversion completed.")==1
    assert s.count("Starting simulation")==s.count("Saving results")==1


def verify_run_provenance(run,manifest_raw,source_map,approval_raw,approval,
                          preflight_raw,preflight_path):
    assert run.is_dir() and run.name==RUN_ID
    files={p.name:p for p in run.iterdir() if p.is_file()}
    assert set(files)==RUN_FILES and len(files)==25 and "failure-seal.json" not in files
    for path in files.values():
        assert bool(os.stat(path).st_file_attributes & 1),f"original native run file not ReadOnly: {path.name}"
    invocation_raw=files["invocation.json"].read_bytes()
    closure_raw=files["closure.json"].read_bytes()
    inv=parse_json(invocation_raw);cl=parse_json(closure_raw)
    assert set(inv)=={"schema","run_id","created_utc","original_run_dir","input_sha256",
        "contract_sha256","manifest_sha256","approval_sha256",
        "approved_preflight_path","approved_preflight_sha256",
        "independent_replay_sha256","runner_script_sha256","session_id",
        "ssh_ancestors","gui","queue_mutex","working_directory",
        "planned_commands","planned_checkers","source_hashes_before",
        "source_hashes_after_pure","pure_proof_path","pure_proof_sha256",
        "pure_checks","publication_state"}
    assert set(cl)=={"schema","run_id","invocation_sha256","manifest_sha256",
        "approval_sha256","approved_preflight_sha256","source_hashes_before",
        "source_hashes_after","raw","step_error","error","publication_state"}
    assert inv["schema"]=="i03-var08-idle-maxut-invocation/v1"
    assert cl["schema"]=="i03-var08-idle-maxut-closure/v1"
    assert inv["run_id"]==cl["run_id"]==RUN_ID and Path(inv["original_run_dir"])==run
    assert_int(inv["session_id"],0)
    assert type(inv["ssh_ancestors"]) is list and "sshd.exe" in inv["ssh_ancestors"]
    assert inv["queue_mutex"]==r"Global\SimloxIssue18NativeQueue"
    assert inv["working_directory"]==WORKSPACE
    verify_gui(inv["gui"])
    for key,want in (("manifest_sha256",sha(manifest_raw)),
                     ("approval_sha256",sha(approval_raw)),
                     ("approved_preflight_sha256",sha(preflight_raw))):
        assert inv[key]==cl[key]==want,key
    assert Path(inv["approved_preflight_path"])==preflight_path
    assert inv["independent_replay_sha256"]==source_map["independent_replay"]
    assert inv["runner_script_sha256"]==source_map["runner_script"]
    assert inv["contract_sha256"]==CONTRACT_SHA
    assert inv["input_sha256"]==source_map["child_input"]
    assert cl["invocation_sha256"]==sha(invocation_raw)
    for rec in (inv["source_hashes_before"],inv["source_hashes_after_pure"],
                cl["source_hashes_before"],cl["source_hashes_after"]):
        assert typed(rec,source_map)
    assert inv["publication_state"]==cl["publication_state"]=="not_published"
    assert cl["error"] in (None,"") and cl["step_error"] in (None,"")
    native_proof_path=Path(inv["pure_proof_path"])
    assert native_proof_path.name=="pure-proof.json"
    assert native_proof_path.parent.parent==PKG/"test-output"
    assert native_proof_path.parent.name.startswith("native-pure-")
    native_proof=verify_pure_proof(native_proof_path,"native",manifest_raw,source_map,
                                   inv["pure_proof_sha256"])
    assert typed(inv["pure_checks"],native_proof["checks"])
    raw=cl["raw"]
    assert type(raw) is dict and set(raw)==RUN_FILES-{"invocation.json","closure.json"} and len(raw)==23
    for name,rec in raw.items():
        assert set(rec)=={"bytes","sha256"}
        assert type(rec["bytes"]) is int and type(rec["sha256"]) is str
        assert rec==file_record(files[name])
    steps=parse_json(files["steps.json"].read_bytes())
    plan=planned_steps(run)
    assert type(steps) is list and len(steps)==len(plan)==6
    assert typed(inv["planned_commands"],[plan[i] for i in (0,1,3,4)])
    assert typed(inv["planned_checkers"],[plan[i] for i in (2,5)])
    previous=None
    for index,(step,want) in enumerate(zip(steps,plan)):
        assert set(step)=={"sequence","name","program","arguments","started_utc",
            "completed_utc","child_pid","child_session_id","exit_code",
            "capture_error","stdout_path","stderr_path","stdout_bytes",
            "stderr_bytes","stdout_sha256","stderr_sha256",
            "converter_log_bytes","converter_log_sha256","converter_log_validated",
            "gui_preserved","status","error"}
        assert_int(step["sequence"],index)
        assert {k:step[k] for k in ("name","program","arguments")}==want
        start,end=utc(step["started_utc"]),utc(step["completed_utc"])
        assert start<=end and (previous is None or previous<=start);previous=end
        assert_int(step["child_pid"]);assert step["child_pid"]>0
        assert_int(step["child_session_id"],0);assert_int(step["exit_code"],0)
        assert step["capture_error"] is None and step["error"] is None
        assert step["status"]=="completed"
        assert type(step["gui_preserved"]) is bool and step["gui_preserved"]
        stdout=("roundtrip-validation.json" if index==2 else
                "author-validation.json" if index==5 else step["name"]+"-stdout.txt")
        stderr=step["name"]+"-stderr.txt"
        for stream,name in (("stdout",stdout),("stderr",stderr)):
            assert Path(step[stream+"_path"])==run/name
            assert_int(step[stream+"_bytes"],raw[name]["bytes"])
            assert step[stream+"_sha256"]==raw[name]["sha256"]
        assert files[stderr].read_bytes()==b""
        if index!=3:
            assert step["converter_log_bytes"] is None
            assert step["converter_log_sha256"] is None
            assert type(step["converter_log_validated"]) is bool and not step["converter_log_validated"]
    calc=steps[3]
    assert_int(calc["converter_log_bytes"],raw["model-run.log"]["bytes"])
    assert calc["converter_log_sha256"]==raw["model-run.log"]["sha256"]
    assert type(calc["converter_log_validated"]) is bool and calc["converter_log_validated"]
    assert bool(os.stat(files["model-run.log"]).st_file_attributes & 1)
    verify_converter(run)
    return files,raw,steps


def verify_checker_receipts(run,raw,c,events,cells):
    roundtrip=parse_json((run/"roundtrip-validation.json").read_bytes())
    assert set(roundtrip)=={"schema","passed","issues","input_sha256","export_sha256",
                            "tables","authored_rows","exported_rows","authored_cells",
                            "exported_cells","all_null_placeholder_tables"}
    assert roundtrip["schema"]=="i03-var08-idle-maxut-roundtrip/v1"
    assert type(roundtrip["passed"]) is bool and roundtrip["passed"]
    assert roundtrip["issues"]==[]
    assert roundtrip["input_sha256"]==file_record(run/"input.json")["sha256"]
    assert roundtrip["export_sha256"]==raw["roundtrip-raw.json"]["sha256"]
    for key,want in (("tables",36),("authored_rows",28),("exported_rows",39),
        ("authored_cells",242),("exported_cells",383),
        ("all_null_placeholder_tables",11)):
        assert_int(roundtrip[key],want)
    behavior=parse_json((run/"author-validation.json").read_bytes())
    assert set(behavior)=={"schema","passed","issues","run_id","input_sha256",
                          "report_cell_checks","timed_event_records","timeline","report"}
    assert behavior["schema"]=="i03-var08-idle-maxut-behavior/v1"
    assert type(behavior["passed"]) is bool and behavior["passed"]
    assert behavior["issues"]==[] and behavior["run_id"]==RUN_ID
    assert behavior["input_sha256"]==file_record(run/"input.json")["sha256"]
    assert_int(behavior["report_cell_checks"],cells)
    assert_int(behavior["timed_event_records"],events)
    terminal=behavior["timeline"]["terminal"]
    for key,want in (("local",1),("nominal",1),("booked",0),
        ("reserved_OUT",0),("pending_OUT",0),("backorder",0),
        ("ready_aircraft",2)):
        assert_int(terminal[key],want)
    assert behavior["report"]["cells_checked"]==cells
    return behavior


def sealed(c,run):
    manifest_raw,manifest,source_map,map_sha=verify_manifest()
    approval_raw,approval,preflight_raw,preflight,preflight_path=verify_preflight(
        manifest_raw,source_map,map_sha)
    files,raw,steps=verify_run_provenance(run,manifest_raw,source_map,approval_raw,
        approval,preflight_raw,preflight_path)
    assert file_record(run/"input.json")["sha256"]==source_map["child_input"]
    child_source=parse_json((run/"input.json").read_bytes())
    assert verify_source(c,child_source)==242
    export=parse_json((run/"roundtrip-raw.json").read_bytes())
    assert verify_export(child_source,export)==383
    for name,marker in (("import.log",b"Import completed!"),
                        ("export.log",b"Export completed!")):
        assert marker in files[name].read_bytes()
    events=verify_log(files["model.log"].read_bytes())
    report=parse_json(files["report-raw.json"].read_bytes(),native=True)
    cells=verify_report(c,report)
    verify_checker_receipts(run,raw,c,events,cells)
    return {"mode":"GO_BOUNDED_SEALED_ORIGINAL_NATIVE",
            "source_cells":242,"export_cells":383,"timed_events":events,
            "report_cells":cells,"original_run_files":25,"closure_raw_files":23,
            "native_and_checker_stages":6}


def main():
    p=argparse.ArgumentParser();p.add_argument("--pure-fixture",action="store_true");p.add_argument("--run-dir",type=Path)
    args=p.parse_args()
    raw=CONTRACT.read_bytes();assert sha(raw)==CONTRACT_SHA
    c=parse_json(raw)
    pins=custody(c)
    if args.pure_fixture:
        result=pure(c)
    else:
        run=args.run_dir or PKG/"runs"/RUN_ID
        result=sealed(c,run)
    result["source_and_custody_pins"]=pins
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":main()
