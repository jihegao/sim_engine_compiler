from pathlib import Path
import sys,json,hashlib
repo=Path(__file__).resolve().parents[1]
pkg=repo/'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2'
sys.path.insert(0,str(pkg/'review'));sys.path.insert(0,str(pkg))
import independent_self_check_v3 as fixture
import event_ledger as author
before=hashlib.sha256((pkg/'event_ledger.py').read_bytes()).hexdigest()
lines=fixture.synthetic_child_log().decode().splitlines()
author.child_timeline(author.parse_log('\n'.join(lines)+'\n'))
mutants={}
owner=next(i for i,x in enumerate(lines) if x.startswith('Time: 8.0 <TEACH-AIR-01,1> Next random failure'))
assert 'Tasks waiting for resources at: <BASE-01,0> 0' in lines[owner+1]
changed=lines.copy();del changed[owner+1];mutants['missing post-grant empty queue']=changed
changed=lines.copy();changed.insert(owner+2,changed[owner+1]);mutants['duplicate post-grant empty queue']=changed
changed=lines.copy();n=next(i for i,x in enumerate(changed) if 'Tasks waiting for resources at: <BASE-01,0> 1' in x);changed[n]=changed[n].replace('> 1','> 0');mutants['waiting count zero with one waiting task']=changed
results=[]
for name,changed in mutants.items():
    raw='\n'.join(changed)+'\n'
    try: author.child_timeline(author.parse_log(raw));result='ESCAPED';error=None
    except (AssertionError,ValueError,TypeError,KeyError,IndexError) as exc:result='REJECTED';error=str(exc)
    results.append({'mutation':name,'result':result,'error':error,'sha256':hashlib.sha256(raw.encode()).hexdigest()})
assert before==hashlib.sha256((pkg/'event_ledger.py').read_bytes()).hexdigest()
receipt={'schema':'i03-var02-root-author-queue-probes/v1','author_gate_sha256':before,'synthetic_only':True,'new_native_runs':0,'results':results}
out=repo/'tmp/i03-var02-author-queue-context-probes-20261007.json';assert not out.exists();out.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt,indent=2))
