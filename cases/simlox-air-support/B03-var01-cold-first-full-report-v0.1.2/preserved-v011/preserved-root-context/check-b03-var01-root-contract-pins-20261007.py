from pathlib import Path
import hashlib,json,subprocess,stat
root=Path(__file__).resolve().parents[1]
pkg=root/'cases/simlox-air-support/B03-var01-cold-first-full-report-v0.1.0'
c=json.loads((pkg/'contract.json').read_text(encoding='utf-8'))
checks=[]
def check(b,p,label):
 actual={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
 assert actual==p,(label,actual,p)
 checks.append(label)
for rec in c['accepted_source_files']:
 check((root/rec['path']).read_bytes(),rec['local_disk'],'disk:'+rec['path'])
 check(subprocess.check_output(['git','show',c['base_commit']+':'+rec['path']],cwd=root),rec['published_git_at_base'],'git:'+rec['path'])
for rec in c['installed'].values():check(Path(rec['path']).read_bytes(),{k:rec[k] for k in ['bytes','sha256']},rec['path'])
for run in c['parent_runs']:
 d=Path(run['original_directory'])
 for field,filename in [('closure','closure.json'),('invocation','invocation.json')]:check((d/filename).read_bytes(),run[field],run['run_id']+'/'+filename)
 for group in ['raw','other_local_files']:
  for filename,pin in run[group].items():check((d/filename).read_bytes(),pin,run['run_id']+'/'+filename)
 closure=json.loads((d/'closure.json').read_text(encoding='utf-8-sig'))
 assert closure['raw']==run['raw']
 assert closure['invocation_sha256']==run['invocation']['sha256']
 if run['status']=='ACCEPTED_PARENT_RUN':
  v=json.loads((d/'validation.json').read_text(encoding='utf-8-sig'));assert v['passed'] and not v['differences']
 else:
  v=json.loads((d/'validation.json').read_text(encoding='utf-8-sig'));assert not v['passed'] and v['differences']
catalog=json.loads((root/c['published_parent_scope']['catalog_path']).read_text(encoding='utf-8'))
print(json.dumps({'passed':True,'checks':len(checks),'contract_sha256':hashlib.sha256((pkg/'contract.json').read_bytes()).hexdigest(),'accepted_parent_status_unchanged':True,'failed_run_still_failed':True,'new_native_runs':0,'checks_labels':checks},indent=2))
