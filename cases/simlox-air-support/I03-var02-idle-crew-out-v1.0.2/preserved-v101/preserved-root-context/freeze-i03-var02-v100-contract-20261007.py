from pathlib import Path
import hashlib,json,subprocess,stat
r=Path(__file__).resolve().parents[1];p=r/'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.0';base='2e9f1e178056469a9903640ff970a5f2375274d4'
def pin(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def verify(f,x):b=f.read_bytes();assert pin(b)=={k:x[k] for k in ('bytes','sha256')},str(f);return b
def git(*a):return subprocess.check_output(['git',*a],cwd=r)
expected={'contract.json':{'bytes':41930,'sha256':'7020f5b51496f10ff2d7ba53ca8f8acdc3fb727c596c5f776068573c3cff5539'},'README.md':{'bytes':1580,'sha256':'6c2afc710796011f46b800f3818d1da3ea7e0f6d6567c6a6b4cfc09cc05f877c'},'.gitattributes':{'bytes':8,'sha256':'705fd4d6451a31d36b3df7de96f83f30ac976c9b4a6d1e51671d8e2f33e2d0da'}}
assert {f.name for f in p.iterdir()}==set(expected)
for name,x in expected.items():verify(p/name,x);(p/name).chmod(stat.S_IREAD)
d=json.loads((p/'contract.json').read_bytes());s=d['source_lineage'];assert d['ownership']['base_commit']==base
for x in s['accepted_source_local_vs_published_git_at_base']:
 f=r/x['path'];verify(f,x['local_disk']);assert pin(git('show',base+':'+x['path']))==x['published_git_at_base']
for x in s['accepted_original_run_records']:verify(Path(x['path']),x)
for x in s['installed'].values():verify(Path(x['path']),x)
for name in ['root_selection_receipt','root_live_context','accepted_parent_index']:
 x=s[name];verify(r/x['path'],x)
catalog=s['catalog_at_selection'];verify(r/catalog['path'],catalog['local_disk']);assert pin(git('show',base+':'+catalog['path']))==catalog['published_git_at_base']
assert not (p/'runs'/d['run_id']).exists()
v={'decision':'ROOT_BYTES_ONLY_CONTRACT_FREEZE','case_id':'I03','variant_id':'I03.var02','version':'1.0.0','base':base,'files':expected,'source_pairs':20,'original_raw_pins':34,'installed_pins':3,'root_context_pins':3,'catalog_byte_identities_distinct':True,'contract_semantic_approval':False,'native_approved':False,'new_native_runs':0,'findings_for_independent_review':['quantity conservation counts outside then subtracts OUT again','success/return after launch ceiling wording ambiguous'],'originals_preserved':True}
out=r/'tmp/i03-var02-v100-root-contract-freeze-20261007.json';assert not out.exists();out.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8');out.chmod(stat.S_IREAD);print(json.dumps({'decision':v['decision'],'receipt':pin(out.read_bytes())}))
