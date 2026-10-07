"""Prelaunch event-derived oracle for every C05.var03 default report cell."""
from __future__ import annotations

import math
import re
from pathlib import Path

from check_roundtrip import parse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONTROL = ROOT / "C05-mission-resource-v1.0.0/runs/c05-capacity-2-20260930-01/report-raw.json"
SHAPES = {"ProblemDescription": (1,1), "ResultSummary": (1,11),
          "SystemResults": (72,40), "StockTotalResults": (72,16),
          "ResourceResults": (72,16), "ResourceResultsTotal": (1,14)}
FRACTIONAL = {"NSYRY","NSYMA","NSYMO","NSYMC","NSYMR","NSYA","FTMO","STREQ","STACC",
              "NRMO","NRMA","NRUM","NRLA","NRW","NRRI","NRRT","NRRO"}


def tables(path: Path) -> dict:
    raw = parse(path)["report"]["tables"]
    assert len(raw) == len({t["name"] for t in raw})
    return {t["name"]:t for t in raw}


def columns(t: dict) -> list[str]:
    return [c["name"] for c in t["columns"]]


def rows(t: dict) -> list[list]:
    assert len(t["instances"]) == 1
    return t["instances"][0]["rows"]


def overlap(a,b,c,d):
    return max(0.0,min(b,d)-max(a,c))


def timed_blocks(path: Path) -> list[tuple[float,str]]:
    result=[]
    for line in path.read_text(encoding="utf-8-sig",errors="replace").splitlines():
        found=re.match(r"Time:\s*([0-9.eE+-]+)\s+(.*)",line)
        if found:
            result.append((float(found.group(1)),found.group(2)))
        elif result:
            when,body=result[-1]
            result[-1]=(when,body+"\n"+line)
    return result


def integrate_system(blocks: list[tuple[float,str]]) -> tuple[list[dict[str,float]],list[int]]:
    current={n:{"ready":1,"assigned":0,"config":0,"flight":0} for n in (0,1)}
    config_owner={}
    for _,text in blocks:
        match=re.search(r"<TEACH-LRU-([AB]),0,BASE-01,0> Reconfiguration item demand arrives from pos <TEACH-AIR-01,BASE-01,(\d+)>",text)
        if match:
            config_owner[match.group(1)]=int(match.group(2))
    measure_names=("NSYRY","NSYMA","NSYMO","NSYMC","NSYMR","NSYA","FTMO","STREQ","STACC")
    def snapshot():
        ready=sum(v["ready"] for v in current.values())
        assigned=sum(v["assigned"] for v in current.values())
        config=sum(v["config"] for v in current.values())
        flight=sum(v["flight"] for v in current.values())
        return {"NSYRY":ready,"NSYMA":assigned,"NSYMO":flight,"NSYMC":config,
                "NSYMR":assigned-config-flight,"NSYA":2,"FTMO":int(flight>0),
                "STREQ":int(flight>0),"STACC":flight}
    def update(text):
        identities=re.findall(r"<TEACH-(AIR-01|CONF-[AB]),(\d+)>",text)
        ids=[int(number) if name=="AIR-01" else config_owner.get(name[-1],int(number))
             for name,number in identities]
        if "mission allocates system:" in text and ids:
            target=current[ids[-1]]
            target["ready"]=0;target["assigned"]=1
        elif "nbr ready increased at unit:" in text and ids:
            target=current[ids[0]]
            target.update(ready=1,assigned=0,config=0,flight=0)
        elif "reconfig started, mission:" in text and ids:
            current[ids[0]]["config"]=1
        elif "reconfig ended, mission:" in text and ids:
            current[ids[0]]["config"]=0
        elif "mission starting," in text:
            for ident in set(ids):
                current[ident]["flight"]=1
        elif "mission success:" in text or "mission cancelled:" in text:
            for target in current.values():
                target["flight"]=0
    result=[];markers=[];cursor=0
    for i in range(72):
        a,b=i*.5,(i+1)*.5
        subtotal={key:0.0 for key in measure_names}
        prev=a;started=0
        while cursor<len(blocks) and blocks[cursor][0]<b-1e-8:
            when,text=blocks[cursor]
            if when>prev:
                for key,value in snapshot().items():
                    subtotal[key]+=value*(when-prev)/.5
                prev=when
            if "reconfig started, mission:" in text and when>=a-1e-8:
                started+=1
            update(text)
            cursor+=1
        for key,value in snapshot().items():
            subtotal[key]+=value*(b-prev)/.5
        result.append(subtotal);markers.append(started)
    return result,markers


def resource_spans(blocks):
    starts=[];ends=[]
    for when,text in blocks:
        if "<MISSION-CREW at <BASE-01,0>> allocated to mission assigned: 1" in text:
            starts.append(when)
        if "<MISSION-CREW at <BASE-01,0>> deallocated from" in text and "mission" in text:
            ends.append(when)
    assert len(starts)==len(ends)
    assert all(end>=start for start,end in zip(starts,ends))
    mission_starts=[when for when,text in blocks if "mission starting," in text]
    mission_ends=[when for when,text in blocks if "mission success:" in text]
    assert len(mission_starts)==len(mission_ends)<=1
    flight=(mission_starts[0],mission_ends[0]) if mission_starts else None
    return list(zip(starts,ends)),flight


def build_expected(arm: str, model_log: Path) -> tuple[dict,dict]:
    reference=tables(CONTROL)
    blocks=timed_blocks(model_log)
    expected={name:[r.copy() for r in rows(t)] for name,t in reference.items()}
    expected["ProblemDescription"][0][0]=(
        "C05.var03 v1.0.2 shared CBSID mission; configuration B needs available crew" if arm=="crew" else
        "C05.var03 v1.0.2 shared CBSID mission; configuration B needs unavailable radio")
    expected["ResultSummary"][0]=[1,0,36,1,0,1,0,1,0,1,0] if arm=="crew" else [1,0,36,0,0,0,0,0,0,0,0]
    system,markers=integrate_system(blocks)
    names=columns(reference["SystemResults"])
    for i,row in enumerate(expected["SystemResults"]):
        for key,value in system[i].items():
            row[names.index(key)]=value
        row[names.index("NRCFG")]=markers[i]
    demands=[when for when,text in blocks if "Reconfiguration item demand arrives" in text]
    stock_names=columns(reference["StockTotalResults"])
    for i,row in enumerate(expected["StockTotalResults"]):
        count=sum(i*.5-1e-8<=when<(i+1)*.5-1e-8 for when in demands)
        row[stock_names.index("NDR")]=count
        row[stock_names.index("NWT")]=count
        for name in ("ROS","ROST","WT","WTT"):
            row[stock_names.index(name)]=0 if count else None
    bookings,flight=resource_spans(blocks)
    resource_names=columns(reference["ResourceResults"])
    total_names=columns(reference["ResourceResultsTotal"])
    hours_assigned=hours_operation=0.0
    for i,row in enumerate(expected["ResourceResults"]):
        a,b=i*.5,(i+1)*.5
        assigned=operation=0.0
        for start,end in bookings:
            first_end=min(end,flight[0]) if flight else end
            assigned+=overlap(a,b,start,first_end)/.5
            if flight:
                operation+=overlap(a,b,max(start,flight[0]),min(end,flight[1]))/.5
        hours_assigned+=assigned*.5
        hours_operation+=operation*.5
        for name,value in (("NR",2),("NRA",2),("NRN",2),("NRMA",assigned),("NRMO",operation)):
            row[resource_names.index(name)]=value
    for name,value in (("NR",2),("NRA",2),("NRN",2),
                       ("NRMA",hours_assigned/36),("NRMO",hours_operation/36)):
        expected["ResourceResultsTotal"][0][total_names.index(name)]=value
    return expected,reference


def equal_cell(actual,expected,field):
    if isinstance(expected,bool) or expected is None or isinstance(expected,str) or isinstance(expected,int):
        return type(actual) is type(expected) and actual==expected
    if not isinstance(actual,(int,float)) or isinstance(actual,bool) or not math.isfinite(actual):
        return False
    tolerance=2e-4 if field in FRACTIONAL else 1e-6
    return abs(actual-expected)<=tolerance


def check_full_report(g,report: Path,model_log: Path,arm: str):
    native=tables(report)
    expected,reference=build_expected(arm,model_log)
    g.check(set(native)==set(SHAPES),"six exact report tables")
    cells=0
    for name,(count,width) in SHAPES.items():
        if name not in native:
            continue
        table=native[name]
        g.check(table["columns"]==reference[name]["columns"],f"{name} column metadata")
        actual_rows=rows(table)
        g.check(len(actual_rows)==count,f"{name} row count")
        names=columns(table)
        for i,want in enumerate(expected[name]):
            if i>=len(actual_rows):
                break
            got=actual_rows[i]
            g.check(len(got)==width,f"{name} row {i} width")
            for j,target in enumerate(want):
                if j<len(got):
                    g.check(equal_cell(got[j],target,names[j]),f"{name}[{i},{names[j]}]: {got[j]!r}!={target!r}")
                    cells+=1
    g.check(cells==5210,f"all 5210 cells compared: {cells}")
    return cells
