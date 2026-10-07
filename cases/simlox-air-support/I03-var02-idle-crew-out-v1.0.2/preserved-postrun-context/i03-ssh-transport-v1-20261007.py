"""Fixed file-backed SSH dispatch; guards and frozen runner remain unchanged."""
from pathlib import Path
import datetime,hashlib,json,subprocess,sys

repo=Path(__file__).resolve().parents[1]
pkg=repo/'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2'
runner=pkg/'run_native_ssh_v3.ps1'
manifest=pkg/'prelaunch-manifest-v2.json'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(runner)=='c5c117363458ffa38d61bc4296c07cdd5dc0b536953385e36a00c9e5570f5953'
assert sha(manifest)=='fa803d4b0dc7746e4ae3e72288dcdb2cc1a3d3334ca6e5adcb2df8fcb2de1da6'
assert sys.argv[1:] in (['preflight'],['native'])
mode=sys.argv[1]
if mode=='native':
    approval=json.loads((pkg/'review/independent-prelaunch-go.json').read_text(encoding='utf-8-sig'))
    assert approval['decision']=='GO_PRELAUNCH' and approval['manifest_sha256']==sha(manifest)
    assert approval['runner_sha256']==sha(runner)
out=repo/'tmp'/('i03-ssh-transport-v1-'+mode+'-20261007-01')
assert not out.exists();out.mkdir()
command=['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=10','-i','C:/Users/user/.ssh/id_rsa','user@127.0.0.1','powershell.exe','-NoProfile','-NonInteractive','-File',str(runner).replace('\\','/')]
if mode=='preflight':command.append('-PreflightOnly')
started=datetime.datetime.now(datetime.timezone.utc).isoformat()
# No timeout, termination, source edits, guard exceptions or run directory reuse.
result=subprocess.run(command,cwd=repo,capture_output=True)
(out/'ssh-stdout.bin').write_bytes(result.stdout)
(out/'ssh-stderr.bin').write_bytes(result.stderr)
receipt={'schema':'i03-root-file-backed-ssh-transport/v1','mode':mode,'transport_sha256':sha(Path(__file__)),'runner_sha256':sha(runner),'manifest_sha256':sha(manifest),'started_utc':started,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command':command,'exit_code':result.returncode,'streams':{name:{'bytes':(out/name).stat().st_size,'sha256':sha(out/name)} for name in ('ssh-stdout.bin','ssh-stderr.bin')}}
(out/'transport-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'mode':mode,'exit_code':result.returncode,'evidence_dir':str(out),'stdout':result.stdout.decode('utf-8',errors='replace'),'stderr':result.stderr.decode('utf-8',errors='replace')},indent=2))
raise SystemExit(result.returncode)
