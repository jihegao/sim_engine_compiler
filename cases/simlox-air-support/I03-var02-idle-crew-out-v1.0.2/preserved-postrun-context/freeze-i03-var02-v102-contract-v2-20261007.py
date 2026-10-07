from pathlib import Path
import argparse,hashlib,json,subprocess,stat,datetime
r=Path(__file__).resolve().parents[1]
p=r/'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2'
base='2e9f1e178056469a9903640ff970a5f2375274d4'
ap=argparse.ArgumentParser(); ap.add_argument('--contract-sha',required=True); ap.add_argument('--contract-bytes',required=True,type=int); ap.add_argument('--readme-sha',required=True); ap.add_argument('--readme-bytes',required=True,type=int); a=ap.parse_args()
def pin(b): return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def verify(f,x):
 b=f.read_bytes(); assert pin(b)=={k:x[k] for k in ('bytes','sha256')},str(f); return b
def git(*xs): return subprocess.check_output(['git',*xs],cwd=r)
def typed_equal(a,b):
 if type(a) is not type(b): return False
 if isinstance(a,dict): return a.keys()==b.keys() and all(typed_equal(a[k],b[k]) for k in a)
 if isinstance(a,list): return len(a)==len(b) and all(typed_equal(x,y) for x,y in zip(a,b))
 return a==b
expected={'contract.json':{'bytes':a.contract_bytes,'sha256':a.contract_sha},'README.md':{'bytes':a.readme_bytes,'sha256':a.readme_sha},'.gitattributes':{'bytes':8,'sha256':'705fd4d6451a31d36b3df7de96f83f30ac976c9b4a6d1e51671d8e2f33e2d0da'}}
for name,x in expected.items(): verify(p/name,x)
d=json.loads((p/'contract.json').read_bytes()); s=d['source_lineage']
assert d['version']=='1.0.2' and d['run_id']=='i03-var02-idle-out-v102-ssh-20261007-01'
assert d['ownership']['base_commit']==base and git('rev-parse','HEAD').decode().strip()==base
assert len(s['accepted_source_local_vs_published_git_at_base'])==20 and len(s['accepted_original_run_records'])==34
for x in s['accepted_source_local_vs_published_git_at_base']:
 verify(r/x['path'],x['local_disk']); assert pin(git('show',base+':'+x['path']))==x['published_git_at_base']
for x in s['accepted_original_run_records']: verify(Path(x['path']),x)
for x in s['installed'].values(): verify(Path(x['path']),x)
for name in ['root_selection_receipt','root_live_context','accepted_parent_index']:
 x=s[name]; verify(r/x['path'],x)
c=s['catalog_at_selection']; historical=verify(p/c['owned_exact_archive'],c['local_disk']); published=git('show',base+':'+c['path'])
assert pin(published)==c['published_git_at_base'] and historical!=published and typed_equal(json.loads(historical),json.loads(published))
expected[c['owned_exact_archive']]={k:c['local_disk'][k] for k in ('bytes','sha256')}
old=json.loads(historical); live=json.loads((r/c['path']).read_bytes())
assert len(old['entries'])==490 and typed_equal(live['entries'][:490],old['entries'])
assert typed_equal({k:v for k,v in live.items() if k!='entries'},{k:v for k,v in old.items() if k!='entries'})
records=[]
def walk(x):
 if isinstance(x,dict):
  if 'owned_inert_copy' in x: records.append(x)
  for y in x.values(): walk(y)
 elif isinstance(x,list):
  for y in x: walk(y)
walk(s)
for x in records:
 copy=(p/x['owned_inert_copy']).resolve(); assert copy.is_relative_to(p.resolve())
 verify(copy,x); expected[copy.relative_to(p).as_posix()]={k:x[k] for k in ('bytes','sha256')}
 original=r/x['original_path']
 if original.exists() and x['original_path']!=c['path']: verify(original,x)
assert {f.relative_to(p).as_posix() for f in p.rglob('*') if f.is_file()}==set(expected)
assert not (p/'runs'/d['run_id']).exists()
for name in expected: (p/name).chmod(stat.S_IREAD)
out=r/'tmp/i03-var02-v102-root-contract-freeze-v2-20261007.json'; assert not out.exists()
v={'decision':'ROOT_BYTES_ONLY_CONTRACT_FREEZE','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'version':'1.0.2','base':base,'run_id':d['run_id'],'files':expected,'source_pairs':20,'original_raw_pins':34,'installed_pins':3,'preserved_copies':len(records),'catalog_byte_identities_distinct':True,'catalog_type_sensitive_parsed_content_equal':True,'contract_semantic_approval':False,'native_approved':False,'new_native_runs':0,'excluded_v100_v101_preserved':True}
out.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8'); out.chmod(stat.S_IREAD)
print(json.dumps({'decision':v['decision'],'receipt':str(out),'pin':pin(out.read_bytes()),'frozen_files':len(expected)}))
