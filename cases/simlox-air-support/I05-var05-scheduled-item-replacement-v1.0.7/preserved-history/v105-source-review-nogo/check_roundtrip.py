#!/usr/bin/env python3
"""Prospective, source-bound I05.var05 roundtrip gate (v1.0.5)."""
from __future__ import annotations
import hashlib, json, math, sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

PACKAGE=Path(__file__).resolve().parent
PARENT=PACKAGE.parent/"H02-var04-item-damage-replacement-fallback-v1.0.0"/"fallback-input.json"
INPUT=PACKAGE/"native-input.json"
CONTRACT=PACKAGE/"contract.json"
PARENT_SHA="2e29c2ea72304544c68281e8629bd242cca3d6252cbbe7cea2c48e0a00716a97"
INPUT_SHA="c30b0849ad46a6351e4c94a2964f0f6f16274b6b926508b8fe47ecd9a5323480"
CONTRACT_SHA="3caee5543f9fa4f30c3986d25b52e6606b4cc95de824351ced9a2bee13771475"
CHANGE_ROW=["TEACH-AIR-01","TEACH-LRU-01","BASE-01",5.0,1.5,None,None,None]
EXPECTED_TABLES=36
EXPECTED_POPULATED=25


def sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_native(path:Path)->dict:
    raw=path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw=raw[3:]
    text=raw.decode("utf-8",errors="strict")
    def pairs(items):
        out={}
        for key,value in items:
            if key in out: raise ValueError(f"duplicate JSON key: {key}")
            out[key]=value
        return out
    return json.loads(text,object_pairs_hook=pairs,parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))


def strict_equal(a:object,b:object)->bool:
    if type(a) is not type(b): return False
    if isinstance(a,dict): return a.keys()==b.keys() and all(strict_equal(a[k],b[k]) for k in a)
    if isinstance(a,list): return len(a)==len(b) and all(strict_equal(x,y) for x,y in zip(a,b))
    return a==b


def double_equal(a:object,b:object)->bool:
    if a is None or b is None: return a is None and b is None
    if isinstance(a,bool) or isinstance(b,bool) or not isinstance(a,(int,float)) or not isinstance(b,(int,float)):
        return False
    if not math.isfinite(float(a)) or not math.isfinite(float(b)): return False
    try: return Decimal(str(a))==Decimal(str(b))
    except (InvalidOperation,ValueError): return False


def row_tables(doc:dict)->dict[str,dict]:
    result={}
    for table in doc["model"]["tables"]:
        name=table["name"]
        if name in result: raise ValueError(f"duplicate table: {name}")
        result[name]=table
    return result


def compare_cell(value:object,actual:object,datatype:str)->bool:
    return double_equal(value,actual) if datatype=="double" else strict_equal(value,actual)


def compare_documents(source:dict,exported:dict)->tuple[list[str],dict[str,int]]:
    issues=[]
    counts={"table_count":0,"authored_populated_tables":0,"empty_tables":0,"double_representation_changes":0,"null_placeholders":0}
    try: before=source["model"]["tables"]; after=exported["model"]["tables"]
    except (KeyError,TypeError): return ["model.tables missing or malformed"],counts
    counts["table_count"]=len(before)
    if len(before)!=EXPECTED_TABLES: issues.append(f"authored table count {len(before)} != {EXPECTED_TABLES}")
    if len(after)!=len(before): issues.append(f"export table count {len(after)} != authored {len(before)}")
    if [t.get("name") for t in before] != [t.get("name") for t in after]: issues.append("table names/order differ")
    try: source_by_name=row_tables(source); export_by_name=row_tables(exported)
    except (KeyError,TypeError,ValueError) as exc: return issues+[f"invalid table map: {exc}"],counts
    if len(source_by_name)!=len(before) or len(export_by_name)!=len(after): issues.append("duplicate table names")
    if set(source_by_name)!=set(export_by_name): issues.append("export table-name set differs")
    for index,src in enumerate(before):
        name=src["name"]
        if name not in export_by_name: continue
        out=export_by_name[name]
        if not strict_equal(src.get("columns"),out.get("columns")): issues.append(f"column metadata changed in {name}");continue
        src_instances=src.get("instances",[]); out_instances=out.get("instances",[])
        if len(src_instances)!=len(out_instances): issues.append(f"instance count changed in {name}");continue
        table_has_rows=any(si.get("rows",[]) for si in src_instances)
        if table_has_rows: counts["authored_populated_tables"]+=1
        else: counts["empty_tables"]+=1
        for ii,(si,oi) in enumerate(zip(src_instances,out_instances)):
            if not strict_equal({k:v for k,v in si.items() if k!="rows"},{k:v for k,v in oi.items() if k!="rows"}):
                issues.append(f"instance metadata changed in {name}[{ii}]");continue
            sr=si.get("rows",[]); er=oi.get("rows",[]); cols=src["columns"]
            if sr:
                if len(sr)!=len(er): issues.append(f"row count changed in {name}[{ii}]");continue
                for ri,(srow,erow) in enumerate(zip(sr,er)):
                    if len(srow)!=len(cols) or len(erow)!=len(cols): issues.append(f"row width changed in {name}[{ii}][{ri}]");continue
                    for ci,(sv,ev) in enumerate(zip(srow,erow)):
                        dtype=cols[ci].get("datatype") if isinstance(cols[ci],dict) else None
                        if not compare_cell(sv,ev,dtype): issues.append(f"cell changed in {name}[{ii}][{ri}][{ci}]")
                        elif dtype=="double" and type(sv) is not type(ev): counts["double_representation_changes"]+=1
            else:
                null_row=[None]*len(cols)
                if er==[null_row]:
                    if ii==0: counts["null_placeholders"]+=1
                else: issues.append(f"empty table serialization differs in {name}[{ii}]")
    if counts["authored_populated_tables"]!=EXPECTED_POPULATED: issues.append(f"authored populated table count {counts['authored_populated_tables']} != {EXPECTED_POPULATED}")
    if counts["empty_tables"]+counts["authored_populated_tables"]!=EXPECTED_TABLES: issues.append("populated/empty table partition is incomplete")
    if "ChangesItemReplacement" in export_by_name:
        change=export_by_name["ChangesItemReplacement"]
        if before[-1].get("name")!="ChangesItemReplacement": issues.append("scheduled change table is not appended last")
        if len(change.get("instances",[]))!=1: issues.append("change table instance count differs")
        else:
            rowset=change["instances"][0].get("rows",[])
            if len(rowset)!=1 or len(rowset[0])!=len(CHANGE_ROW): issues.append("exact scheduled change row shape differs")
            else:
                for i,(expected,actual) in enumerate(zip(CHANGE_ROW,rowset[0])):
                    dtype=change["columns"][i].get("datatype")
                    if not compare_cell(expected,actual,dtype): issues.append(f"exact scheduled change row differs at column {i}")
    else: issues.append("exported ChangesItemReplacement absent")
    return issues,counts


def main()->None:
    if sha(PARENT)!=PARENT_SHA or sha(INPUT)!=INPUT_SHA or sha(CONTRACT)!=CONTRACT_SHA:
        raise SystemExit("frozen parent/input/contract hash mismatch")
    argv=sys.argv[1:]
    if len(argv)!=4: raise SystemExit("usage: check_roundtrip.py INPUT EXPORT IMPORT_LOG EXPORT_LOG")
    import_path,export_path=map(Path,argv[:2])
    if sha(import_path)!=INPUT_SHA: raise SystemExit("run input byte hash differs from frozen source")
    source=parse_native(import_path); exported=parse_native(export_path)
    import_log=Path(argv[2]).read_text(encoding="utf-8-sig",errors="replace")
    export_log=Path(argv[3]).read_text(encoding="utf-8-sig",errors="replace")
    issues,counts=compare_documents(source,exported)
    if "Import completed!" not in import_log: issues.append("import completion marker absent")
    if "Export completed!" not in export_log: issues.append("export completion marker absent")
    if issues: raise SystemExit("ROUNDTRIP_NO_GO: "+"; ".join(issues))
    print(json.dumps({"schema":"i05-var05-roundtrip/v2","status":"PASS_AUTHORED_CONTENT_WITH_DECLARED_NATIVE_ENCODING","input_sha256":INPUT_SHA,"export_sha256":sha(export_path),**counts,"native_actions":0,"issues":[]},sort_keys=True))

if __name__=="__main__": main()
