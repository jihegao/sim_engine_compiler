import json,hashlib,datetime,subprocess
from pathlib import Path
C=Path(__file__).resolve().parent;W=C.parents[2];R=Path(r'C:/Users/user/Documents/Codex/2026-10-10/issue18-cli-20261009T195400Z/resume-20261010t032847z');OUT=C/'prelaunch-manifest-v100-run01.json'
def pin(p):b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def read(p):return json.loads(p.read_bytes())
def main():
 if OUT.exists():raise FileExistsError('immutable manifest alreadyexists')
 c=read(C/'contract.json');m=read(C/'method-source-manifest.json');g=read(C/'review/independent-method-go-v100.json');head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()
 if head!='f17db3edc6d38216ede99f5c418eb209e522a037':raise ValueError('actualbasechanged')
 if subprocess.check_output(['git','branch','--show-current'],cwd=W,text=True).strip()!='codex/simlox-i05-var08-pm-location-20261009':raise ValueError('branchdiffers')
 if g.get('decision')!='GO_METHOD_ONLY':raise ValueError('independentmethodGOmissing')
 if pin(C/'review/independent-method-go-v100.json')['sha256']!='0b9f2bbe0ea220da58583fd27fb23278001e28f7f45afadb8d44e9a6d0c3a9f8':raise ValueError('methodreceiptchanged')
 for p in [c['candidate']['physical_directory'],c['candidate']['recovered_directory']]:
  if Path(p).exists():raise ValueError('unique run occupied')
 sources=[];seen=set()
 def add(key,path,expected=None):
  p=Path(path).resolve(strict=True);v=pin(p)
  if expected and v!={k:expected[k] for k in ['bytes','sha256']}:raise ValueError('pindrift '+str(p))
  if key in seen:return
  sources.append({'key':key,'path':str(p),**v});seen.add(key)
 def walk(x):
  if isinstance(x,dict):
   if {'path','bytes','sha256'}.issubset(x):
    p=Path(x['path'])
    if not p.is_absolute():raise ValueError('relative selectedpin '+str(p))
    add('selected:'+str(p.resolve()),p,x)
   for k,v in x.items():
    if k!='historical':walk(v)
  elif isinstance(x,list):
   for v in x:walk(v)
 for e in m['files']:add('method:'+e['path'],C/e['path'],e)
 for n in ['contract.json','method-source-manifest.json','run_native_ssh.ps1','ssh_transport.py','check_model.py','author_reader.py','make_prelaunch_manifest.py','review/independent-method-review-v100-run01.md','review/independent-method-go-v100.json']:add('current:'+n,C/n)
 walk(read(C/'fresh-source-selection.json'))
 for n in ['reception.json','official-scope-and-refs.json','official-Issue18-body-current.md','official-body-byte-receipt.json','current-execution-plan.md','var10-turnround-prestart-method-v1/method-manifest-v1.json','var10-method-review/independent-method-go-v1.json']:add('resume:'+n,R/n)
 add('scope:override',R.parent/'goal-scope-current.md')
 for n in ['catalog-v2.json','publication-index-v1.json','execution-plan-nongui-v3.md','ssh-cli-acceptance-policy-v1.md']:add('scope:'+n,C.parent/n)
 exe=Path(r'C:/Program Files/Systecon/SIMLOX/Simlox.exe');py=Path(r'C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe');review=C/'review/independent-method-review-v100-run01.md'
 doc={'schema':'simlox-i05-var10-prelaunch-manifest/v100','version':'1.0.0','run_id':c['candidate']['run_id'],'native_run_directory':c['candidate']['physical_directory'],'recovered_run_directory':c['candidate']['recovered_directory'],'base_commit':head,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'FROZEN_PENDING_INDEPENDENT_STATIC','sources':sorted(sources,key=lambda e:e['key']),'source_count':len(sources),'simlox_exe_sha256':pin(exe)['sha256'],'python_sha256':pin(py)['sha256'],'runner_sha256':pin(C/'run_native_ssh.ps1')['sha256'],'roundtrip_checker_sha256':pin(C/'check_model.py')['sha256'],'author_reader_sha256':pin(C/'author_reader.py')['sha256'],'method_review_sha256':pin(review)['sha256'],'live_catalog':{'path':str(C.parent/'catalog-v2.json'),**pin(C.parent/'catalog-v2.json')},'native_calls':0,'effective_non_gui_denominator':None,'all_later_gates_pending':True,'GUI':'process safety only; functionality excluded'}
 OUT.write_bytes((json.dumps(doc,indent=2)+'\n').encode());print(json.dumps({'manifest':str(OUT),**pin(OUT),'source_roles':len(sources),'native_calls':0}))
if __name__=='__main__':main()
