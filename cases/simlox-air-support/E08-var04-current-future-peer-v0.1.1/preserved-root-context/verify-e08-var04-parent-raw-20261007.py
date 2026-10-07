import hashlib,json
from pathlib import Path
r=Path(__file__).resolve().parents[1];cases=r/'cases/simlox-air-support'
checks=[]
def check(f,sha,size=None):
 b=f.read_bytes();assert hashlib.sha256(b).hexdigest()==sha,str(f)
 if size is not None:assert len(b)==size,str(f)
 checks.append({'path':str(f),'bytes':len(b),'sha256':sha})
def walk(n):
 if isinstance(n,dict):
  if 'local_path' in n and 'raw' in n:
   p=Path(n['local_path']);check(p/'closure.json',n['closure_sha256']);check(p/'invocation.json',n['invocation_sha256'])
   for name,x in n['raw'].items():check(p/name,x['sha256'],x['bytes'])
  for v in n.values():walk(v)
 elif isinstance(n,list):
  for v in n:walk(v)
for name in ['E08-var01-immediate-lateral-v1.0.2','E08-var03-delayed-lateral-v1.0.0']:
 idx=json.loads((cases/name/'evidence-index.json').read_bytes());walk(idx)
 assert idx['independent_review_sha256']==hashlib.sha256((cases/name/'review/independent-readonly-2026-10-02.json').read_bytes()).hexdigest()
 rev=json.loads((cases/name/'review/independent-readonly-2026-10-02.json').read_bytes());assert rev['passed'] and rev['failures']==[]
 print(name,rev['checks_total'],rev['verdict'])
assert len(checks)==104,len(checks)
out=r/'tmp/e08-var04-parent-raw-rehash-20261007.json';assert not out.exists();out.write_text(json.dumps({'decision':'ACCEPTED_PARENT_RAW_PINS_PASS','raw_and_closure_invocation_records':104,'records':checks,'new_native_runs':0},indent=2)+'\n',encoding='utf-8');out.chmod(0o444)
print(json.dumps({'records':104,'receipt_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))
