from pathlib import Path
import hashlib,json,subprocess,stat,datetime
r=Path(__file__).resolve().parents[1]
p=r/'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.1'
base='2e9f1e178056469a9903640ff970a5f2375274d4'
def pin(b): return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def verify(f,x):
 b=f.read_bytes(); assert pin(b)=={k:x[k] for k in ('bytes','sha256')},str(f); return b
def git(*a): return subprocess.check_output(['git',*a],cwd=r)
expected={'contract.json':{'bytes':48826,'sha256':'a614608f87608b68f4bd1645107fb3dfe88b20ea4bf8634e4ebdd4de6d3fa391'},'README.md':{'bytes':1546,'sha256':'f9954c22df936529aaf52710ef457ec6719862a7d73922c5b25f0dc55f6d26ec'},'.gitattributes':{'bytes':8,'sha256':'705fd4d6451a31d36b3df7de96f83f30ac976c9b4a6d1e51671d8e2f33e2d0da'}}
for name,x in expected.items(): verify(p/name,x)
d=json.loads((p/'contract.json').read_bytes()); s=d['source_lineage']
assert d['ownership']['base_commit']==base and git('rev-parse','HEAD').decode().strip()==base
for x in s['accepted_source_local_vs_published_git_at_base']:
 verify(r/x['path'],x['local_disk']); assert pin(git('show',base+':'+x['path']))==x['published_git_at_base']
for x in s['accepted_original_run_records']: verify(Path(x['path']),x)
for x in s['installed'].values(): verify(Path(x['path']),x)
for name in ['root_selection_receipt','root_live_context','accepted_parent_index']:
 x=s[name]; verify(r/x['path'],x)
c=s['catalog_at_selection']; local=verify(r/c['path'],c['local_disk']); published=git('show',base+':'+c['path'])
assert pin(published)==c['published_git_at_base'] and local!=published and json.loads(local)==json.loads(published)
for x in s['excluded_v100_NO_GO_files']+s['owned_historical_root_context']:
 verify(r/x['original_path'],x); verify(p/x['owned_inert_copy'],x); expected[x['owned_inert_copy']]={k:x[k] for k in ('bytes','sha256')}
assert {f.relative_to(p).as_posix() for f in p.rglob('*') if f.is_file()}==set(expected)
assert not (p/'runs'/d['run_id']).exists()
for name in expected: (p/name).chmod(stat.S_IREAD)
out=r/'tmp/i03-var02-v101-root-contract-freeze-20261007.json'
assert not out.exists()
v={'decision':'ROOT_BYTES_ONLY_CONTRACT_FREEZE','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'case_id':'I03','variant_id':'I03.var02','version':'1.0.1','base':base,'run_id':d['run_id'],'files':expected,'source_pairs':len(s['accepted_source_local_vs_published_git_at_base']),'original_raw_pins':len(s['accepted_original_run_records']),'installed_pins':len(s['installed']),'preserved_copies':10,'catalog_byte_identities_distinct':True,'catalog_parsed_content_equal':True,'contract_semantic_approval':False,'native_approved':False,'new_native_runs':0,'excluded_v100_preserved':True}
out.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8'); out.chmod(stat.S_IREAD)
print(json.dumps({'decision':v['decision'],'receipt':str(out),'pin':pin(out.read_bytes()),'frozen_files':len(expected)}))
