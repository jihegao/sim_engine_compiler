"""Freeze new I05.var09 sources once, preserving prior immutable selections."""
import pathlib,json,hashlib,datetime,subprocess
CASE=pathlib.Path(__file__).resolve().parent;ROOT=CASE.parents[2]
RESUME=pathlib.Path(r'C:/Users/user/Documents/Codex/2026-10-10/issue18-cli-20261009T195400Z/resume-20261009T221148Z')
OUT=CASE/'prelaunch-manifest-v100-run01.json'
def seal(p):b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
 if OUT.exists():raise FileExistsError('frozen manifest exists')
 contract=load(CASE/'contract.json');method=load(CASE/'method-source-manifest.json');sources=[];seen=set()
 def add(key,path,expected=None):
  p=pathlib.Path(path).resolve(strict=True);actual=seal(p)
  if expected and actual!={k:expected[k] for k in ['bytes','sha256']}:raise ValueError('source drift: '+str(p))
  if key in seen:raise ValueError('duplicate key')
  seen.add(key);sources.append({'key':key,'path':str(p),**actual})
 def walk(obj):
  if isinstance(obj,dict):
   if {'path','bytes','sha256'}.issubset(obj):
    p=pathlib.Path(obj['path'])
    if not p.is_absolute():p=ROOT/p
    key='selected:'+str(p.resolve())
    if key not in seen:add(key,p,obj)
   for v in obj.values():walk(v)
  elif isinstance(obj,list):
   for v in obj:walk(v)
 head=subprocess.run(['git','-C',str(ROOT),'rev-parse','HEAD'],check=True,capture_output=True,text=True).stdout.strip()
 assert head=='33b35ba73151bb44c36b5599a498ffdeeff1e4c4'
 assert subprocess.run(['git','-C',str(ROOT),'branch','--show-current'],check=True,capture_output=True,text=True).stdout.strip()=='codex/simlox-i05-var08-pm-location-20261009'
 physical=contract['candidate']['physical_directory'];assert not pathlib.Path(physical).exists() and not (CASE/'runs'/contract['candidate']['run_id']).exists()
 for row in method['files']:add('method:'+row['path'],CASE/row['path'],row)
 for name in ['contract.json','method-source-manifest.json','check_model.py','author_reader.py','run_native_ssh.ps1','ssh_transport.py','make_prelaunch_manifest.py','review/independent-method-review-v100-run01.md','review/independent-method-go-v100.json']:add('current:'+name,CASE/name)
 walk(load(RESUME/'var09-source-review/independent-source-selection-v2.json'))
 for p in ['reception.json','issue18-current-scope-source-v3.json','scope-alignment-v3.json','var09-author-method-selection-v100-v2.json','var09-method-review/independent-method-go-v100.json']:add('resume:'+p,RESUME/p)
 for p in ['execution-plan-nongui-v3.md','catalog-v2.json','publication-index-v1.json']:add('scope:'+p,CASE.parent/p)
 add('scope:goal-override',RESUME.parent/'goal-scope-current.md')
 review=CASE/'review/independent-method-review-v100-run01.md';assert 'GO_METHOD_ONLY' in review.read_text(encoding='utf-8')
 simlox=pathlib.Path(r'C:/Program Files/Systecon/SIMLOX/Simlox.exe');python=pathlib.Path(r'C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe')
 doc={'schema':'simlox-i05-var09-prelaunch-manifest/v100','version':'1.0.0','run_id':contract['candidate']['run_id'],'native_run_directory':physical,'recovered_run_directory':str(CASE/'runs'/contract['candidate']['run_id']),'base_commit':head,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'FROZEN_PENDING_INDEPENDENT_STATIC','sources':sorted(sources,key=lambda v:v['key']),'source_count':len(sources),'simlox_exe_sha256':seal(simlox)['sha256'],'python_sha256':seal(python)['sha256'],'runner_sha256':seal(CASE/'run_native_ssh.ps1')['sha256'],'roundtrip_checker_sha256':seal(CASE/'check_model.py')['sha256'],'author_reader_sha256':seal(CASE/'author_reader.py')['sha256'],'method_review_sha256':seal(review)['sha256'],'live_catalog':{'path':str(CASE.parent/'catalog-v2.json'),**seal(CASE.parent/'catalog-v2.json')},'effective_non_gui_denominator':None,'native_calls':0,'all_later_gates_pending':True,'original_GUI_preservation':'process safety only, no GUI functionality verification'}
 OUT.write_bytes((json.dumps(doc,indent=2)+'\n').encode());print(json.dumps({'manifest':str(OUT),**seal(OUT),'source_count':len(sources),'native_calls':0}))
if __name__=='__main__':main()