"""Fixed Git SSH443 network child only. No SIMLOX/owner/queue operations."""
import argparse,datetime,hashlib,ipaddress,json,os,subprocess,sys,threading,time,uuid
from pathlib import Path

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(p):
 b=Path(p).read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def save(p,x):
 with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def raw(p,b):
 with Path(p).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def retain_unknown(directory,process,error):
 # Deliberate ownership hold, not automatic recovery. No further kill/wait/retry.
 try:save(directory/'UNKNOWN-RETAINED.json',dict(utc=utc(),error=repr(error),owned_direct_pid=process.pid,meaning='Original wrapper and exact direct SSH process object retained; no terminal result/no retry/release authority'))
 except BaseException:pass
 while True:time.sleep(1)

def exchange(command,directory,popen=subprocess.Popen,hold=retain_unknown):
 started=utc()
 process=popen(command,stdin=None,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0,shell=False)
 owned=utc();tick=time.monotonic();timeout=False
 files=[];threads=[];errors=[];eof=[False,False]
 try:
  # Inherit Git stdin. Forward binary advertisements/requests while SSH lives;
  # never communicate-then-replay a bidirectional Git protocol.
  def pump(index,source,spool,sink):
   try:
    while True:
     chunk=os.read(source.fileno(),65536)
     if not chunk:break
     if spool.write(chunk)!=len(chunk):raise IOError('Short raw sidecar write')
     if sink.write(chunk)!=len(chunk):raise IOError('Short live Git pipe write')
     sink.flush()
    eof[index]=True
   except BaseException as error:errors.append(repr(error))
  for index,(name,source,sink) in enumerate([('stdout',process.stdout,sys.stdout.buffer),('stderr',process.stderr,sys.stderr.buffer)]):
   spool=(directory/(name+'.bin')).open('xb',buffering=0);files.append(spool)
   thread=threading.Thread(target=pump,args=(index,source,spool,sink),name='fixed-Git-SSH-'+name,daemon=False);threads.append(thread);thread.start()
  try:process.wait(timeout=max(0.0,20-(time.monotonic()-tick)))
  except subprocess.TimeoutExpired:
   timeout=True
   process.kill()  # Windows Popen retained _handle, no PID lookup/tree kill.
   process.wait(timeout=5)
  if process.returncode is None or process.poll() is None:raise RuntimeError('Original direct SSH terminal status unconfirmed')
  drain_deadline=time.monotonic()+5
  for thread in threads:thread.join(timeout=max(0.0,drain_deadline-time.monotonic()))
  if any(thread.is_alive() for thread in threads) or errors or eof!=[True,True]:raise RuntimeError('Live Git stream completion unconfirmed: '+repr(errors))
  for spool in files:spool.flush();os.fsync(spool.fileno());spool.close()
  for source in (process.stdout,process.stderr):source.close()
  result=dict(schema='issue18-fixed-Git-SSH443-network-child/v2',started_utc=started,owned_utc=owned,completed_utc=utc(),elapsed_after_Popen_seconds=time.monotonic()-tick,command=command,owned_direct_pid=process.pid,timeout_seconds=20,timeout_observed=timeout,owned_direct_process_terminal=True,actual_ssh_exit_code=process.returncode,wrapper_exit_code=124 if timeout else process.returncode,scope='SSH network phase after successful Popen only; not total Git/DNS/process-creation harddeadline',kill_target='same directly created Popen retained handle only' if timeout else None,stdin='inherited Git input',stdout_stderr='live unbuffered binary tee with per-chunk parent flush, no replay',both_streams_EOF=True,both_tee_threads_joined=True)
  result['streams']={n:digest(directory/(n+'.bin')) for n in ('stdout','stderr')}
  save(directory/'result.json',result)
  return result['wrapper_exit_code']
 except BaseException as error:
  # Locals retain the same process, tee threads, pipes and sidecars here.
  return hold(directory,process,error)

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--manifest',type=Path,required=True);p.add_argument('--manifest-sha',required=True)
 p.add_argument('--mode',choices=['probe0','probe7','preflight','native'],required=True)
 p.add_argument('--resolved-ip',required=True);p.add_argument('git_argv',nargs=argparse.REMAINDER)
 a=p.parse_args()
 if digest(a.manifest)['sha256']!=a.manifest_sha:raise ValueError('Exact manifest differs')
 m=json.loads(a.manifest.read_text(encoding='utf-8-sig'))
 if m['schema']!='simlox-k02-selected-manifest/v10':raise ValueError('Selected network version differs')
 ip=ipaddress.ip_address(a.resolved_ip)
 if ip.version!=4 or str(ip)!=a.resolved_ip:raise ValueError('Canonical IPv4 required')
 tail=a.git_argv
 if tail and tail[0]=='--':tail=tail[1:]
 expected=['-o','SendEnv=GIT_PROTOCOL','git@github.com',"git-upload-pack 'jihegao/sim_engine_compiler.git'"]
 if tail not in (expected,expected[2:]):raise ValueError('Undeclared Git SSH argv rejected')
 profile=m['git_network']
 if profile['host']!='ssh.github.com' or profile['port']!=443 or profile['ssh_network_timeout_seconds']!=20 or profile['ssh_terminal_wait_seconds']!=5 or profile['ssh_config_file']!='/dev/null':raise ValueError('Fixed network profile differs')
 if profile['identity_file']!=r'C:\Users\user\.ssh\github_deploy_20260927':raise ValueError('Existing deploy identity differs')
 ssh=Path(profile['ssh']['path'])
 if ssh!=Path(r'C:\Program Files\Git\usr\bin\ssh.exe') or digest(ssh)!={k:profile['ssh'][k] for k in ('bytes','sha256')} or profile['ssh']['sha256']!='3b2752c1b15caf75ac3b5997fb28d410529007cfbaa6ae026b36c3adf662ad6f':raise ValueError('Separate Git network SSH pin differs')
 known=Path(profile['user_known_hosts']['path'])
 if known!=Path(r'C:\Users\user\.ssh\known_hosts') or digest(known)!={k:profile['user_known_hosts'][k] for k in ('bytes','sha256')}:raise ValueError('Existing explicit known_hosts pin differs')
 if digest(sys.executable)!={k:m['python'][k] for k in ('bytes','sha256')}:raise ValueError('Python interpreter pin differs')
 target=m['targets']['native' if a.mode=='preflight' else a.mode]
 directory=a.manifest.parent/'review'/('git-network-'+a.mode+'-'+uuid.uuid4().hex);directory.mkdir()
 # -F NUL excludes user/system ssh configuration. No proxies, local commands,
 # multiplexing, forwarding, external agent or arbitrary config include helpers.
 command=[str(ssh),'-F','/dev/null','-i',profile['identity_file'].replace('\\','/'),'-p','443']
 for option in ['IdentitiesOnly=yes','HostName='+str(ip),'HostKeyAlias=github.com','UserKnownHostsFile='+known.as_posix(),'GlobalKnownHostsFile=/dev/null','StrictHostKeyChecking=yes','UpdateHostKeys=no','BatchMode=yes','ConnectTimeout=10','ServerAliveInterval=5','ServerAliveCountMax=2','ProxyCommand=none','ProxyJump=none','PermitLocalCommand=no','ControlMaster=no','ControlPath=none','ControlPersist=no','IdentityAgent=none','ForwardAgent=no','ClearAllForwardings=yes']:
  command+=['-o',option]
 command+=tail
 save(directory/'request.json',dict(utc=utc(),manifest_sha256=a.manifest_sha,mode=a.mode,run_id=target['run_id'],resolved_ipv4=str(ip),command=command,Git_arguments=tail,SSH_network_timeout_seconds=20,config_isolated=True,native_or_probe_processes_created=0))
 return exchange(command,directory)
if __name__=='__main__':raise SystemExit(main())

