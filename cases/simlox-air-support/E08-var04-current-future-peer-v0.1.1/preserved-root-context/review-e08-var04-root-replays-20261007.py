import hashlib,json,subprocess,sys
from pathlib import Path
r=Path(__file__).resolve().parents[1]
p=r/'cases/simlox-air-support/E08-var04-current-future-peer-v0.1.1'
out=r/'tmp/e08-var04-root-replays-20261007.json'
assert not out.exists()
methods={
 'replay.py':('9cc22516d1fbd9fdee1f0b8c2e09980f57bfccba8e0421b00c492777c8b56ad7','author-validation.json'),
 'self_check.py':('8c3e6a93e87e57363845678d59e0b3d84aa2551049a6c9e1968aaaaf3fe22ff6','author-self-check.json'),
 'self_check_v2.py':('7b991e0d76cde281930303d1693dda6597f753d8a9cfd13c050a72e8c225179c','author-self-check-v2.json'),
 'review/independent_replay.py':('558993694997f82db32b8fd85598f3c251a2f304eac61dfaa27184c019a43dc7','review/independent-verdict.json'),
}
def digest(b): return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
records=[]
for method,(expected,verdict) in methods.items():
 b=(p/method).read_bytes();assert digest(b)['sha256']==expected,(method,digest(b))
 result=subprocess.run([sys.executable,'-X','utf8','-B',str(p/method)],cwd=r,capture_output=True)
 assert result.returncode==0,(method,result.returncode,result.stderr.decode('utf-8','replace'))
 assert not result.stderr,(method,result.stderr)
 saved=(p/verdict).read_bytes()
 assert json.loads(result.stdout)==json.loads(saved),method
 assert (p/method).read_bytes()==b,method
 records.append({'method':method,'method_pin':digest(b),'verdict':verdict,'saved_pin':digest(saved),'stdout_pin':digest(result.stdout),'exact_stdout_equal':result.stdout==saved,'exit_code':0,'decision':json.loads(saved)})
receipt={'decision':'ROOT_READONLY_REPLAYS_PASS','new_native_runs':0,'methods':records,'WTS_limitation':'No-positive-wait null is a bounded accepted native presentation convention, not a general formula law.','issue18_unfinished':True}
out.write_bytes((json.dumps(receipt,indent=2)+'\n').encode());out.chmod(0o444)
print(json.dumps({'decision':receipt['decision'],'receipt':digest(out.read_bytes()),'methods':len(records)}))
