from pathlib import Path
import hashlib, json, sys

repo = Path(__file__).resolve().parents[1]
review = repo / 'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2/review'
sys.path.insert(0, str(review))
import independent_replay_v2 as v
import independent_self_check_v2 as s

expected = {'independent_replay_v2.py':'62a302f222170d93a3eb068c29dd453f0901052cc419abcc7acd3126d107c5fd', 'independent_self_check_v2.py':'cc32f630bbe634a7356035c6a8cffe6c4fd3db2fa5458f4ccbab86f6eeb2e268'}
def hashes():
    return {name:hashlib.sha256((review/name).read_bytes()).hexdigest() for name in expected}
assert hashes() == expected
raw=s.synthetic_child_log(); a=v.Audit(); v.child_physical(raw,a)
lines=raw.decode().splitlines(); mutants={}
def index(fragment):
    return next(i for i,x in enumerate(lines) if fragment in x)
def record(label, changed):
    assert changed != lines
    mutants[label]=('\n'.join(changed)+'\n').encode()
changed=[x for x in lines if x.strip() not in ('no failures','no PMTasks')]
changed[-1:-1]=[x for x in lines if x.strip() in ('no failures','no PMTasks')]
record('orphan return continuations at terminal',changed)
changed=lines.copy(); changed.insert(index('allocated to maintenance task')+1,'  Free resources at: <BASE-01,0> P-CREW 2')
record('contradictory free crew while booked',changed)
changed=lines.copy(); changed.insert(index('Time: 8.0 '),'Time: 8.0 <TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>')
record('extra ready increase during preparation',changed)
for fragment in ('Start of day no 0','Start of day no 1','resource shift 0 created','resource shift 0 starting','resource shift 0 ended','Free resources at:','systems ready: 2','System soon ready','turnround started','turnround ended','System ready <','Repair task priority list:','nbr ready decreased','Missions and tasks using resources at:','< subtask 0 seqno 1','Tasks waiting for resources at: <BASE-01,0> 1'):
    n=index(fragment)
    changed=lines.copy(); del changed[n]; record('delete '+fragment,changed)
    changed=lines.copy(); changed.insert(n+1,changed[n]); record('duplicate '+fragment,changed)
for label, fragment, old, new in (
    ('wrong booked quantity','< subtask 0 seqno 1',', C, 1, 0.5>',', C, 2, 0.5>'),
    ('wrong return diagnostic aircraft','System ready <TEACH-AIR-01,0>','System ready <TEACH-AIR-01,0>','System ready <TEACH-AIR-01,1>'),
    ('wrong opening resource station','Free resources at:','<BASE-01,0>','<BASE-01,1>')):
    changed=lines.copy(); n=index(fragment); assert old in changed[n]; changed[n]=changed[n].replace(old,new); record(label,changed)
for label, moving, target in (
    ('turnround starts after ending','<TEACH-AIR-01,0> turnround started','<TEACH-AIR-01,0> turnround ended'),
    ('soon ready after turnround ending','System soon ready <TEACH-AIR-01,0>','<TEACH-AIR-01,0> turnround ended')):
    changed=lines.copy(); n=index(moving); line=changed.pop(n); dest=next(i for i,x in enumerate(changed) if target in x); changed.insert(dest+1,line); record(label,changed)
results=[]
for label, mutation in mutants.items():
    try:
        v.child_physical(mutation,v.Audit()); result='ESCAPED'
    except (AssertionError,ValueError,TypeError,KeyError,IndexError) as exc:
        result='REJECTED'; error=str(exc)
    results.append({'mutation':label,'sha256':hashlib.sha256(mutation).hexdigest(),'result':result,**({'error':error} if result=='REJECTED' else {})})
assert hashes()==expected
receipt={'schema':'i03-var02-root-independent-v2-probes/v1','synthetic_only':True,'new_native_runs':0,'method_hashes':expected,'clean_checks':a.checks,'results':results,'escapes':[x['mutation'] for x in results if x['result']=='ESCAPED']}
out=repo/'tmp/i03-var02-independent-v2-probes-20261007.json'
assert not out.exists(); out.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt,indent=2))
