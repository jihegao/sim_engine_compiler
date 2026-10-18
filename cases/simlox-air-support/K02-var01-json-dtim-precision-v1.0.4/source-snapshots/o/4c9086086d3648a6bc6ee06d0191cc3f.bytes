"""One-shot, externally reviewed SSH transport; no retries, kills or timeouts."""
import argparse,datetime,hashlib,json,shutil,subprocess,uuid
from pathlib import Path
CASE=Path(__file__).resolve().parent
def seal(p):
 b=Path(p).read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def check_sources(m):
 for x in m['sources']:
  if seal(x['path'])!={k:x[k] for k in ('bytes','sha256')}:raise ValueError('source pin differs: '+x['path'])
 for x in (m['live_index'],m['live_catalog']):
  if seal(x['path'])!={k:x[k] for k in ('bytes','sha256')}:raise ValueError('live epoch advanced')
def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['preflight','probe0','probe7','native']);p.add_argument('--review-sha',required=True);p.add_argument('--manifest-sha',required=True);p.add_argument('--guardian',required=True,type=Path);p.add_argument('--guardian-sha',required=True);a=p.parse_args()
 manifest_path=CASE/'selected-manifest-v4.json'
 if seal(manifest_path)['sha256']!=a.manifest_sha:raise ValueError('externally expected manifest differs')
 m=json.loads(manifest_path.read_text(encoding='utf-8-sig'));check_sources(m)
 target=m['targets']['native' if a.mode=='preflight' else a.mode]
 rp=CASE/'review'/('independent-'+a.mode+'-go-v4.json')
 if seal(rp)['sha256']!=a.review_sha:raise ValueError('externally expected independent review differs')
 review=json.loads(rp.read_text(encoding='utf-8-sig'))
 if review.get('terminal') is not True or review.get('mode')!=a.mode or review['decision']!=('GO_PRELAUNCH_STATIC' if a.mode=='preflight' else 'GO_PRELAUNCH' if a.mode=='native' else 'GO_REAL_BENIGN_EXACT_BOUND') or review['manifest_sha256']!=a.manifest_sha or review['run_id']!=target['run_id']:raise ValueError('review gate differs')
 if seal(a.guardian)['sha256']!=a.guardian_sha:raise ValueError('standalone guardian receipt differs')
 guardian=json.loads(a.guardian.read_text(encoding='utf-8-sig'))
 if guardian['decision']!='GO_STANDALONE_SAFETY_ONLY' or guardian['manifest_sha256']!=a.manifest_sha or guardian['run_id']!=target['run_id'] or guardian['native_calls']!=0 or guardian['terminal'] is not True:raise ValueError('guardian binding differs')
 # Receipt records completed standalone process. Its handle must now be absent;
 # do not nest a live guardian/transport command that can self-match contender.
 ps=[m['powershell']['path'],'-NoProfile','-NonInteractive','-Command',f"$ErrorActionPreference='Stop'; $p=@(Get-CimInstance Win32_Process -Filter 'ProcessId={int(guardian['guard_pid'])}'); if($p.Count -gt 0){{exit 1}}; exit 0"]
 guard_check=subprocess.run(ps,capture_output=True)
 diagnostic=CASE/'review'/('guardian-pid-check-'+uuid.uuid4().hex);diagnostic.mkdir()
 (diagnostic/'stdout.bin').write_bytes(guard_check.stdout);(diagnostic/'stderr.bin').write_bytes(guard_check.stderr)
 (diagnostic/'receipt.json').write_text(json.dumps(dict(utc=utc(),run_id=target['run_id'],guardian_sha256=a.guardian_sha,command=ps,exit_code=guard_check.returncode,SSH_calls=0,native_calls=0),indent=2)+'\n',encoding='utf-8')
 if guard_check.returncode!=0 or guard_check.stderr:raise ValueError('standalone guardian PID live or query failed; see '+str(diagnostic))
 if Path(target['physical_directory']).exists() or Path(target['recovered_directory']).exists():raise ValueError('unique run path occupied')
 # The remote entry independently verifies the complete exact-bound preceding receipt graph.
 ssh=Path(m['ssh']['path'])
 if not ssh.is_file() or seal(ssh)!={k:m['ssh'][k] for k in ('bytes','sha256')}:raise ValueError('SSH tool fingerprint differs')
 runner=CASE/'run_selected_ssh_v4.ps1';key=Path('C:/Users/user/.ssh/id_rsa')
 if not key.is_file():raise ValueError('existing authorized SSH identity missing')
 cmd=[str(ssh),'-n','-o','BatchMode=yes','-o','ConnectTimeout=10','-i',str(key),'user@127.0.0.1','powershell.exe','-NoProfile','-NonInteractive','-File',runner.as_posix(),'-ExpectedManifestSha',a.manifest_sha,'-ExpectedReviewSha',a.review_sha,'-Mode',a.mode,'-GuardianPath',a.guardian.as_posix(),'-ExpectedGuardianSha',a.guardian_sha]
 directory=CASE/'review'/('transport-'+a.mode+'-'+uuid.uuid4().hex);directory.mkdir()
 started=utc();code=None;error=None
 try:
  with (directory/'stdout.bin').open('xb') as out,(directory/'stderr.bin').open('xb') as err:code=subprocess.run(cmd,cwd=CASE,stdout=out,stderr=err).returncode
 except Exception as exc:error=repr(exc)
 stability=None
 try:check_sources(m)
 except Exception as exc:stability=repr(exc)
 result=dict(schema='simlox-k02-selected-transport/v4',mode=a.mode,run_id=target['run_id'],started_utc=started,completed_utc=utc(),exit_code=code,error=error,source_stability_error=stability,manifest_sha256=a.manifest_sha,review_sha256=a.review_sha,guardian_sha256=a.guardian_sha,command=cmd,streams={n:seal(directory/(n+'.bin')) for n in ('stdout','stderr')},native_approved=a.mode=='native')
 (directory/'transport-receipt.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(evidence=str(directory),exit_code=code,error=error,source_stability_error=stability)))
 return code if isinstance(code,int) and not(error or stability) else 1
if __name__=='__main__':raise SystemExit(main())
