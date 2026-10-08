"""PURE source, parent and prospective-child checks. No native calls or files."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
from build import run as build_run,parse,topology
from check_roundtrip import row_equal
from event_ledger import expected_synthetic,validate as check_events
from report_oracle import accepted_parent,expected as expected_report,validate as check_report,f32
from source_gate import verify as verify_sources
from validate_native_cli import converter

HERE=Path(__file__).resolve().parent

def rejects(fn):
    try:fn()
    except (AssertionError,ValueError,KeyError,TypeError,OverflowError):return True
    raise AssertionError("semantic mutant escaped")

def run():
    source=build_run(False)
    assert source["input"]["exists"] and source["diff"]["exists"]
    custody=verify_sources("live")
    authored=parse((HERE/"native-input.json").read_bytes())
    assert topology(authored["model"])["cells"]==242
    parent=accepted_parent()
    event=check_events(expected_synthetic())
    prospective=check_report(expected_report(True),True)
    assert parent["cells_checked"]==prospective["cells_checked"]==5210
    assert prospective["prospective_paired_differences"]==55
    count=0
    def reject(fn):
        nonlocal count
        rejects(fn);count+=1
    for index,new in ((2,"Time: 24.75  resource transfer task 0 (OUT)  starts with 2 resources, transfer time: 0"),
                      (3,"Time: 24.75  resource transfer task 0 (OUT)  arrives with 2 resources")):
        def bad(index=index,new=new):
            lines=expected_synthetic();at=next(i for i,s in enumerate(lines) if s.startswith("Time: 24.75  resource transfer task"));lines[at+index]=new;check_events(lines)
        reject(bad)
    for mutation in (lambda x:x.pop(103),lambda x:x.insert(103,x[103]),
                     lambda x:x.__setitem__(next(i for i,s in enumerate(x) if s.startswith("Time: 26  resource shift 3 starting"))+1,"  Free resources at: <BASE-01,0> P-CREW 2")):
        def bad(mutation=mutation):
            lines=expected_synthetic();mutation(lines);check_events(lines)
        reject(bad)
    fields=("NR","NRA","NRN","NRUM","NRW")
    report=expected_report(True)
    def resource_index(field):
        t=next(t for t in report["report"]["tables"] if t["name"]=="ResourceResultsTotal")
        return t,t["columns"].index(next(c for c in t["columns"] if c["name"]==field))
    for field in fields:
        def bad(field=field):
            x=copy.deepcopy(report);t=next(t for t in x["report"]["tables"] if t["name"]=="ResourceResultsTotal")
            k=next(i for i,c in enumerate(t["columns"]) if c["name"]==field)
            t["instances"][0]["rows"][0][k]=math.nextafter(t["instances"][0]["rows"][0][k],math.inf)
            check_report(x,True)
        reject(bad)
    def metadata_mutation():
        x=copy.deepcopy(report);x["report"]["tables"][0]["columns"][0]["datatype"]="integer";check_report(x,True)
    reject(metadata_mutation)
    def null_mutation():
        x=copy.deepcopy(report);t=next(t for t in x["report"]["tables"] if t["name"]=="SystemResults")
        k=next(i for i,c in enumerate(t["columns"]) if c["name"]=="SYDT")
        t["instances"][0]["rows"][0][k]=0;check_report(x,True)
    reject(null_mutation)
    def integer_float_mutation():
        x=copy.deepcopy(report);t=next(t for t in x["report"]["tables"] if t["name"]=="ResultSummary")
        k=next(i for i,c in enumerate(t["columns"]) if c["name"]=="NREP")
        t["instances"][0]["rows"][0][k]=float(t["instances"][0]["rows"][0][k]);check_report(x,True)
    reject(integer_float_mutation)
    def numeric_bool_mutation():
        x=copy.deepcopy(report);t=next(t for t in x["report"]["tables"] if t["name"]=="ResourceResults")
        k=next(i for i,c in enumerate(t["columns"]) if c["name"]=="NR")
        t["instances"][0]["rows"][0][k]=True;check_report(x,True)
    reject(numeric_bool_mutation)
    def extra_report_key():
        x=copy.deepcopy(report);x["report"]["tables"][0]["extra"]=0;check_report(x,True)
    reject(extra_report_key)
    def duplicate_json():parse(b'{"a":1,"a":2}')
    reject(duplicate_json)
    def overflow_json():parse(b'{"a":1e999}')
    reject(overflow_json)
    def bool_double():
        assert row_equal([{"datatype":"double"}],[ [1.0] ],[ [True] ])
    reject(bool_double)
    parent_run=HERE.parent/"C08-exact-limit-v1.0.0"/"runs"/"c08-exact-limit-20260930-02"
    child_run=HERE/"runs"/"i03-var08-idle-maxut-out-v100-ssh-20261008-01"
    parent_text=(parent_run/"run.log").read_text(encoding="utf-8-sig")
    text=parent_text.replace(str(parent_run),str(child_run)).replace(
        str(parent_run).replace("\\","/"),str(child_run).replace("\\","/"))
    converter(text,child_run)
    for old,new in (
        ("Form: Control","Form: System"),
        ("extensive data in log file","extensive data elsewhere"),
        ("(warning #108)","(warning #109)"),
        ("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0",
         "Input conversion completed. Errors: 0, Warnings: 2, Notes: 1"),
        ("File: "+str(child_run).replace("\\","/")+"/model.sxi",
         "File: "+str(parent_run).replace("\\","/")+"/model.sxi"),
    ):
        assert old in text
        reject(lambda old=old,new=new:converter(text.replace(old,new,1),child_run))
    return {"schema":"i03-var08-pure-self-check/v1","native_calls":0,
            "source_pairs":custody["counts"]["accepted_source_git_pairs"],
            "accepted_raw":custody["counts"]["mandatory_accepted_original_raw"],
            "parent_cells":parent["cells_checked"],"prospective_child_cells":prospective["cells_checked"],
            "typed_lines":event["lines"],"semantic_mutants_rejected":count}

if __name__=="__main__":print(json.dumps(run(),sort_keys=True))
