"""Restricted full raw read-only replay; projections are hypotheses until native acceptance."""
import argparse,copy,hashlib,json,math,re,sys
from pathlib import Path
H=Path(__file__).resolve().parent
def load(name):return json.loads((H/name).read_bytes())
C=load("contract.json");P=load("parent-evidence-pins.json");E=load("event-oracle.json");O=load("report-oracle.json")
def sha(b):return hashlib.sha256(b).hexdigest()
def norm(raw):
 text=raw.decode("utf-8-sig");out=[];quoted=False;escaped=False
 for i,ch in enumerate(text):
  if quoted:
   out.append(ch)
   if escaped:escaped=False
   elif ch=="\\":escaped=True
   elif ch=='"':quoted=False
  elif ch=='"':quoted=True;out.append(ch)
  elif ch==",":
   j=i+1
   while j<len(text) and text[j].isspace():j+=1
   if j==len(text) or text[j] not in "}]":out.append(ch)
  else:out.append(ch)
 return "".join(out).encode()
def typed(a,b):
 if type(a) is not type(b):return False
 if isinstance(b,dict):return a.keys()==b.keys() and all(typed(a[k],b[k]) for k in b)
 if isinstance(b,list):return len(a)==len(b) and all(typed(x,y) for x,y in zip(a,b))
 return a==b
def parentraw():
 r=Path(P["parent_run"]);out={}
 for pin in P["parent_raw_12"]:
  p=Path(pin["path"]);raw=p.read_bytes()
  if len(raw)!=pin["bytes"] or sha(raw)!=pin["sha256"]:raise ValueError("parent raw pin drift: "+str(p))
  out[p.name]=raw
 return out
def expected_log(raw):
 lines=raw.splitlines(keepends=True)
 if len(lines)!=E["physical_lines"]:raise ValueError("parent physical count drift")
 for c in E["line_substitutions"]:
  i=c["physical_line_1based"]-1;body=lines[i].rstrip(b"\r\n")
  if body!=c["parent"].encode():raise ValueError("parent exact line drift")
  lines[i]=c["child"].encode()+lines[i][len(body):]
 return b"".join(lines)
def parse_report(raw):
 d=json.loads(norm(raw))
 if set(d)!={"report"} or set(d["report"])!={"tables"}:raise ValueError("report schema")
 return d
def ledger(log):
 text=log.decode("utf-8-sig").replace("\r\n","\n").replace("\r","\n")
 start=re.findall(r"^Time: ([\d.]+)  system DIRP task (\d+) on <TEACH-AIR-01,0> started$",text,re.M)
 end=re.findall(r"^Time: ([\d.]+)  system DIRP task (\d+) on <TEACH-AIR-01,0> completed$",text,re.M)
 work=re.findall(r"^Time: ([\d.]+)  direct repair subtask (\d+) seqno 0 within system DIRP task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for ([\d.]+) hours$",text,re.M)
 if len(start)!=3 or len(end)!=3 or len(work)!=3:raise ValueError("missing/duplicate repair events")
 periods=[]
 for (s,i),(e,j),(ws,k,d) in zip(start,end,work):
  if i!=j or i!=k or s!=ws or abs(float(e)-float(s)-float(d))>0.0001:raise ValueError("inconsistent rounded event ledger")
  periods.append({"task":i,"start":s,"end":e,"duration_hours":float(d),"display_time_rounding_tolerance_hours":0.0001})
 return periods
def reconcile(report,log):
 tables=report["report"]["tables"]
 def rows(name):
  t=next(t for t in tables if t["name"]==name);ns=[c["name"] for c in t["columns"]]
  return [dict(zip(ns,r)) for i in t["instances"] for r in i["rows"]]
 s=rows("SystemResults");stock=rows("StockTotalResults")
 periods=ledger(log);hours=sum(p["duration_hours"] for p in periods)
 occupancy=sum((r["ETINT"]-r["STINT"])*r["NSYRP"] for r in s)
 registered=sum(r["SYDT"]*r["NSYDT"] for r in s if r["SYDT"] is not None)
 if len(s)!=72 or len(stock)!=72 or abs(occupancy-hours)>1e-6 or registered!=hours:raise ValueError("occupancy/start-registered downtime ledger mismatch")
 for r in s:
  starts=[p for p in periods if r["STINT"]<=float(p["start"])<r["ETINT"]]
  if r["NSYDT"]!=len(starts):raise ValueError("downtime count not start registered")
  expected=sum(p["duration_hours"] for p in starts)/len(starts) if starts else None
  # Exporter emits integral durations as integer tokens; full typed comparison checks exact representation.
  if r["SYDT"]!=expected:raise ValueError("downtime duration differs")
 if sum(r["NDAM"] for r in s)!=3 or sum(r["NREPT"] for r in s)!=3:raise ValueError("damage/completion counts")
 if s[-1]["NSYRY"]!=1 or s[-1]["NSYLA"]!=0 or s[-1]["NSYRP"]!=0:raise ValueError("terminal state")
 totals={n:sum(r[n] or 0 for r in stock) for n in ["NBO","NDD","NDR","NDP","NLD"]}
 if any(totals.values()):raise ValueError("unexpected stock activity")
 return {"periods":periods,"occupied_aircraft_hours":occupancy,"registered_downtime_hours":registered,"repair_count":3,"damage_count":3,"stock_totals":totals,"terminal_ready":1,"terminal_lost":0}
def validate(log,report,arm):
 parent=parentraw()
 expectedlog=parent["model.log"] if arm=="parent" else expected_log(parent["model.log"])
 expected=load("parent-report-projection.json")["report"] if arm=="parent" else O["expected_report"]
 if log!=expectedlog:return False
 actual=parse_report(report)
 if not typed(actual,expected):return False
 count=sum(len(t["columns"])*len(i["rows"]) for t in actual["report"]["tables"] for i in t["instances"])
 if count!=4044:return False
 reconcile(actual,log)
 return True
def selfcheck():
 raw=parentraw();pl=raw["model.log"];pr=raw["report-raw.json"]
 cl=expected_log(pl);cr=json.dumps(O["expected_report"],ensure_ascii=False).encode()
 checks={"parent_positive":validate(pl,pr,"parent"),"synthetic_child_positive":validate(cl,cr,"child"),"parent_not_child":not validate(pl,pr,"child"),"synthetic_not_parent":not validate(cl,cr,"parent")}
 for c in E["line_substitutions"]:
  ls=cl.splitlines(keepends=True);i=c["physical_line_1based"]-1;body=ls[i].rstrip(b"\r\n");ls[i]=c["parent"].encode()+ls[i][len(body):]
  checks["event_restore_"+str(i+1)]=not validate(b"".join(ls),cr,"child")
 base=load("parent-report-projection.json")["report"];expected=O["expected_report"]
 mutations=[]
 for ti,(t,u) in enumerate(zip(base["report"]["tables"],expected["report"]["tables"])):
  for ii,(inst,ins2) in enumerate(zip(t["instances"],u["instances"])):
   for ri,(a,b) in enumerate(zip(inst["rows"],ins2["rows"])):
    for ci,(x,y) in enumerate(zip(a,b)):
     if not typed(x,y):
      m=copy.deepcopy(expected);m["report"]["tables"][ti]["instances"][ii]["rows"][ri][ci]=x
      key=f"report_restore_{ti}_{ii}_{ri}_{ci}"
      checks[key]=not validate(cl,json.dumps(m).encode(),"child");mutations.append(key)
 assert len(mutations)==34
 checks["extra_line"]=not validate(cl+b"unexpected\r\n",cr,"child")
 checks["line_ending_drift"]=not validate(cl.replace(b"\r\n",b"\n",1),cr,"child")
 m=copy.deepcopy(expected);t=next(t for t in m["report"]["tables"] if t["name"]=="SystemResults");t["columns"][0]["key"]=1
 checks["metadata_bool_int_alias"]=not validate(cl,json.dumps(m).encode(),"child")
 m=copy.deepcopy(expected);t=next(t for t in m["report"]["tables"] if t["name"]=="StockTotalResults");cols=[c["name"] for c in t["columns"]];t["instances"][0]["rows"][0][cols.index("NBO")]=False
 checks["stock_int_bool_alias"]=not validate(cl,json.dumps(m).encode(),"child")
 m=copy.deepcopy(expected);t=next(t for t in m["report"]["tables"] if t["name"]=="SystemResults");cols=[c["name"] for c in t["columns"]];t["instances"][0]["rows"][0][cols.index("NSYRY")]=1.0
 checks["system_int_float_alias"]=not validate(cl,json.dumps(m).encode(),"child")
 checks["quoted_comma_preserved"]=json.loads(norm(b'{"literal":",] ,}","a":[1,],}'))=={"literal":",] ,}","a":[1]}
 if not all(checks.values()):raise AssertionError([k for k,v in checks.items() if not v])
 return {"decision":"GO_AUTHOR_METHOD_CONTROLS_ONLY","checks_total":len(checks),"checks":checks,"report_delta_mutations":mutations,"ledger":reconcile(parse_report(cr),cl),"native_calls":0,"synthetic_positive_is_not_native_acceptance":True}
def main():
 p=argparse.ArgumentParser();p.add_argument("--self-check",action="store_true");p.add_argument("--arm",choices=["parent","child"]);p.add_argument("--model-log",type=Path);p.add_argument("--report",type=Path);a=p.parse_args()
 if a.self_check:return selfcheck()
 if not a.arm or not a.model_log or not a.report:raise ValueError("requires arm/model-log/report")
 log=a.model_log.read_bytes();report=a.report.read_bytes();passed=validate(log,report,a.arm)
 return {"decision":"GO_AUTHOR_RAW_REPLAY" if passed else "NO_GO","arm":a.arm,"model_log_sha256":sha(log),"report_sha256":sha(report),"full_typed_report_and_log_passed":passed,"ledger":reconcile(parse_report(report),log) if passed else None}
if __name__=="__main__":
 try:
  d=main();print(json.dumps(d,ensure_ascii=False,sort_keys=True));sys.exit(1 if d["decision"]=="NO_GO" else 0)
 except (OSError,ValueError,KeyError,TypeError,IndexError,AssertionError,StopIteration) as e:
  print(json.dumps({"decision":"NO_GO","error":str(e)}));sys.exit(1)
