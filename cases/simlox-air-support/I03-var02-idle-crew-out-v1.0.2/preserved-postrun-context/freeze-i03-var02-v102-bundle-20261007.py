from pathlib import Path
import hashlib,json,stat,subprocess,datetime

repo=Path(__file__).resolve().parents[1]
pkg=repo/'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2'
manifest=pkg/'prelaunch-manifest-v2.json'
expected_sha='fa803d4b0dc7746e4ae3e72288dcdb2cc1a3d3334ca6e5adcb2df8fcb2de1da6'
def identity(path):
    raw=path.read_bytes();return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
assert identity(manifest)=={'bytes':66992,'sha256':expected_sha}
doc=json.loads(manifest.read_bytes())
assert doc['schema']=='i03-var02-v102-prelaunch-manifest/v2'
assert doc['source_count']==179==len(doc['source_files'])
assert len({x['key'] for x in doc['source_files']})==179
assert doc['native_runs_authorized_by_manifest']==0
assert doc['run_id']=='i03-var02-idle-out-v102-ssh-20261007-01'
assert not (pkg/'runs'/doc['run_id']).exists()
sources={}
for item in doc['source_files']:
    path=Path(item['path']).resolve(strict=True)
    assert identity(path)=={k:item[k] for k in ('bytes','sha256')},item['key']
    sources[item['key']]={'path':str(path),**identity(path)}
roles={'runner_script':('run_native_ssh_v3.ps1','c5c117363458ffa38d61bc4296c07cdd5dc0b536953385e36a00c9e5570f5953'),
       'independent_replay':('review/independent_replay_v3.py','e8a249c11df2f90f08e838f854432a27eeffacae5b814ceeb16ab4c00ad27e6e'),
       'independent_self_check':('review/independent_self_check_v3.py','46b09155540c59de9369b26f4f6258d4c079e6cb75710dbd841bd075a35d73ae'),
       'child_input':('native-input.json','b6cebc1b3a44e6bd462e222690e90026e8336e1ad55f0b68b2d9212c635176b4'),
       'child_contract':('contract.json','1f058ae8706d4de81c28099b6580619eb4cb879e20314619f387839d9150ee29')}
for key,(name,sha) in roles.items():
    assert Path(sources[key]['path'])==pkg/name and sources[key]['sha256']==sha
protected=[]
for rec in sources.values():
    path=Path(rec['path'])
    if path.is_relative_to(pkg):
        path.chmod(path.stat().st_mode & ~stat.S_IWRITE);protected.append(str(path))
manifest.chmod(manifest.stat().st_mode & ~stat.S_IWRITE)
assert identity(manifest)['sha256']==expected_sha
for key,rec in sources.items():
    assert identity(Path(rec['path']))=={k:rec[k] for k in ('bytes','sha256')},key
python=Path(r'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
checks=[]
commands=[
 [str(python),'-X','utf8','-B',str(pkg/'build.py')],
 [str(python),'-X','utf8','-B',str(pkg/'verify_sources.py'),'--mode','live','--manifest',str(manifest)],
 [str(python),'-X','utf8','-B',str(pkg/'make_prelaunch_manifest_v2.py')],
 [str(python),'-X','utf8','-B',str(pkg/'self_check.py')],
 [str(python),'-X','utf8','-B',str(pkg/'test_sealed_catalog.py')],
 [str(python),'-X','utf8','-B',str(pkg/'review/independent_replay_v3.py'),'--control-only'],
]
for command in commands:
    result=subprocess.run(command,cwd=repo,capture_output=True,text=True,encoding='utf-8')
    record={'command':command,'exit_code':result.returncode,'stdout_sha256':hashlib.sha256(result.stdout.encode()).hexdigest(),'stderr':result.stderr}
    try: record['verdict']=json.loads(result.stdout)
    except json.JSONDecodeError: record['stdout']=result.stdout
    checks.append(record)
    assert result.returncode==0 and result.stderr=='',record
for key,rec in sources.items():
    assert identity(Path(rec['path']))=={k:rec[k] for k in ('bytes','sha256')},key
assert identity(manifest)['sha256']==expected_sha
receipt={'schema':'i03-var02-root-frozen-bundle/v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'manifest':identity(manifest),'source_count':179,'frozen_owned_source_count':len(protected),'source_files':sources,'checks':checks,'native_child_started':False,'run_directory_absent':True,'decision':'FROZEN_FOR_PURE_PREFLIGHT_REVIEW'}
out=repo/'tmp/i03-var02-v102-root-bundle-freeze-20261007.json';assert not out.exists();out.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');out.chmod(out.stat().st_mode&~stat.S_IWRITE)
print(json.dumps({'decision':receipt['decision'],'manifest_sha256':expected_sha,'source_count':179,'frozen_owned':len(protected),'checks':len(checks),'receipt':identity(out)},indent=2))
