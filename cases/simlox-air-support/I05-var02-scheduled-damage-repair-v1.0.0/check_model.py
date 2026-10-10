"""Exact restricted input and full parent-generated roundtrip contract; no native calls."""
import copy,json,math,sys
from pathlib import Path
from author_reader import C,P,typed,norm,parentraw
H=Path(__file__).resolve().parent
def expected():
 p=P["parent_source"];raw=Path(p["path"]).read_bytes()
 from author_reader import sha
 if len(raw)!=p["bytes"] or sha(raw)!=p["sha256"]:raise ValueError("parent source pin drift")
 d=json.loads(raw)
 next(t for t in d["model"]["tables"] if t["name"]=="ProblemDescription")["instances"][0]["rows"][0][0]=C["candidate"]["description"]
 d["model"]["tables"].append(C["delta"]["table"])
 return d
def validate_source(doc):
 if not typed(doc,expected()):raise ValueError("unknown/different/unsupported source outside exact scalar profile")
 return True
def model_equal(a,b):
 if not typed(a["columns"],b["columns"]) or not typed(a.keys(),b.keys()):raise ValueError("column/table metadata differs")
 if a["name"]!=b["name"] or len(a["instances"])!=len(b["instances"]):raise ValueError("table identity")
 for ia,ib in zip(a["instances"],b["instances"]):
  if ia.keys()!=ib.keys() or ia["instance_name"]!=ib["instance_name"] or len(ia["rows"])!=len(ib["rows"]):raise ValueError("instance topology")
  for ra,rb in zip(ia["rows"],ib["rows"]):
   if len(ra)!=len(a["columns"]) or len(rb)!=len(b["columns"]):raise ValueError("row width")
   for x,y,c in zip(ra,rb,a["columns"]):
    if c["datatype"]=="double" and x is not None:
     if type(y) not in (int,float) or not math.isfinite(y) or y!=x:raise ValueError("double cell drift")
    elif not typed(x,y):raise ValueError("typed model cell drift")
def check_export(source,export):
 validate_source(source);raw=parentraw()
 parent=json.loads(norm(raw["roundtrip-raw.json"]))
 if set(export)!=set(parent) or set(export["model"])!=set(parent["model"]):raise ValueError("model root metadata drift")
 for k,v in parent["model"].items():
  if k!="tables" and not typed(v,export["model"][k]):raise ValueError("database metadata drift")
 a=copy.deepcopy(parent["model"]["tables"]);b=export["model"]["tables"]
 next(t for t in a if t["name"]=="ProblemDescription")["instances"][0]["rows"][0][0]=C["candidate"]["description"]
 a.append(C["delta"]["table"])
 bm={t["name"]:t for t in b}
 if len(bm)!=len(b) or set(bm)!={t["name"] for t in a}:raise ValueError("added/missing/duplicate table")
 if [t["name"] for t in b if t["name"]!="ChangesDamageRepair"]!=[t["name"] for t in parent["model"]["tables"]]:raise ValueError("parent native table relative order drift")
 for t in a:model_equal(t,bm[t["name"]])
 authored=[t for t in source["model"]["tables"] if any(i["rows"] for i in t["instances"])]
 return {"authored_row_bearing_tables":len(authored),"authored_cells":sum(len(t["columns"])*len(i["rows"]) for t in authored for i in t["instances"]),"all_export_tables":len(b),"parent_native_tables_full_metadata_rows":len(a)-1,"native_generated_row_bearing_tables":sorted({t["name"] for t in b}-{t["name"] for t in authored}),"new_table_index_observed":next(i for i,t in enumerate(b) if t["name"]=="ChangesDamageRepair")}
def selfcheck():
 base=expected();checks={"exact_source_positive":validate_source(base)}
 def row(d):return next(t for t in d["model"]["tables"] if t["name"]=="ChangesDamageRepair")["instances"][0]["rows"][0]
 for name,i,val in [("damage_ref",0,"NO-DAMAGE"),("system_ref",1,"NO-SYS"),("station_ref",2,"NO-STATION"),("nonpositive_time",3,0),("bool_time",3,True),("duration",4,2.0),("fraction",6,0.5),("distribution",8,"DIST-X"),("inprogress",3,9.3)]:
  m=copy.deepcopy(base);row(m)[i]=val
  try:validate_source(m)
  except ValueError:checks[name]=True
  else:checks[name]=False
 parent=json.loads(norm(parentraw()["roundtrip-raw.json"]));m=copy.deepcopy(parent)
 next(t for t in m["model"]["tables"] if t["name"]=="ProblemDescription")["instances"][0]["rows"][0][0]=C["candidate"]["description"]
 m["model"]["tables"].append(C["delta"]["table"])
 checks["synthetic_parent_roundtrip_plus_change_positive"]=bool(check_export(base,m))
 mutant=copy.deepcopy(m);next(t for t in mutant["model"]["tables"] if t["name"]=="Tasks")["instances"][0]["rows"][0][0]="CHANGED-DEFAULT"
 try:check_export(base,mutant)
 except ValueError:checks["native_default_task_drift_negative"]=True
 else:checks["native_default_task_drift_negative"]=False
 mutant=copy.deepcopy(m);mutant["model"]["tables"][-1]["columns"][0]["key"]=1
 try:check_export(base,mutant)
 except ValueError:checks["change_key_bool_int_negative"]=True
 else:checks["change_key_bool_int_negative"]=False
 if not all(checks.values()):raise AssertionError(checks)
 return {"decision":"GO_AUTHOR_SOURCE_CONTROLS_ONLY","checks":checks,"checks_total":len(checks),"roundtrip":check_export(base,m),"native_calls":0}
def main():
 if sys.argv[1:]==["--self-check"]:return selfcheck()
 if len(sys.argv)!=2:raise ValueError("requires --self-check or run directory")
 r=Path(sys.argv[1])
 if (r/"input.json").read_bytes()!=(H/"native-input.json").read_bytes():raise ValueError("run input byte drift")
 for name,marker in [("import.log","Import completed!"),("export.log","Export completed!")]:
  if marker not in (r/name).read_text(encoding="utf-8-sig"):raise ValueError("missing completion")
 return {"passed":True,**check_export(json.loads((r/"input.json").read_bytes()),json.loads(norm((r/"roundtrip-raw.json").read_bytes())))}
if __name__=="__main__":
 try:print(json.dumps(main(),sort_keys=True))
 except (ValueError,OSError,KeyError,TypeError,IndexError,AssertionError,StopIteration) as e:print(json.dumps({"passed":False,"error":str(e)}));sys.exit(1)
