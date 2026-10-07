import pathlib, subprocess, sys, json, hashlib, datetime
root=pathlib.Path(__file__).resolve().parents[1]
out=root/'tmp/i03-var06-parent-replay-20261008'
out.mkdir()
method=root/'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2/postappend_replay_v2.py'
result=subprocess.run([sys.executable,'-X','utf8','-B',str(method)],cwd=root,capture_output=True)
def pin(b): return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
for name,b in [('stdout.bin',result.stdout),('stderr.bin',result.stderr)]:
 p=out/name;p.write_bytes(b);p.chmod(0o444)
receipt={'schema':'issue18-i03-var06-parent-replay/v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':str(method),'method_pin':pin(method.read_bytes()),'exit':result.returncode,'stdout':pin(result.stdout),'stderr':pin(result.stderr),'native_calls':0,'verdict':json.loads(result.stdout) if result.returncode==0 else None}
p=out/'receipt.json';p.write_bytes((json.dumps(receipt,indent=2)+'\n').encode());p.chmod(0o444)
print(json.dumps(receipt))
assert result.returncode==0 and not result.stderr
