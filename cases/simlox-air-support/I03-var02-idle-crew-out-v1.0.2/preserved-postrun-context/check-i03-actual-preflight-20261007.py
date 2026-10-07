from pathlib import Path
import hashlib,json,stat
repo=Path(__file__).resolve().parents[1]
pkg=repo/'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2'
transport=repo/'tmp/i03-ssh-transport-v1-preflight-20261007-01'
def pin(path):
    raw=path.read_bytes();return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
tr=json.loads((transport/'transport-receipt.json').read_bytes())
assert tr['exit_code']==0 and tr['mode']=='preflight'
assert tr['transport_sha256']=='34571d878bce88b56aedbf9620f5bb155abad21ae5b56b630933ffb134dacdc1'
for name,rec in tr['streams'].items():assert pin(transport/name)==rec
assert (transport/'ssh-stderr.bin').read_bytes()==b''
path=Path((transport/'ssh-stdout.bin').read_bytes().decode('utf-8').strip())
assert path.parent==pkg/'review' and path.name=='preflight-ssh0-20261007T154508453Z.json'
receipt=json.loads(path.read_text(encoding='utf-8-sig'))
manifest=json.loads((pkg/'prelaunch-manifest-v2.json').read_bytes())
expected={x['key']:x['sha256'] for x in manifest['source_files']}
assert receipt['schema']=='i03-var02-v102-ssh-preflight/v1'
assert receipt['run_id']==manifest['run_id']=='i03-var02-idle-out-v102-ssh-20261007-01'
assert receipt['manifest_sha256']==pin(pkg/'prelaunch-manifest-v2.json')['sha256']==tr['manifest_sha256']
assert receipt['source_hashes']==expected and len(expected)==179
assert receipt['source_map_sha256']==hashlib.sha256(json.dumps(expected,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
for key,value in [('ssh_session',0),('ps_major',5),('wts_active_gui_count',1),('accepted_raw_seals',32),('accepted_closures',1),('accepted_invocations',1)]:assert type(receipt[key]) is int and receipt[key]==value
for key,value in [('mutex_free',True),('run_dirs_absent',True),('native_process_started',False)]:assert type(receipt[key]) is bool and receipt[key] is value
assert receipt['gui']=={'pid':13340,'session_id':1,'start_unix_ms':1790590196826,'responding':True}
assert type(receipt['ssh_ancestors']) is list and 'sshd.exe' in receipt['ssh_ancestors']
assert not (pkg/'runs'/receipt['run_id']).exists()
for item in manifest['source_files']:assert pin(Path(item['path']))=={k:item[k] for k in ('bytes','sha256')}
for file in [path,*transport.iterdir()]:file.chmod(file.stat().st_mode&~stat.S_IWRITE)
out=repo/'tmp/i03-var02-root-actual-preflight-check-20261007.json';assert not out.exists()
doc={'schema':'i03-root-actual-preflight-check/v1','decision':'ACTUAL_SSH_PREFLIGHT_VERIFIED_REQUIRES_GO_PRELAUNCH','receipt_path':str(path),'receipt':pin(path),'transport_receipt':pin(transport/'transport-receipt.json'),'source_map_sha256':receipt['source_map_sha256'],'source_count':179,'native_process_started':False,'run_directory_absent':True}
out.write_text(json.dumps(doc,indent=2)+'\n',encoding='utf-8');out.chmod(out.stat().st_mode&~stat.S_IWRITE);print(json.dumps({**doc,'root_check':pin(out)},indent=2))
