"""Read-only static and mutation checks before freezing a native runner."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from build import make, sha, flattened_diff
from check_roundtrip import INPUT_SHA, tablemap
from report_oracle import build_expected, columns, equal_cell, rows, tables, timed_blocks, resource_spans
from validate_native_cli import Gate, diagnostic_rows, physical_item_ledger, records

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def check() -> dict:
    count = 0
    def require(condition, label):
        nonlocal count
        count += 1
        if not condition:
            raise AssertionError(label)
    pair = {arm:make(arm) for arm in ("crew","radio")}
    for arm,doc in pair.items():
        require(sha(HERE/f"{arm}-input.json")==INPUT_SHA[arm],f"{arm} input pin")
        require(json.loads((HERE/f"{arm}-input.json").read_text(encoding="utf-8-sig"))==doc,f"{arm} full object")
        t={x["name"]:x for x in doc["model"]["tables"]}
        mr=rows(t["MissionResource"])
        ms=rows(t["MissionSystem"])
        require(ms[0][2]==1 and ms[1][2]==2,"A/B priority")
        require(mr[0][2]=="MISSION-CREW" and mr[1][2]==("MISSION-CREW" if arm=="crew" else "MISSION-RADIO"),"typed RID")
        changed=copy.deepcopy(doc)
        changed["model"]["tables"][0]["instances"][0]["instance_name"]="tampered"
        require(tablemap(changed)!=tablemap(doc),"instance-name drift detected")
        changed=copy.deepcopy(doc)
        changed["model"]["tables"][0]["columns"][0]["datatype"]="tampered"
        require(tablemap(changed)!=tablemap(doc),"column datatype drift detected")
    require(len(flattened_diff(pair["crew"],pair["radio"]))==2,"exact pair delta")
    a16=ROOT/"A16-two-config-reconfiguration-v1.0.0/runs/a16-two-config-v100-20261001-01"
    actual=diagnostic_rows((a16/"run.log").read_text(encoding="utf-8-sig"))
    expected=[("Control",1,"108","Enabling simulation log may generate extensive data in log file")]
    expected += [("Item",i,"2053",f"FRT is zero for: {iid}") for i,iid in
                 enumerate(("TEACH-LRU-01","TEACH-LRU-A","TEACH-LRU-B"),1)]
    require(actual==expected,"accepted warning attribution")
    for swap in (("Item",2,"2053","FRT is zero for: TEACH-LRU-01"),
                 ("Item",1,"2053","FRT is zero for: TEACH-LRU-B")):
        mutated=actual.copy();mutated[1]=swap
        require(mutated!=expected,"warning rec/item mutation rejected")
    physical=records(a16/"model.log")
    physical_gate=Gate()
    physical_item_ledger(physical_gate,physical,"crew")
    require(physical_gate.checks>=25 and not physical_gate.failures,"accepted A16 physical stock edges")
    physical_mutations=(
        ("opening ID missing","Items:<TEACH-LRU-A,0,0>","Items:<TEACH-LRU-A,0,99>"),
        ("opening count doubled","Level: 1 Items:<TEACH-LRU-A,0,0>",
         "Level: 2 Items:<TEACH-LRU-A,0,0>,<TEACH-LRU-A,0,99>"),
        ("taken ID swapped","Take replacement item <TEACH-LRU-A,0,0>","Take replacement item <TEACH-LRU-A,0,2>"),
        ("demand owner swapped","demand arrives from pos <TEACH-AIR-01,BASE-01,0>","demand arrives from pos <TEACH-AIR-01,BASE-01,1>"),
        ("fit owner swapped","system reconfig fit task 0 on <TEACH-AIR-01,0> started","system reconfig fit task 0 on <TEACH-AIR-01,1> started"),
        ("arrival ID swapped","Replacement item arrives <TEACH-LRU-A,0,3>","Replacement item arrives <TEACH-LRU-A,0,4>"),
    )
    for label,before,after in physical_mutations:
        altered=[];changed=0
        for t,body in physical:
            if before in body and not changed:
                body=body.replace(before,after,1);changed+=1
            altered.append((t,body))
        require(changed==1,f"{label} fixture exists")
        mutated_gate=Gate()
        physical_item_ledger(mutated_gate,altered,"crew")
        require(bool(mutated_gate.failures),f"{label} physical tamper rejected")
    orphan=physical.copy()
    orphan.insert(next(i for i,(_,body) in enumerate(orphan) if "Replacement item arrives <TEACH-LRU-A,0,3>" in body)+1,
                  (19.1667,"<TEACH-LRU-A,0,BASE-01,0> Replacement item arrives <TEACH-LRU-A,0,99>"))
    orphan_gate=Gate()
    physical_item_ledger(orphan_gate,orphan,"crew")
    require(any("arrival-to-return bijection" in label for label in orphan_gate.failures),
            "orphan arrival rejected")
    for arm,relative in (("crew","C05-mission-resource-v1.0.0/runs/c05-capacity-2-20260930-01"),
                         ("radio","C05-var02-two-resource-types-v1.0.0/runs/c05-var02-radio-0-20260930-01")):
        run=ROOT/relative
        predicted,_=build_expected(arm,run/"model.log")
        report=tables(run/"report-raw.json")
        mismatches=[];inspected=0
        for name in predicted:
            for i,row in enumerate(rows(report[name])):
                for j,value in enumerate(row):
                    field=columns(report[name])[j]
                    if not equal_cell(value,predicted[name][i][j],field):
                        mismatches.append((name,i,field))
                    inspected+=1
        require(inspected==5210,f"{arm} reference 5210 cells")
        allowed={("ProblemDescription",0,"PDESC")}
        if arm=="crew":
            allowed |= {("SystemResults",i,"STREQ") for i in range(16,20)}
        require(set(mismatches)==allowed,f"{arm} calibrated report mismatches {mismatches[:10]}")
    require(not equal_cell(1,0,"NRCFG"),"interior count mutation rejected")
    require(not equal_cell(0,None,"ROS"),"stock null mutation rejected")
    require(not equal_cell(.8,.5,"NSYMC"),"fractional state mutation rejected")
    require(resource_spans([(7,"<MISSION-CREW at <BASE-01,0>> allocated to mission assigned: 1"),
                            (8,"<MISSION-CREW at <BASE-01,0>> deallocated from mission assigned: 1")])[0]==[(7,8)],
            "one partial crew interval")
    require(resource_spans([])==([],None),"zero partial crew interval")
    blocks=timed_blocks(ROOT/"C05-mission-resource-v1.0.0/runs/c05-capacity-2-20260930-01/model.log")
    require(any("Availability test on" in text and "request for: 1 OK" in text for _,text in blocks),
            "indented availability continuation retained")
    return {"schema":"c05-var03-v101-static-self-check/v1","passed":True,"checks":count,
            "scope":"frozen source, exact warnings, accepted report calibration and tamper rejection"}


if __name__=="__main__":
    print(json.dumps(check(),indent=2))
