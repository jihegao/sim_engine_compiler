import pathlib,subprocess,sys,json,hashlib,datetime
root=pathlib.Path(__file__).resolve().parents[1]
case=root/'cases/simlox-air-support/I03-var06-out-ignored-duration-v1.0.0'
out=root/'tmp/i03-var06-root-contract-replay-20261008'
out.mkdir()
def pin(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
method=case/'review/independent-contract-audit-2026-10-08.py'
memo=case/'review/independent-contract-go-2026-10-08.md'
assert pin(method.read_bytes())['sha256']=='b2b89af73de5a95caa139ea53bcb65a43a36367ba013ef77e0d6b3bc928657d5'
assert pin(memo.read_bytes())['sha256']=='5f71fba60e7f8075dcfe5bc8a5a694e20b1a00e934765035e23ec25aafddd402'
r=subprocess.run([sys.executable,'-X','utf8','-B',str(method)],cwd=root,capture_output=True)
for n,b in [('stdout.bin',r.stdout),('stderr.bin',r.stderr)]:
 p=out/n;p.write_bytes(b);p.chmod(0o444)
rec={'schema':'issue18-i03-var06-root-contract-replay/v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':pin(method.read_bytes()),'memo':pin(memo.read_bytes()),'exit':r.returncode,'streams':{n:pin(b) for n,b in [('stdout.bin',r.stdout),('stderr.bin',r.stderr)]},'native_calls':0,'verdict':json.loads(r.stdout) if r.returncode==0 else None}
p=out/'receipt.json';p.write_bytes((json.dumps(rec,indent=2)+'\n').encode());p.chmod(0o444)
print(json.dumps(rec));assert r.returncode==0 and not r.stderr
