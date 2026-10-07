"""Pure synthetic negative fixtures; no accepted or native files are written."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import struct

from build import construct, typed_equal, verify
from check_roundtrip import parse
from event_ledger import child_timeline, parse_log
from report_oracle import GATE, PARENT_REPORT, check_report, expected

HERE = Path(__file__).resolve().parent


def fixture_log() -> str:
    lines = ["SIMLOX LOG FILE", "36"]
    def add(t: float, body: str, *continuations: str) -> None:
        lines.append(f"Time: {t:g} {body}")
        lines.extend("  " + c for c in continuations)
    crew = "<P-CREW at <BASE-01,0>>"
    add(0, "<TEACH-AIR-01,0> Next random failure will occur 1e+010")
    add(6, f"resource transfer task 0 (OUT)  created: starting from  {crew}")
    add(6, f"{crew} Resource transfer demand arrives from OUT-transfer")
    add(6, "resource transfer task 0 (OUT)  starts with 1 resources, transfer time: 0")
    add(6, "resource transfer task 0 (OUT)  arrives with 1 resources")
    for wave, start in enumerate((7.5, 19.5)):
        mid = f"<BASIC-MISSION,TEACH-UNIT,0,0,{wave}>"
        first = 2*wave
        s0 = f"subtask {first} seqno 1 within system preparation task {first} on <TEACH-AIR-01,0>"
        s1 = f"subtask {first+1} seqno 1 within system preparation task {first+1} on <TEACH-AIR-01,1>"
        add(start, "<TEACH-UNIT> mission ordered: BASIC-MISSION")
        add(start, mid + " mission created:")
        add(start, mid + " mission activated, systems requested: 2")
        for aircraft in (0,1):
            add(start, mid + f" mission allocates system: <TEACH-AIR-01,{aircraft}>")
        for aircraft in (0,1):
            add(start, f"<TEACH-AIR-01,{aircraft}> preparation started, mission: {mid}")
        add(start, f"system preparation task {first} on <TEACH-AIR-01,0> started")
        add(start, s0+" started")
        add(start, s0+" requests resources")
        add(start, s0+" resource availability test", f"Availability test on  {crew} request for: 1 OK")
        add(start, s0+" books resources")
        add(start, crew+" allocated to maintenance task: 1  available now: 0")
        add(start, s0+" starts performing, planned to last for 0.5 hours")
        add(start, f"system preparation task {first+1} on <TEACH-AIR-01,1> started")
        add(start, s1+" started")
        add(start, s1+" requests resources")
        add(start, s1+" resource availability test", f"Availability test on  {crew} request for: 1 failed")
        add(start+.5, s0+" completed")
        add(start+.5, s0+" frees resources")
        add(start+.5, crew+" deallocated from  maintenance task: 1  available now: 1")
        add(start+.5, s1+" resource availability test", f"Availability test on  {crew} request for: 1 OK")
        add(start+.5, s1+" resource received")
        add(start+.5, s1+" books resources")
        add(start+.5, crew+" allocated to maintenance task: 1  available now: 0")
        add(start+.5, s1+" starts performing, planned to last for 0.5 hours")
        add(start+.5, f"system preparation task {first} on <TEACH-AIR-01,0> completed")
        add(start+.5, f"<TEACH-AIR-01,0> preparation ended, mission: {mid}")
        add(start+1, s1+" completed")
        add(start+1, s1+" frees resources")
        add(start+1, crew+" deallocated from  maintenance task: 1  available now: 1")
        add(start+1, f"system preparation task {first+1} on <TEACH-AIR-01,1> completed")
        add(start+1, f"<TEACH-AIR-01,1> preparation ended, mission: {mid}")
        add(start+1, mid+" mission starting, duration: 1 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
        add(start+1.25, mid+" task starting: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
        add(start+1.75, mid+" task completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
        add(start+2, mid+" mission success:")
        add(start+2, mid+" mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
        for aircraft in (0,1):
            a=f"<TEACH-AIR-01,{aircraft}>"
            add(start+2, f"{a} turnround started, mission: {mid} reduction factor: 1")
            add(start+2, f"{a} turnround ended, mission: {mid}")
            add(start+2, f"<TEACH-AIR-01,BASE-01,0> System arrives {a}, mission success,", "no failures", "no PMTasks")
            add(start+2, f"<TEACH-AIR-01,BASE-01,0> System ready {a}")
    add(36, "resource shift 0 ended at <P-CREW at <BASE-01,0>> time gap to next = 0")
    return "\n".join(lines)+"\n"


def synthetic_report(timeline: dict) -> dict:
    metadata = parse(PARENT_REPORT)["report"]["tables"]
    rows = expected(timeline)
    report = {"report": {"tables": []}}
    for table in metadata:
        name = table["name"]
        columns = [c["name"] for c in table["columns"]]
        report["report"]["tables"].append({"name": name, "columns": copy.deepcopy(table["columns"]),
            "instances": [{"instance_name": table["instances"][0]["instance_name"],
                           "rows": [[r[c] for c in columns] for r in rows[name]]}]})
    return report


def rejects(action) -> None:
    try:
        action()
    except (AssertionError, ValueError, KeyError, TypeError):
        return
    raise AssertionError("tamper unexpectedly accepted")


def f32_next(value: float) -> float:
    bits = struct.unpack("<I", struct.pack("<f", value))[0]
    return struct.unpack("<f", struct.pack("<I", bits+1))[0]


def main() -> None:
    parent = parse(HERE.parent / "I03-var01-crew-out-in-v1.0.0" / "out-input.json")
    child = construct(parent)
    verify(parent, child)
    log = fixture_log()
    timeline = child_timeline(parse_log(log))
    baseline = synthetic_report(timeline)
    assert check_report(baseline, timeline) == 5210
    negative = 0
    def probe(fn):
        nonlocal negative
        rejects(fn)
        negative += 1
    for old,new in [("SIMLOX LOG FILE", "OTHER LOG FILE"), ("\n36\n", "\n35\n"),
                    ("starts with 1 resources", "starts with 0 resources"),
                    ("mission activated, systems requested: 2", "mission activated, systems requested: 1"),
                    ("request for: 1 failed", "request for: 1 OK"),
                    ("mission success:", "mission cancelled:"),
                    ("Resource transfer demand arrives", "Resource transfer backorder added")]:
        probe(lambda old=old,new=new: child_timeline(parse_log(log.replace(old,new,1))))
    probe(lambda: child_timeline(parse_log(log.replace("Time: 6 resource transfer task 0 (OUT)  arrives with 1 resources\n",
                         "Time: 6 resource transfer task 0 (OUT)  arrives with 1 resources\nTime: 6 resource transfer task 0 (OUT)  arrives with 1 resources\n",1))))
    probe(lambda: child_timeline(parse_log(log.replace("Time: 9.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:\n",
                         "Time: 9.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:\nTime: 9.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:\n",1))))
    probe(lambda: child_timeline(parse_log(log.replace("mission allocates system: <TEACH-AIR-01,1>",
                         "mission allocates system: <TEACH-AIR-01,0>",1))))
    def swap_equal_time() -> None:
        lines=log.splitlines()
        a=next(i for i,x in enumerate(lines) if x == "Time: 7.5 subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> requests resources")
        b=next(i for i,x in enumerate(lines) if x == "Time: 7.5 subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> books resources")
        lines[a],lines[b]=lines[b],lines[a]
        child_timeline(parse_log("\n".join(lines)+"\n"))
    probe(swap_equal_time)
    def report_mutation(name, row, field, change):
        modified=copy.deepcopy(baseline)
        table=next(t for t in modified["report"]["tables"] if t["name"]==name)
        index=[c["name"] for c in table["columns"]].index(field)
        table["instances"][0]["rows"][row][index]=change
        check_report(modified,timeline)
    for field in GATE["resource_fields"]["total_expected_float32"]:
        v=GATE["resource_fields"]["total_expected_float32"][field]
        probe(lambda field=field,v=v: report_mutation("ResourceResultsTotal",0,field,f32_next(v)))
    probe(lambda: report_mutation("SystemResults",0,"NSYMO",1e-9))
    probe(lambda: report_mutation("StockTotalResults",0,"ROS",0))
    probe(lambda: report_mutation("StockTotalResults",0,"PNB",0))
    probe(lambda: report_mutation("ResourceResults",0,"NR",True))
    probe(lambda: report_mutation("SystemResults",15,"NPSTA",1))
    probe(lambda: report_mutation("ResourceResults",15,"NRUM",0))
    changed=copy.deepcopy(baseline)
    changed["report"]["tables"][2]["columns"][0]["key"]=1
    probe(lambda: check_report(changed,timeline))
    changed=copy.deepcopy(child)
    changed["model"]["tables"][0]["columns"][0]["key"]=True
    probe(lambda: verify(parent,changed))
    changed=copy.deepcopy(child)
    transfer=next(t for t in changed["model"]["tables"] if t["name"]=="ResourceTransfer")
    transfer["instances"][0]["rows"][0][4]=2
    probe(lambda: verify(parent,changed))
    print(json.dumps({"schema":"i03-var02-v102-self-check/v1","passed":True,
                      "synthetic_report_cells":5210,"semantic_rejections":negative},separators=(",", ":")))


if __name__=="__main__":
    main()
