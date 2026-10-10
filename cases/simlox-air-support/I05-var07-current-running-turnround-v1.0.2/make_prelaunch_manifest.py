import json,hashlib,datetime,subprocess
from pathlib import Path
C=Path(__file__).resolve().parent;W=C.parents[2];R=Path('C:/Users/user/Documents/Codex/2026-10-10/issue18-cli-20261009T195400Z/resume-20261010T114528Z');OUT=C/'prelaunch-manifest-v102-run01.json'
def pin(p):b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def main():
 assert not OUT.exists(),'immutable manifest exists';c=json.loads((C/'contract.json').read_bytes());m=json.loads((C/'method-source-manifest.json').read_bytes());g=C/'review/independent-method-go-v102.json'
 assert pin(g)['sha256']=='12a48adec05401f1353b8d78677e8992c6e48d6f6a8023d6065b040340981751';assert 'GO_METHOD_ONLY' in g.read_text(encoding='utf-8-sig')
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip();assert head=='d2d6e6f822d93814aa428e1b8fcdf7baad401d71';assert subprocess.check_output(['git','branch','--show-current'],cwd=W,text=True).strip()=='codex/simlox-i05-var08-pm-location-20261009'
 for n in ['physical_directory','recovered_directory']:assert not Path(c['candidate'][n]).exists()
 sources=[];seen=set()
 def add(k,p,e=None):
  p=Path(p).resolve(strict=True);v=pin(p)
  if e:assert v=={n:e[n] for n in ['bytes','sha256']},str(p)
  if k in seen:return
  sources.append({'key':k,'path':str(p),**v});seen.add(k)
 for e in m['files']:add('current:'+e['path'],C/e['path'],e)
 add('current:method-source-manifest.json',C/'method-source-manifest.json')
 def walk(x):
  if isinstance(x,dict):
   if {'path','bytes','sha256'}.issubset(x):
    p=Path(x['path']);assert p.is_absolute(),str(p);add('selected:'+str(p.resolve()),p,x)
   for v in x.values():walk(v)
  elif isinstance(x,list):
   for v in x:walk(v)
 walk(json.loads((C/'fresh-source-selection.json').read_bytes()))
 for n in ['binding.json','prompt.md','reception.json','reception-pin-alignment-v2.json','official-Issue18-body-current.md','official-scope-current.json','current-execution-plan-v2.md','source-construction-failure-v1.json','var07-current-main-method-v1/method-manifest-v1.json','var07-method-review/independent-method-go-v1.json','var07-method-review/terminal-method-review-v1.json']:add('resume:'+n,R/n)
 add('scope:override',R.parent/'goal-scope-current.md')
 add('historical:v101-manifest',Path(c['transport_binding_recovery']['failed_v101_manifest']['path']),c['transport_binding_recovery']['failed_v101_manifest'])
 add('historical:v100-static',C/'preserved-v100-static-no-go.json')
 add('historical:v100-manifest',Path(c['execution_recovery']['old_frozen_manifest']['path']),c['execution_recovery']['old_frozen_manifest'])
 for n in ['catalog-v2.json','publication-index-v1.json','execution-plan-nongui-v3.md','ssh-cli-acceptance-policy-v1.md']:add('scope:'+n,C.parent/n)
 exe=Path('C:/Program Files/Systecon/SIMLOX/Simlox.exe');py=Path('C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe')
 d={'schema':'simlox-i05-var07-current-prelaunch-manifest/v102','version':'1.0.2','run_id':c['candidate']['run_id'],'native_run_directory':c['candidate']['physical_directory'],'recovered_run_directory':c['candidate']['recovered_directory'],'base_commit':head,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'FROZEN_PENDING_INDEPENDENT_STATIC','sources':sorted(sources,key=lambda e:e['key']),'source_count':len(sources),'simlox_exe_sha256':pin(exe)['sha256'],'python_sha256':pin(py)['sha256'],'runner_sha256':pin(C/'run_native_ssh.ps1')['sha256'],'roundtrip_checker_sha256':pin(C/'check_model.py')['sha256'],'author_reader_sha256':pin(C/'author_reader.py')['sha256'],'method_review_sha256':pin(g)['sha256'],'live_catalog':{'path':str(C.parent/'catalog-v2.json'),**pin(C.parent/'catalog-v2.json')},'native_calls':0,'effective_non_gui_denominator':None,'all_later_gates_pending':True,'GUI':'process safety only; functionality excluded'}
 OUT.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8');print(json.dumps({'manifest':str(OUT),**pin(OUT),'roles':len(sources),'native_calls':0}))
if __name__=='__main__':main()
