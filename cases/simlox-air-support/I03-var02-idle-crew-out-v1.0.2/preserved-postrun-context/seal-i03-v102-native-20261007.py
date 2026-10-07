from pathlib import Path
import hashlib,json,stat
repo=Path(__file__).resolve().parents[1]
pkg=repo/'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2'
run=pkg/'runs/i03-var02-idle-out-v102-ssh-20261007-01'
outer=repo/'tmp/i03-ssh-transport-v1-native-20261007-01'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def pin(p):
    b=p.read_bytes();return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
c=read(run/'closure.json');i=read(run/'invocation.json');m=read(pkg/'prelaunch-manifest-v2.json')
assert not c['error'] and not c['step_error'] and not (run/'failure-seal.json').exists()
assert c['invocation_sha256']==pin(run/'invocation.json')['sha256']
expected={x['key']:x['sha256'] for x in m['source_files']}
assert len(expected)==179 and c['source_hashes_before']==c['source_hashes_after']==i['source_hashes_before']==expected
for x in m['source_files']:assert pin(Path(x['path']))=={k:x[k] for k in ('bytes','sha256')}
for name,p in c['raw'].items():assert pin(run/name)==p
assert set(c['raw'])=={p.name for p in run.iterdir() if p.name not in ('closure.json','invocation.json')}
steps=read(run/'steps.json')
assert [s['name'] for s in steps]==['import','export','check_import_export','calc','jsonreport','check_behavior']
for s in steps:
    assert type(s['exit_code']) is int and s['exit_code']==0
    assert type(s['child_pid']) is int and s['child_pid']>0
    assert type(s['child_session_id']) is int and s['child_session_id']==0
    assert s['capture_error'] is None and s['error'] is None and s['status']=='completed' and s['gui_preserved'] is True
for a,b in zip(steps,steps[1:]):assert a['completed_utc']<=b['started_utc']
tr=read(outer/'transport-receipt.json')
assert type(tr['exit_code']) is int and tr['exit_code']==0 and tr['mode']=='native'
assert tr['transport_sha256']=='34571d878bce88b56aedbf9620f5bb155abad21ae5b56b630933ffb134dacdc1'
for name,p in tr['streams'].items():assert pin(outer/name)==p
assert (outer/'ssh-stderr.bin').read_bytes()==b''
assert read(outer/'ssh-stdout.bin')=={'decision':'NATIVE_CHILD_COMPLETED','run_id':m['run_id']}
files=[*run.iterdir(),*outer.iterdir()]
for p in files:p.chmod(p.stat().st_mode&~stat.S_IWRITE)
out=repo/'tmp/i03-v102-root-native-seal-20261007.json';assert not out.exists()
doc={'schema':'i03-root-native-seal/v1','decision':'SEALED_REQUIRES_INDEPENDENT_BEHAVIOR_REVIEW','run_id':m['run_id'],'closure':pin(run/'closure.json'),'invocation':pin(run/'invocation.json'),'source_count':179,'raw_count':len(c['raw']),'steps':[{'name':s['name'],'pid':s['child_pid'],'session':s['child_session_id'],'exit':s['exit_code']} for s in steps],'files':{str(p.relative_to(repo)):pin(p) for p in files}}
out.write_text(json.dumps(doc,indent=2)+'\n',encoding='utf-8');out.chmod(out.stat().st_mode&~stat.S_IWRITE)
Path(__file__).chmod(Path(__file__).stat().st_mode&~stat.S_IWRITE)
print(json.dumps({'seal':pin(out),'closure':doc['closure'],'invocation':doc['invocation'],'raw_count':doc['raw_count'],'step_count':len(steps)},indent=2))
