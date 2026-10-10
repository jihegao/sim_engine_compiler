"""One-shot freeze of I05.var02 after independent METHOD_ONLY; no native calls."""
import datetime,hashlib,json,subprocess
from pathlib import Path
CASE=Path(__file__).resolve().parent;ROOT=CASE.parents[2]
RESUME=Path(r"C:/Users/user/Documents/Codex/2026-10-10/issue18-cli-20261009T195400Z/resume-20261010T002248Z")
OUT=CASE/"prelaunch-manifest-v100-run01.json"
def seal(p):
 raw=p.read_bytes();return {"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
def read(p):return json.loads(p.read_bytes())
def main():
 if OUT.exists():raise FileExistsError("immutable prelaunch exists")
 contract=read(CASE/"contract.json");method=read(CASE/"method-source-manifest.json")
 review=CASE/"review/independent-method-review-v100-run01.md"
 go=read(CASE/"review/independent-method-go-v100.json")
 if go["decision"]!="GO_METHOD_ONLY" or "GO_METHOD_ONLY" not in review.read_text(encoding="utf-8-sig"):raise ValueError("independent method GO missing")
 sources=[];seen=set()
 def add(key,path,expected=None):
  p=Path(path).resolve(strict=True);actual=seal(p)
  if expected and actual!={k:expected[k] for k in ["bytes","sha256"]}:raise ValueError("pin drift: "+str(p))
  if key in seen:raise ValueError("duplicate source key")
  seen.add(key);sources.append({"key":key,"path":str(p),**actual})
 def walk(d):
  if isinstance(d,dict):
   if {"path","bytes","sha256"}.issubset(d):
    p=Path(d["path"]);p=p if p.is_absolute() else ROOT/p;key="selected:"+str(p.resolve())
    if key not in seen:add(key,p,d)
   for v in d.values():walk(v)
  elif isinstance(d,list):
   for v in d:walk(v)
 head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
 if head!="502f027d3c0193d9c48993de3a07bf6ed9947dd0":raise ValueError("base changed; fresh version required")
 if subprocess.check_output(["git","branch","--show-current"],cwd=ROOT,text=True).strip()!="codex/simlox-i05-var08-pm-location-20261009":raise ValueError("branch differs")
 for p in [contract["candidate"]["physical_directory"],contract["candidate"]["recovered_directory"]]:
  if Path(p).exists():raise ValueError("occupied run directory")
 for entry in method["files"]:add("method:"+entry["path"],CASE/entry["path"],entry)
 for name in ["contract.json","method-source-manifest.json","author_reader.py","check_model.py","run_native_ssh.ps1","ssh_transport.py","make_prelaunch_manifest.py","review/independent-method-review-v100-run01.md","review/independent-method-go-v100.json"]:add("current:"+name,CASE/name)
 walk(read(CASE/"fresh-source-selection.json"))
 walk(read(RESUME/"var02-source-review/independent-source-review-v2.json"))
 for name in ["reception.json","official-scope-ref-readback.json","current-execution-plan.md","var02-author-method-selection-v100.json","var02-author-method-controls.json"]:add("resume:"+name,RESUME/name)
 add("scope:goal-override",RESUME.parent/"goal-scope-current.md")
 for name in ["catalog-v2.json","publication-index-v1.json","execution-plan-nongui-v3.md","ssh-cli-acceptance-policy-v1.md"]:add("scope:"+name,CASE.parent/name)
 for name in ["independent-source-review-v2.json","primary-manual-summary.txt","primary-manual-damage-and-downtime.txt"]:add("primary:"+name,RESUME/"var02-source-review"/name)
 simlox=Path(r"C:/Program Files/Systecon/SIMLOX/Simlox.exe");python=Path(r"C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe")
 doc={"schema":"simlox-i05-var02-prelaunch-manifest/v100","version":"1.0.0","run_id":contract["candidate"]["run_id"],"native_run_directory":contract["candidate"]["physical_directory"],"recovered_run_directory":contract["candidate"]["recovered_directory"],"base_commit":head,"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"status":"FROZEN_PENDING_INDEPENDENT_STATIC","sources":sorted(sources,key=lambda x:x["key"]),"source_count":len(sources),"simlox_exe_sha256":seal(simlox)["sha256"],"python_sha256":seal(python)["sha256"],"runner_sha256":seal(CASE/"run_native_ssh.ps1")["sha256"],"roundtrip_checker_sha256":seal(CASE/"check_model.py")["sha256"],"author_reader_sha256":seal(CASE/"author_reader.py")["sha256"],"method_review_sha256":seal(review)["sha256"],"live_catalog":{"path":str(CASE.parent/"catalog-v2.json"),**seal(CASE.parent/"catalog-v2.json")},"effective_non_gui_denominator":None,"native_calls":0,"all_later_gates_pending":True,"GUI":"preserved process safety only, functionality excluded"}
 OUT.write_bytes((json.dumps(doc,indent=2)+"\n").encode())
 print(json.dumps({"manifest":str(OUT),**seal(OUT),"sources":len(sources),"native_calls":0}))
if __name__=="__main__":main()
